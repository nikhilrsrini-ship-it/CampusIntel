"""Evaluate TF-IDF duplicate candidates on a human-labeled CSV; no rows are fabricated."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV with query_id, query_text, candidate_text, is_duplicate")
    parser.add_argument("--output", default="research/duplicate_metrics.json")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.25)
    args = parser.parse_args()
    with Path(args.input).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"query_id", "query_text", "candidate_text", "is_duplicate"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit("Input must contain labeled query/candidate pairs; no metrics were created.")
    vectors = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform([row["query_text"] for row in rows] + [row["candidate_text"] for row in rows])
    scores = cosine_similarity(vectors[:len(rows)], vectors[len(rows):]).diagonal()
    groups = defaultdict(list)
    for row, score in zip(rows, scores):
        groups[row["query_id"]].append((float(score), str(row["is_duplicate"]).strip().lower() in {"1", "true", "yes"}))
    precisions, recalls, f1_values = [], [], []
    for pairs in groups.values():
        ranked = sorted(pairs, key=lambda item: item[0], reverse=True)
        relevant = sum(label for _, label in pairs)
        hits = sum(label for _, label in ranked[:args.k])
        precisions.append(hits / min(args.k, len(ranked)))
        recalls.append(hits / relevant if relevant else 0.0)
        tp = sum(score >= args.threshold and label for score, label in pairs)
        fp = sum(score >= args.threshold and not label for score, label in pairs)
        fn = sum(score < args.threshold and label for score, label in pairs)
        f1_values.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0)
    dataset_types = {row.get("dataset_type", "UNSPECIFIED") for row in rows}
    result = {"dataset_type": dataset_types.pop() if len(dataset_types) == 1 else "MIXED_OR_UNSPECIFIED", "queries": len(groups), "candidate_pairs": len(rows), "k": args.k, "threshold": args.threshold, "precision_at_k": float(np.mean(precisions)), "recall_at_k": float(np.mean(recalls)), "f1_at_threshold": float(np.mean(f1_values)), "method": "tfidf_cosine_similarity"}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": result}, indent=2))


if __name__ == "__main__":
    main()
