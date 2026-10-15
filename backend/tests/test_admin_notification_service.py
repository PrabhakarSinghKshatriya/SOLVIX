from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.services.admin_notification_service import AdminNotificationService


def test_notification_is_created_for_each_active_configured_admin():
    admin_one = {"_id": ObjectId()}
    admin_two = {"_id": ObjectId()}

    db = MagicMock()
    db["users"].find.return_value = [admin_one, admin_two]

    with (
        patch(
            "app.services.admin_notification_service.get_database",
            return_value=db,
        ),
        patch(
            "app.services.admin_notification_service.settings.admin_emails",
            " ADMIN1@example.com,admin2@example.com ",
        ),
    ):
        count = AdminNotificationService().notify(
            title="New registration",
            message="A worker registered.",
            event_type="user_registered",
        )

    assert count == 2

    query = db["users"].find.call_args.args[0]
    assert query["email"]["$in"] == [
        "admin1@example.com",
        "admin2@example.com",
    ]
    assert query["role"] == "admin"
    assert query["is_active"] == {"$ne": False}

    documents = db["admin_notifications"].insert_many.call_args.args[0]
    assert len(documents) == 2
    assert {item["admin_id"] for item in documents} == {
        str(admin_one["_id"]),
        str(admin_two["_id"]),
    }

    for document in documents:
        assert document["title"] == "New registration"
        assert document["message"] == "A worker registered."
        assert document["event_type"] == "user_registered"
        assert document["is_read"] is False
        assert document["read_at"] is None
        assert document["created_at"] is not None


def test_notification_is_skipped_when_admin_emails_are_not_configured():
    db = MagicMock()

    with (
        patch(
            "app.services.admin_notification_service.get_database",
            return_value=db,
        ),
        patch(
            "app.services.admin_notification_service.settings.admin_emails",
            "",
        ),
    ):
        count = AdminNotificationService().notify(
            title="Test",
            message="Test notification",
            event_type="test",
        )

    assert count == 0
    db["users"].find.assert_not_called()
    db["admin_notifications"].insert_many.assert_not_called()


def test_notification_is_skipped_when_no_active_admin_is_found():
    db = MagicMock()
    db["users"].find.return_value = []

    with (
        patch(
            "app.services.admin_notification_service.get_database",
            return_value=db,
        ),
        patch(
            "app.services.admin_notification_service.settings.admin_emails",
            "admin@example.com",
        ),
    ):
        count = AdminNotificationService().notify(
            title="Test",
            message="Test notification",
            event_type="test",
        )

    assert count == 0
    db["admin_notifications"].insert_many.assert_not_called()


def test_database_insert_failure_is_propagated_to_caller():
    db = MagicMock()
    db["users"].find.return_value = [{"_id": ObjectId()}]
    db["admin_notifications"].insert_many.side_effect = RuntimeError(
        "database unavailable"
    )

    with (
        patch(
            "app.services.admin_notification_service.get_database",
            return_value=db,
        ),
        patch(
            "app.services.admin_notification_service.settings.admin_emails",
            "admin@example.com",
        ),
    ):
        service = AdminNotificationService()

        try:
            service.notify(
                title="Test",
                message="Test notification",
                event_type="test",
            )
        except RuntimeError as exc:
            assert str(exc) == "database unavailable"
        else:
            raise AssertionError("Expected database failure to propagate")
