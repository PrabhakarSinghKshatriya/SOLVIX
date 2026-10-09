from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from app.services.service_request_service import ServiceRequestService


CUSTOMER_ID = "customer-test-123"
WORKER_ID = "worker-test-456"
REQUEST_ID = str(ObjectId())


@pytest.fixture
def setup_service():
    service = ServiceRequestService()

    service.db = MagicMock()
    service.requests = MagicMock()
    service.db.__getitem__.return_value = MagicMock()

    # Simulate MongoDB's transaction callback in unit tests.
    session = service.db.client.start_session.return_value.__enter__.return_value
    session.with_transaction.side_effect = (
        lambda callback, *args, **kwargs: callback(session)
    )

    return service


def make_request(status="accepted"):
    return {
        "_id": ObjectId(REQUEST_ID),
        "customer_id": CUSTOMER_ID,
        "assigned_worker_id": WORKER_ID,
        "status": status,
    }


def test_invalid_request_id_returns_none(setup_service):
    result = setup_service.transition_status(
        request_id="invalid-id",
        user_id=CUSTOMER_ID,
        user_role="customer",
        new_status="confirmed",
    )

    assert result is None
    setup_service.requests.find_one.assert_not_called()


def test_missing_request_returns_none(setup_service):
    setup_service.requests.find_one.return_value = None

    result = setup_service.transition_status(
        request_id=REQUEST_ID,
        user_id=CUSTOMER_ID,
        user_role="customer",
        new_status="confirmed",
    )

    assert result is None


def test_other_customer_cannot_modify_request(setup_service):
    setup_service.requests.find_one.return_value = make_request()

    with pytest.raises(ValueError, match="permission"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id="another-customer",
            user_role="customer",
            new_status="confirmed",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_unassigned_worker_cannot_modify_request(setup_service):
    setup_service.requests.find_one.return_value = make_request()

    with pytest.raises(ValueError, match="assigned worker"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id="another-worker",
            user_role="worker",
            new_status="cancelled",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_unsupported_role_cannot_modify_request(setup_service):
    setup_service.requests.find_one.return_value = make_request()

    with pytest.raises(ValueError, match="role cannot update"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id="admin-test",
            user_role="admin",
            new_status="confirmed",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_customer_can_confirm_accepted_request(setup_service):
    setup_service.requests.find_one.return_value = make_request()
    updated_request = make_request(status="confirmed")
    setup_service.requests.find_one_and_update.return_value = updated_request

    with patch(
        "app.services.service_request_service.ServiceRequestModel.serialize",
        return_value={"id": REQUEST_ID, "status": "confirmed"},
    ):
        result = setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=CUSTOMER_ID,
            user_role="customer",
            new_status="confirmed",
        )

    assert result["status"] == "confirmed"
    update_filter = setup_service.requests.find_one_and_update.call_args.args[0]
    assert update_filter["status"] == "accepted"
    assert update_filter["customer_id"] == CUSTOMER_ID


def test_worker_cannot_confirm_request(setup_service):
    setup_service.requests.find_one.return_value = make_request()

    with pytest.raises(ValueError, match="Only the customer can confirm"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=WORKER_ID,
            user_role="worker",
            new_status="confirmed",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_customer_cannot_complete_service(setup_service):
    setup_service.requests.find_one.return_value = make_request(
        status="in_progress"
    )

    with pytest.raises(ValueError, match="Only the assigned worker"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=CUSTOMER_ID,
            user_role="customer",
            new_status="completed",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_completed_request_cannot_be_cancelled(setup_service):
    setup_service.requests.find_one.return_value = make_request(
        status="completed"
    )

    with pytest.raises(ValueError, match="Cannot change status"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=CUSTOMER_ID,
            user_role="customer",
            new_status="cancelled",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_invalid_transition_is_rejected(setup_service):
    setup_service.requests.find_one.return_value = make_request(
        status="accepted"
    )

    with pytest.raises(ValueError, match="Cannot change status"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=CUSTOMER_ID,
            user_role="customer",
            new_status="completed",
        )

    setup_service.requests.find_one_and_update.assert_not_called()


def test_concurrent_status_change_is_detected(setup_service):
    setup_service.requests.find_one.return_value = make_request()
    setup_service.requests.find_one_and_update.return_value = None

    with pytest.raises(ValueError, match="another operation"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=CUSTOMER_ID,
            user_role="customer",
            new_status="confirmed",
        )


def test_completion_increments_worker_counter_once(setup_service):
    setup_service.requests.find_one.return_value = make_request(
        status="in_progress"
    )
    setup_service.requests.find_one_and_update.return_value = make_request(
        status="completed"
    )

    worker_collection = MagicMock()
    setup_service.db.__getitem__.return_value = worker_collection
    setup_service.requests.find_one.side_effect = [
        make_request(status="in_progress"),
        None,
    ]

    with patch(
        "app.services.service_request_service.ServiceRequestModel.serialize",
        return_value={"id": REQUEST_ID, "status": "completed"},
    ):
        result = setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=WORKER_ID,
            user_role="worker",
            new_status="completed",
        )

    assert result["status"] == "completed"
    assert worker_collection.update_one.call_count == 2

    counter_update = worker_collection.update_one.call_args_list[0].args[1]
    assert counter_update["$inc"]["completed_services"] == 1

    availability_update = worker_collection.update_one.call_args_list[1].args[1]
    assert availability_update["$set"]["availability"] == "available"


def test_failed_completion_does_not_increment_counter(setup_service):
    setup_service.requests.find_one.return_value = make_request(
        status="in_progress"
    )
    setup_service.requests.find_one_and_update.return_value = None

    worker_collection = MagicMock()
    setup_service.db.__getitem__.return_value = worker_collection

    with pytest.raises(ValueError, match="another operation"):
        setup_service.transition_status(
            request_id=REQUEST_ID,
            user_id=WORKER_ID,
            user_role="worker",
            new_status="completed",
        )

    worker_collection.update_one.assert_not_called()

def test_worker_action_accepts_matched_worker(setup_service):
    service = setup_service
    request = {
        "_id": ObjectId(REQUEST_ID),
        "customer_id": CUSTOMER_ID,
        "assigned_worker_id": None,
        "matched_worker_ids": [WORKER_ID],
        "status": "requested",
    }
    updated_request = {
        **request,
        "assigned_worker_id": WORKER_ID,
        "status": "accepted",
        "match_status": "assigned",
    }

    service.requests.find_one.return_value = request
    service.db["workers"].update_one.return_value.modified_count = 1
    service.requests.find_one_and_update.return_value = updated_request

    with patch(
        "app.services.service_request_service.ServiceRequestModel.serialize",
        return_value={"id": REQUEST_ID, "status": "accepted"},
    ):
        result = service.worker_action(
            REQUEST_ID, WORKER_ID, "accept"
        )

    assert result["status"] == "accepted"
    service.db["workers"].update_one.assert_called_once()
    service.requests.find_one_and_update.assert_called_once()
    service.db.client.start_session.return_value.__enter__.return_value.with_transaction.assert_called_once()


def test_worker_action_rejects_matched_worker(setup_service):
    service = setup_service
    request = {
        "_id": ObjectId(REQUEST_ID),
        "customer_id": CUSTOMER_ID,
        "assigned_worker_id": None,
        "matched_worker_ids": [WORKER_ID],
        "status": "requested",
    }
    updated_request = {
        **request,
        "status": "rejected",
        "match_status": "rejected",
    }

    service.requests.find_one.return_value = request
    service.requests.find_one_and_update.return_value = updated_request

    with patch(
        "app.services.service_request_service.ServiceRequestModel.serialize",
        return_value={"id": REQUEST_ID, "status": "rejected"},
    ):
        result = service.worker_action(
            REQUEST_ID, WORKER_ID, "reject"
        )

    assert result["status"] == "rejected"
    service.db["workers"].update_one.assert_not_called()
    service.requests.find_one_and_update.assert_called_once()


def test_unmatched_worker_cannot_accept_request(setup_service):
    service = setup_service
    service.requests.find_one.return_value = {
        "_id": ObjectId(REQUEST_ID),
        "status": "requested",
        "assigned_worker_id": None,
        "matched_worker_ids": ["another-worker"],
    }

    with pytest.raises(ValueError, match="not matched"):
        service.worker_action(REQUEST_ID, WORKER_ID, "accept")

    service.db["workers"].update_one.assert_not_called()
    service.requests.find_one_and_update.assert_not_called()


def test_unavailable_worker_cannot_accept_request(setup_service):
    service = setup_service
    service.requests.find_one.return_value = {
        "_id": ObjectId(REQUEST_ID),
        "status": "requested",
        "assigned_worker_id": None,
        "matched_worker_ids": [WORKER_ID],
    }
    service.db["workers"].update_one.return_value.modified_count = 0

    with pytest.raises(ValueError, match="not available"):
        service.worker_action(REQUEST_ID, WORKER_ID, "accept")

    service.requests.find_one_and_update.assert_not_called()


def test_worker_action_rejects_invalid_action(setup_service):
    with pytest.raises(ValueError, match="Invalid worker action"):
        setup_service.worker_action(
            REQUEST_ID, WORKER_ID, "unknown"
        )

    setup_service.requests.find_one.assert_not_called()


def test_worker_action_invalid_request_id_returns_none(setup_service):
    result = setup_service.worker_action(
        "invalid-id", WORKER_ID, "accept"
    )

    assert result is None
    setup_service.requests.find_one.assert_not_called()
