package search

import (
	"context"
	"errors"
	"testing"
	"time"

	pb "github.com/ChristianSch/hiro/yours-truly/adapters/search/grpc"
	"google.golang.org/grpc"
)

type fakeSearchClient struct {
	statusResponse *pb.StatusResponse
	statusError    error
	searchResponse *pb.SearchResponse
	searchRequest  *pb.SearchRequest
}

func (f *fakeSearchClient) Search(_ context.Context, request *pb.SearchRequest, _ ...grpc.CallOption) (*pb.SearchResponse, error) {
	f.searchRequest = request
	if f.searchResponse == nil {
		return &pb.SearchResponse{}, nil
	}
	return f.searchResponse, nil
}

func (f *fakeSearchClient) Status(context.Context, *pb.StatusRequest, ...grpc.CallOption) (*pb.StatusResponse, error) {
	return f.statusResponse, f.statusError
}

func TestSearchMapsPagination(t *testing.T) {
	client := &fakeSearchClient{searchResponse: &pb.SearchResponse{
		PageNumber: 2,
		HasNext:    true,
		Results: []*pb.SearchResponse_Result{{
			Url:         "https://example.com/docs",
			Title:       "Docs",
			Description: "Example docs",
		}},
	}}
	searcher := &GrpcSearcher{
		cfg:    GrpcSearcherConfig{Timeout: time.Second},
		client: client,
	}

	page, err := searcher.Search(context.Background(), "example", 2, 10)
	if err != nil {
		t.Fatalf("Search returned an error: %v", err)
	}
	if client.searchRequest.PageNumber != 2 || client.searchRequest.ResultPerPage != 10 {
		t.Fatalf("unexpected request pagination: %#v", client.searchRequest)
	}
	if page.PageNumber != 2 || !page.HasPrevious || !page.HasNext {
		t.Fatalf("unexpected page metadata: %#v", page)
	}
	if page.LoadTime == "" {
		t.Fatal("expected search load time")
	}
	if len(page.Results) != 1 || page.Results[0].Page != "/docs" {
		t.Fatalf("unexpected mapped results: %#v", page.Results)
	}
}

func TestFormatSearchDuration(t *testing.T) {
	t.Parallel()

	cases := map[time.Duration]string{
		500 * time.Microsecond:  "< 1 ms",
		126 * time.Millisecond:  "126 ms",
		1250 * time.Millisecond: "1.2 s",
	}
	for duration, expected := range cases {
		if actual := formatSearchDuration(duration); actual != expected {
			t.Errorf("formatSearchDuration(%s) = %q, want %q", duration, actual, expected)
		}
	}
}

func TestStatusMapsAggregateAndDependencyStates(t *testing.T) {
	searcher := &GrpcSearcher{client: &fakeSearchClient{
		statusResponse: &pb.StatusResponse{
			State: pb.OperationalState_OPERATIONAL_STATE_OPERATIONAL,
			Dependencies: []*pb.DependencyStatus{
				{
					Name:  "postgresql",
					State: pb.OperationalState_OPERATIONAL_STATE_OPERATIONAL,
				},
			},
		},
	}}

	status, err := searcher.Status(context.Background())
	if err != nil {
		t.Fatalf("Status returned an error: %v", err)
	}
	if !status.Operational {
		t.Fatal("expected search to be operational")
	}
	if !status.Dependencies["postgresql"] {
		t.Fatal("expected PostgreSQL dependency to be operational")
	}
}

func TestStatusReturnsTransportErrors(t *testing.T) {
	expected := errors.New("search server unavailable")
	searcher := &GrpcSearcher{client: &fakeSearchClient{statusError: expected}}

	status, err := searcher.Status(context.Background())
	if !errors.Is(err, expected) {
		t.Fatalf("expected transport error, got %v", err)
	}
	if status != nil {
		t.Fatalf("expected no status, got %#v", status)
	}
}
