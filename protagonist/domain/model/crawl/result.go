package crawl

type CrawlResult struct {
	Url string
	Title string
	Body string
	References []CrawlReference
}