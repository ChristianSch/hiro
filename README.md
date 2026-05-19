# Hiro Search + AI Knowledgebase

## Project Overview

Hiro is a local semantic search engine / AI knowledgebase. It crawls web pages, turns their content into embeddings with a SentenceTransformer model, stores those embeddings in Postgres using pgvector, and exposes a small web UI for vector-based search.

At a high level, the system works like this:

```text
Website URL
   │
   ▼
Protagonist crawler
   │ crawls pages and extracts title/body/description
   ▼
Wintermute embedding service
   │ creates embeddings for crawled content
   ▼
Postgres + pgvector
   │ stores documents and vectors
   ▼
Wintermute search service
   │ embeds user queries and runs vector similarity search
   ▼
Yours-Truly web UI
   │ displays matching pages in the browser
```

### Protagonist: crawler and indexing client

`protagonist/` is a Go command-line crawler. Its entry point is:

```text
protagonist/cmd/crawl.go
```

It uses Colly to crawl pages from a starting URL up to a configurable maximum depth. For every fetched page, it extracts:

- the page URL
- the `<title>` text
- the `<meta name="description">` content
- the body text
- discovered links

It then sends the page to Wintermute's embedding service over gRPC at `localhost:50052`.

### Wintermute: embedding and search backend

`wintermute/` is a Python backend exposing two gRPC services.

The embedding service is implemented in:

```text
wintermute/embed/server.py
```

It receives crawled pages using the service defined in `proto/embedding.proto`. For each page, it loads the `BAAI/bge-base-en` SentenceTransformer model, embeds the page content, and inserts or updates the document in Postgres.

The search service is implemented in:

```text
wintermute/search/server.py
```

It receives search queries using the service defined in `proto/search.proto`. For each query, it creates an embedding with the same model, calls the Postgres `match_documents(...)` function, and returns the most similar documents.

### Postgres + pgvector: storage and retrieval

Postgres stores the crawled documents and their embeddings in a `documents` table. The `embedding` column uses pgvector's `vector(768)` type, matching the output size of `BAAI/bge-base-en`.

Search is performed by comparing the query embedding against stored document embeddings using pgvector cosine distance:

```sql
1 - (documents.embedding <=> query_embedding) as similarity
```

The README setup below creates the table, the `match_documents(...)` helper function, and an HNSW vector index.

### Yours-Truly: web search UI

`yours-truly/` is a Go web application using Fiber, Go HTML templates, HTMX, and static CSS/JS. Its entry point is:

```text
yours-truly/cmd/server.go
```

It serves the search UI on port `8973`. When a user searches, it calls Wintermute's search gRPC service at `localhost:50053`, transforms the response into display-friendly results, and renders them in:

```text
yours-truly/views/search.gohtml
```

HTMX is used for partial search-result updates through `/htmx/search`, while `/search?q=...` renders the full page.

### Shared protocol buffers

The gRPC contracts live in:

```text
proto/embedding.proto
proto/search.proto
```

These definitions are used to generate Python gRPC stubs for Wintermute and Go gRPC clients for Protagonist and Yours-Truly.

### Search evaluation harness

A small evaluation harness lives in:

```text
eval/run_eval.py
eval/queries.example.json
```

It measures search quality against a labeled set of queries. Create `eval/queries.json` with either binary relevance:

```json
[
  {
    "query": "contact support",
    "relevant_urls": [
      "https://example.com/contact",
      "https://example.com/help"
    ]
  }
]
```

or graded relevance for NDCG:

```json
[
  {
    "query": "pricing plans",
    "relevance": {
      "https://example.com/pricing": 2,
      "https://example.com/blog/how-pricing-works": 1
    }
  }
]
```

Then run it while the Wintermute search service is running:

```bash
python3 eval/run_eval.py --queries eval/queries.json --host localhost:50053
```

The harness reports:

- `Precision@k`: how many of the top `k` results are relevant
- `Recall@k`: how many known relevant documents were found in the top `k`
- `MRR`: whether the first relevant result appears near the top
- `MAP`: ranking quality across all relevant results
- `NDCG@k`: ranking quality with graded relevance labels

Useful options:

```bash
python3 eval/run_eval.py --queries eval/queries.json --k 1 5 10 --show-cases
python3 eval/run_eval.py --queries eval/queries.json --json-output eval/results.json
```

### Current caveats

- Search pagination fields exist in `proto/search.proto`, but the current search service always requests 10 matches.
- The SentenceTransformer device is hardcoded to `mps`, which is appropriate for Apple Silicon. Use `cpu` or `cuda` if running elsewhere.
- Local service hosts and the Postgres DSN are currently hardcoded for development.

## Components

-   Protagonist: Crawler
-   Wintermute: indexer + query engine
-   Yours-Truly: Search UI
-   postgres + pgvector: Database and embedding storage as well as search

## Development & Building

### Quick start

Start Postgres with pgvector:

```bash
docker compose up -d postgres
```

Install Python dependencies:

```bash
python3 -m pip install -r wintermute/requirements.txt
```

Run Wintermute's embedding and search services in separate terminals:

```bash
python3 -m wintermute.embed.server
python3 -m wintermute.search.server
```

Crawl a site into the embedding index:

```bash
cd protagonist
go run ./cmd -url https://example.com -max-depth 2
```

Run the web UI:

```bash
cd yours-truly
go run ./cmd
```

Then open:

```text
http://localhost:8973
```

### Database setup

`docker-compose.yml` starts Postgres with pgvector and automatically runs `docker/postgres/init.sql`, which creates:

- the `vector` extension
- the `documents` table
- the `match_documents(...)` search function
- the HNSW embedding index

The local development defaults match the current application code:

```text
dbname=hiro user=hiro password=hiro host=localhost port=5432
```

### Generated gRPC stubs

Generated gRPC stubs are committed intentionally so normal development does not require `protoc`. Regenerate them only when files in `proto/` change.

Python stubs for Wintermute:

```bash
python3 -m grpc_tools.protoc -I proto \
  --python_out=wintermute/embed/stubs \
  --pyi_out=wintermute/embed/stubs \
  --grpc_python_out=wintermute/embed/stubs \
  proto/embedding.proto

python3 -m grpc_tools.protoc -I proto \
  --python_out=wintermute/search/stubs \
  --pyi_out=wintermute/search/stubs \
  --grpc_python_out=wintermute/search/stubs \
  proto/search.proto
```

If regenerated, keep the Python gRPC imports package-relative:

```py
from . import embedding_pb2 as embedding__pb2
from . import search_pb2 as search__pb2
```

Go stubs for Protagonist and Yours-Truly:

```bash
cd protagonist
protoc -I=../proto --go_out=adapters/index/grpc --go_opt=paths=source_relative \
  --go-grpc_out=adapters/index/grpc --go-grpc_opt=paths=source_relative \
  ../proto/embedding.proto

cd ../yours-truly
protoc -I=../proto --go_out=adapters/search/grpc --go_opt=paths=source_relative \
  --go-grpc_out=adapters/search/grpc --go-grpc_opt=paths=source_relative \
  ../proto/search.proto
```
