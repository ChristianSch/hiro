#!/usr/bin/env python3
"""Evaluate Hiro search quality against a labeled query set.

Run from the repository root while Wintermute's search service is running:

    uv run python eval/run_eval.py --queries eval/queries.json --host localhost:50053

Query file format:

    [
      {
        "query": "contact support",
        "relevant_urls": ["https://example.com/contact"]
      },
      {
        "query": "pricing plans",
        "relevance": {
          "https://example.com/pricing": 2,
          "https://example.com/blog/pricing": 1
        }
      }
    ]

`relevant_urls` is binary relevance. `relevance` supports graded relevance for NDCG.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

import grpc

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from wintermute.search.stubs.search_pb2 import SearchRequest  # noqa: E402
from wintermute.search.stubs.search_pb2_grpc import SearchServiceStub  # noqa: E402


@dataclass
class QueryCase:
    query: str
    relevance: dict[str, float]


def load_cases(path: Path) -> list[QueryCase]:
    raw = json.loads(path.read_text())
    cases: list[QueryCase] = []

    if not isinstance(raw, list):
        raise ValueError("query file must contain a JSON array")

    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"case {i} must be an object")
        query = item.get("query")
        if not query:
            raise ValueError(f"case {i} is missing 'query'")

        if "relevance" in item:
            relevance = {
                url: float(score)
                for url, score in item["relevance"].items()
                if float(score) > 0
            }
        elif "relevant_urls" in item:
            relevance = {url: 1.0 for url in item["relevant_urls"]}
        else:
            raise ValueError(f"case {i} needs 'relevant_urls' or 'relevance'")

        if not relevance:
            raise ValueError(f"case {i} has no relevant URLs")

        cases.append(QueryCase(query=query, relevance=relevance))

    return cases


def precision_at(results: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for url in results[:k] if url in relevant) / k


def recall_at(results: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for url in results[:k] if url in relevant) / len(relevant)


def reciprocal_rank(results: list[str], relevant: set[str]) -> float:
    for idx, url in enumerate(results, start=1):
        if url in relevant:
            return 1.0 / idx
    return 0.0


def average_precision(results: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0

    hits = 0
    precisions: list[float] = []
    for idx, url in enumerate(results, start=1):
        if url in relevant:
            hits += 1
            precisions.append(hits / idx)

    # Divide by total known relevant docs, not only retrieved relevant docs.
    return sum(precisions) / len(relevant)


def dcg(grades: list[float], k: int) -> float:
    total = 0.0
    for idx, grade in enumerate(grades[:k], start=1):
        total += (2**grade - 1) / math.log2(idx + 1)
    return total


def ndcg_at(results: list[str], relevance: dict[str, float], k: int) -> float:
    actual_grades = [relevance.get(url, 0.0) for url in results[:k]]
    ideal_grades = sorted(relevance.values(), reverse=True)[:k]
    ideal = dcg(ideal_grades, k)
    if ideal == 0:
        return 0.0
    return dcg(actual_grades, k) / ideal


def search(stub: SearchServiceStub, query: str, limit: int, timeout: float) -> list[str]:
    response = stub.Search(
        SearchRequest(query=query, page_number=1, result_per_page=limit),
        timeout=timeout,
    )
    return [result.url for result in response.results]


def evaluate_case(stub: SearchServiceStub, case: QueryCase, args: argparse.Namespace) -> dict[str, Any]:
    returned = search(stub, case.query, args.limit, args.timeout)
    relevant = set(case.relevance.keys())

    metrics: dict[str, Any] = {
        "query": case.query,
        "returned_urls": returned,
        "relevant_urls": sorted(relevant),
        "mrr": reciprocal_rank(returned, relevant),
        "ap": average_precision(returned, relevant),
    }

    for k in args.k:
        metrics[f"precision@{k}"] = precision_at(returned, relevant, k)
        metrics[f"recall@{k}"] = recall_at(returned, relevant, k)
        metrics[f"ndcg@{k}"] = ndcg_at(returned, case.relevance, k)

    return metrics


def write_results(path: Path, case_metrics: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"cases": case_metrics}, indent=2))


def print_summary(case_metrics: list[dict[str, Any]], ks: list[int]) -> None:
    print(f"Queries evaluated: {len(case_metrics)}")
    print(f"MRR: {mean(m['mrr'] for m in case_metrics):.4f}")
    print(f"MAP: {mean(m['ap'] for m in case_metrics):.4f}")

    for k in ks:
        print(f"Precision@{k}: {mean(m[f'precision@{k}'] for m in case_metrics):.4f}")
        print(f"Recall@{k}:    {mean(m[f'recall@{k}'] for m in case_metrics):.4f}")
        print(f"NDCG@{k}:      {mean(m[f'ndcg@{k}'] for m in case_metrics):.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Hiro search relevance")
    parser.add_argument("--queries", default="eval/queries.json", type=Path)
    parser.add_argument("--host", default="localhost:50053")
    parser.add_argument("--k", nargs="+", type=int, default=[5, 10])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--show-cases", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.queries)

    with grpc.insecure_channel(args.host) as channel:
        stub = SearchServiceStub(channel)
        case_metrics = [evaluate_case(stub, case, args) for case in cases]

    print_summary(case_metrics, args.k)

    if args.show_cases:
        print("\nPer-query metrics:")
        for metrics in case_metrics:
            print(json.dumps(metrics, indent=2))

    if args.json_output:
        write_results(args.json_output, case_metrics)
        print(f"\nWrote {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
