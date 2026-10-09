from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId


class UserModel:
    collection_name = "users"

    @staticmethod
    def create_document(
        name: str,
        email: str,
        password_hash: str,
        role: str,
        phone: Optional[str] = None,
    ) -> dict:
        now = datetime.now(timezone.utc)

        return {
            "name": name.strip(),
            "email": email.strip().lower(),
            "phone": phone,
            "password_hash": password_hash,
            "role": role,
            "is_active": True,
            "is_verified": False,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def serialize(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "name": document["name"],
            "email": document["email"],
            "phone": document.get("phone"),
            "role": document["role"],
            "is_active": document.get("is_active", True),
            "is_verified": document.get("is_verified", False),
            "created_at": document.get("created_at"),
            "updated_at": document.get("updated_at"),
        }