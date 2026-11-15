from collections import Counter, defaultdict
from datetime import timezone
from io import StringIO
import csv

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.database.session import get_db
from app.models import Department, DepartmentStaff, RequestAssignment, RequestEvent, ServiceRequest, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _hours(start, end) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0.0, (end - start).total_seconds() / 3600)


def _scope_query(db: Session, user: User):
    query = select(ServiceRequest)
    if user.role == "STAFF":
        memberships = select(DepartmentStaff.department_id).where(DepartmentStaff.staff_id == user.id)
        query = query.where((ServiceRequest.assigned_staff_id == user.id) | ServiceRequest.assigned_department_id.in_(memberships))
    return query


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    requests = db.scalars(select(ServiceRequest)).all()
    total = len(requests)
    by_status = dict(db.execute(select(ServiceRequest.current_status, func.count()).group_by(ServiceRequest.current_status)).all())
    resolved = [row for row in requests if row.resolved_at]
    average_hours = sum(_hours(row.created_at, row.resolved_at) for row in resolved) / len(resolved) if resolved else None
    return {"total_requests": total, "by_status": by_status, "resolved_count": len(resolved), "average_resolution_hours": average_hours, "source": "live_database_records"}


@router.get("/departments")
def department_performance(db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    departments = db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.department_name)).all()
    rows = db.scalars(select(ServiceRequest)).all()
    output = []
    for department in departments:
        work = [row for row in rows if row.assigned_department_id == department.id]
        resolved = [row for row in work if row.resolved_at]
        average = sum(_hours(row.created_at, row.resolved_at) for row in resolved) / len(resolved) if resolved else None
        output.append({"department_id": str(department.id), "department_name": department.department_name, "open_requests": sum(row.current_status not in {"RESOLVED", "CLOSED"} for row in work), "resolved_requests": len(resolved), "average_resolution_hours": average})
    return output


@router.get("/export/requests.csv")
def export_requests(db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.scalars(select(ServiceRequest).order_by(ServiceRequest.created_at.desc())).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ticket_number", "status", "priority", "category_id", "assigned_department_id", "created_at", "resolved_at"])
    for row in rows:
        writer.writerow([row.ticket_number, row.current_status, row.priority, row.category_id, row.assigned_department_id, row.created_at.isoformat(), row.resolved_at.isoformat() if row.resolved_at else ""])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=campusintel-requests.csv"})


@router.get("/workflow")
def workflow_performance(db: Session = Depends(get_db), user: User = Depends(require_roles("STAFF", "ADMIN", "SUPER_ADMIN"))):
    rows = db.scalars(_scope_query(db, user)).all()
    request_ids = [row.id for row in rows]
    events = db.scalars(select(RequestEvent).where(RequestEvent.request_id.in_(request_ids)).order_by(RequestEvent.request_id, RequestEvent.event_timestamp)).all() if request_ids else []
    cases: dict[str, list[str]] = defaultdict(list)
    times: dict[str, list] = defaultdict(list)
    for event in events:
        cases[str(event.request_id)].append(event.event_type)
        times[str(event.request_id)].append(event.event_timestamp)
    variants = Counter(tuple(activities) for activities in cases.values())
    waits: list[float] = []
    for timestamps in times.values():
        waits.extend(_hours(start, end) for start, end in zip(timestamps, timestamps[1:]))
    assignments = db.scalars(select(RequestAssignment).where(RequestAssignment.request_id.in_(request_ids))).all() if request_ids else []
    return {
        "open_requests": sum(row.current_status not in {"RESOLVED", "CLOSED"} for row in rows),
        "resolved_requests": len([row for row in rows if row.resolved_at]),
        "average_resolution_hours": (sum(_hours(row.created_at, row.resolved_at) for row in rows if row.resolved_at) / len([row for row in rows if row.resolved_at])) if any(row.resolved_at for row in rows) else None,
        "cases_with_events": len(cases),
        "event_count": len(events),
        "mean_inter_event_hours": sum(waits) / len(waits) if waits else None,
        "handoff_count": max(0, len(assignments) - len({item.request_id for item in assignments})),
        "reassignment_count": sum(max(0, count - 1) for count in Counter(item.request_id for item in assignments).values()),
        "common_variants": [{"activities": list(variant), "cases": count} for variant, count in variants.most_common(10)],
        "source": "request_event_records",
    }


@router.get("/bottlenecks")
def bottlenecks(db: Session = Depends(get_db), user: User = Depends(require_roles("STAFF", "ADMIN", "SUPER_ADMIN"))):
    rows = db.scalars(_scope_query(db, user)).all()
    ids = [row.id for row in rows]
    events = db.scalars(select(RequestEvent).where(RequestEvent.request_id.in_(ids)).order_by(RequestEvent.request_id, RequestEvent.event_timestamp)).all() if ids else []
    by_request: dict[object, list[RequestEvent]] = defaultdict(list)
    for event in events:
        by_request[event.request_id].append(event)
    event_waits: dict[str, list[float]] = defaultdict(list)
    for history in by_request.values():
        for previous, current in zip(history, history[1:]):
            event_waits[current.event_type].append(_hours(previous.event_timestamp, current.event_timestamp))
    longest = sorted(((name, sum(values) / len(values), len(values)) for name, values in event_waits.items()), key=lambda row: row[1], reverse=True)
    department_assignments = db.scalars(select(RequestAssignment).where(RequestAssignment.request_id.in_(ids))).all() if ids else []
    reassignments = Counter(item.request_id for item in department_assignments)
    return {
        "longest_inter_event_gaps": [{"event_type": name, "mean_wait_hours": round(avg, 2), "observations": count} for name, avg, count in longest[:5]],
        "reassigned_request_count": sum(count > 1 for count in reassignments.values()),
        "open_requests": sum(row.current_status not in {"RESOLVED", "CLOSED"} for row in rows),
        "source": "live_workflow_event_records",
        "interpretation": "These signals identify elapsed gaps and repeated assignment records; review case context before changing procedures.",
    }
