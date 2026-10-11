import hashlib
import hmac
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.subscriptions import routes


@pytest.fixture
def payment_setup(monkeypatch):
    """Provide isolated mocked payment data without using a real database."""

    monkeypatch.setattr(
        routes.settings, "razorpay_key_id", "rzp_test_example"
    )
    monkeypatch.setattr(
        routes.settings, "razorpay_key_secret", "test_secret"
    )
    monkeypatch.setattr(
        routes.settings, "razorpay_webhook_secret", "webhook_test_secret"
    )

    payment = {
        "worker_id": "worker-test-1",
        "plan": "monthly",
        "amount": 15000,
        "currency": "INR",
        "razorpay_order_id": "order_test_123",
        "status": "created",
    }

    fake_payments = MagicMock()
    fake_payments.find_one.return_value = payment

    fake_events = MagicMock()
    fake_events.update_one.return_value.matched_count = 1

    fake_collections = {
        "payments": fake_payments,
        "subscriptions": MagicMock(),
        "payment_webhook_events": fake_events,
    }

    fake_db = MagicMock()
    fake_db.__getitem__.side_effect = lambda name: fake_collections.setdefault(
        name, MagicMock()
    )

    # Mock MongoDB sessions and execute the transaction callback.
    fake_session = MagicMock()

    def run_transaction(callback, *args, **kwargs):
        return callback(fake_session, *args, **kwargs)

    fake_session.with_transaction.side_effect = run_transaction
    fake_db.client.start_session.return_value.__enter__.return_value = fake_session

    monkeypatch.setattr(routes, "db", fake_db)

    signature = hmac.new(
        b"test_secret",
        b"order_test_123|pay_test_123",
        hashlib.sha256,
    ).hexdigest()

    request_data = routes.VerifyPaymentRequest(
        razorpay_order_id="order_test_123",
        razorpay_payment_id="pay_test_123",
        razorpay_signature=signature,
    )

    return {
        "payment": payment,
        "payments": fake_payments,
        "db": fake_db,
        "data": request_data,
        "worker": {"user_id": "worker-test-1", "role": "worker"},
    }


def test_monthly_and_yearly_plan_prices():
    monthly = routes._plan_details("monthly")
    yearly = routes._plan_details("yearly")

    assert monthly["amount"] == 15000
    assert monthly["duration_days"] == 30

    assert yearly["amount"] == 150000
    assert yearly["duration_days"] == 365


def test_invalid_subscription_plan_is_rejected():
    with pytest.raises(HTTPException) as exc:
        routes._plan_details("invalid")

    assert exc.value.status_code == 400


def test_invalid_payment_signature_is_rejected(payment_setup):
    data = payment_setup["data"].model_copy(
        update={"razorpay_signature": "invalid_signature"}
    )

    with pytest.raises(HTTPException) as exc:
        routes.verify_payment(data, payment_setup["worker"])

    assert exc.value.status_code == 400
    assert "signature" in exc.value.detail.lower()


def test_uncaptured_payment_is_rejected(payment_setup):
    data = payment_setup["data"]

    provider_payment = {
        "id": data.razorpay_payment_id,
        "order_id": data.razorpay_order_id,
        "status": "authorized",
        "captured": False,
        "amount": 15000,
        "currency": "INR",
    }

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = provider_payment

    with patch.object(routes.requests, "get", return_value=response):
        with pytest.raises(HTTPException) as exc:
            routes.verify_payment(data, payment_setup["worker"])

    assert exc.value.status_code == 400
    payment_setup["db"]["subscriptions"].update_one.assert_not_called()


def test_amount_mismatch_is_rejected(payment_setup):
    data = payment_setup["data"]

    provider_payment = {
        "id": data.razorpay_payment_id,
        "order_id": data.razorpay_order_id,
        "status": "captured",
        "captured": True,
        "amount": 100,
        "currency": "INR",
    }

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = provider_payment

    with patch.object(routes.requests, "get", return_value=response):
        with pytest.raises(HTTPException) as exc:
            routes.verify_payment(data, payment_setup["worker"])

    assert exc.value.status_code == 400
    payment_setup["db"]["subscriptions"].update_one.assert_not_called()


def test_currency_mismatch_is_rejected(payment_setup):
    data = payment_setup["data"]

    provider_payment = {
        "id": data.razorpay_payment_id,
        "order_id": data.razorpay_order_id,
        "status": "captured",
        "captured": True,
        "amount": 15000,
        "currency": "USD",
    }

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = provider_payment

    with patch.object(routes.requests, "get", return_value=response):
        with pytest.raises(HTTPException) as exc:
            routes.verify_payment(data, payment_setup["worker"])

    assert exc.value.status_code == 400
    payment_setup["db"]["subscriptions"].update_one.assert_not_called()


def test_provider_unavailable_returns_safe_error(payment_setup):
    data = payment_setup["data"]

    with patch.object(
        routes.requests,
        "get",
        side_effect=routes.requests.Timeout("Test timeout"),
    ):
        with pytest.raises(HTTPException) as exc:
            routes.verify_payment(data, payment_setup["worker"])

    assert exc.value.status_code == 502
    assert "verify payment" in exc.value.detail.lower()


def test_payment_order_must_belong_to_current_worker(payment_setup):
    payment_setup["payments"].find_one.return_value = None

    with pytest.raises(HTTPException) as exc:
        routes.verify_payment(
            payment_setup["data"],
            {"user_id": "different-worker", "role": "worker"},
        )

    assert exc.value.status_code == 404


# ---------------- Webhook security tests ----------------

import asyncio
import json
from starlette.requests import Request
from pymongo.errors import DuplicateKeyError


def make_webhook_request(body, headers=None):
    """Build a Starlette request without starting a server."""
    body_bytes = json.dumps(body).encode("utf-8")
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]

    delivered = False

    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {
                "type": "http.request",
                "body": body_bytes,
                "more_body": False,
            }
        return {"type": "http.disconnect"}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/subscriptions/webhook",
        "raw_path": b"/api/subscriptions/webhook",
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    return Request(scope, receive)


def make_captured_event():
    return {
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_123",
                    "order_id": "order_test_123",
                    "status": "captured",
                    "captured": True,
                    "amount": 15000,
                    "currency": "INR",
                }
            }
        },
    }


def signed_webhook_request(body, event_id="evt_test_123"):
    body_bytes = json.dumps(body).encode("utf-8")
    signature = hmac.new(
        b"webhook_test_secret",
        body_bytes,
        hashlib.sha256,
    ).hexdigest()

    return make_webhook_request(
        body,
        {
            "X-Razorpay-Signature": signature,
            "X-Razorpay-Event-Id": event_id,
        },
    )


def test_webhook_rejects_invalid_signature(payment_setup):
    request = make_webhook_request(
        make_captured_event(),
        {
            "X-Razorpay-Signature": "invalid_signature",
            "X-Razorpay-Event-Id": "evt_invalid",
        },
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.razorpay_webhook(request))

    assert exc.value.status_code == 400
    assert "signature" in exc.value.detail.lower()

    payment_setup["db"]["payment_webhook_events"].insert_one.assert_not_called()
    payment_setup["db"]["subscriptions"].update_one.assert_not_called()


def test_valid_capture_webhook_activates_payment(payment_setup):
    request = signed_webhook_request(make_captured_event())

    with patch.object(
        routes,
        "_activate_verified_payment",
        return_value={"success": True},
    ) as activate:
        result = asyncio.run(routes.razorpay_webhook(request))

    assert result == {"success": True}
    activate.assert_called_once_with("order_test_123", "pay_test_123")

    payment_setup["db"]["payment_webhook_events"].insert_one.assert_called_once()
    payment_setup["db"]["payment_webhook_events"].update_one.assert_called_once()


def test_processed_duplicate_webhook_is_ignored(payment_setup):
    events = payment_setup["db"]["payment_webhook_events"]
    events.insert_one.side_effect = DuplicateKeyError("duplicate event")
    events.find_one.return_value = {"event_id": "evt_test_123", "status": "processed"}

    request = signed_webhook_request(make_captured_event())

    with patch.object(routes, "_activate_verified_payment") as activate:
        result = asyncio.run(routes.razorpay_webhook(request))

    assert result["success"] is True
    assert result["message"] == "Duplicate event ignored"
    activate.assert_not_called()


def test_webhook_rejects_invalid_amount_without_activation(payment_setup):
    event = make_captured_event()
    event["payload"]["payment"]["entity"]["amount"] = 100

    request = signed_webhook_request(event, event_id="evt_wrong_amount")

    with patch.object(routes, "_activate_verified_payment") as activate:
        result = asyncio.run(routes.razorpay_webhook(request))

    assert result == {"success": True}
    activate.assert_not_called()

    payment_setup["db"]["payment_webhook_events"].update_one.assert_called_once()


def test_already_verified_payment_does_not_create_duplicate_subscription(
    payment_setup,
):
    payment = payment_setup["payment"]
    payment["status"] = "verified"
    payment["razorpay_payment_id"] = "pay_test_123"

    existing_subscription = {
        "_id": "subscription_test_123",
        "worker_id": "worker-test-1",
        "plan": "monthly",
        "status": "active",
        "payment_id": "pay_test_123",
        "razorpay_order_id": "order_test_123",
    }

    subscriptions = payment_setup["db"]["subscriptions"]
    subscriptions.find_one.return_value = existing_subscription

    result = routes._activate_verified_payment(
        "order_test_123",
        "pay_test_123",
    )

    assert result["success"] is True
    assert result["message"] == "Payment already verified"

    # Existing subscription must not be created or updated again.
    subscriptions.update_one.assert_not_called()

    # A verified payment must not be updated again.
    payment_setup["payments"].update_one.assert_not_called()


def test_webhook_recovers_expired_processing_event(payment_setup):
    events = payment_setup["db"]["payment_webhook_events"]
    events.insert_one.side_effect = DuplicateKeyError("duplicate event")
    events.find_one.return_value = {
        "event_id": "evt_test_123",
        "status": "processing",
    }
    events.find_one_and_update.return_value = {
        "event_id": "evt_test_123",
        "status": "processing",
    }

    request = signed_webhook_request(make_captured_event())

    with patch.object(
        routes,
        "_activate_verified_payment",
        return_value={"success": True},
    ) as activate:
        result = asyncio.run(routes.razorpay_webhook(request))

    assert result == {"success": True}
    events.find_one_and_update.assert_called_once()
    claim_filter = events.find_one_and_update.call_args.args[0]
    assert claim_filter["event_id"] == "evt_test_123"
    assert claim_filter["status"] == "processing"
    assert "$or" in claim_filter
    activate.assert_called_once_with("order_test_123", "pay_test_123")


def test_webhook_rejects_event_with_active_lease(payment_setup):
    events = payment_setup["db"]["payment_webhook_events"]
    events.insert_one.side_effect = DuplicateKeyError("duplicate event")
    events.find_one.return_value = {
        "event_id": "evt_test_123",
        "status": "processing",
    }
    events.find_one_and_update.return_value = None

    request = signed_webhook_request(make_captured_event())

    with patch.object(routes, "_activate_verified_payment") as activate:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(routes.razorpay_webhook(request))

    assert exc.value.status_code == 503
    activate.assert_not_called()


def test_webhook_rejects_lost_ownership_at_completion(payment_setup):
    events = payment_setup["db"]["payment_webhook_events"]
    events.update_one.return_value.matched_count = 0

    request = signed_webhook_request(make_captured_event())

    with patch.object(
        routes,
        "_activate_verified_payment",
        return_value={"success": True},
    ) as activate:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(routes.razorpay_webhook(request))

    assert exc.value.status_code == 503
    assert "ownership changed" in exc.value.detail.lower()
    activate.assert_called_once_with("order_test_123", "pay_test_123")

    # Cleanup must only target this request's event ownership token.
    delete_filter = events.delete_one.call_args.args[0]
    assert delete_filter["event_id"] == "evt_test_123"
    assert delete_filter["status"] == "processing"
    assert delete_filter["owner_token"]

def test_webhook_rejects_missing_event_id(payment_setup):
    request = signed_webhook_request(
        make_captured_event(),
        event_id="",
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.razorpay_webhook(request))

    assert exc.value.status_code == 400
    assert "event id" in exc.value.detail.lower()
