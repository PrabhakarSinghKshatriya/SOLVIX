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

from app.core.security import create_access_token, hash_password
from app.schemas.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    VerifyLoginOTPRequest,
)
from app.services.auth_service import AuthService

from datetime import datetime, timezone, timedelta
from typing import Literal
import hashlib
import logging

logger = logging.getLogger(__name__)
import secrets
import smtplib
from email.message import EmailMessage

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



def _otp_digest(email: str, otp: str) -> str:
    value = f"{email.strip().lower()}:{otp}:{settings.jwt_secret_key}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _send_login_otp(email: str, otp: str) -> None:
    """Send login OTP using the Resend HTTPS API."""
    import os
    import requests

    api_key = os.getenv("RESEND_API_KEY", "").strip()
    sender = os.getenv(
        "RESEND_FROM_EMAIL",
        "onboarding@resend.dev",
    ).strip()

    if not api_key:
        logger.error("RESEND_API_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email OTP service is not configured.",
        )

    payload = {
        "from": sender,
        "to": [email],
        "subject": "Your SOLVIX login verification code",
        "text": (
            f"Your SOLVIX login OTP is {otp}. "
            "It expires in 5 minutes. "
            "Do not share this code with anyone."
        ),
    }

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )

        if not response.ok:
            logger.error(
                "SOLVIX Resend API rejected email: status=%s response=%s",
                response.status_code,
                response.text[:500],
            )

        response.raise_for_status()
        logger.info("SOLVIX login OTP email accepted by Resend.")

    except requests.RequestException as exc:
        logger.exception(
            "SOLVIX Resend email delivery failed: exception_type=%s",
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not send the login verification email. Please try again later.",
        ) from exc
