package index

import (
	"context"

	pb "github.com/ChristianSch/hiro/protagonist/adapters/index/grpc"
	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type WintermuteIndexer struct {
	cfg    WintermuteConfig
	client pb.EmbeddingServiceClient
}

type WintermuteConfig struct {
	Host string
}

func NewWintermuteIndexer(cfg WintermuteConfig) *WintermuteIndexer {
	conn, err := grpc.Dial(cfg.Host, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		panic(err)
	}
	// defer conn.Close()

	c := pb.NewEmbeddingServiceClient(conn)

	zap.L().Info("grpc searcher initialized", zap.String("host", cfg.Host))

	return &WintermuteIndexer{
		cfg:    cfg,
		client: c,
	}
}

func (i *WintermuteIndexer) PutPage(page crawl.CrawlResult) error {
	zap.L().Info("putting page into wintermute", zap.String("url", page.Url))

	_, err := i.client.Embed(context.Background(), &pb.EmbeddingRequest{
		Url:         page.Url,
		Description: page.Description,
		Content:     page.Body,
		Title:       page.Title,
	})
	if err != nil {
		return err
	}

	return nil
}
