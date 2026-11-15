import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models import Department, User


@pytest.fixture
def system():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with TestingSession() as db:
        department = Department(department_code="EXAM", department_name="Examination Department")
        db.add(department)
        db.flush()
        admin = User(full_name="Test Admin", email="admin@example.com", password_hash=hash_password("a-very-long-test-password"), role="ADMIN")
        staff = User(full_name="Test Staff", email="staff@example.com", password_hash=hash_password("a-very-long-test-password"), role="STAFF", department_id=department.id)
        db.add_all([admin, staff])
        db.commit()
        identities = {"department_id": department.id, "admin_id": admin.id, "staff_id": staff.id}

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, identities, TestingSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
