package main

import (
	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
	"github.com/ChristianSch/hiro/protagonist/adapters/index"
)

func main() {
	crawler := crawl.NewNetCrawler()
	indexer := index.NewSolrIndexer(index.SolarIndexerConfig{
		Core: "hproto",
		Host: "http://localhost:8983",
	})
	res, err := crawler.Crawl("https://andinfinity.eu")
	if err != nil {
		panic(err)
	}

	println("Crawled:")
	println(res.Url)
	println(res.Title)
	// println(res.Body)

	// add to solar
	println("Indexing...")
	err = indexer.PutPage(*res)
	if err != nil {
		panic(err)
	}
}
