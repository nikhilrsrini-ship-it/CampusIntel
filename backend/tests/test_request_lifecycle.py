from app.core.config import get_settings
from app.core.security import create_access_token
from app.models import RequestCategory


def bearer(user_id, role):
    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}


def test_auth_request_assignment_resolution_reopen_and_visibility(system):
    client, identities, session_factory = system
    with session_factory() as db:
        category = RequestCategory(category_name="Examination", default_department_id=identities["department_id"])
        db.add(category)
        db.commit()
        category_id = category.id

    created = client.post("/auth/register", json={
        "full_name": "Student One", "email": "student@example.com",
        "password": "a-secure-test-password", "student_identifier": "S-101",
    })
    assert created.status_code == 201
    student = created.json()["user"]
    student_headers = {"Authorization": f"Bearer {created.json()['access_token']}"}

    response = client.post("/requests", headers=student_headers, json={
        "subject": "Assessment marks are missing", "description": "My internal assessment marks are not displayed in the student portal.", "category_id": str(category_id),
    })
    assert response.status_code == 201
    request_data = response.json()
    request_id = request_data["id"]
    assert request_data["current_status"] == "SUBMITTED"

    admin_headers = bearer(identities["admin_id"], "ADMIN")
    assignment = client.post(f"/requests/{request_id}/assign", headers=admin_headers, json={
        "department_id": str(identities["department_id"]), "staff_id": str(identities["staff_id"]), "reason": "Examination request",
    })
    assert assignment.status_code == 200
    assert assignment.json()["current_status"] == "ASSIGNED"

    staff_headers = bearer(identities["staff_id"], "STAFF")
    note = client.post(f"/requests/{request_id}/comments", headers=staff_headers, json={"message": "Checked the record internally.", "visibility": "INTERNAL"})
    assert note.status_code == 201
    assert client.get(f"/requests/{request_id}/comments", headers=student_headers).json() == []

    for target in ("IN_PROGRESS", "RESOLVED"):
        result = client.post(f"/requests/{request_id}/status", headers=staff_headers, json={"status": target})
        assert result.status_code == 200
        assert result.json()["current_status"] == target

    feedback = client.post(f"/requests/{request_id}/feedback", headers=student_headers, json={"rating": 5, "feedback_text": "Resolved, thank you."})
    assert feedback.status_code == 201
    reopened = client.post(f"/requests/{request_id}/status", headers=student_headers, json={"status": "REOPENED"})
    assert reopened.status_code == 200
    assert reopened.json()["current_status"] == "REOPENED"

    events = client.get(f"/requests/{request_id}/events", headers=student_headers)
    assert events.status_code == 200
    assert [event["new_status"] for event in events.json() if event["new_status"]] == ["SUBMITTED", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "REOPENED"]
    assert client.get("/notifications", headers=student_headers).status_code == 200


def test_student_data_is_scoped_and_transition_validation(system):
    client, _, session_factory = system
    first = client.post("/auth/register", json={"full_name": "First Student", "email": "first@example.com", "password": "another-secure-password"}).json()
    second = client.post("/auth/register", json={"full_name": "Second Student", "email": "second@example.com", "password": "another-secure-password"}).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    created = client.post("/requests", headers=first_headers, json={"subject": "Portal login issue", "description": "The college portal rejects my login credentials today."})
    assert created.status_code == 201
    request_id = created.json()["id"]
    assert client.get(f"/requests/{request_id}", headers=second_headers).status_code == 404
    assert client.get("/requests", headers=second_headers).json() == []
    invalid = client.post(f"/requests/{request_id}/status", headers=first_headers, json={"status": "CLOSED"})
    assert invalid.status_code == 403
    assert client.get("/requests").status_code == 401


def test_admin_catalog_analytics_and_staff_provisioning(system):
    client, identities, _ = system
    admin_headers = bearer(identities["admin_id"], "ADMIN")
    escalated_role = client.post("/auth/staff", headers=admin_headers, json={"full_name": "Admin Two", "email": "admin-two@example.com", "password": "strong-initial-password", "role": "ADMIN"})
    assert escalated_role.status_code == 403
    created = client.post("/auth/staff", headers=admin_headers, json={"full_name": "Staff Two", "email": "staff-two@example.com", "password": "strong-initial-password", "role": "STAFF", "department_id": str(identities["department_id"])})
    assert created.status_code == 201
    assert created.json()["role"] == "STAFF"

    student = client.post("/auth/register", json={"full_name": "Analytics Student", "email": "analytics-student@example.com", "password": "strong-initial-password"}).json()
    student_headers = {"Authorization": f"Bearer {student['access_token']}"}
    request = client.post("/requests", headers=student_headers, json={"subject": "Need an enrollment letter", "description": "Please provide an enrollment letter for my travel application."})
    assert request.status_code == 201
    summary = client.get("/analytics/summary", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["total_requests"] == 1
    assert summary.json()["source"] == "live_database_records"
    assert client.get("/analytics/workflow", headers=admin_headers).json()["event_count"] == 1


def test_attachment_validation_and_access_scope(system, tmp_path, monkeypatch):
    client, _, _ = system
    monkeypatch.setattr(get_settings(), "upload_directory", str(tmp_path))
    student = client.post("/auth/register", json={"full_name": "File Owner", "email": "file-owner@example.com", "password": "strong-initial-password"}).json()
    other = client.post("/auth/register", json={"full_name": "Other Student", "email": "other-student@example.com", "password": "strong-initial-password"}).json()
    headers = {"Authorization": f"Bearer {student['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    created = client.post("/requests", headers=headers, json={"subject": "Fee receipt question", "description": "My payment receipt is missing from the online account."})
    request_id = created.json()["id"]
    uploaded = client.post(f"/requests/{request_id}/attachments", headers=headers, files={"file": ("receipt.pdf", b"%PDF-1.7\ncontents", "application/pdf")})
    assert uploaded.status_code == 201
    attachment_id = uploaded.json()["id"]
    assert client.get(f"/requests/{request_id}/attachments/{attachment_id}", headers=headers).status_code == 200
    assert client.get(f"/requests/{request_id}/attachments", headers=other_headers).status_code == 404
    rejected = client.post(f"/requests/{request_id}/attachments", headers=headers, files={"file": ("bad.pdf", b"not a pdf", "application/pdf")})
    assert rejected.status_code == 415


def test_model_unavailable_is_reported_without_fabricated_prediction(system, tmp_path, monkeypatch):
    from app.core.config import get_settings
    client, _, _ = system
    monkeypatch.setattr(get_settings(), "classification_model_path", str(tmp_path / "missing-model.joblib"))
    student = client.post("/auth/register", json={"full_name": "Model Tester", "email": "model-tester@example.com", "password": "strong-initial-password"}).json()
    headers = {"Authorization": f"Bearer {student['access_token']}"}
    result = client.post("/ml/classify", headers=headers, json={"subject": "Assessment score", "description": "My internal assessment score is missing from the portal."})
    assert result.status_code == 200
    assert result.json()["available"] is False
    assert result.json()["predicted_category"] is None
    assert "No trained classifier" in result.json()["explanation"]


def test_duplicate_suggestions_respect_request_visibility(system):
    client, identities, _ = system
    first = client.post("/auth/register", json={"full_name": "First Owner", "email": "first-owner@example.com", "password": "strong-initial-password"}).json()
    second = client.post("/auth/register", json={"full_name": "Second Owner", "email": "second-owner@example.com", "password": "strong-initial-password"}).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    payload = {"subject": "Student portal fee receipt is missing", "description": "The payment receipt is missing from the student portal and I need help."}
    first_request = client.post("/requests", headers=first_headers, json=payload).json()
    second_request = client.post("/requests", headers=second_headers, json=payload).json()
    private_result = client.get(f"/ml/requests/{first_request['id']}/duplicates", headers=first_headers)
    assert private_result.status_code == 200
    assert all(item["request_id"] != second_request["id"] for item in private_result.json()["candidates"])
    admin_result = client.get(f"/ml/requests/{first_request['id']}/duplicates", headers=bearer(identities["admin_id"], "ADMIN"))
    assert any(item["request_id"] == second_request["id"] for item in admin_result.json()["candidates"])
