from unittest.mock import MagicMock

import pytest
from bson import ObjectId

from app.services.review_service import ReviewService


CUSTOMER_ID = "customer-test-123"
WORKER_ID = "worker-test-456"
REQUEST_ID = str(ObjectId())
WORKER_OBJECT_ID = ObjectId()


@pytest.fixture
def setup_review_service(monkeypatch):
    db = MagicMock()

    requests = MagicMock()
    reviews = MagicMock()
    workers = MagicMock()

    collections = {
        "service_requests": requests,
        "reviews": reviews,
        "workers": workers,
    }
    db.__getitem__.side_effect = collections.__getitem__

    session = db.client.start_session.return_value.__enter__.return_value
    session.with_transaction.side_effect = (
        lambda callback, *args, **kwargs: callback(session)
    )

    monkeypatch.setattr(
        "app.services.review_service.get_database",
        lambda: db,
    )

    service = ReviewService()

    return service, requests, reviews, workers


def completed_request(customer_id=CUSTOMER_ID, status="completed"):
    return {
        "_id": ObjectId(REQUEST_ID),
        "customer_id": customer_id,
        "assigned_worker_id": WORKER_ID,
        "status": status,
    }


def active_worker():
    return {
        "_id": WORKER_OBJECT_ID,
        "user_id": WORKER_ID,
        "is_active": True,
        "rating": 0.0,
        "total_reviews": 0,
    }


def test_invalid_request_id_is_rejected(setup_review_service):
    service, requests, _, _ = setup_review_service

    with pytest.raises(ValueError, match="Invalid service request ID"):
        service.create_review(
            "invalid-id", CUSTOMER_ID, 5, "Excellent"
        )

    requests.find_one.assert_not_called()


@pytest.mark.parametrize("rating", [0, 6, -1, 1.5, True, "5"])
def test_invalid_rating_is_rejected(setup_review_service, rating):
    service, requests, _, _ = setup_review_service

    with pytest.raises(ValueError, match="Rating"):
        service.create_review(
            REQUEST_ID, CUSTOMER_ID, rating, "Feedback"
        )

    requests.find_one.assert_not_called()


def test_another_customer_cannot_review_booking(setup_review_service):
    service, requests, reviews, workers = setup_review_service
    requests.find_one.return_value = completed_request()

    with pytest.raises(PermissionError, match="Only the customer"):
        service.create_review(
            REQUEST_ID, "different-customer", 5, "Excellent"
        )

    reviews.insert_one.assert_not_called()
    workers.update_one.assert_not_called()


def test_booking_must_be_completed(setup_review_service):
    service, requests, reviews, workers = setup_review_service
    requests.find_one.return_value = completed_request(status="in_progress")

    with pytest.raises(ValueError, match="only after it is completed"):
        service.create_review(
            REQUEST_ID, CUSTOMER_ID, 5, "Excellent"
        )

    reviews.insert_one.assert_not_called()
    workers.update_one.assert_not_called()


def test_existing_review_cannot_be_submitted_again(setup_review_service):
    service, requests, reviews, workers = setup_review_service
    requests.find_one.return_value = completed_request()
    workers.find_one.return_value = active_worker()
    reviews.find_one.return_value = {"_id": ObjectId()}

    with pytest.raises(ValueError, match="already been submitted"):
        service.create_review(
            REQUEST_ID, CUSTOMER_ID, 5, "Excellent"
        )

    reviews.insert_one.assert_not_called()
    workers.update_one.assert_not_called()


def test_completed_booking_accepts_review_and_updates_rating(
    setup_review_service,
):
    service, requests, reviews, workers = setup_review_service

    requests.find_one.return_value = completed_request()
    workers.find_one.return_value = active_worker()
    reviews.find_one.return_value = None

    inserted_id = ObjectId()
    reviews.insert_one.return_value.inserted_id = inserted_id
    reviews.aggregate.return_value = [
        {"_id": None, "average": 4.5, "count": 2}
    ]
    workers.update_one.return_value.matched_count = 1

    result = service.create_review(
        REQUEST_ID,
        CUSTOMER_ID,
        5,
        "  Excellent service!  ",
    )

    assert result["id"] == str(inserted_id)
    assert result["request_id"] == REQUEST_ID
    assert result["worker_id"] == WORKER_ID
    assert result["rating"] == 5
    assert result["feedback"] == "Excellent service!"
    assert result["worker_rating"] == 4.5
    assert result["worker_total_reviews"] == 2

    reviews.insert_one.assert_called_once()
    workers.update_one.assert_called_once()

    update_fields = workers.update_one.call_args.args[1]["$set"]
    assert update_fields["rating"] == 4.5
    assert update_fields["total_reviews"] == 2


def test_feedback_over_1000_characters_is_rejected(setup_review_service):
    service, requests, _, _ = setup_review_service

    with pytest.raises(ValueError, match="1000 characters"):
        service.create_review(
            REQUEST_ID, CUSTOMER_ID, 5, "x" * 1001
        )

    requests.find_one.assert_not_called()
