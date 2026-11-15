import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.permissions import get_current_user, require_roles
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models import AuditLog, Department, DepartmentStaff, PasswordResetToken, User
from app.schemas.auth import LoginInput, PasswordResetConfirmInput, PasswordResetRequestInput, RegisterInput, StaffCreateInput, TokenView, UserView
from app.services.password_reset_email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["authentication"])


def _token(user: User) -> TokenView:
    return TokenView(access_token=create_access_token(user.id, user.role, user.auth_token_version), user=UserView.model_validate(user))


@router.post("/register", response_model=TokenView, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterInput, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    if payload.student_identifier and db.scalar(select(User.id).where(User.student_identifier == payload.student_identifier)):
        raise HTTPException(status_code=409, detail="Student identifier is already registered")
    user = User(full_name=payload.full_name.strip(), email=email, password_hash=hash_password(payload.password), role="STUDENT", student_identifier=payload.student_identifier)
    db.add(user)
    db.flush()
    db.add(AuditLog(actor_id=user.id, action="account.registered", resource_type="user", resource_id=str(user.id), metadata_json={}))
    db.commit()
    db.refresh(user)
    return _token(user)


@router.post("/login", response_model=TokenView)
def login(payload: LoginInput, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == str(payload.email).lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
    return _token(user)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequestInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Always return the same response, whether an account exists or not.
    response = {"message": "If an active account matches that email, password reset instructions will be sent."}
    settings = get_settings()
    if not settings.password_reset_email_configured:
        return response

    email = str(payload.email).lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email, User.is_active.is_(True)))
    if user is None:
        return response

    now = datetime.now(timezone.utc)
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.created_at < now - timedelta(days=1)))
    recent_count = db.scalar(
        select(func.count()).select_from(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.created_at >= now - timedelta(hours=1),
        )
    ) or 0
    if recent_count >= 3:
        return response

    # New requests invalidate earlier active links for this account.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        created_at=now,
        expires_at=now + timedelta(minutes=settings.password_reset_expire_minutes),
    )
    db.add(reset_token)
    db.commit()
    background_tasks.add_task(send_password_reset_email, user.email, user.full_name, raw_token)
    return response


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirmInput, db: Session = Depends(get_db)):
    hashed_token = hashlib.sha256(payload.token.encode()).hexdigest()
    reset_token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hashed_token)
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if reset_token is None or reset_token.used_at is not None:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or has expired")
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    user = db.get(User, reset_token.user_id)
    if expires_at <= now or user is None or not user.is_active:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or has expired")

    user.password_hash = hash_password(payload.new_password)
    user.auth_token_version += 1
    user.updated_at = now
    reset_token.used_at = now
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.add(AuditLog(actor_id=None, action="account.password_reset", resource_type="user", resource_id=str(user.id), metadata_json={"method": "email_token"}))
    db.commit()
    return {"message": "Password reset successfully. Sign in with your new password."}


@router.get("/me", response_model=UserView)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/staff", response_model=UserView, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreateInput,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles("ADMIN", "SUPER_ADMIN")),
):
    if payload.role in {"ADMIN", "SUPER_ADMIN"} and actor.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only a super administrator can create administrators")
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    student_identifier = payload.student_identifier if payload.role == "STUDENT" else None
    if student_identifier and db.scalar(select(User.id).where(User.student_identifier == student_identifier)):
        raise HTTPException(status_code=409, detail="Student identifier is already registered")
    if payload.role != "STAFF" and payload.department_id:
        raise HTTPException(status_code=422, detail="Only staff accounts can be assigned to a department")
    department = db.get(Department, payload.department_id) if payload.department_id else None
    if payload.department_id and (department is None or not department.is_active):
        raise HTTPException(status_code=404, detail="Department not found")
    user = User(full_name=payload.full_name.strip(), email=email, password_hash=hash_password(payload.password), role=payload.role, department_id=payload.department_id, student_identifier=student_identifier)
    db.add(user)
    db.flush()
    if payload.role == "STAFF" and payload.department_id:
        db.add(DepartmentStaff(staff_id=user.id, department_id=payload.department_id, is_primary=True))
    db.add(AuditLog(actor_id=actor.id, action="account.created", resource_type="user", resource_id=str(user.id), metadata_json={"role": payload.role}))
    db.commit()
    db.refresh(user)
    return user
