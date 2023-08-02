package crawl

import (
	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
	"net/http"
	"io"

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

	// read body
	body, err := io.ReadAll(res.Body)
	if err != nil {
		return nil, err
	}

	// parse body for links
	doc, err := goquery.NewDocumentFromReader(res.Body)

	if err != nil {
		return nil, err
	}

	links := []crawl.CrawlReference{}

	doc.Find("a").Each(func(i int, s *goquery.Selection) {
		link, _ := s.Attr("href")
		links = append(links, link)
		println(link)
	})

	return &crawl.CrawlResult{
		Url: url,
		Title: "",
		Body: string(body),
		References: links,
	}, nil
}