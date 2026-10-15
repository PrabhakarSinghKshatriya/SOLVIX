from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, Query

from app.database.connection import get_database
from app.dependencies import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


def safe_datetime(value):
    return value.isoformat() if isinstance(value, datetime) else value


@router.get("/overview")
def overview():
    db = get_database()
    users = db["users"]
    workers = db["workers"]
    requests = db["service_requests"]
    subscriptions = db["subscriptions"]
    payments = db["payments"]

    return {
        "success": True,
        "users": {
            "total": users.count_documents({}),
            "customers": users.count_documents({"role": "customer"}),
            "workers": users.count_documents({"role": "worker"}),
            "admins": users.count_documents({"role": "admin"}),
            "active": users.count_documents({"is_active": {"$ne": False}}),
        },
        "workers": {
            "total": workers.count_documents({}),
            "available": workers.count_documents({"availability": "available"}),
            "busy": workers.count_documents({"availability": "busy"}),
        },
        "requests": {
            "total": requests.count_documents({}),
            "requested": requests.count_documents({"status": "requested"}),
            "accepted": requests.count_documents({"status": "accepted"}),
            "in_progress": requests.count_documents({"status": "in_progress"}),
            "completed": requests.count_documents({"status": "completed"}),
            "cancelled": requests.count_documents({"status": "cancelled"}),
        },
        "subscriptions": {
            "total": subscriptions.count_documents({}),
            "active": subscriptions.count_documents({
                "status": "active",
                "expires_at": {"$gt": datetime.now(timezone.utc)},
            }),
        },
        "payments": {
            "total": payments.count_documents({}),
            "verified": payments.count_documents({"status": "verified"}),
        },
    }


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    role: str | None = Query(None, pattern="^(customer|worker|admin)$"),
):
    db = get_database()
    query = {"role": role} if role else {}

    cursor = (
        db["users"]
        .find(
            query,
            {
                "name": 1,
                "email": 1,
                "phone": 1,
                "role": 1,
                "is_active": 1,
                "is_verified": 1,
                "created_at": 1,
            },
        )
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    items = []
    for user in cursor:
        items.append({
            "id": str(user["_id"]),
            "name": user.get("name"),
            "email": user.get("email"),
            "phone": user.get("phone"),
            "role": user.get("role"),
            "is_active": user.get("is_active", True),
            "is_verified": user.get("is_verified", False),
            "created_at": safe_datetime(user.get("created_at")),
        })

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": db["users"].count_documents(query),
        "items": items,
    }


@router.get("/workers")
def list_workers(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
):
    db = get_database()
    query = {}

    cursor = (
        db["workers"]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    items = []
    for worker in cursor:
        user_id = str(worker.get("user_id", ""))
        user_profile = _admin_get_user(db, user_id)

        # Prefer the latest Aadhaar decision when a record exists.
        aadhaar_record = db["aadhaar_verifications"].find_one(
            {"worker_id": user_id},
            {"_id": 0, "status": 1},
        )
        is_verified = (
            aadhaar_record.get("status") == "verified"
            if aadhaar_record is not None
            else bool(worker.get("is_verified", False))
        )

        items.append({
            "id": str(worker["_id"]),
            "user_id": worker.get("user_id"),
            "name": (user_profile or {}).get("name"),
            "email": (user_profile or {}).get("email"),
            "phone": (user_profile or {}).get("phone"),
            "profession": worker.get("profession"),
            "skills": worker.get("skills", []),
            "experience_years": worker.get("experience_years", 0),
            "availability": worker.get("availability", "offline"),
            "rating": worker.get("rating", 0),
            "total_reviews": worker.get("total_reviews", 0),
            "completed_services": worker.get("completed_services", 0),
            "is_verified": is_verified,
            "is_active": worker.get("is_active", True),
            "created_at": safe_datetime(worker.get("created_at")),
        })

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": db["workers"].count_documents(query),
        "items": items,
    }


@router.get("/requests")
def list_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
):
    db = get_database()
    query = {"status": status_filter} if status_filter else {}

    cursor = (
        db["service_requests"]
        .find(query)
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    items = []
    for request in cursor:
        location = request.get("location") or {}
        coordinates = location.get("coordinates") or []
        people = _admin_request_people(db, request)

        items.append({
            "id": str(request["_id"]),
            **people,
            "customer_id": request.get("customer_id"),
            "service": request.get("service"),
            "description": request.get("description"),
            "status": request.get("status", "requested"),
            "assigned_worker_id": request.get("assigned_worker_id"),
            "latitude": coordinates[1] if len(coordinates) >= 2 else None,
            "longitude": coordinates[0] if len(coordinates) >= 2 else None,
            "created_at": safe_datetime(request.get("created_at")),
            "updated_at": safe_datetime(request.get("updated_at")),
        })

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": db["service_requests"].count_documents(query),
        "items": items,
    }


@router.get("/subscriptions")
def list_subscriptions(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
):
    db = get_database()
    query = {}

    cursor = (
        db["subscriptions"]
        .find(
            query,
            {
                "_id": 1,
                "worker_id": 1,
                "plan": 1,
                "status": 1,
                "payment_id": 1,
                "razorpay_order_id": 1,
                "starts_at": 1,
                "expires_at": 1,
                "created_at": 1,
                "updated_at": 1,
            },
        )
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    items = []
    for record in cursor:
        record["id"] = str(record.pop("_id"))
        for key, value in list(record.items()):
            record[key] = safe_datetime(value)
        items.append(record)

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": db["subscriptions"].count_documents(query),
        "items": items,
    }


@router.get("/payments")
def list_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
):
    db = get_database()
    query = {}

    cursor = (
        db["payments"]
        .find(
            query,
            {
                "_id": 1,
                "worker_id": 1,
                "plan": 1,
                "amount": 1,
                "currency": 1,
                "razorpay_order_id": 1,
                "razorpay_payment_id": 1,
                "status": 1,
                "created_at": 1,
                "updated_at": 1,
                "verified_at": 1,
            },
        )
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    items = []
    for record in cursor:
        record["id"] = str(record.pop("_id"))
        for key, value in list(record.items()):
            record[key] = safe_datetime(value)
        items.append(record)

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": db["payments"].count_documents(query),
        "items": items,
    }

# SOLVIX_ADMIN_DETAIL_APIS_V1
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException


def _admin_id(value):
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


def _admin_safe(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        blocked = {
            "password", "password_hash", "secret", "token",
            "access_token", "refresh_token", "id_token",
            "payment_signature", "webhook_secret", "reset_token",
            "otp", "login_otp", "otp_hash", "verification_token",
            "email_verification_token", "api_key",
        }
        return {
            str(k): _admin_safe(v)
            for k, v in value.items()
            if str(k).lower() not in blocked
        }
    if isinstance(value, (list, tuple)):
        return [_admin_safe(v) for v in value]
    return value


def _admin_get_user(db, user_id):
    oid = _admin_id(user_id)
    if oid is None:
        return None
    return db["users"].find_one(
        {"_id": oid},
        {"password": 0, "password_hash": 0, "reset_token": 0},
    )


def _admin_request_people(db, record):
    """Attach safe customer and assigned-worker summaries to a request."""
    customer_id = str(record.get("customer_id") or "")
    assigned_id = str(record.get("assigned_worker_id") or "")

    customer = _admin_get_user(db, customer_id) if customer_id else None

    worker_profile = (
        db["workers"].find_one({"user_id": assigned_id})
        if assigned_id else None
    )
    worker_user = (
        _admin_get_user(db, assigned_id)
        if assigned_id else None
    )

    return {
        "customer": (
            {
                "name": customer.get("name"),
                "email": customer.get("email"),
                "phone": customer.get("phone"),
            }
            if customer else None
        ),
        "assigned_worker": (
            {
                "name": (worker_user or {}).get("name"),
                "email": (worker_user or {}).get("email"),
                "phone": (worker_user or {}).get("phone"),
                "profession": (worker_profile or {}).get("profession"),
                "rating": (worker_profile or {}).get("rating"),
            }
            if worker_profile or worker_user else None
        ),
    }

@router.get("/workers/{worker_id}/details")
def admin_worker_details(worker_id: str):
    db = get_database()
    oid = _admin_id(worker_id)

    worker = db["workers"].find_one({"_id": oid}) if oid else None
    if worker is None:
        worker = db["workers"].find_one({"user_id": worker_id})

    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    user_id = str(worker.get("user_id", ""))
    profile = _admin_get_user(db, user_id)

    # SOLVIX_ADMIN_PROFILE_ENRICHMENT_V1
    jobs_query = {"assigned_worker_id": user_id}
    jobs = list(
        db["service_requests"]
        .find(jobs_query)
        .sort("created_at", -1)
        .limit(200)
    )

    # Count every matching record, not only the 200 displayed records.
    job_counts = {}
    for item in db["service_requests"].aggregate([
        {"$match": jobs_query},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]):
        job_counts[str(item.get("_id") or "unknown")] = item["count"]

    for job in jobs:
        customer = _admin_get_user(db, str(job.get("customer_id", "")))
        job["customer"] = (
            {
                "name": customer.get("name"),
                "email": customer.get("email"),
                "phone": customer.get("phone"),
            }
            if customer else None
        )

    subscriptions = list(
        db["subscriptions"]
        .find({"worker_id": user_id})
        .sort("created_at", -1)
        .limit(100)
    )

    try:
        from app.config import settings
        free_limit = int(settings.worker_free_opportunities)
    except (ImportError, AttributeError, TypeError, ValueError):
        free_limit = 5

    free_used = int(worker.get("free_opportunities_used", 0) or 0)

    return {
        "success": True,
        "worker": _admin_safe({
            **worker,
            "id": str(worker["_id"]),
        }),
        "user": _admin_safe(profile) if profile else None,
        "jobs": {
            "total": db["service_requests"].count_documents(
                {"assigned_worker_id": user_id}
            ),
            "by_status": job_counts,
            "items": [
                _admin_safe({**job, "id": str(job["_id"])})
                for job in jobs
            ],
        },
        "opportunities": {
            "free_limit": free_limit,
            "free_used": free_used,
            "free_remaining": max(0, free_limit - free_used),
        },
        "subscriptions": [
            _admin_safe({**item, "id": str(item["_id"])})
            for item in subscriptions
        ],
    }


@router.get("/customers/{customer_id}/details")
def admin_customer_details(customer_id: str):
    db = get_database()
    customer = _admin_get_user(db, customer_id)

    if customer is None or customer.get("role") != "customer":
        raise HTTPException(status_code=404, detail="Customer not found")

    # Count all requests independently of the recent-history limit.
    customer_query = {"customer_id": customer_id}
    records = list(
        db["service_requests"]
        .find(customer_query)
        .sort("created_at", -1)
        .limit(200)
    )

    counts = {}
    for item in db["service_requests"].aggregate([
        {"$match": customer_query},
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
    ]):
        counts[str(item.get("_id") or "unknown")] = item["count"]

    for record in records:
        assigned_id = str(record.get("assigned_worker_id") or "")
        worker = db["workers"].find_one({"user_id": assigned_id}) if assigned_id else None
        worker_user = (
            _admin_get_user(db, assigned_id)
            if assigned_id else None
        )
        record["assigned_worker"] = (
            {
                "name": (worker_user or {}).get("name"),
                "email": (worker_user or {}).get("email"),
                "phone": (worker_user or {}).get("phone"),
                "profession": (worker or {}).get("profession"),
                "rating": (worker or {}).get("rating"),
            }
            if worker or worker_user else None
        )

    return {
        "success": True,
        "customer": _admin_safe(customer),
        "requests": {
            "total": db["service_requests"].count_documents(
                {"customer_id": customer_id}
            ),
            "by_status": counts,
            "items": [
                _admin_safe({**record, "id": str(record["_id"])})
                for record in records
            ],
        },
    }


@router.get("/requests/filter")
def admin_filter_requests(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status: str | None = Query(None),
    customer_id: str | None = Query(None),
    worker_id: str | None = Query(None),
    profession: str | None = Query(None, min_length=1, max_length=100),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
):
    db = get_database()
    conditions = []

    if status:
        conditions.append({"status": status})
    if customer_id:
        conditions.append({"customer_id": customer_id})
    if worker_id:
        conditions.append({"assigned_worker_id": worker_id})

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must not be later than end_date",
        )

    dates = {}
    if start_date:
        dates["$gte"] = start_date
    if end_date:
        dates["$lte"] = end_date
    if dates:
        conditions.append({"created_at": dates})

    if profession:
        matching_workers = db["workers"].find(
            {"profession": {"$regex": re.escape(profession), "$options": "i"}},
            {"user_id": 1},
        )
        worker_ids = [
            item["user_id"]
            for item in matching_workers
            if item.get("user_id")
        ]
        conditions.append({
            "assigned_worker_id": {"$in": worker_ids}
        })

    query = {"$and": conditions} if conditions else {}
    collection = db["service_requests"]

    records = list(
        collection.find(query)
        .sort("created_at", -1)
        .skip((page - 1) * limit)
        .limit(limit)
    )

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": collection.count_documents(query),
        "items": [
            _admin_safe({
                **record,
                "id": str(record["_id"]),
                **_admin_request_people(db, record),
            })
            for record in records
        ],
    }
