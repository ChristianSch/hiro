"""Canonicalize stored document URLs and merge equivalent documents."""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from .embed.config import EmbeddingSettings
from .url_utils import canonicalize_url


def stage_canonical_urls(source, target, apply: bool) -> int:
    invalid = 0
    if apply:
        target.execute("LOCK TABLE documents IN SHARE ROW EXCLUSIVE MODE")
    target.execute(
        '''CREATE TEMP TABLE url_normalization (
             document_id bigint PRIMARY KEY,
             canonical_url text NOT NULL
           ) ON COMMIT DROP'''
    )
    with source.cursor(name="url_normalization_source") as source_cursor:
        source_cursor.execute("SELECT id, url FROM documents ORDER BY id")
        with target.cursor().copy(
            "COPY url_normalization (document_id, canonical_url) FROM STDIN"
        ) as copy:
            for document_id, url in source_cursor:
                try:
                    canonical_url = canonicalize_url(url)
                except ValueError:
                    canonical_url = url
                    invalid += 1
                copy.write_row((document_id, canonical_url))
    target.execute(
        "CREATE INDEX url_normalization_canonical_idx ON url_normalization (canonical_url)"
    )
    return invalid


def normalization_stats(connection) -> tuple[int, int, int]:
    changed = connection.execute(
        '''SELECT count(*)
           FROM url_normalization
           JOIN documents ON documents.id = url_normalization.document_id
           WHERE documents.url <> url_normalization.canonical_url'''
    ).fetchone()[0]
    duplicate_groups, duplicate_documents = connection.execute(
        '''SELECT count(*), coalesce(sum(group_size - 1), 0)
           FROM (
             SELECT count(*) AS group_size
             FROM url_normalization
             GROUP BY canonical_url
             HAVING count(*) > 1
           ) groups'''
    ).fetchone()
    return changed, duplicate_groups, duplicate_documents


def apply_normalization(connection) -> tuple[int, int]:
    connection.execute(
        '''CREATE TEMP TABLE url_winners ON COMMIT DROP AS
           WITH chunk_counts AS (
             SELECT document_id, count(*) AS chunk_count
             FROM document_chunks
             GROUP BY document_id
           )
           SELECT DISTINCT ON (normalization.canonical_url)
             normalization.canonical_url,
             documents.id AS document_id
           FROM url_normalization normalization
           JOIN documents ON documents.id = normalization.document_id
           LEFT JOIN chunk_counts ON chunk_counts.document_id = documents.id
           ORDER BY
             normalization.canonical_url,
             coalesce(chunk_counts.chunk_count, 0) DESC,
             documents.updated_at DESC,
             documents.id DESC'''
    )
    deleted = connection.execute(
        '''DELETE FROM documents
           USING url_normalization normalization, url_winners winners
           WHERE documents.id = normalization.document_id
             AND winners.canonical_url = normalization.canonical_url
             AND documents.id <> winners.document_id'''
    ).rowcount
    updated = connection.execute(
        '''UPDATE documents
           SET url = winners.canonical_url,
               updated_at = now()
           FROM url_winners winners
           WHERE documents.id = winners.document_id
             AND documents.url <> winners.canonical_url'''
    ).rowcount
    return updated, deleted


def run(settings: EmbeddingSettings, apply: bool) -> None:
    with (
        psycopg.connect(settings.database_url) as source,
        psycopg.connect(settings.database_url) as target,
    ):
        invalid = stage_canonical_urls(source, target, apply)
        changed, duplicate_groups, duplicate_documents = normalization_stats(target)
        print(
            f"changed_urls={changed} duplicate_groups={duplicate_groups} "
            f"duplicate_documents={duplicate_documents} invalid_urls={invalid}"
        )
        if not apply:
            print("dry run; pass --apply to canonicalize and merge")
            return
        updated, deleted = apply_normalization(target)
        print(f"updated_urls={updated} deleted_duplicates={deleted}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("config"))
    parser.add_argument(
        "--apply",
        action="store_true",
        help="apply changes; without this flag the command is read-only",
    )
    args = parser.parse_args()
    settings = EmbeddingSettings.from_files(
        args.config_dir / "global.yml",
        args.config_dir / "embed.yml",
    )
    run(settings, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
