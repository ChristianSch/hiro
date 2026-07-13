package search

import (
	"context"
	"errors"
	"testing"

	pb "github.com/ChristianSch/hiro/yours-truly/adapters/search/grpc"
	"google.golang.org/grpc"
)

type fakeSearchClient struct {
	statusResponse *pb.StatusResponse
	statusError    error
}

func (f *fakeSearchClient) Search(context.Context, *pb.SearchRequest, ...grpc.CallOption) (*pb.SearchResponse, error) {
	return &pb.SearchResponse{}, nil
}

func (f *fakeSearchClient) Status(context.Context, *pb.StatusRequest, ...grpc.CallOption) (*pb.StatusResponse, error) {
	return f.statusResponse, f.statusError
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
