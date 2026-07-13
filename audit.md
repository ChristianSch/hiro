# Production readiness audit

_Updated: 2026-07-13_

## Current verdict

Hiro has moved from an unsafe development prototype to a substantially hardened local application, but it is **not yet production-ready**. The immediate correctness, concurrency, configuration, and known dependency-vulnerability findings from the original audit have largely been resolved. The remaining blockers are primarily deployment, observability, resilience, test depth, and search scalability.

## Resolved since the original audit

- Services now use typed, validated, layered YAML configuration from `config/global.yml` plus a service-specific file.
- Python gRPC services bind to loopback by default. Non-loopback listeners require a service token, and TLS certificates can be configured.
- Go gRPC clients support authenticated metadata, TLS, request deadlines, and explicit connection cleanup.
- Python services use bounded PostgreSQL connection pools instead of sharing one transactional connection across worker threads.
- Embedding requests validate URL scheme, required content, metadata length, and content size. Both gRPC servers enforce message-size limits.
- The crawler is restricted to the starting domain, limits response size, rejects non-HTML responses, applies request timeouts and concurrency limits, and propagates parsing, network, and indexing failures safely.
- Crawler asynchronous error handling no longer races, and duplicate-visit errors are handled explicitly.
- Search queries have length and pagination validation. The UI and gRPC calls have deadlines, and HTTP search routes are rate-limited.
- The Go search adapter no longer dereferences an invalid parsed URL.
- Unsafe client-side regular-expression highlighting was removed, and history URLs are URL-encoded.
- Internal exception details are no longer returned to clients. Search queries and complete result rows are no longer emitted in debug logs.
- Search responses no longer send full document bodies that the web UI does not consume.
- Go and Python services now close connections and pools and perform graceful shutdown where supported.
- Model name and device are configurable; CPU is the portable default.
- Static assets use content-hashed URLs, and the search-result layout has bounded responsive dimensions and safe wrapping.
- Go is pinned to patched toolchain version `1.26.5`. Go and Python dependencies were upgraded to patched versions.
- `govulncheck` reports no vulnerabilities for either Go module, and `pip-audit` reports no known Python vulnerabilities.

## Remaining production blockers

### 1. Delivery and operations

There is still no CI workflow, production container image, deployment definition, secrets-delivery mechanism, operational runbook, or documented release/rollback process. The existing Compose file only starts a development PostgreSQL instance, publishes it on the host, and uses development credentials.

Before production deployment, add:

- CI gates for formatting, tests, race detection, vet, builds, migration validation, `govulncheck`, and `pip-audit`.
- Reproducible, non-root container images for the Python services and web application.
- A production topology with private service networking, mounted configuration/secrets, health checks, restart policies, and resource limits.
- Database backup, restore, migration rollback, and disaster-recovery procedures.

### 2. Test depth remains insufficient

The test suite passes, but coverage is still shallow:

- Protagonist has one test file covering configuration; eight packages have no tests.
- Yours-Truly has tests for configuration, asset versioning, and limited gRPC status mapping, but no HTTP handler integration tests.
- Wintermute has eight unit tests focused on configuration, status behavior, and the random-result limit.
- There are no automated database migration, embedding, crawler, authentication/TLS, concurrency, failure-recovery, or end-to-end tests.

The race detector currently passes, but it cannot validate crawler concurrency paths that are not exercised by tests.

### 3. Search scalability is unresolved

`db/migrations/002_hybrid_search.sql` combines vector similarity and full-text ranking in a way that is likely to require broad candidate evaluation rather than an efficient HNSW top-K lookup. This needs `EXPLAIN (ANALYZE, BUFFERS)` against production-scale data and probably a two-stage candidate query before claiming scalable search.

The landing-page query still uses `ORDER BY random()`, which becomes a full-table operation as the document count grows. Replace it with preselected random IDs, sampling, or a maintained random key if the corpus becomes large.

No load tests or latency budgets currently exist for model inference, database search, crawling, or the web tier.

### 4. Remote-service security is configurable, not fully enforced

Loopback defaults are safe for local development, and non-loopback Python listeners require a token. However:

- TLS remains optional.
- Authentication is a single static bearer token without service identity, rotation, or revocation.
- Direct gRPC search traffic has validation and message limits but no server-side rate limiter.
- Production configuration files may contain credentials and therefore must be delivered as protected mounted secrets, not committed.

The crawler intentionally allows resolvable private addresses. That is acceptable while it remains an operator-controlled CLI. If crawl targets ever become user-controlled or remotely submitted, private/link-local/metadata address protections become mandatory to prevent SSRF.

### 5. Resilience and readiness are incomplete

The application now has deadlines, pools, and graceful shutdown, but still lacks retry policy, circuit breaking, load shedding, and explicit backpressure around model inference and indexing. Retries must be bounded and limited to idempotent operations.

The search service exposes dependency status, but the embedding service has no equivalent readiness RPC. There is no readiness distinction between process startup, model warmup, database availability, and the ability to serve an embedding.

### 6. Observability is still logging-only

Structured logs exist, but there are no service metrics, traces, dashboards, or alerts. At minimum, production operation needs:

- Request count, latency, and error rate by RPC/route.
- Model inference duration and queue depth.
- Database pool saturation and query duration.
- Crawl throughput, rejection count, and indexing failures.
- Health/readiness state and alerting thresholds.

### 7. Data lifecycle is undefined

Documents have no crawl timestamp, update timestamp, source ownership, model/version metadata, or stale-document deletion policy. Embedding dimensions are fixed in the schema, but there is no migration strategy for changing embedding models. Retention, recrawling, deletion, and re-embedding behavior must be defined before operating a durable corpus.

## Current validation baseline

The following currently pass:

- Both Go test suites.
- Go race detector and `go vet` for both modules.
- Builds for the crawler and web application.
- Python compilation and all eight Python unit tests.
- `govulncheck` for both Go modules with no reported vulnerabilities.
- `pip-audit` with no known Python vulnerabilities.

## Recommended next order

1. Add CI and meaningful crawler, HTTP, database, and end-to-end tests.
2. Add production containers, private networking, secret-mounted configuration, and health checks.
3. Benchmark and redesign hybrid retrieval using production-scale data.
4. Add embedding readiness, metrics, tracing, dashboards, and alerts.
5. Define backup/restore, data lifecycle, recrawling, and embedding-model migration procedures.
6. Add load testing, resilience controls, and a documented release/rollback runbook.
