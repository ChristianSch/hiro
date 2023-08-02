package index

type PageIndexer interface {
	PutPage(page crawl.CrawlResult) error
}
