from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user, require_roles
from app.database.session import get_db
from app.models import AuditLog, Department, RequestCategory, User

router = APIRouter(tags=["catalog"])


class DepartmentInput(BaseModel):
    department_code: str = Field(min_length=2, max_length=32)
    department_name: str = Field(min_length=2, max_length=160)
    description: str | None = None
    department_email: str | None = None


class CategoryInput(BaseModel):
    category_name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    default_department_id: UUID | None = None
    priority_weight: int = Field(default=3, ge=1, le=5)


@router.get("/departments")
def list_departments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Department).where(Department.is_active.is_(True)).order_by(Department.department_name)).all()


@router.get("/categories")
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(RequestCategory).where(RequestCategory.is_active.is_(True)).order_by(RequestCategory.category_name)).all()


@router.post("/admin/departments", status_code=201)
def create_department(payload: DepartmentInput, db: Session = Depends(get_db), actor: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    if db.scalar(select(Department.id).where(Department.department_code == payload.department_code)):
        raise HTTPException(status_code=409, detail="Department code already exists")
    row = Department(**payload.model_dump())
    db.add(row)
    db.flush()
    db.add(AuditLog(actor_id=actor.id, action="department.created", resource_type="department", resource_id=str(row.id), metadata_json={}))
    db.commit()
    db.refresh(row)
    return row


@router.post("/admin/categories", status_code=201)
def create_category(payload: CategoryInput, db: Session = Depends(get_db), actor: User = Depends(require_roles("ADMIN", "SUPER_ADMIN"))):
    if db.scalar(select(RequestCategory.id).where(RequestCategory.category_name == payload.category_name)):
        raise HTTPException(status_code=409, detail="Category already exists")
    values = payload.model_dump()
    if values["default_department_id"]:
        if db.get(Department, values["default_department_id"]) is None:
            raise HTTPException(status_code=404, detail="Department not found")
    row = RequestCategory(**values)
    db.add(row)
    db.flush()
    db.add(AuditLog(actor_id=actor.id, action="category.created", resource_type="category", resource_id=str(row.id), metadata_json={}))
    db.commit()
    db.refresh(row)
    return row
