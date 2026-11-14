"""Compare lexical and real 256/1024-dimensional retrieval on a fixed synthetic corpus."""

import argparse
import hashlib
import json
import math
import statistics
import time
from pathlib import Path

import httpx

from app.config import Settings
from app.knowledge import embed

MODEL = "Qwen/Qwen3-Embedding-0.6B"
INSTRUCTION = "Given a user question, retrieve relevant document passages that answer the question"


def normalize(vector):
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector]


def scores(documents, queries, doc_vectors, query_vectors):
    rows = []
    for query, vector in zip(queries, query_vectors, strict=True):
        ranked = sorted(
            zip(documents, doc_vectors, strict=True),
            key=lambda pair: sum(a * b for a, b in zip(vector, pair[1], strict=True)),
            reverse=True,
        )
        identifiers = [doc["id"] for doc, _ in ranked]
        rank = next(i + 1 for i, name in enumerate(identifiers) if name in query["relevant"])
        rows.append(
            {
                "query_id": query["id"],
                "language": query["language"],
                "rank": rank,
                "top3": identifiers[:3],
            }
        )
    return {
        "top1": sum(r["rank"] == 1 for r in rows) / len(rows),
        "recall3": sum(r["rank"] <= 3 for r in rows) / len(rows),
        "mrr": statistics.mean(1 / r["rank"] for r in rows),
        "per_language_top1": {
            lang: statistics.mean(r["rank"] == 1 for r in rows if r["language"] == lang)
            for lang in ["en", "de"]
        },
        "queries": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:8364/v1/embeddings")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument(
        "--fixture", type=Path, default=Path(__file__).with_name("semantic-retrieval.v1.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.endpoint.startswith("http://127.0.0.1:"):
        raise SystemExit("This local synthetic qualification command requires a loopback endpoint")
    fixture = json.loads(args.fixture.read_text())
    docs, queries = fixture["documents"], fixture["queries"]
    results = {
        "fixture_sha256": hashlib.sha256(args.fixture.read_bytes()).hexdigest(),
        "scope": (
            "24 synthetic passages / 48 EN-DE questions; local retrieval qualification, "
            "not production or broad-language acceptance"
        ),
        "results": {},
    }
    results["results"]["lexical256"] = scores(
        docs,
        queries,
        embed([d["text"] for d in docs], Settings()),
        embed([q["text"] for q in queries], Settings()),
    )
    with httpx.Client(
        timeout=90, headers={"Authorization": "Bearer " + args.key_file.read_text().strip()}
    ) as client:
        for dimension in [256, 1024]:
            timings = []

            def vectors(texts, dimension=dimension, timings=timings):
                output = []
                for start in range(0, len(texts), 8):
                    before = time.perf_counter()
                    response = client.post(
                        args.endpoint,
                        json={
                            "model": MODEL,
                            "input": texts[start : start + 8],
                            "dimensions": dimension,
                        },
                    )
                    response.raise_for_status()
                    timings.append(time.perf_counter() - before)
                    rows = response.json()["data"]
                    assert [r["index"] for r in rows] == list(range(len(texts[start : start + 8])))
                    for row in rows:
                        vector = row["embedding"]
                        assert len(vector) == dimension and all(math.isfinite(v) for v in vector)
                        assert abs(sum(v * v for v in vector) - 1) < 0.001
                        output.append(vector)
                return output

            doc_vectors = vectors([d["text"] for d in docs])
            query_vectors = vectors(
                [f"Instruct: {INSTRUCTION}\nQuery:{q['text']}" for q in queries]
            )
            outcome = scores(docs, queries, doc_vectors, query_vectors)
            outcome["batch_latency_seconds"] = {
                "median": statistics.median(timings),
                "maximum": max(timings),
                "all": timings,
            }
            results["results"]["qwen" + str(dimension)] = outcome
            print(
                dimension,
                {
                    key: value
                    for key, value in outcome.items()
                    if key not in {"queries", "batch_latency_seconds"}
                },
                flush=True,
            )
    a = fixture["acceptance"]
    small = results["results"]["qwen256"]
    full = results["results"]["qwen1024"]
    results["acceptance"] = a
    results["passed"] = (
        small["top1"] >= a["top1_minimum"]
        and small["recall3"] >= a["recall3_minimum"]
        and all(v >= a["per_language_top1_minimum"] for v in small["per_language_top1"].values())
        and full["top1"] - small["top1"] <= a["maximum_256_top1_drop"]
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print("Local synthetic retrieval thresholds passed:", results["passed"])
    raise SystemExit(0 if results["passed"] else 1)


if __name__ == "__main__":
    main()
