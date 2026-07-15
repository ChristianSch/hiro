"""Batch re-embed stored document chunks with the configured model."""

from __future__ import annotations

import argparse
import logging
import time
from collections import defaultdict
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

from .chunking import chunk_content
from .config import EmbeddingSettings


def prepared_contents(
    tokenizer,
    stored_chunks: list[tuple[str, str]],
    max_tokens: int,
    overlap_tokens: int,
    rechunk_legacy: bool,
) -> list[str]:
    if (
        rechunk_legacy
        and len(stored_chunks) == 1
        and stored_chunks[0][1] == "legacy"
    ):
        return chunk_content(
            tokenizer,
            stored_chunks[0][0],
            max_tokens,
            overlap_tokens,
        )
    return [content for content, _model in stored_chunks]


def target_counts(connection, model_name: str, force: bool) -> tuple[int, int]:
    condition = "true" if force else "chunks.embedding_model <> %s"
    parameters = () if force else (model_name,)
    row = connection.execute(
        f'''SELECT count(DISTINCT chunks.document_id), count(*)
            FROM document_chunks chunks
            WHERE {condition}''',
        parameters,
    ).fetchone()
    return row[0], row[1]


def run(
    settings: EmbeddingSettings,
    batch_documents: int,
    limit_documents: int | None,
    force: bool,
    rechunk_legacy: bool,
    dry_run: bool,
) -> tuple[int, int]:
    with psycopg.connect(settings.database_url, autocommit=True) as connection:
        register_vector(connection)
        if dry_run:
            document_count, chunk_count = target_counts(
                connection,
                settings.model_name,
                force,
            )
            print(
                f"target_documents={document_count} target_chunks={chunk_count} "
                f"model={settings.model_name}"
            )
            return 0, 0

        print(f"model={settings.model_name}")
        model = SentenceTransformer(
            settings.model_name,
            device=settings.model_device,
        )
        cursor = 0
        processed_documents = 0
        processed_chunks = 0
        started = time.perf_counter()

        while True:
            if limit_documents is not None:
                remaining = limit_documents - processed_documents
                if remaining <= 0:
                    break
                current_batch_size = min(batch_documents, remaining)
            else:
                current_batch_size = batch_documents

            with connection.transaction():
                document_ids = [
                    row[0]
                    for row in connection.execute(
                        '''SELECT documents.id
                           FROM documents
                           WHERE documents.id > %s
                             AND EXISTS (
                               SELECT 1 FROM document_chunks
                               WHERE document_chunks.document_id = documents.id
                             )
                             AND (
                               %s OR EXISTS (
                                 SELECT 1 FROM document_chunks
                                 WHERE document_chunks.document_id = documents.id
                                   AND document_chunks.embedding_model <> %s
                               )
                             )
                           ORDER BY documents.id
                           LIMIT %s
                           FOR UPDATE OF documents''',
                        (
                            cursor,
                            force,
                            settings.model_name,
                            current_batch_size,
                        ),
                    ).fetchall()
                ]
                if not document_ids:
                    break

                rows = connection.execute(
                    '''SELECT document_id, content, embedding_model
                       FROM document_chunks
                       WHERE document_id = ANY(%s)
                       ORDER BY document_id, chunk_index''',
                    (document_ids,),
                ).fetchall()
                by_document: dict[int, list[tuple[str, str]]] = defaultdict(list)
                for document_id, content, embedding_model in rows:
                    by_document[document_id].append((content, embedding_model))

                prepared: list[tuple[int, int, str]] = []
                texts: list[str] = []
                for document_id in document_ids:
                    contents = prepared_contents(
                        model.tokenizer,
                        by_document[document_id],
                        settings.chunk_max_tokens,
                        settings.chunk_overlap_tokens,
                        rechunk_legacy,
                    )
                    for chunk_index, content in enumerate(contents):
                        prepared.append((document_id, chunk_index, content))
                        texts.append(content)

                embeddings = model.encode(
                    texts,
                    batch_size=settings.embedding_batch_size,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                connection.execute(
                    "DELETE FROM document_chunks WHERE document_id = ANY(%s)",
                    (document_ids,),
                )
                with connection.cursor() as cursor_handle:
                    cursor_handle.executemany(
                        '''INSERT INTO document_chunks (
                             document_id, chunk_index, content, embedding, embedding_model
                           ) VALUES (%s, %s, %s, %s, %s)''',
                        [
                            (
                                document_id,
                                chunk_index,
                                content,
                                embeddings[index],
                                settings.model_name,
                            )
                            for index, (document_id, chunk_index, content) in enumerate(prepared)
                        ],
                    )
                connection.execute(
                    "UPDATE documents SET updated_at = now() WHERE id = ANY(%s)",
                    (document_ids,),
                )

            cursor = document_ids[-1]
            processed_documents += len(document_ids)
            processed_chunks += len(prepared)
            elapsed = max(time.perf_counter() - started, 1e-9)
            print(
                f"documents={processed_documents} chunks={processed_chunks} "
                f"documents_per_second={processed_documents / elapsed:.2f}",
                flush=True,
            )

    return processed_documents, processed_chunks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument("--batch-documents", type=int, default=50)
    parser.add_argument("--limit-documents", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--rechunk-legacy",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="split one-chunk legacy documents using the current chunk settings",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.batch_documents < 1:
        parser.error("--batch-documents must be positive")
    if args.limit_documents is not None and args.limit_documents < 1:
        parser.error("--limit-documents must be positive")

    settings = EmbeddingSettings.from_files(
        args.config_dir / "global.yml",
        args.config_dir / "embed.yml",
    )
    logging.basicConfig(level=settings.log_level)
    run(
        settings,
        batch_documents=args.batch_documents,
        limit_documents=args.limit_documents,
        force=args.force,
        rechunk_legacy=args.rechunk_legacy,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
