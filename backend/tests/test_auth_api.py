from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_current_user


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Welcome to SOLVIX API"


def test_customer_can_access_customer_endpoint():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-customer-id",
        "role": "customer",
    }

    response = client.get(
        "/api/auth/customer-test",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Customer access granted"


def test_worker_cannot_access_customer_endpoint():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-worker-id",
        "role": "worker",
    }

    response = client.get(
        "/api/auth/customer-test",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_customer_cannot_access_worker_endpoint():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-customer-id",
        "role": "customer",
    }

    response = client.get(
        "/api/auth/worker-test",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 403


def test_worker_can_access_worker_endpoint():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-worker-id",
        "role": "worker",
    }

    response = client.get(
        "/api/auth/worker-test",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Worker access granted"


def test_me_requires_authentication():
    response = client.get("/api/auth/me")

    assert response.status_code in (401, 403)


def test_register_creates_user_without_real_database():
    fake_user = {
        "id": "test-user-id",
        "name": "Test Customer",
        "email": "test@example.com",
        "phone": None,
        "role": "customer",
        "is_active": True,
        "is_verified": False,
    }

    with patch(
        "app.api.auth.routes.AuthService"
    ) as mock_service_class:
        mock_service = mock_service_class.return_value
        mock_service.create_user.return_value = fake_user

        response = client.post(
            "/api/auth/register",
            json={
                "name": "Test Customer",
                "email": "test@example.com",
                "password": "TestPassword@123",
                "role": "customer",
            },
        )

    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    mock_service.create_user.assert_called_once()


def test_register_duplicate_email_returns_400():
    with patch(
        "app.api.auth.routes.AuthService"
    ) as mock_service_class:
        mock_service_class.return_value.create_user.side_effect = (
            ValueError("Email is already registered")
        )

        response = client.post(
            "/api/auth/register",
            json={
                "name": "Test Customer",
                "email": "test@example.com",
                "password": "TestPassword@123",
                "role": "customer",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already registered"


def test_login_invalid_credentials_returns_401():
    with patch(
        "app.api.auth.routes.AuthService"
    ) as mock_service_class:
        mock_service_class.return_value.authenticate_user.return_value = None

        response = client.post(
            "/api/auth/login",
            json={
                "email": "missing@example.com",
                "password": "WrongPassword@123",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
