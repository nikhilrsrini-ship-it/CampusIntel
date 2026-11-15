"""Collect existing model evaluation files into CSV and JSON; never invents metrics."""
import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="research")
    parser.add_argument("--json-output", default="research/evaluation_results.json")
    parser.add_argument("--csv-output", default="research/evaluation_results.csv")
    args = parser.parse_args()
    root = Path(args.input_dir)
    results = []
    for path in sorted(root.glob("*metrics.json")):
        results.append({"experiment": path.stem, "metrics": json.loads(path.read_text(encoding="utf-8"))})
    if not results:
        raise SystemExit("No evaluation metric files exist yet; no results were generated.")
    Path(args.json_output).write_text(json.dumps(results, indent=2), encoding="utf-8")
    rows = []
    for result in results:
        for name, value in result["metrics"].items():
            if isinstance(value, (int, float, str)) or value is None:
                rows.append({"experiment": result["experiment"], "dataset_type": result["metrics"].get("dataset_type"), "metric": name, "value": value})
            elif isinstance(value, dict):
                for subname, subvalue in value.items():
                    rows.append({"experiment": result["experiment"], "dataset_type": result["metrics"].get("dataset_type"), "metric": f"{name}.{subname}", "value": subvalue})
    with Path(args.csv_output).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["experiment", "dataset_type", "metric", "value"]); writer.writeheader(); writer.writerows(rows)
    print(f"Combined {len(results)} existing metric files. No new measurements were synthesized.")


if __name__ == "__main__":
    main()
