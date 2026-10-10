from datetime import datetime, timezone

from bson import ObjectId
from pymongo import DESCENDING

from app.database.connection import get_database


class NotificationService:
    COLLECTION = "notifications"

    def __init__(self):
        self.db = get_database()
        self.notifications = self.db[self.COLLECTION]

    def create_notification(
        self,
        user_id: str,
        title: str,
        message: str,
        event_type: str,
        booking_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("Notification recipient is required")

        now = datetime.now(timezone.utc)

        document = {
            "user_id": user_id,
            "title": title.strip(),
            "message": message.strip(),
            "event_type": event_type,
            "booking_id": booking_id,
            "is_read": False,
            "created_at": now,
            "read_at": None,
        }

        result = self.notifications.insert_one(document)
        document["_id"] = result.inserted_id

        return self.serialize(document)

    @staticmethod
    def serialize(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "title": document["title"],
            "message": document["message"],
            "event_type": document["event_type"],
            "booking_id": document.get("booking_id"),
            "is_read": document.get("is_read", False),
            "created_at": document.get("created_at"),
            "read_at": document.get("read_at"),
        }

    def list_notifications(
        self,
        user_id: str,
        limit: int = 50,
        unread_only: bool = False,
    ) -> dict:
        query = {"user_id": user_id}

        if unread_only:
            query["is_read"] = False

        items = self.notifications.find(query).sort(
            "created_at", DESCENDING
        ).limit(limit)

        unread_count = self.notifications.count_documents({
            "user_id": user_id,
            "is_read": False,
        })

        return {
            "notifications": [
                self.serialize(item) for item in items
            ],
            "unread_count": unread_count,
        }

    def mark_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> dict | None:
        if not ObjectId.is_valid(notification_id):
            return None

        result = self.notifications.find_one_and_update(
            {
                "_id": ObjectId(notification_id),
                "user_id": user_id,
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc),
                }
            },
            return_document=True,
        )

        return self.serialize(result) if result else None

    def mark_all_read(self, user_id: str) -> int:
        result = self.notifications.update_many(
            {
                "user_id": user_id,
                "is_read": False,
            },
            {
                "$set": {
                    "is_read": True,
                    "read_at": datetime.now(timezone.utc),
                }
            },
        )

        return result.modified_count
