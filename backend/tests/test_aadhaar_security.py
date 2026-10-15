from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def set_user(user_id, role):
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": user_id,
        "role": role,
    }


def test_unauthenticated_user_cannot_access_aadhaar_status():
    response = client.get("/api/workers/aadhaar")
    assert response.status_code in (401, 403)


@pytest.mark.parametrize(
    "role",
    ["customer", "admin"],
)
def test_non_worker_cannot_access_worker_aadhaar_status(role):
    set_user(str(ObjectId()), role)

    response = client.get(
        "/api/workers/aadhaar",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_worker_status_does_not_expose_private_file_id():
    worker_id = str(ObjectId())
    set_user(worker_id, "worker")

    record = {
        "worker_id": worker_id,
        "status": "pending",
        "filename": "aadhaar.pdf",
        "content_type": "application/pdf",
        "file_id": ObjectId(),
        "size_bytes": 1234,
    }

    with patch(
        "app.api.aadhaar.routes._db"
    ) as mock_db:
        mock_db.return_value.__getitem__.return_value.find_one.return_value = (
            record
        )

        response = client.get(
            "/api/workers/aadhaar",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["worker_id"] == worker_id
    assert body["status"] == "pending"
    assert "file_id" not in body
    assert "size_bytes" not in body


@pytest.mark.parametrize(
    "role",
    ["customer", "worker"],
)
def test_non_admin_cannot_access_admin_aadhaar_queue(role):
    set_user(str(ObjectId()), role)

    response = client.get(
        "/api/admin/aadhaar",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    ["customer", "worker"],
)
def test_non_admin_cannot_preview_aadhaar_document(role):
    set_user(str(ObjectId()), role)

    response = client.get(
        f"/api/admin/aadhaar/{ObjectId()}/document",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_non_admin_cannot_decide_aadhaar_verification():
    set_user(str(ObjectId()), "worker")

    response = client.post(
        f"/api/admin/aadhaar/{ObjectId()}/decision",
        json={
            "decision": "verified",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_admin_rejection_requires_reason():
    admin_id = str(ObjectId())
    set_user(admin_id, "admin")

    fake_db = MagicMock()
    fake_db["users"].find_one.return_value = {
        "_id": ObjectId(admin_id),
        "email": "admin@example.com",
        "role": "admin",
        "is_active": True,
    }

    with (
        patch("app.dependencies.get_database", return_value=fake_db),
        patch("app.api.aadhaar.routes.settings.admin_emails",
              "admin@example.com"),
    ):
        response = client.post(
            f"/api/admin/aadhaar/{ObjectId()}/decision",
            json={
                "decision": "rejected",
                "rejection_reason": "   ",
            },
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 422
    assert "reason" in response.json()["detail"].lower()


def test_admin_notification_update_is_scoped_to_current_admin():
    admin_id = str(ObjectId())
    notification_id = ObjectId()
    set_user(admin_id, "admin")

    fake_db = MagicMock()
    fake_db["users"].find_one.return_value = {
        "_id": ObjectId(admin_id),
        "email": "admin@example.com",
        "role": "admin",
        "is_active": True,
    }
    fake_db["admin_notifications"].update_one.return_value.matched_count = 0

    with (
        patch("app.dependencies.get_database", return_value=fake_db),
        patch("app.api.aadhaar.routes._db", return_value=fake_db),
        patch("app.api.aadhaar.routes.settings.admin_emails",
              "admin@example.com"),
    ):
        response = client.patch(
            f"/api/admin/notifications/{notification_id}/read",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 404

    query = fake_db["admin_notifications"].update_one.call_args.args[0]
    assert query["_id"] == notification_id
    assert query["admin_id"] == admin_id


def test_admin_preview_missing_document_returns_404():
    from app.dependencies import require_admin

    admin_id = str(ObjectId())
    worker_id = str(ObjectId())

    app.dependency_overrides[require_admin] = lambda: {
        "user_id": admin_id,
        "role": "admin",
    }

    fake_db = MagicMock()
    fake_db["aadhaar_verifications"].find_one.return_value = None

    with patch(
        "app.api.aadhaar.routes._db",
        return_value=fake_db,
    ):
        response = client.get(
            f"/api/admin/aadhaar/{worker_id}/document",
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Aadhaar document not found."
