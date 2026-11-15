"""Train a semantic classifier using a local, pre-downloaded sentence model."""
import argparse
import csv
import json
from pathlib import Path

import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sentence_transformers import SentenceTransformer

from app.scripts_data import category_departments
from app.services.experiment_service import record_experiment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/synthetic_requests.csv")
    parser.add_argument("--embedding-model", required=True, help="Local model directory. Remote model downloads are disabled.")
    parser.add_argument("--output", default=".models/category_semantic_classifier.joblib")
    parser.add_argument("--metrics", default="research/semantic_classification_metrics.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    model_path = Path(args.embedding_model).resolve()
    if not model_path.is_dir():
        raise SystemExit("Provide a local embedding model directory. This script does not download model code or weights.")
    with Path(args.input).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    texts, labels = [row["text"] for row in rows], [row["category"] for row in rows]
    dataset_type = "SYNTHETIC" if all(row.get("dataset_type") == "SYNTHETIC" for row in rows) else "INSTITUTIONAL_LABELED"
    if dataset_type == "SYNTHETIC" and all(row.get("scenario_id") for row in rows):
        test_groups = {groups[args.seed % len(groups)] for category in sorted(set(labels)) if (groups := sorted({row["scenario_id"] for row in rows if row["category"] == category}))}
        train_indexes = [i for i, row in enumerate(rows) if row["scenario_id"] not in test_groups]
        test_indexes = [i for i, row in enumerate(rows) if row["scenario_id"] in test_groups]
        train_x, test_x = [texts[i] for i in train_indexes], [texts[i] for i in test_indexes]
        train_y, test_y = [labels[i] for i in train_indexes], [labels[i] for i in test_indexes]
    else:
        train_x, test_x, train_y, test_y = train_test_split(texts, labels, test_size=0.25, random_state=args.seed, stratify=labels)
    encoder = SentenceTransformer(str(model_path), device="cpu", local_files_only=True)
    train_vectors = encoder.encode(train_x, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    test_vectors = encoder.encode(test_x, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=args.seed).fit(train_vectors, train_y)
    predictions = classifier.predict(test_vectors)
    precision, recall, macro_f1, _ = precision_recall_fscore_support(test_y, predictions, average="macro", zero_division=0)
    metrics = {"dataset_type": dataset_type, "dataset_rows": len(rows), "train_rows": len(train_x), "test_rows": len(test_x), "seed": args.seed, "split_method": "scenario_group_holdout" if dataset_type == "SYNTHETIC" and all(row.get("scenario_id") for row in rows) else "stratified_random", "accuracy": accuracy_score(test_y, predictions), "macro_precision": precision, "macro_recall": recall, "macro_f1": macro_f1, "embedding_model_path": str(model_path)}
    full_vectors = encoder.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
    full_classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=args.seed).fit(full_vectors, labels)
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"classifier": full_classifier, "model_version": "semantic-1.0.0", "dataset_type": metrics["dataset_type"], "category_departments": category_departments()}, output)
    metrics_path = Path(args.metrics); metrics_path.parent.mkdir(parents=True, exist_ok=True); metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    recorded = record_experiment("request-classification-sentence-embedding", "LogisticRegression", "semantic-1.0.0", Path(args.input).name, {"seed": args.seed, "test_size": 0.25, "embedding_model_path": str(model_path)}, metrics)
    print(json.dumps({"model_path": str(output), "experiment_recorded_in_database": recorded, "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
