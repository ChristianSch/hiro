package index

import (
	"context"
	"crypto/tls"
	"fmt"
	"time"

	pb "github.com/ChristianSch/hiro/protagonist/adapters/index/grpc"
	"github.com/ChristianSch/hiro/protagonist/domain/model/crawl"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
)

type WintermuteIndexer struct {
	cfg    WintermuteConfig
	conn   *grpc.ClientConn
	client pb.EmbeddingServiceClient
}

type WintermuteConfig struct {
	Host       string
	Token      string
	Timeout    time.Duration
	Insecure   bool
	ServerName string
}

func NewWintermuteIndexer(cfg WintermuteConfig) (*WintermuteIndexer, error) {
	if cfg.Timeout <= 0 {
		cfg.Timeout = 30 * time.Second
	}

	var transport credentials.TransportCredentials
	if cfg.Insecure {
		transport = insecure.NewCredentials()
	} else {
		transport = credentials.NewTLS(&tls.Config{
			MinVersion: tls.VersionTLS12,
			ServerName: cfg.ServerName,
		})
	}

	conn, err := grpc.Dial(cfg.Host, grpc.WithTransportCredentials(transport))
	if err != nil {
		return nil, fmt.Errorf("connect to embedding service: %w", err)
	}

	zap.L().Info("grpc indexer initialized", zap.String("host", cfg.Host))
	return &WintermuteIndexer{
		cfg:    cfg,
		conn:   conn,
		client: pb.NewEmbeddingServiceClient(conn),
	}, nil
}

func (i *WintermuteIndexer) Close() error {
	if i.conn == nil {
		return nil
	}
	return i.conn.Close()
}

func (i *WintermuteIndexer) PutPage(page crawl.CrawlResult) error {
	zap.L().Info("putting page into wintermute", zap.String("url", page.Url))

	ctx, cancel := context.WithTimeout(context.Background(), i.cfg.Timeout)
	defer cancel()
	if i.cfg.Token != "" {
		ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+i.cfg.Token)
	}

	_, err := i.client.Embed(ctx, &pb.EmbeddingRequest{
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
