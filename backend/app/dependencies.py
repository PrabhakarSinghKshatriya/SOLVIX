from typing import Callable

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.database.connection import get_database


security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(credentials.credentials)

        user_id = payload.get("sub")

        if not user_id or not ObjectId.is_valid(user_id):
            raise unauthorized

        db = get_database()

        user = db["users"].find_one(
            {"_id": ObjectId(user_id)}
        )

        if not user or not user.get("is_active", True):
            raise unauthorized

        role = user.get("role")

        if role not in ("customer", "worker"):
            raise unauthorized

        return {
            "user_id": str(user["_id"]),
            "role": role,
        }

    except HTTPException:
        raise
    except (ValueError, TypeError) as exc:
        raise unauthorized from exc


def require_role(*allowed_roles: str) -> Callable:
    async def role_checker(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )

        return current_user

    return role_checker
