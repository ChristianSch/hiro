package search

import (
	"context"
	"fmt"
	"net/url"

	pb "github.com/ChristianSch/hiro/yours-truly/adapters/search/grpc"
	"go.uber.org/zap"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type GrpcSearcher struct {
	cfg    GrpcSearcherConfig
	client pb.SearchServiceClient
}

type GrpcSearcherConfig struct {
	Host string
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

func NewGrpcSearcher(cfg GrpcSearcherConfig) *GrpcSearcher {
	conn, err := grpc.Dial(cfg.Host, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		panic(err)
	}
	// defer conn.Close()

	c := pb.NewSearchServiceClient(conn)

	zap.L().Info("grpc searcher initialized", zap.String("host", cfg.Host))

	return &GrpcSearcher{
		cfg:    cfg,
		client: c,
	}
}

func (s *GrpcSearcher) Status(ctx context.Context) (*ServiceStatus, error) {
	response, err := s.client.Status(ctx, &pb.StatusRequest{})
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

func (s *GrpcSearcher) Search(query string) ([]*SearchResult, error) {
	zap.L().Info("searching via grpc", zap.String("query", query))
	r, err := s.client.Search(context.Background(), &pb.SearchRequest{Query: query})
	if err != nil {
		return nil, err
	}

	out := make([]*SearchResult, len(r.Results))
	for i, res := range r.Results {
		var host string
		// parse url and get host
		u, err := url.Parse(res.Url)
		if err != nil {
			zap.L().Error("failed to parse url", zap.Error(err), zap.String("url", res.Url))
			host = ""
		} else {
			host = fmt.Sprintf("%s://%s", u.Scheme, u.Host)
		}

		out[i] = &SearchResult{
			Title:       res.Title,
			Url:         res.Url,
			Host:        host,
			Page:        u.Path,
			Description: res.Description,
		}
	}

	return out, nil
}
