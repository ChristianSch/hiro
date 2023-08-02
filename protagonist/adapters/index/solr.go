package index

import (
	"github.com/stevenferrer/solr-go"
	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
	"encoding/json"
	"context"
	"bytes"
)

type SolrIndexer struct {
	Core string
	Host string
	client *solr.JSONClient
}

type SolarIndexerConfig struct {
	Core string
	Host string
}

type solrDocument struct {
	Body string `json:"body"`
	Title string `json:"title"`
}

func NewSolrIndexer(cfg SolarIndexerConfig) *SolrIndexer {
	return &SolrIndexer{
		Core: cfg.Core,
		Host: cfg.Host,
		client: solr.NewJSONClient(cfg.Host),
	}
}

func (i *SolrIndexer) PutPage(page crawl.CrawlResult) error {
	// put content of page into solr
	// convert page into io.Reader
	docs := []solr.M{
		{"title": page.Title, "body": page.Body},
	}
	buf := &bytes.Buffer{}
	err := json.NewEncoder(buf).Encode(docs)
	if err != nil {
		return err
	}

	res, err := i.client.Update(context.Background(), i.Core, solr.JSON, buf)
	if err != nil {
		println(res.Error.Msg)
		return err
	}

	return nil
}