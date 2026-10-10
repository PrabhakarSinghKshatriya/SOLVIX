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


@router.post("/login")
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

    email = data.email.strip().lower()
    otp = f"{secrets.randbelow(1_000_000):06d}"

    # Send first; store only the digest, never the raw OTP.
    _send_login_otp(email, otp)

    now = datetime.now(timezone.utc)
    collection = get_database()["login_otps"]
    collection.delete_many({"email": email})
    collection.insert_one({
        "email": email,
        "otp_digest": _otp_digest(email, otp),
        "attempts": 0,
        "created_at": now,
        "expires_at": now + timedelta(minutes=5),
    })

    return {
        "success": True,
        "otp_required": True,
        "email": email,
        "message": "A verification code has been sent to your email.",
    }


@router.post("/login/verify-otp", response_model=TokenResponse)
async def verify_login_otp(data: VerifyLoginOTPRequest):
    email = data.email.strip().lower()
    collection = get_database()["login_otps"]
    record = collection.find_one({"email": email})
    now = datetime.now(timezone.utc)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP request found. Please log in again.",
        )

    expires_at = record.get("expires_at")
    if not expires_at or expires_at <= now:
        collection.delete_many({"email": email})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please log in again.",
        )

    if record.get("attempts", 0) >= 5:
        collection.delete_many({"email": email})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect OTP attempts. Please log in again.",
        )

    if not secrets.compare_digest(
        record.get("otp_digest", ""),
        _otp_digest(email, data.otp),
    ):
        collection.update_one(
            {"_id": record["_id"]},
            {"$inc": {"attempts": 1}},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    user_doc = get_database()[UserModel.collection_name].find_one(
        {"email": email}
    )
    if not user_doc or not user_doc.get("is_active", True):
        collection.delete_many({"email": email})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account is unavailable.",
        )

    user = UserModel.serialize(user_doc)
    collection.delete_many({"email": email})

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




@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """
    Request a password-reset OTP.
    The response is generic to avoid revealing whether an account exists.
    """
    email = data.email.strip().lower()
    generic_response = {
        "success": True,
        "message": (
            "If an account exists for this email, a password-reset "
            "code will be sent shortly."
        ),
    }

    users = get_database()[UserModel.collection_name]
    user = users.find_one({"email": email})

    # Do not disclose whether this email is registered.
    if not user or not user.get("is_active", True) or not user.get("password_hash"):
        return generic_response

    otp = f"{secrets.randbelow(1_000_000):06d}"

    try:
        message = EmailMessage()
        message["Subject"] = "Your SOLVIX password-reset code"
        message["From"] = settings.email_from or settings.smtp_username
        message["To"] = email
        message.set_content(
            f"Your SOLVIX password-reset OTP is {otp}. "
            "It expires in 5 minutes. Do not share this code with anyone."
        )

        if not settings.smtp_username or not settings.smtp_password:
            return generic_response

        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=15
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except Exception:
        # Avoid exposing account existence or internal email errors.
        return generic_response

    now = datetime.now(timezone.utc)
    collection = get_database()["password_reset_otps"]
    collection.delete_many({"email": email})
    collection.insert_one({
        "email": email,
        "otp_digest": _otp_digest(email, otp),
        "attempts": 0,
        "created_at": now,
        "expires_at": now + timedelta(minutes=5),
    })

    return generic_response


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest):
    email = data.email.strip().lower()
    collection = get_database()["password_reset_otps"]
    record = collection.find_one({"email": email})
    now = datetime.now(timezone.utc)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password-reset code. Request a new code.",
        )

    expires_at = record.get("expires_at")
    if not expires_at or expires_at <= now:
        collection.delete_many({"email": email})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password-reset code has expired. Request a new code.",
        )

    if record.get("attempts", 0) >= 5:
        collection.delete_many({"email": email})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Request a new code.",
        )

    if not secrets.compare_digest(
        record.get("otp_digest", ""),
        _otp_digest(email, data.otp),
    ):
        collection.update_one(
            {"_id": record["_id"]},
            {"$inc": {"attempts": 1}},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password-reset code.",
        )

    users = get_database()[UserModel.collection_name]
    user = users.find_one({"email": email})

    if not user or not user.get("is_active", True) or not user.get("password_hash"):
        collection.delete_many({"email": email})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account cannot reset its password.",
        )

    users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(data.new_password),
                "updated_at": now,
            }
        },
    )

    collection.delete_many({"email": email})

    # Invalidate any pending login OTP for this account.
    get_database()["login_otps"].delete_many({"email": email})

    return {
        "success": True,
        "message": "Password reset successfully. You can now log in.",
    }


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
