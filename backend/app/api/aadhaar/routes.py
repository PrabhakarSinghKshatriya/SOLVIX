from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal

from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymongo import DESCENDING
from gridfs import GridFSBucket
from gridfs.errors import NoFile

from app.config import settings
from app.database.connection import get_database
from app.dependencies import require_admin, require_role

router = APIRouter(tags=["Aadhaar verification"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _db():
    return get_database()


def _bucket():
    # Files are stored in GridFS, not in public/static storage.
    return GridFSBucket(_db(), bucket_name="private_aadhaar")


def _admin_ids():
    emails = [
        item.strip().lower()
        for item in settings.admin_emails.split(",")
        if item.strip()
    ]
    if not emails:
        return []

    return [
        str(item["_id"])
        for item in _db()["users"].find(
            {
                "email": {"$in": emails},
                "role": "admin",
                "is_active": {"$ne": False},
            },
            {"_id": 1},
        )
    ]


def _notify_admins(title: str, message: str, event_type: str):
    db = _db()
    now = datetime.now(timezone.utc)
    docs = [
        {
            "admin_id": admin_id,
            "title": title,
            "message": message,
            "event_type": event_type,
            "is_read": False,
            "created_at": now,
            "read_at": None,
        }
        for admin_id in _admin_ids()
    ]
    if docs:
        db["admin_notifications"].insert_many(docs)


def _serialize(record: dict) -> dict:
    return {
        "worker_id": record["worker_id"],
        "status": record.get("status", "pending"),
        "filename": record.get("filename"),
        "content_type": record.get("content_type"),
        "uploaded_at": record.get("uploaded_at"),
        "reviewed_at": record.get("reviewed_at"),
        "rejection_reason": record.get("rejection_reason"),
    }


class AadhaarDecision(BaseModel):
    decision: Literal["verified", "rejected"]
    rejection_reason: str | None = Field(default=None, max_length=1000)


class AdminNotificationRead(BaseModel):
    notification_id: str


@router.get("/api/workers/aadhaar")
def worker_aadhaar_status(
    current_user: dict = Depends(require_role("worker")),
):
    record = _db()["aadhaar_verifications"].find_one(
        {"worker_id": current_user["user_id"]},
        {"_id": 0, "file_id": 0},
    )
    if not record:
        return {
            "worker_id": current_user["user_id"],
            "status": "not_uploaded",
            "filename": None,
            "uploaded_at": None,
            "reviewed_at": None,
            "rejection_reason": None,
        }
    return _serialize(record)


@router.post("/api/workers/aadhaar")
async def upload_worker_aadhaar(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_role("worker")),
):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Upload a PDF, JPEG, PNG, or WebP document.",
        )

    filename = Path(file.filename or "aadhaar-document").name
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Maximum upload size is 10 MB.")

    # Check basic file signatures instead of trusting Content-Type alone.
    if content_type == "application/pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="The file is not a valid PDF.")
    if content_type == "image/jpeg" and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=400, detail="The file is not a valid JPEG image.")
    if content_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=400, detail="The file is not a valid PNG image.")
    if content_type == "image/webp" and (
        len(content) < 12 or content[:4] != b"RIFF" or content[8:12] != b"WEBP"
    ):
        raise HTTPException(status_code=400, detail="The file is not a valid WebP image.")

    db = _db()
    collection = db["aadhaar_verifications"]
    worker_id = current_user["user_id"]
    now = datetime.now(timezone.utc)

    # Keep one bucket instance so cleanup targets the exact uploaded file.
    bucket = _bucket()
    file_id = bucket.upload_from_stream(
        filename,
        BytesIO(content),
        metadata={
            "worker_id": worker_id,
            "content_type": content_type,
            "purpose": "private_aadhaar_verification",
        },
    )

    try:
        old = collection.find_one({"worker_id": worker_id})
        collection.update_one(
            {"worker_id": worker_id},
            {
                "$set": {
                    "worker_id": worker_id,
                    "file_id": file_id,
                    "filename": filename,
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "status": "pending",
                    "rejection_reason": None,
                    "uploaded_at": now,
                    "reviewed_at": None,
                    "reviewed_by": None,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
    except Exception:
        # Metadata was not saved. Remove only the newly uploaded file;
        # preserve the previous metadata and document.
        try:
            bucket.delete(file_id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not clean up Aadhaar upload after metadata failure."
            )
        raise

    # Remove old private file only after new metadata has been saved.
    if old and old.get("file_id") and old["file_id"] != file_id:
        try:
            bucket.delete(old["file_id"])
        except Exception:
            # A stale orphan is safer than failing a successful resubmission.
            pass

    user = db["users"].find_one(
        {"_id": ObjectId(worker_id)},
        {"name": 1, "email": 1},
    ) if ObjectId.is_valid(worker_id) else None
    label = (user or {}).get("name") or worker_id
    try:
        _notify_admins(
            "Aadhaar document submitted",
            f"{label} uploaded or resubmitted an Aadhaar document for review.",
            "aadhaar_uploaded",
        )
    except Exception:
        # Upload and metadata are already saved; notification failure must
        # not make the worker's successful upload appear to have failed.
        import logging
        logging.getLogger(__name__).exception(
            "Failed to notify admins about an Aadhaar upload."
        )

    return {
        "success": True,
        "message": "Document uploaded. Admin verification is pending.",
        "status": "pending",
    }


@router.get("/api/admin/aadhaar")
def list_aadhaar_verifications(
    status_filter: str = Query(default="pending", alias="status"),
    limit: int = Query(default=100, ge=1, le=200),
    admin: dict = Depends(require_admin),
):
    if status_filter not in {"pending", "verified", "rejected", "all"}:
        raise HTTPException(status_code=400, detail="Invalid status filter.")

    db = _db()
    query = {} if status_filter == "all" else {"status": status_filter}
    records = list(
        db["aadhaar_verifications"]
        .find(query, {"file_id": 0, "size_bytes": 0})
        .sort("uploaded_at", DESCENDING)
        .limit(limit)
    )

    worker_ids = [r.get("worker_id") for r in records]
    users = {}
    if worker_ids:
        for item in db["users"].find(
            {"_id": {"$in": [
                ObjectId(uid) for uid in worker_ids if ObjectId.is_valid(uid)
            ]}},
            {"name": 1, "email": 1, "phone": 1},
        ):
            users[str(item["_id"])] = {
                "name": item.get("name"),
                "email": item.get("email"),
                "phone": item.get("phone"),
            }

    items = []
    for record in records:
        item = _serialize(record)
        item["worker"] = users.get(record["worker_id"], {})
        items.append(item)

    return {"success": True, "items": items, "count": len(items)}


@router.get("/api/admin/aadhaar/{worker_id}/document")
def preview_aadhaar_document(
    worker_id: str,
    admin: dict = Depends(require_admin),
):
    record = _db()["aadhaar_verifications"].find_one({"worker_id": worker_id})
    if not record or not record.get("file_id"):
        raise HTTPException(status_code=404, detail="Aadhaar document not found.")

    try:
        stream = _bucket().open_download_stream(record["file_id"])
        try:
            content = stream.read()
        finally:
            stream.close()
    except NoFile as exc:
        raise HTTPException(
            status_code=404,
            detail="The stored document could not be found.",
        ) from exc
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to retrieve a private Aadhaar document."
        )
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve the document right now.",
        ) from exc

    content_type = record.get("content_type", "application/octet-stream")
    safe_filename = Path(
        record.get("filename") or "aadhaar-document"
    ).name
    safe_filename = (
        safe_filename
        .replace("\\", "_")
        .replace('"', "_")
        .replace("\r", "_")
        .replace("\n", "_")
    )
    return StreamingResponse(
        BytesIO(content),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/api/admin/aadhaar/{worker_id}/decision")
def decide_aadhaar_verification(
    worker_id: str,
    data: AadhaarDecision,
    admin: dict = Depends(require_admin),
):
    if data.decision == "rejected" and not (data.rejection_reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail="A rejection reason is required.",
        )

    db = _db()
    now = datetime.now(timezone.utc)
    result = db["aadhaar_verifications"].update_one(
        {
            "worker_id": worker_id,
            "file_id": {"$exists": True},
        },
        {
            "$set": {
                "status": data.decision,
                "rejection_reason": (
                    data.rejection_reason.strip()
                    if data.decision == "rejected"
                    else None
                ),
                "reviewed_at": now,
                "reviewed_by": admin["user_id"],
                "updated_at": now,
            }
        },
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Uploaded document not found.")

    # Notify the worker through the existing worker notification system.
    try:
        from app.services.notification_service import NotificationService
        title = (
            "Aadhaar verified"
            if data.decision == "verified"
            else "Aadhaar verification rejected"
        )
        message = (
            "Your Aadhaar document has been verified. You can now accept paid jobs."
            if data.decision == "verified"
            else f"Please upload the document again. Reason: {data.rejection_reason.strip()}"
        )
        NotificationService().create_notification(
            user_id=worker_id,
            title=title,
            message=message,
            event_type=f"aadhaar_{data.decision}",
        )
    except Exception:
        # The verification decision itself must remain saved if notification fails.
        pass

    return {
        "success": True,
        "worker_id": worker_id,
        "status": data.decision,
        "rejection_reason": (
            data.rejection_reason.strip()
            if data.decision == "rejected"
            else None
        ),
    }


@router.get("/api/admin/notifications")
def list_admin_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    unread_only: bool = False,
    admin: dict = Depends(require_admin),
):
    db = _db()
    query = {"admin_id": admin["user_id"]}
    if unread_only:
        query["is_read"] = False

    items = list(
        db["admin_notifications"].find(query)
        .sort("created_at", DESCENDING)
        .limit(limit)
    )
    unread_count = db["admin_notifications"].count_documents(
        {"admin_id": admin["user_id"], "is_read": False}
    )
    return {
        "success": True,
        "unread_count": unread_count,
        "items": [
            {
                "id": str(item["_id"]),
                "title": item["title"],
                "message": item["message"],
                "event_type": item["event_type"],
                "is_read": item.get("is_read", False),
                "created_at": item.get("created_at"),
                "read_at": item.get("read_at"),
            }
            for item in items
        ],
    }


@router.patch("/api/admin/notifications/{notification_id}/read")
def mark_admin_notification_read(
    notification_id: str,
    admin: dict = Depends(require_admin),
):
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=404, detail="Notification not found.")

    now = datetime.now(timezone.utc)
    result = _db()["admin_notifications"].update_one(
        {
            "_id": ObjectId(notification_id),
            "admin_id": admin["user_id"],
        },
        {"$set": {"is_read": True, "read_at": now}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"success": True}


@router.patch("/api/admin/notifications/read-all")
def mark_all_admin_notifications_read(
    admin: dict = Depends(require_admin),
):
    result = _db()["admin_notifications"].update_many(
        {"admin_id": admin["user_id"], "is_read": False},
        {
            "$set": {
                "is_read": True,
                "read_at": datetime.now(timezone.utc),
            }
        },
    )
    return {"success": True, "updated_count": result.modified_count}
