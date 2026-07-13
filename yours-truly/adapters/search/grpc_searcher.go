package search

import (
	"context"
	"crypto/tls"
	"fmt"
	"net/url"
	"time"

	pb "github.com/ChristianSch/hiro/yours-truly/adapters/search/grpc"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
)

type GrpcSearcher struct {
	cfg    GrpcSearcherConfig
	conn   *grpc.ClientConn
	client pb.SearchServiceClient
}

type GrpcSearcherConfig struct {
	Host       string
	Token      string
	Timeout    time.Duration
	Insecure   bool
	ServerName string
}

type SearchResult struct {
	Title       string
	Url         string
	Host        string
	Page        string
	Description string
}

type ServiceStatus struct {
	Operational  bool
	Dependencies map[string]bool
}

func NewGrpcSearcher(cfg GrpcSearcherConfig) (*GrpcSearcher, error) {
	if cfg.Timeout <= 0 {
		cfg.Timeout = 5 * time.Second
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
		return nil, fmt.Errorf("connect to search service: %w", err)
	}

	zap.L().Info("grpc searcher initialized", zap.String("host", cfg.Host))
	return &GrpcSearcher{
		cfg:    cfg,
		conn:   conn,
		client: pb.NewSearchServiceClient(conn),
	}, nil
}

func (s *GrpcSearcher) Close() error {
	if s.conn == nil {
		return nil
	}
	return s.conn.Close()
}

func (s *GrpcSearcher) requestContext(parent context.Context) (context.Context, context.CancelFunc) {
	ctx, cancel := context.WithTimeout(parent, s.cfg.Timeout)
	if s.cfg.Token != "" {
		ctx = metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+s.cfg.Token)
	}
	return ctx, cancel
}

func (s *GrpcSearcher) Status(ctx context.Context) (*ServiceStatus, error) {
	requestCtx, cancel := s.requestContext(ctx)
	defer cancel()
	response, err := s.client.Status(requestCtx, &pb.StatusRequest{})
	if err != nil {
		return nil, err
	}

	status := &ServiceStatus{
		Operational:  response.State == pb.OperationalState_OPERATIONAL_STATE_OPERATIONAL,
		Dependencies: make(map[string]bool, len(response.Dependencies)),
	}
	for _, dependency := range response.Dependencies {
		status.Dependencies[dependency.Name] = dependency.State == pb.OperationalState_OPERATIONAL_STATE_OPERATIONAL
	}

	return status, nil
}

func (s *GrpcSearcher) Search(ctx context.Context, query string) ([]*SearchResult, error) {
	requestCtx, cancel := s.requestContext(ctx)
	defer cancel()
	zap.L().Info("searching via grpc")
	r, err := s.client.Search(requestCtx, &pb.SearchRequest{Query: query})
	if err != nil {
		return nil, err
	}

	out := make([]*SearchResult, len(r.Results))
	for i, res := range r.Results {
		var host string
		// parse url and get host
		var page string
		u, err := url.Parse(res.Url)
		if err != nil {
			zap.L().Warn("failed to parse search result URL", zap.Error(err))
		} else {
			host = fmt.Sprintf("%s://%s", u.Scheme, u.Host)
			page = u.Path
		}

		out[i] = &SearchResult{
			Title:       res.Title,
			Url:         res.Url,
			Host:        host,
			Page:        page,
			Description: res.Description,
		}
	}

	return out, nil
}
