from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user
from app.database.session import get_db
from app.models import Notification, User

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationView(BaseModel):
    id: UUID
    request_id: UUID | None
    title: str
    message: str
    is_read: bool
    created_at: object
    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[NotificationView])
def list_notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Notification).where(Notification.recipient_id == user.id).order_by(Notification.created_at.desc()).limit(100)).all()


@router.post("/{notification_id}/read", response_model=NotificationView)
def mark_read(notification_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(Notification, notification_id)
    if row is None or row.recipient_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.is_read = True
    db.commit()
    db.refresh(row)
    return row
