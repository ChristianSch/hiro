package crawl

import (
	"net/http"

	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"

	"github.com/PuerkitoBio/goquery"
)

type NetCrawler struct {
}

func NewNetCrawler() *NetCrawler {
	return &NetCrawler{}
}

func (c *NetCrawler) Crawl(url string) (*crawl.CrawlResult, error) {
	res, err := http.Get(url)
	if err != nil {
		return nil, err
	}

	defer res.Body.Close()

	// parse body for links
	doc, err := goquery.NewDocumentFromReader(res.Body)
	if err != nil {
		return nil, err
	}

	body := doc.Find("body").Text()

	links := []crawl.CrawlReference{}

	doc.Find("a").Each(func(i int, s *goquery.Selection) {
		link, _ := s.Attr("href")
		links = append(links, link)
		println(link)
	})

	title := doc.Find("title").Text()
	description, _ := doc.Find("meta[name=description]").Attr("content")

	return &crawl.CrawlResult{
		Url:         url,
		Title:       title,
		Description: description,
		Body:        string(body),
		References:  links,
	}, nil
}
