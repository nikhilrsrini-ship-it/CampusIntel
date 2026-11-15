"""Export request event history as an authorized local process-mining CSV."""
import argparse
import csv
from pathlib import Path

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import RequestEvent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/process_event_log.csv")
    args = parser.parse_args()
    with SessionLocal() as db:
        events = db.scalars(select(RequestEvent).order_by(RequestEvent.request_id, RequestEvent.event_timestamp)).all()
        rows = [{"case:concept:name": str(row.request_id), "concept:name": row.event_type, "time:timestamp": row.event_timestamp.isoformat(), "org:resource": str(row.department_id or "unassigned")} for row in events]
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case:concept:name", "concept:name", "time:timestamp", "org:resource"])
        writer.writeheader(); writer.writerows(rows)
    print(f"Exported {len(rows)} workflow events to {path} from database records.")


if __name__ == "__main__":
    main()
