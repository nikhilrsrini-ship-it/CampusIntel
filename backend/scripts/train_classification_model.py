"""Train a local TF-IDF/logistic regression baseline from labeled CSV rows."""
import argparse
import csv
import json
import platform
from pathlib import Path

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.scripts_data import category_departments
from app.services.experiment_service import record_experiment


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/synthetic_requests.csv")
    parser.add_argument("--output", default=".models/category_classifier.joblib")
    parser.add_argument("--metrics", default="research/classification_metrics.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    with Path(args.input).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) < 30 or len({row["category"] for row in rows}) < 2:
        raise SystemExit("Provide at least 30 labeled rows across two or more categories.")
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
    evaluation = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)), ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=args.seed))])
    evaluation.fit(train_x, train_y)
    predicted = evaluation.predict(test_x)
    precision, recall, macro_f1, _ = precision_recall_fscore_support(test_y, predicted, average="macro", zero_division=0)
    labels_sorted = sorted(set(labels))
    metrics = {
        "dataset_type": dataset_type,
        "dataset_rows": len(rows),
        "train_rows": len(train_x),
        "test_rows": len(test_x),
        "seed": args.seed,
        "split_method": "scenario_group_holdout" if dataset_type == "SYNTHETIC" and all(row.get("scenario_id") for row in rows) else "stratified_random",
        "accuracy": accuracy_score(test_y, predicted),
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1": macro_f1,
        "classes": labels_sorted,
        "confusion_matrix": confusion_matrix(test_y, predicted, labels=labels_sorted).tolist(),
        "sklearn_version": sklearn.__version__,
    }
    pipeline = Pipeline([("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)), ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", random_state=args.seed))])
    pipeline.fit(texts, labels)
    feature_names = pipeline.named_steps["tfidf"].get_feature_names_out()
    coefficients = pipeline.named_steps["classifier"].coef_
    explanation = {}
    for index, category in enumerate(pipeline.named_steps["classifier"].classes_):
        top = coefficients[index].argsort()[-8:][::-1]
        explanation[str(category)] = [str(feature_names[item]) for item in top]
    artifact = {
        "pipeline": pipeline,
        "model_name": "tfidf-logistic-regression",
        "model_version": "1.0.0",
        "dataset_type": dataset_type,
        "category_departments": category_departments(),
        "explanations": explanation,
    }
    model_path = Path(args.output); model_path.parent.mkdir(parents=True, exist_ok=True); joblib.dump(artifact, model_path)
    metrics_path = Path(args.metrics); metrics_path.parent.mkdir(parents=True, exist_ok=True); metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    recorded = record_experiment("request-classification-tfidf-baseline", "LogisticRegression", "tfidf-1.0.0", Path(args.input).name, {"seed": args.seed, "test_size": 0.25, "vectorizer": "word 1-2 gram TF-IDF"}, metrics)
    print(json.dumps({"model_path": str(model_path), "metrics_path": str(metrics_path), "experiment_recorded_in_database": recorded, "dataset_type": dataset_type, "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
