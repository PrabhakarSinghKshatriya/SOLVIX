import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, require_role
from app.schemas.service_request import CreateServiceRequest, StatusTransitionRequest, WorkerRequestAction
from app.services.worker_service import WorkerService
from app.services.notification_service import NotificationService
from app.services.service_request_service import (
    ServiceRequestService,
)


logger = logging.getLogger(__name__)

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
