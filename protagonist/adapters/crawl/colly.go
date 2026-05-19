package crawl

import (
	"bytes"
	"time"

	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
	"github.com/ChristianSch/hiro/protagonist/domain/model/index"
	"github.com/gocolly/colly/v2"
	"github.com/gocolly/colly/v2/extensions"
	"go.uber.org/zap"

	"github.com/PuerkitoBio/goquery"
)

type CollyConfig struct {
	// Proxies []string
	Indexer  index.PageIndexer
	MaxDepth *int
}

type CollyCrawler struct {
	c       *colly.Collector
	cfg     CollyConfig
	indexer index.PageIndexer
}

func NewCollyCrawler(cfg CollyConfig) *CollyCrawler {
	var maxDepth int = 2
	if cfg.MaxDepth != nil {
		maxDepth = *cfg.MaxDepth
	}

	c := colly.NewCollector(
		colly.MaxDepth(maxDepth),
		colly.Async(true),
		// rate limit
		// random user agent
	)

	c.Limit(&colly.LimitRule{
		RandomDelay: 2 * time.Second,
		Parallelism: 2,
	})

	extensions.RandomUserAgent(c)

	// load proxies into round robin switcher
	// rp, err := proxy.RoundRobinProxySwitcher(proxies.GetAll()...) // list of proxy strings
	// if err != nil {
	// 	log.Fatal(err)
	// }

	// if using async then disable transport keep alives
	// c.WithTransport(&http.Transport{
	// 	Proxy:             rp,
	// 	DisableKeepAlives: true, // must be true
	// })

	return &CollyCrawler{
		c:       c,
		cfg:     cfg,
		indexer: cfg.Indexer,
	}
}

func (c *CollyCrawler) Crawl(url string) error {
	c.c.OnHTML("a[href]", func(e *colly.HTMLElement) {
		e.Request.Visit(e.Attr("href"))
	})

	var err error = nil

	c.c.OnResponse(func(res *colly.Response) {
		pageUrl := res.Request.URL.String()
		zap.L().Info("received response", zap.String("url", pageUrl))
		// convert body to reader
		body := bytes.NewReader(res.Body)

		// parse body for links
		doc, err2 := goquery.NewDocumentFromReader(body)
		if err != nil {
			err = err2
		} else {
			bodyText := doc.Find("body").Text()

			links := []crawl.CrawlReference{}

			doc.Find("a").Each(func(i int, s *goquery.Selection) {
				link, _ := s.Attr("href")
				links = append(links, link)

				res.Request.Visit(link)
			})

			title := doc.Find("title").Text()
			description, _ := doc.Find("meta[name=description]").Attr("content")

			crawl := crawl.CrawlResult{
				Url:         pageUrl,
				Title:       title,
				Description: description,
				Body:        string(bodyText),
				References:  links,
			}

			zap.L().Info("crawled page",
				zap.String("url", crawl.Url),
				zap.String("title", crawl.Title),
				zap.String("description", crawl.Description),
				zap.Int("references", len(crawl.References)))

			c.indexer.PutPage(crawl)
		}
	})

	c.c.OnRequest(func(r *colly.Request) {
		zap.L().Info("Visiting", zap.String("url", r.URL.String()))
	})

	c.c.Visit(url)

	return err
}
