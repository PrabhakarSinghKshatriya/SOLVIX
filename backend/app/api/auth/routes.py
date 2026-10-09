from app.schemas.worker import (
    CreateWorkerProfileRequest,
    LocationUpdateRequest,
    NearbyWorkersRequest,
    UpdateWorkerProfileRequest,
    WorkerMatchingRequest,
    WorkerResponse,
)
from app.schemas.service_request import (
    CreateServiceRequest,
    StatusTransitionRequest,
    WorkerRequestAction,
)

from fastapi import APIRouter, HTTPException, status
from app.dependencies import get_current_user, require_role
from fastapi import Depends

from app.core.security import create_access_token
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(data: RegisterRequest):

    auth_service = AuthService()

    try:
        user = auth_service.create_user(
            name=data.name,
            email=data.email,
            password=data.password,
            role=data.role,
            phone=data.phone,
        )

        return user

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
)
async def login_user(data: LoginRequest):

    auth_service = AuthService()

    user = auth_service.authenticate_user(
        email=data.email,
        password=data.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(
        user_id=user["id"],
        role=user["role"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "user": current_user,
    }

@router.get("/customer-test")
async def customer_test(
    current_user: dict = Depends(
        require_role("customer")
    ),
):
    return {
        "success": True,
        "message": "Customer access granted",
        "user": current_user,
    }


@router.get("/worker-test")
async def worker_test(
    current_user: dict = Depends(
        require_role("worker")
    ),
):
    return {
        "success": True,
        "message": "Worker access granted",
        "user": current_user,
    }
