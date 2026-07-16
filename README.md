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

It owns the single `BAAI/bge-base-en` model instance. Over gRPC it embeds search queries and receives crawled pages, splits pages into overlapping token chunks, embeds chunks in batches, and atomically replaces searchable chunks in Postgres. Unchanged content with current-model embeddings is not re-embedded.

The search service is implemented in:

```text
wintermute/search/server.py
```

It receives search queries using the service defined in `proto/search.proto`. For each uncached query, it requests an embedding from the embedding service over gRPC, calls the Postgres `match_documents(...)` function, and returns the highest-ranked hybrid matches. The search process does not load model weights.

### Postgres + pgvector: storage and retrieval

Postgres stores page metadata in `documents` and searchable content in `document_chunks`. Chunk embeddings use pgvector's `halfvec(768)` type, cutting vector storage roughly in half while matching the 768-value output of `BAAI/bge-base-en`.

Search uses a hybrid ranking strategy:

- semantic similarity via pgvector cosine distance
- keyword relevance via PostgreSQL full-text search using `tsvector`, `websearch_to_tsquery`, and `ts_rank_cd`

The current fixed ranking blend is `70%` semantic similarity and `30%` keyword relevance. Vector and full-text indexes independently retrieve bounded candidate sets; only their union is reranked. Runtime HNSW `ef_search`, iterative scan mode, and candidate counts are configured in `config/search.yml`.

### Batch re-embedding

Use the batch tool when changing embedding models or upgrading legacy one-chunk documents. It processes a bounded number of documents per transaction and resumes naturally because current-model chunks are skipped.

```bash
# Inspect pending work without loading the model
uv run python -m wintermute.embed.reembed --dry-run

# Re-embed stale chunks, 50 documents at a time
uv run python -m wintermute.embed.reembed --batch-documents 50
```

Legacy chunks created by migration `003` are split with the current overlap settings by default. Existing non-legacy chunk boundaries are preserved because the canonical full page text is not stored separately. Use `--force` to re-encode every document or `--no-rechunk-legacy` to preserve legacy chunks. Run one copy of the tool at a time; each completed batch is atomic.

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
eval/queries.json
eval/queries.example.json
```

`eval/queries.json` is a versioned bootstrap set built from the current corpus. It contains natural-language known-item queries and real relevant URLs; review and expand its labels as the corpus grows. The harness accepts either binary relevance:

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
uv run python eval/run_eval.py --queries eval/queries.json --host localhost:50053
```

The harness reports:

- `Precision@k`: how many of the top `k` results are relevant
- `Recall@k`: how many known relevant documents were found in the top `k`
- `MRR`: whether the first relevant result appears near the top
- `MAP`: ranking quality across all relevant results
- `NDCG@k`: ranking quality with graded relevance labels

Useful options:

```bash
uv run python eval/run_eval.py --queries eval/queries.json --k 1 5 10 --show-cases
uv run python eval/run_eval.py --queries eval/queries.json --json-output eval/results.json
```

### Search scaling benchmarks

`benchmark/` contains a synthetic corpus generator and an HNSW-versus-exact benchmark. See `benchmark/README.md` for the 100k, 1M, and 3M document workflow and the Recall@k/latency measurements.

## Components

-   Protagonist: Crawler
-   Wintermute: indexer + hybrid query engine
-   Yours-Truly: Search UI
-   postgres + pgvector: Database, embedding storage, full-text search, and vector search

## Development & Building

### Quick start

Using [case](https://github.com/christiansch/case), you can run hiro and it's components very easily: 

```bash
casectl up
```

The UI is exposed at [http://127.0.0.1:8973](http://127.0.0.1:8973). Make sure to crawl some pages (see below) to actually get some search results ;)

### Manual Setup

Start Postgres with pgvector and run database migrations:

```bash
docker compose up -d postgres
go install github.com/jackc/tern/v2@latest # if tern is not already installed
tern migrate --migrations db/migrations --config db/tern.conf
```

Install Python dependencies with uv:

```bash
uv sync
```

If you do not have uv installed, see https://docs.astral.sh/uv/getting-started/installation/.

Run Wintermute's embedding and search services in separate terminals:

```bash
uv run python -m wintermute.embed.server
uv run python -m wintermute.search.server
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

### Service configuration

Configuration lives entirely in YAML under `config/`:

- `global.yml` contains values shared across services, such as the database, model, and logging defaults.
- `embed.yml`, `search.yml`, `crawler.yml`, and `web.yml` contain service-owned settings.

Each process loads `global.yml` first and merges its service file over it. Service values win when the same key exists in both files. Go services use Viper for merging and govalidator for validation; Python services apply the same merge order and validate their typed settings.

Model loading always checks local files and the Hugging Face cache before allowing network access. Set `model.allow_download: false` in `config/global.yml` for strict offline operation; startup then fails clearly if the configured model is not available locally. Start the embedding service before the search service because search obtains query embeddings from it over gRPC.

Python commands use `config/` by default. The Go commands are normally run from their module directories and therefore use `../config/` by default. Override either default with `--config-dir`:

```bash
uv run python -m wintermute.search.server --config-dir /etc/hiro
cd protagonist && go run ./cmd --config-dir /etc/hiro -url https://example.com
cd yours-truly && go run ./cmd --config-dir /etc/hiro
```

There is no environment-variable configuration layer.

### Database setup

`docker-compose.yml` starts Postgres with pgvector on host port `51432`. Schema changes are managed with [tern](https://github.com/jackc/tern).

Install tern if needed:

```bash
go install github.com/jackc/tern/v2@latest
```

Run migrations:

```bash
tern migrate --migrations db/migrations --config db/tern.conf
```

The migrations create:

- the `vector` extension
- the `documents` and `document_chunks` tables
- batched chunk metadata and embedding-model tracking
- the bounded-candidate `match_documents(...)` hybrid search function
- HNSW chunk-embedding and GIN full-text indexes
- indexed random landing-page selection

The local development defaults match the current application code:

```text
dbname=hiro user=hiro password=hiro host=localhost port=51432
```

### Generated gRPC stubs

Generated gRPC stubs are committed intentionally so normal development does not require `protoc`. Regenerate them only when files in `proto/` change.

Python stubs for Wintermute:

```bash
uv run python -m grpc_tools.protoc -I proto \
  --python_out=wintermute/embed/stubs \
  --pyi_out=wintermute/embed/stubs \
  --grpc_python_out=wintermute/embed/stubs \
  proto/embedding.proto

uv run python -m grpc_tools.protoc -I proto \
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
