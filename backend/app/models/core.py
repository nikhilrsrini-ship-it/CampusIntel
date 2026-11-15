from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDModel:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Department(UUIDModel, Base):
    __tablename__ = "departments"
    department_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    department_name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    department_email: Mapped[str | None] = mapped_column(String(320))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class User(UUIDModel, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('STUDENT','STAFF','ADMIN','SUPER_ADMIN')", name="ck_users_role"),)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="STUDENT")
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    student_identifier: Mapped[str | None] = mapped_column(String(80), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auth_token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class PasswordResetToken(UUIDModel, Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (Index("ix_password_reset_user_created", "user_id", "created_at"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestCategory(UUIDModel, Base):
    __tablename__ = "request_categories"
    category_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    default_department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    priority_weight: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ServiceRequest(UUIDModel, Base):
    __tablename__ = "service_requests"
    __table_args__ = (
        CheckConstraint("current_status IN ('SUBMITTED','CLASSIFIED','ASSIGNED','IN_PROGRESS','WAITING_FOR_STUDENT','ESCALATED','RESOLVED','CLOSED','REOPENED')", name="ck_service_requests_status"),
        Index("ix_requests_department_status", "assigned_department_id", "current_status"),
    )
    ticket_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("request_categories.id", ondelete="SET NULL"), index=True)
    assigned_department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), index=True)
    assigned_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    subject: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="NORMAL", nullable=False)
    current_status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False, index=True)
    ml_predicted_category: Mapped[str | None] = mapped_column(String(120))
    ml_confidence: Mapped[float | None] = mapped_column(Float)
    ml_predicted_department: Mapped[str | None] = mapped_column(String(160))
    duplicate_group_id: Mapped[UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestAttachment(UUIDModel, Base):
    __tablename__ = "request_attachments"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RequestEvent(UUIDModel, Base):
    __tablename__ = "request_events"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    department_id: Mapped[UUID | None] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"))
    description: Mapped[str | None] = mapped_column(Text)
    event_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class RequestAssignment(UUIDModel, Base):
    __tablename__ = "request_assignments"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), index=True, nullable=False)
    assigned_staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    assigned_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RequestComment(UUIDModel, Base):
    __tablename__ = "request_comments"
    __table_args__ = (CheckConstraint("visibility IN ('STUDENT_VISIBLE','INTERNAL')", name="ck_request_comments_visibility"),)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(24), default="STUDENT_VISIBLE", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class DepartmentStaff(UUIDModel, Base):
    __tablename__ = "departments_staff"
    __table_args__ = (UniqueConstraint("staff_id", "department_id", name="uq_staff_department"),)
    staff_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    department_id: Mapped[UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), index=True, nullable=False)
    designation: Mapped[str | None] = mapped_column(String(120))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MLPrediction(UUIDModel, Base):
    __tablename__ = "ml_predictions"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    predicted_category: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_department: Mapped[str | None] = mapped_column(String(160))
    prediction_explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ResolutionPrediction(UUIDModel, Base):
    __tablename__ = "resolution_predictions"
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    predicted_resolution_hours: Mapped[float] = mapped_column(Float, nullable=False)
    prediction_confidence: Mapped[float | None] = mapped_column(Float)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class StudentFeedback(UUIDModel, Base):
    __tablename__ = "student_feedback"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_student_feedback_rating"), UniqueConstraint("request_id", name="uq_feedback_request"))
    request_id: Mapped[UUID] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Notification(UUIDModel, Base):
    __tablename__ = "notifications"
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    request_id: Mapped[UUID | None] = mapped_column(ForeignKey("service_requests.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(UUIDModel, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class MLModelExperiment(UUIDModel, Base):
    __tablename__ = "model_experiments"
    experiment_name: Mapped[str] = mapped_column(String(180), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(80), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(180), nullable=False)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
