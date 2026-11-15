import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import get_current_user
from app.database.session import get_db
from app.models import AuditLog, RequestAttachment, ServiceRequest, User
from app.routers.requests import _scoped_request

router = APIRouter(prefix="/requests", tags=["attachments"])
ALLOWED = {"application/pdf": (".pdf", b"%PDF"), "image/png": (".png", b"\x89PNG\r\n\x1a\n"), "image/jpeg": (".jpg", b"\xff\xd8\xff")}


@router.post("/{request_id}/attachments", status_code=201)
async def upload_attachment(request_id: UUID, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    mime = file.content_type or ""
    if mime not in ALLOWED:
        raise HTTPException(status_code=415, detail="Only PDF, PNG, and JPEG attachments are supported")
    body = await file.read(get_settings().max_upload_bytes + 1)
    if not body or len(body) > get_settings().max_upload_bytes:
        raise HTTPException(status_code=413, detail="Attachment is empty or exceeds the upload limit")
    extension, signature = ALLOWED[mime]
    if not body.startswith(signature):
        raise HTTPException(status_code=415, detail="File content does not match its declared type")
    original = Path((file.filename or "attachment").replace("\\", "/")).name
    if Path(original).suffix.lower() != extension and not (extension == ".jpg" and Path(original).suffix.lower() == ".jpeg"):
        raise HTTPException(status_code=415, detail="Filename extension does not match the file content type")
    original = re.sub(r"[^A-Za-z0-9._ -]", "_", original)[:255] or "attachment" + extension
    stored = f"{uuid4().hex}{extension}"
    target_dir = Path(get_settings().upload_directory).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / stored).write_bytes(body)
    attachment = RequestAttachment(request_id=row.id, original_filename=original, stored_filename=stored, mime_type=mime, file_size=len(body), uploaded_by=user.id)
    db.add(attachment)
    db.add(AuditLog(actor_id=user.id, action="request.attachment_added", resource_type="service_request", resource_id=str(row.id), metadata_json={"mime_type": mime, "file_size": len(body)}))
    db.commit()
    db.refresh(attachment)
    return {"id": str(attachment.id), "original_filename": attachment.original_filename, "mime_type": attachment.mime_type, "file_size": attachment.file_size}


@router.get("/{request_id}/attachments")
def list_attachments(request_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    records = db.scalars(select(RequestAttachment).where(RequestAttachment.request_id == row.id).order_by(RequestAttachment.created_at)).all()
    return [{"id": str(item.id), "original_filename": item.original_filename, "mime_type": item.mime_type, "file_size": item.file_size, "created_at": item.created_at} for item in records]


@router.get("/{request_id}/attachments/{attachment_id}")
def download_attachment(request_id: UUID, attachment_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _scoped_request(db, user, request_id)
    attachment = db.get(RequestAttachment, attachment_id)
    if attachment is None or attachment.request_id != row.id:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = (Path(get_settings().upload_directory).resolve() / attachment.stored_filename).resolve()
    if path.parent != Path(get_settings().upload_directory).resolve() or not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is unavailable")
    return FileResponse(path, media_type=attachment.mime_type, filename=attachment.original_filename, content_disposition_type="attachment")
