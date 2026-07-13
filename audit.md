# Production readiness: remaining work

_Updated: 2026-07-13_

## 1. Delivery and operations

- Add CI gates for formatting, tests, race detection, vet, builds, migration validation, `govulncheck`, and `pip-audit`.
- Add reproducible, non-root container images for the Python services and web application.
- Define a production topology with private service networking, mounted configuration and secrets, health checks, restart policies, and resource limits.
- Stop using the development PostgreSQL credentials and host-published database port in production.
- Document release, rollback, backup, restore, migration rollback, and disaster-recovery procedures.

## 2. Test coverage

- Add crawler tests for domain boundaries, response limits, content-type rejection, timeouts, duplicate visits, asynchronous failures, and indexing errors.
- Add HTTP integration tests for search, random results, status, validation failures, rate limiting, and backend outages.
- Add embedding-service tests for request validation, authentication, database failures, and concurrent requests.
- Add PostgreSQL migration and hybrid-search integration tests.
- Add authentication and TLS integration tests.
- Add end-to-end tests covering crawl, embedding, storage, search, and rendering.
- Exercise crawler concurrency under the race detector; the currently untested paths make a passing race run insufficient.

## 3. Search scalability and performance

- Run `EXPLAIN (ANALYZE, BUFFERS)` for `match_documents(...)` against production-scale data.
- Replace the broad hybrid-ranking query with a measured two-stage vector and full-text candidate strategy if the HNSW index is not used effectively.
- Replace `ORDER BY random()` with sampling, preselected random IDs, or a maintained random key before the corpus becomes large.
- Establish latency and throughput budgets for model inference, database search, crawling, and HTTP requests.
- Add representative load tests and capacity limits.

## 4. Remote-service security

- Require TLS for non-loopback gRPC listeners rather than merely supporting it.
- Replace the shared static bearer token with service identity and a rotation/revocation strategy.
- Add server-side rate limiting for direct gRPC search and embedding traffic.
- Deliver production configuration files through a protected secret mount and prevent production credentials from being committed.
- If crawl targets ever become remotely submitted or user-controlled, block private, loopback, link-local, and cloud metadata addresses to prevent SSRF.

## 5. Resilience and readiness

- Add bounded retry policies only for safe, idempotent operations.
- Add circuit breaking, load shedding, and explicit backpressure around model inference and indexing.
- Add an embedding-service readiness RPC.
- Distinguish process liveness from model warmup, database readiness, pool saturation, and ability to serve requests.
- Define behavior for partial dependency outages and recovery.

## 6. Observability

- Record request count, latency, and error rate by RPC and HTTP route.
- Record model inference duration and queue depth.
- Record database pool saturation and query duration.
- Record crawl throughput, rejection count, and indexing failures.
- Add distributed tracing across web, gRPC, model inference, and PostgreSQL calls.
- Add dashboards, alert thresholds, and incident-response guidance.

## 7. Data lifecycle

- Add crawl and update timestamps, source ownership, and embedding model/version metadata to documents.
- Define recrawling, retention, stale-document deletion, and user-requested deletion behavior.
- Define a migration and re-embedding strategy for model or vector-dimension changes.
- Define consistency and recovery behavior for interrupted indexing.

## Recommended order

1. CI and meaningful crawler, HTTP, database, and end-to-end tests.
2. Production containers, private networking, secret delivery, and health checks.
3. Production-scale hybrid-search benchmarks and query redesign.
4. Embedding readiness, metrics, tracing, dashboards, and alerts.
5. Backup/restore, data lifecycle, recrawling, and model migration procedures.
6. Load testing, resilience controls, and release/rollback runbooks.
