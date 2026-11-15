"""Create the first super administrator from environment credentials."""
import os

from sqlalchemy import func, select

from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models import User


def main() -> None:
    email = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
    name = os.environ.get("INITIAL_ADMIN_NAME", "Institution Administrator").strip()
    if not email or len(password) < 16:
        raise SystemExit("Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD (at least 16 characters).")
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(func.lower(User.email) == email))
        if existing:
            raise SystemExit("An account with INITIAL_ADMIN_EMAIL already exists; no changes made.")
        db.add(User(full_name=name, email=email, password_hash=hash_password(password), role="SUPER_ADMIN"))
        db.commit()
    print("Initial super administrator created.")


if __name__ == "__main__":
    main()
