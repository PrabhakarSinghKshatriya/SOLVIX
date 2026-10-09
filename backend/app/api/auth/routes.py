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

from datetime import datetime, timezone
from typing import Literal

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from pydantic import BaseModel

from app.config import settings
from app.database.connection import get_database
from app.models.user import UserModel
from pymongo.errors import DuplicateKeyError


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



class GoogleLoginRequest(BaseModel):
    credential: str
    role: Literal["customer", "worker"] = "customer"


@router.post("/google", response_model=TokenResponse)
async def google_login(data: GoogleLoginRequest):
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google login is not configured. Set GOOGLE_CLIENT_ID in backend/.env.",
        )

    try:
        claims = id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google sign-in verification failed. Please try again.",
        ) from exc

    email = str(claims.get("email", "")).strip().lower()
    google_sub = str(claims.get("sub", "")).strip()
    name = str(claims.get("name", "")).strip()

    if not email or not google_sub or claims.get("email_verified") is not True:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account email could not be verified.",
        )

    users = get_database()[UserModel.collection_name]
    user = users.find_one({"email": email})

    if user is None:
        now = datetime.now(timezone.utc)
        document = {
            "name": name or email.split("@")[0],
            "email": email,
            "phone": None,
            "password_hash": None,
            "role": data.role,
            "google_sub": google_sub,
            "is_active": True,
            "is_verified": True,
            "created_at": now,
            "updated_at": now,
        }

        try:
            result = users.insert_one(document)
            document["_id"] = result.inserted_id
            user = document
        except DuplicateKeyError:
            user = users.find_one({"email": email})
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not create or retrieve the Google account.",
                )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is disabled.",
        )

    # Link a verified Google identity to the existing email account.
    if not user.get("google_sub"):
        users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "google_sub": google_sub,
                    "is_verified": True,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    user_data = UserModel.serialize(user)
    access_token = create_access_token(
        user_id=user_data["id"],
        role=user_data["role"],
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data,
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
