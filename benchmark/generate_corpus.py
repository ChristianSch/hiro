#!/usr/bin/env python3
"""Generate a synthetic document/chunk corpus for PostgreSQL search benchmarks."""

from __future__ import annotations

import argparse
import hashlib
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from wintermute.search.config import SearchSettings


VOCABULARY = (
    "architecture authentication benchmark caching crawler database deployment "
    "embedding frontend grpc indexing latency migration model observability "
    "pagination postgres production query ranking retrieval search security "
    "service storage testing vector website"
).split()


def text_for(rng: random.Random, document_id: int, chunk_index: int) -> str:
    terms = rng.choices(VOCABULARY, k=80)
    return f"document {document_id} chunk {chunk_index} " + " ".join(terms)


def normalized_vectors(rng: np.random.Generator, count: int, dimensions: int):
    vectors = rng.standard_normal((count, dimensions), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def insert_batch(
    connection,
    start_id: int,
    count: int,
    chunks_per_document: int,
    dimensions: int,
    seed: int,
) -> None:
    text_rng = random.Random(seed)
    vector_rng = np.random.default_rng(seed)
    now = datetime.now(timezone.utc)
    chunk_count = count * chunks_per_document
    vectors = normalized_vectors(vector_rng, chunk_count, dimensions)

    with connection.transaction():
        with connection.cursor().copy(
            '''COPY documents (
                 id, url, title, content, description,
                 source_host, content_hash, crawled_at, updated_at, random_key
               ) FROM STDIN'''
        ) as copy:
            for offset in range(count):
                document_id = start_id + offset
                content = f"synthetic benchmark document {document_id}"
                copy.write_row((
                    document_id,
                    f"https://benchmark.local/documents/{document_id}",
                    f"Benchmark document {document_id}",
                    None,
                    "Synthetic benchmark document",
                    "benchmark.local",
                    hashlib.sha256(content.encode()).hexdigest(),
                    now,
                    now,
                    text_rng.random(),
                ))

        with connection.cursor().copy(
            '''COPY document_chunks (
                 document_id, chunk_index, content, embedding, embedding_model
               ) FROM STDIN'''
        ) as copy:
            vector_index = 0
            for offset in range(count):
                document_id = start_id + offset
                for chunk_index in range(chunks_per_document):
                    copy.write_row((
                        document_id,
                        chunk_index,
                        text_for(text_rng, document_id, chunk_index),
                        vectors[vector_index],
                        "benchmark-random-v1",
                    ))
                    vector_index += 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--documents", type=int, required=True)
    parser.add_argument("--chunks-per-document", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if min(args.documents, args.chunks_per_document, args.batch_size) < 1:
        parser.error("documents, chunks-per-document, and batch-size must be positive")
    settings = SearchSettings.from_files(
        args.config_dir / "global.yml",
        args.config_dir / "search.yml",
    )
    started = time.perf_counter()
    with psycopg.connect(settings.database_url) as connection:
        register_vector(connection)
        if args.replace:
            with connection.transaction():
                connection.execute(
                    "DELETE FROM documents WHERE source_host = 'benchmark.local'"
                )

        start_id = connection.execute(
            "SELECT coalesce(max(id), 0) + 1 FROM documents"
        ).fetchone()[0]
        inserted = 0
        while inserted < args.documents:
            count = min(args.batch_size, args.documents - inserted)
            insert_batch(
                connection,
                start_id + inserted,
                count,
                args.chunks_per_document,
                settings.model_dimensions,
                args.seed + inserted,
            )
            inserted += count
            elapsed = max(time.perf_counter() - started, 1e-9)
            print(
                f"documents={inserted}/{args.documents} "
                f"chunks={inserted * args.chunks_per_document} "
                f"documents_per_second={inserted / elapsed:.1f}",
                flush=True,
            )

        with connection.transaction():
            connection.execute(
                '''SELECT setval(
                     pg_get_serial_sequence('documents', 'id'),
                     coalesce((SELECT max(id) FROM documents), 1),
                     true
                   )'''
            )
            connection.execute("ANALYZE documents")
            connection.execute("ANALYZE document_chunks")

    elapsed = time.perf_counter() - started
    print(f"completed in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
