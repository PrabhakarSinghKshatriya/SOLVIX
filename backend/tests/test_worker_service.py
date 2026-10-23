from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.services.worker_service import WorkerService


CUSTOMER_LAT = 28.6139
CUSTOMER_LON = 77.2090


def make_worker(
    *,
    user_id=None,
    verified=False,
    profession="Electrician",
    skills=None,
    latitude=CUSTOMER_LAT,
    longitude=CUSTOMER_LON,
):
    return {
        "_id": ObjectId(),
        "user_id": user_id or str(ObjectId()),
        "profession": profession,
        "skills": skills or ["Wiring"],
        "experience_years": 5,
        "service_radius_km": 10,
        "bio": "Experienced professional",
        "availability": "available",
        "location": {
            "type": "Point",
            "coordinates": [longitude, latitude],
        },
        "rating": 4.0,
        "total_reviews": 10,
        "completed_services": 20,
        "is_verified": verified,
        "is_active": True,
    }


def make_service(worker_documents, user_profiles=None, aadhaar_records=None):
    workers_collection = MagicMock()
    users_collection = MagicMock()
    aadhaar_collection = MagicMock()

    workers_collection.find.return_value = worker_documents
    users_collection.find.return_value = user_profiles or []
    aadhaar_collection.find.return_value = aadhaar_records or []

    database = {
        "workers": workers_collection,
        "users": users_collection,
        "aadhaar_verifications": aadhaar_collection,
    }

    with patch(
        "app.services.worker_service.get_database",
        return_value=database,
    ):
        service = WorkerService()

    return (
        service,
        workers_collection,
        users_collection,
        aadhaar_collection,
    )


def test_matching_preserves_score_name_and_verification():
    user_id = str(ObjectId())
    worker = make_worker(user_id=user_id, verified=False)

    (
        service,
        _,
        users_collection,
        aadhaar_collection,
    ) = make_service(
        [worker],
        user_profiles=[{"_id": ObjectId(user_id), "name": "Test Electrician"}],
        aadhaar_records=[{"worker_id": user_id, "status": "verified"}],
    )

    results = service.match_workers(
        CUSTOMER_LAT,
        CUSTOMER_LON,
        "electric",
        radius_km=10,
    )

    assert len(results) == 1
    result = results[0]

    # 50 base + 16 rating + 5 experience + 10 verified + 1 completed.
    assert result["match_score"] == 82
    assert result["name"] == "Test Electrician"
    assert result["is_verified"] is True
    assert result["distance_km"] == 0
    assert "id" in result
    assert result["profession"] == "Electrician"

    # Each public-data collection is queried once for this matching pass.
    users_collection.find.assert_called_once()
    aadhaar_collection.find.assert_called_once()


def test_aadhaar_rejection_overrides_legacy_verified_profile():
    user_id = str(ObjectId())
    worker = make_worker(user_id=user_id, verified=True)

    service, _, _, _ = make_service(
        [worker],
        aadhaar_records=[{"worker_id": user_id, "status": "rejected"}],
    )

    results = service.match_workers(
        CUSTOMER_LAT,
        CUSTOMER_LON,
        "electric",
    )

    assert len(results) == 1
    assert results[0]["is_verified"] is False

    # Rejected Aadhaar record means no +10 verification bonus.
    assert results[0]["match_score"] == 72


def test_missing_aadhaar_record_uses_legacy_profile_fallback():
    user_id = str(ObjectId())
    worker = make_worker(user_id=user_id, verified=True)

    service, _, _, _ = make_service([worker])

    results = service.match_workers(
        CUSTOMER_LAT,
        CUSTOMER_LON,
        "electric",
    )

    assert len(results) == 1
    assert results[0]["is_verified"] is True
    assert results[0]["match_score"] == 82


def test_matching_excludes_workers_outside_service_radius():
    worker = make_worker(
        latitude=28.65,
        longitude=77.25,
    )
    worker["service_radius_km"] = 1

    service, _, _, _ = make_service([worker])

    results = service.match_workers(
        CUSTOMER_LAT,
        CUSTOMER_LON,
        "electric",
        radius_km=10,
    )

    assert results == []


def test_matching_excludes_workers_with_nonmatching_skills():
    worker = make_worker(
        profession="Carpenter",
        skills=["Furniture", "Woodwork"],
    )

    service, _, _, _ = make_service([worker])

    results = service.match_workers(
        CUSTOMER_LAT,
        CUSTOMER_LON,
        "electrician",
    )

    assert results == []


def test_nearby_workers_use_batched_public_data():
    user_id = str(ObjectId())
    worker = make_worker(user_id=user_id)

    (
        service,
        _,
        users_collection,
        aadhaar_collection,
    ) = make_service(
        [worker],
        user_profiles=[{"_id": ObjectId(user_id), "name": "Nearby Worker"}],
        aadhaar_records=[{"worker_id": user_id, "status": "verified"}],
    )

    results = service.find_nearby_workers(
        CUSTOMER_LAT,
        CUSTOMER_LON,
        max_distance_km=10,
    )

    assert len(results) == 1
    assert results[0]["name"] == "Nearby Worker"
    assert results[0]["is_verified"] is True
    assert results[0]["distance_km"] == 0

    users_collection.find.assert_called_once()
    aadhaar_collection.find.assert_called_once()
