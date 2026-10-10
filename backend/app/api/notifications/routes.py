from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from app.services.notification_service import NotificationService


router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)


@router.get("")
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    unread_only: bool = False,
    current_user: dict = Depends(get_current_user),
):
    service = NotificationService()

    result = service.list_notifications(
        user_id=current_user["user_id"],
        limit=limit,
        unread_only=unread_only,
    )

    return {
        "success": True,
        **result,
    }


@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
):
    service = NotificationService()

    notification = service.mark_read(
        notification_id=notification_id,
        user_id=current_user["user_id"],
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return {
        "success": True,
        "notification": notification,
    }


@router.patch("/read-all")
async def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
):
    service = NotificationService()

    updated_count = service.mark_all_read(
        user_id=current_user["user_id"]
    )

    return {
        "success": True,
        "updated_count": updated_count,
        "unread_count": 0,
    }
