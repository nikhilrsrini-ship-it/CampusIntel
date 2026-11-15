from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RequestCreate(BaseModel):
    subject: str = Field(min_length=5, max_length=240)
    description: str = Field(min_length=15, max_length=10000)
    category_id: UUID | None = None


class RequestStatusUpdate(BaseModel):
    status: str = Field(pattern="^(ASSIGNED|IN_PROGRESS|WAITING_FOR_STUDENT|ESCALATED|RESOLVED|CLOSED|REOPENED)$")
    note: str | None = Field(default=None, max_length=2000)


class AssignmentInput(BaseModel):
    department_id: UUID
    staff_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=2000)


class CommentInput(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    visibility: str = Field(default="STUDENT_VISIBLE", pattern="^(STUDENT_VISIBLE|INTERNAL)$")


class FeedbackInput(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback_text: str | None = Field(default=None, max_length=3000)


class RequestView(BaseModel):
    id: UUID
    ticket_number: str
    student_id: UUID
    category_id: UUID | None
    assigned_department_id: UUID | None
    assigned_staff_id: UUID | None
    subject: str
    description: str
    priority: str
    current_status: str
    ml_predicted_category: str | None
    ml_confidence: float | None
    ml_predicted_department: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class EventView(BaseModel):
    event_type: str
    previous_status: str | None
    new_status: str | None
    department_id: UUID | None
    description: str | None
    event_timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


class CommentView(BaseModel):
    id: UUID
    author_id: UUID
    message: str
    visibility: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
