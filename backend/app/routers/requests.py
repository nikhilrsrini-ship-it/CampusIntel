from datetime import timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user, require_roles
from app.database.session import get_db
from app.models import (
    AuditLog, Department, DepartmentStaff, MLPrediction, Notification, RequestAssignment,
    RequestCategory, RequestComment, RequestEvent, ServiceRequest, StudentFeedback, User,
)
from app.ml.classification import classify
from app.models.core import utcnow
from app.schemas.requests import (
    AssignmentInput, CommentInput, CommentView, EventView, FeedbackInput,
    RequestCreate, RequestStatusUpdate, RequestView,
)

router = APIRouter(prefix="/requests", tags=["requests"])
STATUSES = {"SUBMITTED", "CLASSIFIED", "ASSIGNED", "IN_PROGRESS", "WAITING_FOR_STUDENT", "ESCALATED", "RESOLVED", "CLOSED", "REOPENED"}
STAFF_TRANSITIONS = {
    "SUBMITTED": {"ASSIGNED", "IN_PROGRESS", "ESCALATED"},
    "CLASSIFIED": {"ASSIGNED", "IN_PROGRESS", "ESCALATED"},
    "ASSIGNED": {"IN_PROGRESS", "WAITING_FOR_STUDENT", "ESCALATED", "RESOLVED"},
    "IN_PROGRESS": {"WAITING_FOR_STUDENT", "ESCALATED", "RESOLVED"},
    "WAITING_FOR_STUDENT": {"IN_PROGRESS", "ESCALATED", "RESOLVED"},
    "ESCALATED": {"ASSIGNED", "IN_PROGRESS", "RESOLVED"},
    "RESOLVED": {"CLOSED", "IN_PROGRESS"},
    "CLOSED": set(),
    "REOPENED": {"ASSIGNED", "IN_PROGRESS", "ESCALATED"},
}


def _scoped_request(db: Session, user: User, request_id: UUID) -> ServiceRequest:
    row = db.get(ServiceRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    allowed = user.role in {"ADMIN", "SUPER_ADMIN"}
    if user.role == "STUDENT":
        allowed = row.student_id == user.id
    if user.role == "STAFF":
        allowed = row.assigned_staff_id == user.id or (user.department_id is not None and row.assigned_department_id == user.department_id)
        if not allowed:
            allowed = db.scalar(select(DepartmentStaff.id).where(DepartmentStaff.staff_id == user.id, DepartmentStaff.department_id == row.assigned_department_id)) is not None
    if not allowed:
        raise HTTPException(status_code=404, detail="Request not found")
    return row


def _notify(db: Session, recipient_id: UUID, request_id: UUID, title: str, message: str) -> None:
    db.add(Notification(recipient_id=recipient_id, request_id=request_id, title=title, message=message))


@router.post("", response_model=RequestView, status_code=status.HTTP_201_CREATED)
def create_request(payload: RequestCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("STUDENT"))):
    category = db.get(RequestCategory, payload.category_id) if payload.category_id else None
    if payload.category_id and (category is None or not category.is_active):
        raise HTTPException(status_code=404, detail="Request category not found")
    ticket = f"CI-{utcnow():%y%m%d}-{uuid4().hex[:6].upper()}"
    row = ServiceRequest(
        ticket_number=ticket,
        student_id=user.id,
        category_id=category.id if category else None,
        subject=payload.subject.strip(),
        description=payload.description.strip(),
        current_status="SUBMITTED",
    )
    prediction = classify(f"{payload.subject}\n{payload.description}")
    if prediction["available"]:
        row.ml_predicted_category = prediction["predicted_category"]
        row.ml_confidence = prediction["confidence"]
        row.ml_predicted_department = prediction["department"]
    db.add(row)
    db.flush()
    db.add(RequestEvent(request_id=row.id, actor_id=user.id, event_type="REQUEST_SUBMITTED", new_status="SUBMITTED", department_id=row.assigned_department_id, description="Request submitted"))
    if prediction["available"]:
        db.add(MLPrediction(request_id=row.id, model_name=prediction["model_name"], model_version=prediction["model_version"], predicted_category=prediction["predicted_category"], confidence_score=prediction["confidence"], predicted_department=prediction["department"], prediction_explanation={"learned_terms": prediction["explanation"]["learned_terms"], "dataset_type": prediction["dataset_type"], "disclaimer": "Unverified model suggestion; no automatic decision is made."}))
    db.add(AuditLog(actor_id=user.id, action="request.created", resource_type="service_request", resource_id=str(row.id), metadata_json={"ticket_number": ticket}))
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[RequestView])
def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(ServiceRequest)
    if user.role == "STUDENT":
        query = query.where(ServiceRequest.student_id == user.id)
    elif user.role == "STAFF":
        membership_departments = select(DepartmentStaff.department_id).where(DepartmentStaff.staff_id == user.id)
        query = query.where((ServiceRequest.assigned_staff_id == user.id) | ServiceRequest.assigned_department_id.in_(membership_departments))
    if status_filter:
        if status_filter not in STATUSES:
            raise HTTPException(status_code=422, detail="Unknown request status")
        query = query.where(ServiceRequest.current_status == status_filter)
    return db.scalars(query.order_by(ServiceRequest.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/{request_id}", response_model=RequestView)
def get_request(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _scoped_request(db, user, request_id)


@router.post("/{request_id}/assign", response_model=RequestView)
def assign_request(request_id: UUID, payload: AssignmentInput, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    row = _scoped_request(db, user, request_id)
    department = db.get(Department, payload.department_id)
    if department is None or not department.is_active:
        raise HTTPException(status_code=404, detail="Department not found")
    staff = db.get(User, payload.staff_id) if payload.staff_id else None
    membership = db.scalar(select(DepartmentStaff.id).where(DepartmentStaff.staff_id == staff.id, DepartmentStaff.department_id == department.id)) if staff else None
    if staff and (staff.role != "STAFF" or (staff.department_id != department.id and membership is None) or not staff.is_active):
        raise HTTPException(status_code=422, detail="Staff member must be active and belong to the selected department")
    previous_department = row.assigned_department_id
    if previous_department:
        active = db.scalar(select(RequestAssignment).where(RequestAssignment.request_id == row.id, RequestAssignment.unassigned_at.is_(None)).order_by(RequestAssignment.assigned_at.desc()))
        if active:
            active.unassigned_at = utcnow()
    row.assigned_department_id = department.id
    row.assigned_staff_id = staff.id if staff else None
    if row.current_status in {"SUBMITTED", "CLASSIFIED", "REOPENED"}:
        old = row.current_status
        row.current_status = "ASSIGNED"
        db.add(RequestEvent(request_id=row.id, actor_id=user.id, event_type="STATUS_CHANGED", previous_status=old, new_status="ASSIGNED", department_id=department.id, description="Assigned to department"))
    db.add(RequestAssignment(request_id=row.id, department_id=department.id, assigned_staff_id=staff.id if staff else None, assigned_by=user.id, assignment_reason=payload.reason))
    db.add(RequestEvent(request_id=row.id, actor_id=user.id, event_type="REQUEST_ASSIGNED", department_id=department.id, description="Assigned to " + department.department_name))
    db.add(AuditLog(actor_id=user.id, action="request.assigned", resource_type="service_request", resource_id=str(row.id), metadata_json={"department_id": str(department.id)}))
    if staff:
        _notify(db, staff.id, row.id, "Request assigned", f"Ticket {row.ticket_number} was assigned to you.")
    _notify(db, row.student_id, row.id, "Request routed", f"Ticket {row.ticket_number} was routed to {department.department_name}.")
    db.commit()
    db.refresh(row)
    return row


@router.post("/{request_id}/status", response_model=RequestView)
def update_status(request_id: UUID, payload: RequestStatusUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    target = payload.status
    if user.role == "STUDENT":
        if target != "REOPENED" or row.current_status not in {"RESOLVED", "CLOSED"}:
            raise HTTPException(status_code=403, detail="Students may only reopen resolved requests")
        resolved_at = row.resolved_at
        if resolved_at and resolved_at.tzinfo is None:
            resolved_at = resolved_at.replace(tzinfo=timezone.utc)
        if resolved_at and utcnow() - resolved_at > timedelta(days=30):
            raise HTTPException(status_code=409, detail="The request can no longer be reopened")
    elif user.role == "STAFF":
        if target not in STAFF_TRANSITIONS[row.current_status]:
            raise HTTPException(status_code=409, detail=f"Transition {row.current_status} → {target} is not allowed")
    else:
        if target not in STAFF_TRANSITIONS[row.current_status]:
            raise HTTPException(status_code=409, detail=f"Transition {row.current_status} → {target} is not allowed")
    previous = row.current_status
    row.current_status = target
    if target == "RESOLVED":
        row.resolved_at = utcnow()
    if target == "CLOSED":
        row.closed_at = utcnow()
    if target == "REOPENED":
        row.resolved_at = None
        row.closed_at = None
    db.add(RequestEvent(request_id=row.id, actor_id=user.id, event_type="STATUS_CHANGED", previous_status=previous, new_status=target, department_id=row.assigned_department_id, description=payload.note or f"Status changed to {target}"))
    db.add(AuditLog(actor_id=user.id, action="request.status_changed", resource_type="service_request", resource_id=str(row.id), metadata_json={"previous_status": previous, "new_status": target}))
    _notify(db, row.student_id, row.id, "Request status updated", f"Ticket {row.ticket_number} is now {target.replace('_', ' ').lower()}.")
    db.commit()
    db.refresh(row)
    return row


@router.get("/{request_id}/events", response_model=list[EventView])
def request_events(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    return db.scalars(select(RequestEvent).where(RequestEvent.request_id == row.id).order_by(RequestEvent.event_timestamp)).all()


@router.get("/{request_id}/predictions")
def request_predictions(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    predictions = db.scalars(select(MLPrediction).where(MLPrediction.request_id == row.id).order_by(MLPrediction.created_at.desc())).all()
    return [{"model_name": item.model_name, "model_version": item.model_version, "predicted_category": item.predicted_category, "confidence_score": item.confidence_score, "predicted_department": item.predicted_department, "explanation": item.prediction_explanation, "created_at": item.created_at} for item in predictions]


@router.get("/{request_id}/comments", response_model=list[CommentView])
def list_comments(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    query = select(RequestComment).where(RequestComment.request_id == row.id)
    if user.role == "STUDENT":
        query = query.where(RequestComment.visibility == "STUDENT_VISIBLE")
    return db.scalars(query.order_by(RequestComment.created_at)).all()


@router.post("/{request_id}/comments", response_model=CommentView, status_code=201)
def add_comment(request_id: UUID, payload: CommentInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    if payload.visibility == "INTERNAL" and user.role not in {"STAFF", "ADMIN", "SUPER_ADMIN"}:
        raise HTTPException(status_code=403, detail="Only staff can add internal notes")
    comment = RequestComment(request_id=row.id, author_id=user.id, message=payload.message.strip(), visibility=payload.visibility)
    db.add(comment)
    db.add(RequestEvent(request_id=row.id, actor_id=user.id, event_type="COMMENT_ADDED", department_id=row.assigned_department_id, description="Internal note added" if payload.visibility == "INTERNAL" else "Student-visible comment added"))
    db.add(AuditLog(actor_id=user.id, action="request.comment_added", resource_type="service_request", resource_id=str(row.id), metadata_json={"visibility": payload.visibility}))
    if user.role != "STUDENT" and payload.visibility == "STUDENT_VISIBLE":
        _notify(db, row.student_id, row.id, "New request update", f"A response was added to ticket {row.ticket_number}.")
    if user.role == "STUDENT":
        recipients = set()
        if row.assigned_staff_id:
            recipients.add(row.assigned_staff_id)
        if row.assigned_department_id:
            recipients.update(db.scalars(select(DepartmentStaff.staff_id).where(DepartmentStaff.department_id == row.assigned_department_id)).all())
        for recipient_id in recipients:
            _notify(db, recipient_id, row.id, "Student added information", f"New information was added to ticket {row.ticket_number}.")
    db.commit()
    db.refresh(comment)
    return comment


@router.post("/{request_id}/feedback", status_code=201)
def feedback(request_id: UUID, payload: FeedbackInput, db: Session = Depends(get_db), user: User = Depends(require_roles("STUDENT"))):
    row = _scoped_request(db, user, request_id)
    if row.current_status not in {"RESOLVED", "CLOSED"}:
        raise HTTPException(status_code=409, detail="Feedback is available after resolution")
    if db.scalar(select(StudentFeedback.id).where(StudentFeedback.request_id == row.id)):
        raise HTTPException(status_code=409, detail="Feedback has already been submitted")
    feedback_row = StudentFeedback(request_id=row.id, student_id=user.id, rating=payload.rating, feedback_text=payload.feedback_text)
    db.add(feedback_row)
    db.add(AuditLog(actor_id=user.id, action="request.feedback_added", resource_type="service_request", resource_id=str(row.id), metadata_json={"rating": payload.rating}))
    db.commit()
    return {"saved": True}


@router.get("/{request_id}/feedback")
def get_feedback(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_roles("STUDENT"))):
    row = _scoped_request(db, user, request_id)
    feedback_row = db.scalar(select(StudentFeedback).where(StudentFeedback.request_id == row.id, StudentFeedback.student_id == user.id))
    if feedback_row is None:
        return {"saved": False}
    return {"saved": True, "rating": feedback_row.rating, "feedback_text": feedback_row.feedback_text, "created_at": feedback_row.created_at}
