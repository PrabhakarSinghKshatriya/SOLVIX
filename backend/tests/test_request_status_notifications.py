from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user


client = TestClient(app)

REQUEST_ID = "test-request-123"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def setup_status_request():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "customer-test-123",
        "role": "customer",
    }

    request_service = MagicMock()
    request_service.transition_status.return_value = {
        "id": REQUEST_ID,
        "customer_id": "customer-test-123",
        "assigned_worker_id": "worker-test-456",
        "status": "confirmed",
        "_status_changed": True,
        "_previous_status": "accepted",
    }

    return request_service


def test_status_change_sends_admin_and_recipient_notifications():
    request_service = setup_status_request()

    with (
        patch(
            "app.api.requests.routes.ServiceRequestService",
            return_value=request_service,
        ),
        patch(
            "app.services.admin_notification_service.AdminNotificationService.notify"
        ) as admin_notify,
        patch(
            "app.api.requests.routes._safe_notify"
        ) as recipient_notify,
    ):
        response = client.patch(
            f"/api/requests/{REQUEST_ID}/status",
            json={"status": "confirmed"},
        )

    assert response.status_code == 200

    admin_notify.assert_called_once()
    recipient_notify.assert_called_once()

    assert response.json()["request"]["status"] == "confirmed"
    assert "_status_changed" not in response.json()["request"]
    assert "_previous_status" not in response.json()["request"]


def test_reselecting_same_status_sends_no_notifications():
    request_service = setup_status_request()
    request_service.transition_status.return_value = {
        "id": REQUEST_ID,
        "customer_id": "customer-test-123",
        "assigned_worker_id": "worker-test-456",
        "status": "confirmed",
        "_status_changed": False,
        "_previous_status": "confirmed",
    }

    with (
        patch(
            "app.api.requests.routes.ServiceRequestService",
            return_value=request_service,
        ),
        patch(
            "app.services.admin_notification_service.AdminNotificationService.notify"
        ) as admin_notify,
        patch(
            "app.api.requests.routes._safe_notify"
        ) as recipient_notify,
    ):
        response = client.patch(
            f"/api/requests/{REQUEST_ID}/status",
            json={"status": "confirmed"},
        )

    assert response.status_code == 200
    admin_notify.assert_not_called()
    recipient_notify.assert_not_called()

    assert response.json()["request"]["status"] == "confirmed"
    assert "_status_changed" not in response.json()["request"]
    assert "_previous_status" not in response.json()["request"]
