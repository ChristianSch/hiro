package index

import "github.com/ChristianSch/hiro/protagonist/domain/model/crawl"

type PageIndexer interface {
	PutPage(page crawl.CrawlResult) error
}
