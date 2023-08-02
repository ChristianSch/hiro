package crawl

import (
	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
)

type Crawler interface {
	Crawl(target crawl.CrawlTarget) (*crawl.CrawlResult, error)
}