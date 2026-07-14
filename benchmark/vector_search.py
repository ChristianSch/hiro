#!/usr/bin/env python3
"""Benchmark pgvector HNSW latency and ANN Recall@k against exact search."""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from statistics import mean
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from wintermute.search.config import SearchSettings


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def sample_queries(connection, count: int, seed: int) -> list[tuple[int, Any]]:
    bounds = connection.execute(
        "SELECT min(id), max(id) FROM document_chunks"
    ).fetchone()
    if bounds is None or bounds[0] is None:
        raise RuntimeError("document_chunks is empty")

    rng = random.Random(seed)
    sampled: dict[int, Any] = {}
    attempts = 0
    while len(sampled) < count and attempts < count * 20:
        attempts += 1
        candidate = rng.randint(bounds[0], bounds[1])
        row = connection.execute(
            '''SELECT id, embedding
               FROM document_chunks
               WHERE id >= %s
               ORDER BY id
               LIMIT 1''',
            (candidate,),
        ).fetchone()
        if row is not None:
            sampled[row[0]] = row[1]
    if len(sampled) < count:
        raise RuntimeError(f"could only sample {len(sampled)} query vectors")
    return list(sampled.items())


def nearest_neighbors(
    connection,
    query_id: int,
    embedding,
    top_k: int,
    *,
    exact: bool,
    ef_search: int | None = None,
) -> tuple[list[int], float]:
    started = time.perf_counter()
    with connection.transaction():
        if exact:
            connection.execute("SET LOCAL enable_indexscan = off")
        else:
            connection.execute(
                "SELECT set_config('hnsw.ef_search', %s, true)",
                (str(ef_search),),
            )
        rows = connection.execute(
            '''SELECT id
               FROM document_chunks
               WHERE id <> %s
               ORDER BY embedding <=> %s
               LIMIT %s''',
            (query_id, embedding, top_k),
        ).fetchall()
    elapsed_ms = (time.perf_counter() - started) * 1_000
    return [row[0] for row in rows], elapsed_ms


def database_stats(connection) -> dict[str, Any]:
    row = connection.execute(
        '''SELECT
             count(*),
             pg_total_relation_size('document_chunks'),
             pg_relation_size('document_chunks_embedding_hnsw_idx')
           FROM document_chunks'''
    ).fetchone()
    return {
        "vectors": row[0],
        "table_bytes": row[1],
        "hnsw_index_bytes": row[2],
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    settings = SearchSettings.from_files(
        args.config_dir / "global.yml",
        args.config_dir / "search.yml",
    )
    with psycopg.connect(settings.database_url, autocommit=True) as connection:
        register_vector(connection)
        queries = sample_queries(connection, args.samples, args.seed)
        stats = database_stats(connection)

        exact_results: dict[int, set[int]] = {}
        exact_latencies = []
        for query_id, embedding in queries:
            result, latency = nearest_neighbors(
                connection,
                query_id,
                embedding,
                args.top_k,
                exact=True,
            )
            exact_results[query_id] = set(result)
            exact_latencies.append(latency)

        configurations = []
        for ef_search in args.ef_search:
            latencies = []
            recalls = []
            for query_id, embedding in queries:
                result, latency = nearest_neighbors(
                    connection,
                    query_id,
                    embedding,
                    args.top_k,
                    exact=False,
                    ef_search=ef_search,
                )
                expected = exact_results[query_id]
                recalls.append(len(expected.intersection(result)) / max(len(expected), 1))
                latencies.append(latency)
            configurations.append({
                "ef_search": ef_search,
                "recall_at_k": mean(recalls),
                "latency_ms": {
                    "mean": mean(latencies),
                    "p50": percentile(latencies, 0.50),
                    "p95": percentile(latencies, 0.95),
                    "p99": percentile(latencies, 0.99),
                },
            })

    return {
        "top_k": args.top_k,
        "samples": args.samples,
        "database": stats,
        "exact_latency_ms": {
            "mean": mean(exact_latencies),
            "p50": percentile(exact_latencies, 0.50),
            "p95": percentile(exact_latencies, 0.95),
            "p99": percentile(exact_latencies, 0.99),
        },
        "hnsw": configurations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--ef-search", nargs="+", type=int, default=[40, 80, 160, 320])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.top_k < 1 or any(value < 1 for value in args.ef_search):
        parser.error("samples, top-k, and ef-search values must be positive")

    result = run(args)
    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
