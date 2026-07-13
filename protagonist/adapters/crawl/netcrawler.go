package crawl

import (
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"

	"github.com/PuerkitoBio/goquery"
)

type NetCrawler struct {
	client *http.Client
}

func NewNetCrawler() *NetCrawler {
	return &NetCrawler{client: &http.Client{
		Timeout:   15 * time.Second,
		Transport: crawlerTransport(),
	}}
}

func (c *NetCrawler) Crawl(url string) (*crawl.CrawlResult, error) {
	res, err := c.client.Get(url)
	if err != nil {
		return nil, err
	}

	defer res.Body.Close()
	if res.StatusCode < http.StatusOK || res.StatusCode >= http.StatusMultipleChoices {
		return nil, fmt.Errorf("unexpected HTTP status %d", res.StatusCode)
	}
	if !strings.HasPrefix(strings.ToLower(res.Header.Get("Content-Type")), "text/html") {
		return nil, fmt.Errorf("response is not HTML")
	}

	doc, err := goquery.NewDocumentFromReader(io.LimitReader(res.Body, defaultMaxBodySize))
	if err != nil {
		return nil, err
	}

	body := doc.Find("body").Text()

	links := []crawl.CrawlReference{}

	doc.Find("a").Each(func(i int, s *goquery.Selection) {
		link, _ := s.Attr("href")
		links = append(links, link)
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
