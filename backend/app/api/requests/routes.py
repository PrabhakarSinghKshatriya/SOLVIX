import logging

from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, require_role
from app.database.connection import get_database
from app.schemas.service_request import CreateServiceRequest, StatusTransitionRequest, WorkerRequestAction
from app.services.worker_service import WorkerService
from app.services.notification_service import NotificationService
from app.services.service_request_service import (
    ServiceRequestService,
)
from app.models.service_request import ServiceRequestModel


logger = logging.getLogger(__name__)

def _require_saved_phone(user_id: str, role_label: str) -> None:
    """Require a usable phone number before creating/accepting a booking."""
    users = get_database()["users"]

    try:
        user_doc = users.find_one(
            {"_id": ObjectId(str(user_id))},
            {"phone": 1, "is_active": 1},
        )
    except Exception:
        user_doc = None

    phone = str((user_doc or {}).get("phone") or "")
    digits = "".join(character for character in phone if character.isdigit())

    if not user_doc or len(digits) < 10 or len(digits) > 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Add a valid phone number to your {role_label} account "
                "before continuing. Open your account phone settings and save it."
            ),
        )


def _safe_notify(user_id, title, message, event_type, booking_id=None):
    if not user_id:
        return
    try:
        NotificationService().create_notification(
            user_id=str(user_id),
            title=title,
            message=message,
            event_type=event_type,
            booking_id=str(booking_id) if booking_id else None,
        )
    except Exception:
        logger.exception("Notification delivery failed: %s", event_type)




router = APIRouter(
    prefix="/api/requests",
    tags=["Service Requests"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def create_service_request(
    data: CreateServiceRequest,
    current_user: dict = Depends(
        require_role("customer")
    ),
):
    _require_saved_phone(
        current_user["user_id"],
        "customer",
    )

    service = ServiceRequestService()

    request = service.create_request(
        customer_id=current_user["user_id"],
        service=data.service,
        description=data.description,
        latitude=data.latitude,
        longitude=data.longitude,
    )

    matched_workers_count = 0

    try:
        worker_service = WorkerService()

        workers = worker_service.match_workers(
            latitude=data.latitude,
            longitude=data.longitude,
            service=data.service,
        )

        request_id = request.get("id") or request.get("_id")

        if request_id:
            matched_request = service.match_request(
                request_id=str(request_id),
                workers=workers,
            )

            if matched_request:
                request = matched_request
                matched_workers_count = len(workers)

                for worker in workers:
                    worker_id = worker.get("user_id")
                    if worker_id:
                        _safe_notify(
                            worker_id,
                            "New service opportunity",
                            "A customer has requested "
                            + data.service
                            + ". Open SOLVIX to review it.",
                            "booking_created",
                            request_id,
                        )

    except Exception:
        logger.exception(
            "Automatic worker matching failed for service request %s",
            request.get("id", request.get("_id", "unknown")),
        )

    return {
        "success": True,
        "message": "Service request created successfully",
        "matched_workers_count": matched_workers_count,
        "request": request,
    }




# SOLVIX_PRIVATE_DASHBOARD_STATS_V1

def _dashboard_stats(owner_field: str, owner_id: str, role: str):
    db = get_database()
    collection = db["service_requests"]

    # The service-request collection name may be configured through the
    # service itself; use that collection for consistent dashboard data.
    service = ServiceRequestService()
    collection = service.requests

    if role == "worker":
        query = {"assigned_worker_id": owner_id}
    else:
        query = {"customer_id": owner_id}

    records = list(collection.find(query).sort("created_at", -1))
    statuses = [str(record.get("status", "requested")) for record in records]

    active_statuses = {
        "accepted",
        "confirmed",
        "on_the_way",
        "arrived",
        "in_progress",
    }
    completed = statuses.count("completed")
    cancelled = statuses.count("cancelled")
    denominator = completed + cancelled

    recent = [
        ServiceRequestModel.serialize(record)
        for record in records[:8]
    ]

    return {
        "success": True,
        "role": role,
        "total_jobs" if role == "worker" else "total_bookings": len(records),
        "active_jobs" if role == "worker" else "active_bookings": sum(
            status in active_statuses for status in statuses
        ),
        "completed_jobs" if role == "worker" else "completed_bookings": completed,
        "cancelled_jobs" if role == "worker" else "cancelled_bookings": cancelled,
        "completion_rate": round(completed * 100 / denominator, 1) if denominator else 0,
        "recent_requests": recent,
    }


@router.get("/worker/stats")
async def get_worker_dashboard_stats(
    current_user: dict = Depends(require_role("worker")),
):
    return _dashboard_stats(
        "assigned_worker_id",
        str(current_user["user_id"]),
        "worker",
    )


@router.get("/customer/stats")
async def get_customer_dashboard_stats(
    current_user: dict = Depends(require_role("customer")),
):
    return _dashboard_stats(
        "customer_id",
        str(current_user["user_id"]),
        "customer",
    )


@router.get("/worker/my-requests")
async def get_worker_service_requests(
    current_user: dict = Depends(require_role("worker")),
):
    service = ServiceRequestService()

    requests = service.get_worker_requests(
        current_user["user_id"]
    )

    return {
        "success": True,
        "count": len(requests),
        "requests": requests,
    }



# SOLVIX_SECURE_CONTACTS_V1
@router.get("/{request_id}/contacts")
async def get_service_request_contacts(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Reveal booking contact information only to the customer who owns
    the booking and the worker currently assigned to it.
    """
    if not ObjectId.is_valid(request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )

    db = get_database()
    request = db["service_requests"].find_one(
        {"_id": ObjectId(request_id)}
    )

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )

    user_id = str(current_user.get("user_id", ""))
    role = current_user.get("role")

    customer_id = str(request.get("customer_id", ""))
    assigned_worker_id = str(request.get("assigned_worker_id", ""))

    if role == "customer":
        if user_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot access this booking's contacts",
            )

        if not assigned_worker_id or assigned_worker_id in ("None", ""):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A worker must be assigned before contact details are available",
            )

        target_user_id = assigned_worker_id
        target_label = "worker"

    elif role == "worker":
        if not assigned_worker_id or user_id != assigned_worker_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the assigned worker can access customer contact details",
            )

        target_user_id = customer_id
        target_label = "customer"

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access this booking's contacts",
        )

    if not ObjectId.is_valid(target_user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact information not found",
        )

    target_user = db["users"].find_one(
        {"_id": ObjectId(target_user_id)},
        {"name": 1, "phone": 1},
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact information not found",
        )

    return {
        "success": True,
        "contact_type": target_label,
        "contact": {
            "name": target_user.get("name") or target_label.title(),
            "phone": target_user.get("phone") or "",
        },
    }


@router.get("/{request_id}")
async def get_service_request(
    request_id: str,
    current_user: dict = Depends(get_current_user),
):
    service = ServiceRequestService()
    request = service.get_request(request_id)

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )

    user_id = str(current_user["user_id"])
    role = current_user.get("role")

    if role == "customer":
        if str(request.get("customer_id")) != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this request",
            )

    elif role == "worker":
        matched_worker_ids = [
            str(worker_id)
            for worker_id in request.get("matched_worker_ids", [])
        ]
        assigned_worker_id = request.get("assigned_worker_id")

        if (
            user_id not in matched_worker_ids
            and str(assigned_worker_id) != user_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view this request",
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this request",
        )

    return {
        "success": True,
        "request": request,
    }

@router.get("")
async def get_my_service_requests(
    current_user: dict = Depends(
        require_role("customer")
    ),
):
    service = ServiceRequestService()

    requests = service.get_customer_requests(
        current_user["user_id"]
    )

    return {
        "success": True,
        "count": len(requests),
        "requests": requests,
    }


@router.patch("/{request_id}/status")
async def update_request_status(
    request_id: str,
    data: StatusTransitionRequest,
    current_user: dict = Depends(
        get_current_user
    ),
):
    request_service = ServiceRequestService()

    try:
        request = request_service.transition_status(
            request_id=request_id,
            user_id=current_user["user_id"],
            user_role=current_user["role"],
            new_status=data.status,
        )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service request not found",
            )

        labels = {
            "confirmed": "Booking confirmed",
            "on_the_way": "Worker is on the way",
            "arrived": "Worker has arrived",
            "in_progress": "Service has started",
            "completed": "Service completed",
            "cancelled": "Booking cancelled",
        }
        recipient_id = (
            request.get("customer_id")
            if current_user["role"] == "worker"
            else request.get("assigned_worker_id")
        )
        _safe_notify(
            recipient_id,
            labels.get(data.status, "Booking updated"),
            "Booking status changed to " + data.status.replace("_", " ") + ".",
            "booking_" + data.status,
            request_id,
        )

        return {
            "success": True,
            "message": "Request status updated successfully",
            "request": request,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{request_id}/match")
async def match_service_request(
    request_id: str,
    current_user: dict = Depends(require_role("customer")),
):
    request_service = ServiceRequestService()
    request = request_service.get_request(request_id)

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )

    if request["customer_id"] != current_user["user_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to match this request",
        )

    if request["status"] != "requested":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only requested bookings can be matched",
        )

    if request.get("assigned_worker_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A worker is already assigned to this request",
        )

    coordinates = request["location"]["coordinates"]
    longitude, latitude = coordinates

    worker_service = WorkerService()
    workers = worker_service.match_workers(
        latitude=latitude,
        longitude=longitude,
        service=request["service"],
    )

    matched_request = request_service.match_request(
        request_id=request_id,
        workers=workers,
    )

    if not matched_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found",
        )

    return {
        "success": True,
        "message": (
            "Matching workers found"
            if workers
            else "No matching workers found nearby"
        ),
        "count": len(workers),
        "workers": workers,
        "request": matched_request,
    }


@router.patch("/{request_id}/worker-action")
async def handle_worker_request(
    request_id: str,
    data: WorkerRequestAction,
    current_user: dict = Depends(require_role("worker")),
):
    if data.action == "accept":
        _require_saved_phone(
            current_user["user_id"],
            "worker",
        )

    service = ServiceRequestService()

    try:
        request = service.worker_action(
            request_id=request_id,
            worker_id=current_user["user_id"],
            action=data.action,
        )

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found or no longer available",
            )

        if data.action == "accept":
            _safe_notify(
                request.get("customer_id"),
                "Worker accepted your booking",
                "A worker accepted your "
                + request.get("service", "service")
                + " request.",
                "booking_accepted",
                request_id,
            )
        else:
            _safe_notify(
                request.get("customer_id"),
                "Worker declined the booking",
                "A worker declined your request. You can look for another worker.",
                "booking_rejected",
                request_id,
            )

        return {
            "success": True,
            "message": f"Request {data.action}ed successfully",
            "request": request,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
