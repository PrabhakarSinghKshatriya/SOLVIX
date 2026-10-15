import logging
from datetime import datetime, timezone

from app.config import settings
from app.database.connection import get_database

logger = logging.getLogger(__name__)


class AdminNotificationService:
    """Store private, admin-only notifications separately from user alerts."""

    def __init__(self):
        self.db = get_database()

    def notify(
        self,
        title: str,
        message: str,
        event_type: str,
    ) -> int:
        emails = [
            email.strip().lower()
            for email in (settings.admin_emails or "").split(",")
            if email.strip()
        ]

        if not emails:
            logger.warning(
                "Admin notification skipped: ADMIN_EMAILS is not configured."
            )
            return 0

        admins = self.db["users"].find(
            {
                "email": {"$in": emails},
                "role": "admin",
                "is_active": {"$ne": False},
            },
            {"_id": 1},
        )

        now = datetime.now(timezone.utc)
        documents = [
            {
                "admin_id": str(admin["_id"]),
                "title": title,
                "message": message,
                "event_type": event_type,
                "is_read": False,
                "created_at": now,
                "read_at": None,
            }
            for admin in admins
        ]

        if not documents:
            logger.warning(
                "Admin notification skipped: no active configured admin found."
            )
            return 0

        self.db["admin_notifications"].insert_many(documents)
        return len(documents)
