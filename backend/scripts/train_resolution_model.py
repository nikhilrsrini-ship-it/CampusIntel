"""Train and evaluate a local resolution-time model on completed database cases."""
import argparse
import json
import math
from datetime import timezone
from pathlib import Path

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import MLModelExperiment, ServiceRequest


def hours(row) -> float:
    start, end = row.created_at, row.resolved_at
    if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
    return max(0.0, (end - start).total_seconds() / 3600)


def features(row) -> dict[str, str]:
    return {"category": str(row.category_id or "unknown"), "department": str(row.assigned_department_id or "unknown"), "priority": row.priority}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".models/resolution_predictor.joblib")
    parser.add_argument("--metrics", default="research/resolution_metrics.json")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = db.scalars(select(ServiceRequest).where(ServiceRequest.resolved_at.is_not(None))).all()
        if len(rows) < 20:
            raise SystemExit(f"Need at least 20 resolved requests; database has {len(rows)}. No model was trained.")
        x = [features(row) for row in rows]
        y = [hours(row) for row in rows]
        train_x, test_x, train_y, test_y = train_test_split(x, y, test_size=0.2, random_state=args.seed)
        model = Pipeline([("vectorizer", DictVectorizer()), ("forest", RandomForestRegressor(n_estimators=250, min_samples_leaf=2, random_state=args.seed, n_jobs=1))])
        model.fit(train_x, train_y)
        predicted = model.predict(test_x)
        baseline = [sorted(train_y)[len(train_y) // 2]] * len(test_y)
        metrics = {
            "dataset_type": "INSTITUTIONAL_HISTORICAL",
            "training_rows": len(train_x), "test_rows": len(test_x), "seed": args.seed,
            "random_forest": {"mae_hours": mean_absolute_error(test_y, predicted), "rmse_hours": math.sqrt(mean_squared_error(test_y, predicted)), "r2": r2_score(test_y, predicted)},
            "historical_median_baseline": {"mae_hours": mean_absolute_error(test_y, baseline), "rmse_hours": math.sqrt(mean_squared_error(test_y, baseline)), "r2": r2_score(test_y, baseline)},
        }
        model.fit(x, y)
        output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
        version = "random-forest-resolution-v1"
        joblib.dump({"model": model, "model_version": version, "training_rows": len(rows), "dataset_type": "INSTITUTIONAL_HISTORICAL"}, output)
        metrics_path = Path(args.metrics); metrics_path.parent.mkdir(parents=True, exist_ok=True); metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        db.add(MLModelExperiment(experiment_name="resolution-time-baseline-comparison", model_name="RandomForestRegressor", model_version=version, dataset_name="institutional-resolved-requests", configuration_json={"seed": args.seed, "test_size": 0.2, "features": ["category", "department", "priority"]}, metrics_json=metrics))
        db.commit()
    print(json.dumps({"model_path": str(output), "metrics_path": str(metrics_path), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
