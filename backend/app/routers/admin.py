from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_roles
from app.database.session import get_db
from app.models import AuditLog, User

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/users")
def list_users(limit: int = Query(default=100, ge=1, le=250), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), _: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.scalars(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)).all()
    return [{"id": str(row.id), "full_name": row.full_name, "email": row.email, "role": row.role, "department_id": str(row.department_id) if row.department_id else None, "is_active": row.is_active, "created_at": row.created_at} for row in rows]


@router.patch("/users/{user_id}/active")
def set_user_active(user_id: UUID, active: bool, db: Session = Depends(get_db), actor: User = Depends(require_roles("SUPER_ADMIN"))):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == actor.id and not active:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own super administrator account")
    target.is_active = active
    db.add(AuditLog(actor_id=actor.id, action="account.activation_changed", resource_type="user", resource_id=str(target.id), metadata_json={"is_active": active}))
    db.commit()
    return {"id": str(target.id), "is_active": target.is_active}


@router.get("/audit-logs")
def list_audit_logs(limit: int = Query(default=100, ge=1, le=250), offset: int = Query(default=0, ge=0), db: Session = Depends(get_db), _: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
    return [{"id": str(row.id), "actor_id": str(row.actor_id) if row.actor_id else None, "action": row.action, "resource_type": row.resource_type, "resource_id": row.resource_id, "metadata": row.metadata_json, "created_at": row.created_at} for row in rows]
