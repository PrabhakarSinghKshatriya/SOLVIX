from fastapi import APIRouter

from app.database.connection import get_database

router = APIRouter(prefix="/api/stats", tags=["Public Statistics"])


@router.get("/public")
def public_statistics():
    """Return aggregate marketplace counts only; never expose user records."""
    db = get_database()
    users = db["users"]
    workers = db["workers"]
    requests = db["service_requests"]

    return {
        "success": True,
        "users": {
            "total": users.count_documents({}),
            "customers": users.count_documents({"role": "customer"}),
            "workers": users.count_documents({"role": "worker"}),
        },
        "workers": {
            "total": workers.count_documents({}),
            "available": workers.count_documents({
                "availability": "available",
                "is_active": True,
            }),
            "busy": workers.count_documents({
                "availability": "busy",
                "is_active": True,
            }),
            "offline": workers.count_documents({
                "$or": [
                    {"availability": "offline"},
                    {"availability": {"$exists": False}},
                ],
                "is_active": True,
            }),
        },
        "requests": {
            "total": requests.count_documents({}),
            "active": requests.count_documents({
                "status": {
                    "$in": [
                        "requested", "accepted", "confirmed",
                        "on_the_way", "arrived", "in_progress",
                    ]
                }
            }),
            "completed": requests.count_documents({
                "status": "completed"
            }),
            "cancelled": requests.count_documents({
                "status": "cancelled"
            }),
        },
    }
