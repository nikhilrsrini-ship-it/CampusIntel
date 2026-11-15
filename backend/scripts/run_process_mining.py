"""Discover a directly-follows process graph with PM4Py from an exported event log."""
import argparse
import json
from pathlib import Path

import pandas as pd
import pm4py


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/process_event_log.csv")
    parser.add_argument("--output", default="research/process_mining.json")
    args = parser.parse_args()
    log_path = Path(args.input)
    if not log_path.is_file():
        raise SystemExit(f"Event log not found: {log_path}. Export it from authorized database records first.")
    frame = pd.read_csv(log_path)
    if frame.empty:
        raise SystemExit("No events are available; process discovery was not run.")
    frame["time:timestamp"] = pd.to_datetime(frame["time:timestamp"], utc=True)
    dfg = pm4py.discover_dfg(frame, case_id_key="case:concept:name", activity_key="concept:name", timestamp_key="time:timestamp")
    performance = pm4py.discover_performance_dfg(frame, case_id_key="case:concept:name", activity_key="concept:name", timestamp_key="time:timestamp")
    result = {
        "dataset_type": "INSTITUTIONAL_EVENT_LOG",
        "case_count": int(frame["case:concept:name"].nunique()),
        "event_count": int(len(frame)),
        "directly_follows": [{"from": left, "to": right, "count": int(count), "mean_seconds": float(performance.get((left, right), 0.0))} for (left, right), count in sorted(dfg.items(), key=lambda item: (-item[1], item[0]))],
        "method": "PM4Py directly-follows graph and performance DFG",
        "note": "This reflects exported event records only; it does not establish a causal reason for delay.",
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "cases": result["case_count"], "events": result["event_count"], "edges": len(result["directly_follows"])}, indent=2))


if __name__ == "__main__":
    main()
