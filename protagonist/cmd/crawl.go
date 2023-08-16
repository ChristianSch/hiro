package main

import (
	"github.com/ChristianSch/hiro/protagonist/adapters/crawl"
	"github.com/ChristianSch/hiro/protagonist/adapters/index"
)

func main() {
	crawler := crawl.NewNetCrawler()
	indexer := index.NewWintermuteIndexer(index.WintermuteConfig{
		Host: "localhost:50052",
	})
	res, err := crawler.Crawl("https://andinfinity.eu")
	if err != nil {
		panic(err)
	}

	println("Crawled:")
	println(res.Url)
	println(res.Title)
	println(res.Description)

	// println(res.Body)

	// add to solar
	println("Indexing...")
	err = indexer.PutPage(*res)
	if err != nil {
		panic(err)
	}
}
