from datetime import datetime

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
            "active": subscriptions.count_documents({"status": "active"}),
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
        items.append({
            "id": str(worker["_id"]),
            "user_id": worker.get("user_id"),
            "profession": worker.get("profession"),
            "skills": worker.get("skills", []),
            "experience_years": worker.get("experience_years", 0),
            "availability": worker.get("availability", "offline"),
            "rating": worker.get("rating", 0),
            "total_reviews": worker.get("total_reviews", 0),
            "completed_services": worker.get("completed_services", 0),
            "is_verified": worker.get("is_verified", False),
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

        items.append({
            "id": str(request["_id"]),
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
                "secret": 0,
                "token": 0,
                "payment_signature": 0,
                "webhook_secret": 0,
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
                "secret": 0,
                "token": 0,
                "payment_signature": 0,
                "webhook_secret": 0,
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
