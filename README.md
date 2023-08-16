# Hiro Search + AI Knowledgebase

## Components

-   Protagonist: Crawler
-   Wintermute: indexer + query engine
-   Yours-Truly: Search UI
-   postgres + pgvector: Database and embedding storage as well as search

## Development & Building

### Wintermute

To generate your server code, run:

```bash
python3 -m grpc_tools.protoc -I proto --python_out=wintermute/embed/stubs --pyi_out=wintermute/embed/stubs --grpc_python_out=wintermute/embed/stubs proto/embedding.proto
```

and:

```bash
python3 -m grpc_tools.protoc -I proto --python_out=wintermute/search/stubs --pyi_out=wintermute/search/stubs --grpc_python_out=wintermute/search/stubs proto/search.proto
```

We need to fix up some imports for now:

1. in `wintermute/embed/embedding_pb2_grpc.py`, change `import embedding_pb2 as embedding__pb2` to `from . import embedding_pb2 as embedding__pb2`
2. in `wintermute/search/search_pb2_grpc.py`, change `import search_pb2 as search__pb2` to `from . import search_pb2 as search__pb2`

You can run these grpc services with:

```bash
python3 -m wintermute.embed.server
```

and

```bash
python3 -m wintermute.search.server
```

### Yours-Truly

To generate the go client code for the search service, run:

```bash
protoc -I=../proto --go_out=adapters/search/grpc --go_opt=paths=source_relative \
    --go-grpc_out=adapters/search/grpc --go-grpc_opt=paths=source_relative \
    ../proto/search.proto
```

### Protagonist

To generate the go client code for the embedding service, run:

````bash
protoc -I=../proto --go_out=adapters/index/grpc --go_opt=paths=source_relative \
    --go-grpc_out=adapters/index/grpc --go-grpc_opt=paths=source_relative \
    ../proto/embedding.proto
```

### Database Setup
We use postgres and need the following setup:

0. as superuser create the vector extension:
```postgresql
\c hiro
create extension vector;
````

1. as hiro

```postgresql
create table documents (
  id bigserial primary key,
  url text UNIQUE NOT NULL,
  title text,
  content text,
  description text,
  embedding vector(768) NOT NULL,
  CONSTRAINT unique_url UNIQUE (url)
);
```

2.

```postgresql
create or replace function match_documents (
  query_embedding vector(768),
  match_threshold float,
  match_count int
)
returns table (
  id bigint,
  url text,
  title text,
  content text,
  description text,
  similarity float
)
language sql stable
as $$
  select
    documents.id,
    documents.url,
    documents.title,
    documents.content,
    documents.description,
    1 - (documents.embedding <=> query_embedding) as similarity
  from documents
  where 1 - (documents.embedding <=> query_embedding) > match_threshold
  order by similarity desc
  limit match_count;
$$;
```

3.

```postgresql
create index on documents using ivfflat (embedding vector_cosine_ops)
with
  (lists = 100);
```
