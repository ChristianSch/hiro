# Search scaling benchmarks

Run database migration `003_chunked_hybrid_search.sql` before using these tools.

## Generate a corpus

The generator writes synthetic documents and normalized `halfvec` chunk embeddings using `model.dimensions` from the layered configuration. Use a dedicated benchmark database.

```bash
uv run python -m benchmark.generate_corpus \
  --documents 100000 \
  --chunks-per-document 5 \
  --replace
```

Repeat with 1,000,000 and 3,000,000 documents. Three million documents with five chunks produce 15 million vectors and require substantial disk and HNSW build memory.

## Compare HNSW with exact search

```bash
uv run python -m benchmark.vector_search \
  --samples 50 \
  --top-k 10 \
  --ef-search 40 80 160 320 \
  --json-output benchmark/results/vector-1m.json
```

The benchmark reports:

- exact-search p50, p95, and p99 latency
- HNSW p50, p95, and p99 latency for each `ef_search`
- ANN Recall@k against exact nearest-neighbor results
- vector count, chunk-table size, and HNSW index size

Run `eval/run_eval.py` separately to measure labeled relevance with MRR, MAP, Recall@k, and NDCG. ANN recall and relevance recall are different metrics and both must be tracked.

Use `EXPLAIN (ANALYZE, BUFFERS)` on `match_documents(...)` for each corpus size to verify that vector candidates use `document_chunks_embedding_hnsw_idx` and text candidates use the GIN indexes.
