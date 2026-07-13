Bluntly: **this is a development prototype, not production-ready**.

The biggest problems are:

- The gRPC services listen on all interfaces without TLS or authentication. The embedding endpoint permits arbitrary document writes.
- PostgreSQL is exposed with hardcoded `hiro/hiro` credentials. Hosts, ports, model, device, and DSNs are hardcoded throughout.
- The Python embedding service shares one transactional database connection across ten worker threads. Concurrent requests can interfere, and one failed transaction can poison subsequent requests.
- The crawler follows links without domain restrictions, private-network protection, response-size limits, or content-type checks. This creates SSRF, runaway-crawl, and memory-exhaustion risks.
- Crawler indexing failures are silently discarded at `protagonist/adapters/crawl/colly.go:132`. Its shared `err` variable is also written asynchronously without synchronization.
- Search and indexing gRPC calls use `context.Background()` without deadlines. Requests can hang indefinitely.
- Search has no authentication, request-size controls, rate limiting, or query-length limits. Model inference therefore provides an easy resource-exhaustion target.
- Hybrid search likely performs poorly at scale: the combined vector/full-text expression in `002_hybrid_search.sql` prevents straightforward HNSW top-K execution. Empty searches use `ORDER BY random()`, another full-table operation.
- `GrpcSearcher.Search` can dereference `u` after `url.Parse` fails at `yours-truly/adapters/search/grpc_searcher.go:81-94`.
- Pagination exists in the protocol but is ignored; every search is hardcoded to ten results.
- The browser builds a regular expression directly from user input. Invalid or pathological expressions can break or stall highlighting. History URLs are also constructed without URL-encoding the query.
- Raw internal exception text is returned through gRPC, while queries, results, and potentially sensitive content are logged at debug level.
- Entire document contents are returned over gRPC even though the UI does not use them.
- There is no graceful shutdown, connection cleanup, database pool, retry policy, circuit breaker, backpressure, or explicit service readiness for embedding.
- There is no CI, production container image, deployment configuration, secrets strategy, metrics, tracing, alerting, backup guidance, or operational runbook.
- The Apple-only `device='mps'` configuration prevents deployment on ordinary Linux CPU/CUDA hosts.

Validation succeeded superficially: both Go projects build, `go vet` passes, race-enabled tests pass, and Python compiles. However, the coverage is negligible:

- Protagonist: **zero tested packages**, eight packages with no tests.
- Yours Truly: only one tested package, primarily status mapping.
- Python: only three readiness tests, and all three emit ignored `__del__` exceptions.
- No database, migration, embedding, crawler, HTTP, concurrency, or end-to-end tests.

Dependency scanning is also blocking:

- Protagonist: **12 reachable vulnerabilities**, largely from the very old `golang.org/x/net v0.9.0`.
- Yours Truly: **4 reachable vulnerabilities**, including Fiber DoS; Fiber is `v2.48.0`, with the cited fix in `v2.52.12`.
- Python: **12 known vulnerabilities** across Pillow, protobuf, Torch, and Transformers.

The good foundations are the clear service boundaries, parameterized SQL, pinned Python environment, database migrations, basic health status, and a search-quality evaluation harness. But I would not expose the current system to an untrusted network or meaningful production traffic.
