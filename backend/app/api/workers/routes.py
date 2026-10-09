from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import require_role
from app.schemas.worker import (
    CreateWorkerProfileRequest,
    LocationUpdateRequest,
    NearbyWorkersRequest,
    UpdateWorkerProfileRequest,
    WorkerMatchingRequest,
    WorkerResponse,
)
from app.services.worker_service import WorkerService


router = APIRouter(
    prefix="/api/workers",
    tags=["Workers"],
)


@router.post(
    "/profile",
    response_model=WorkerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_worker_profile(
    data: CreateWorkerProfileRequest,
    current_user: dict = Depends(
        require_role("worker")
    ),
):
    worker_service = WorkerService()

    try:
        return worker_service.create_profile(
            user_id=current_user["user_id"],
            profession=data.profession,
            skills=data.skills,
            experience_years=data.experience_years,
            service_radius_km=data.service_radius_km,
            bio=data.bio,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/profile",
    response_model=WorkerResponse,
)
async def get_worker_profile(
    current_user: dict = Depends(
        require_role("worker")
    ),
):
    worker_service = WorkerService()

    profile = worker_service.get_profile(
        current_user["user_id"]
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    return profile


@router.patch(
    "/profile",
    response_model=WorkerResponse,
)
async def update_worker_profile(
    data: UpdateWorkerProfileRequest,
    current_user: dict = Depends(
        require_role("worker")
    ),
):
    worker_service = WorkerService()

    profile = worker_service.update_profile(
        user_id=current_user["user_id"],
        updates=data.model_dump(exclude_unset=True),
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    return profile


@router.patch(
    "/location",
    response_model=WorkerResponse,
)
async def update_worker_location(
    data: LocationUpdateRequest,
    current_user: dict = Depends(
        require_role("worker")
    ),
):
    worker_service = WorkerService()

    profile = worker_service.update_location(
        user_id=current_user["user_id"],
        latitude=data.latitude,
        longitude=data.longitude,
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found",
        )

    return profile


@router.post(
    "/nearby",
)
async def find_nearby_workers(
    data: NearbyWorkersRequest,
    current_user: dict = Depends(
        require_role("customer")
    ),
):
    worker_service = WorkerService()

    workers = worker_service.find_nearby_workers(
        latitude=data.latitude,
        longitude=data.longitude,
        max_distance_km=data.radius_km,
    )

    return {
        "success": True,
        "count": len(workers),
        "radius_km": data.radius_km,
        "workers": workers,
    }


@router.post(
    "/match",
)
async def match_workers(
    data: WorkerMatchingRequest,
    current_user: dict = Depends(
        require_role("customer")
    ),
):
    worker_service = WorkerService()

    workers = worker_service.match_workers(
        latitude=data.latitude,
        longitude=data.longitude,
        service=data.service,
        radius_km=data.radius_km,
    )

    return {
        "success": True,
        "service": data.service,
        "count": len(workers),
        "workers": workers,
    }
