from unittest.mock import MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.main import app


def test_metadata_failure_cleans_new_file_and_preserves_old_document():
    worker_id = str(ObjectId())
    old_file_id = ObjectId()
    new_file_id = ObjectId()

    old_record = {
        "worker_id": worker_id,
        "file_id": old_file_id,
        "filename": "previous.pdf",
        "status": "verified",
    }

    fake_db = MagicMock()
    fake_collection = fake_db["aadhaar_verifications"]
    fake_collection.find_one.return_value = old_record
    fake_collection.update_one.side_effect = RuntimeError(
        "metadata database unavailable"
    )

    fake_bucket = MagicMock()
    fake_bucket.upload_from_stream.return_value = new_file_id

    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": worker_id,
        "role": "worker",
    }

    test_client = TestClient(app, raise_server_exceptions=False)

    try:
        with (
            patch("app.api.aadhaar.routes._db", return_value=fake_db),
            patch("app.api.aadhaar.routes._bucket", return_value=fake_bucket),
        ):
            response = test_client.post(
                "/api/workers/aadhaar",
                files={
                    "file": (
                        "new-document.pdf",
                        b"%PDF-1.7 test document",
                        "application/pdf",
                    )
                },
                headers={"Authorization": "Bearer test-token"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500

    fake_bucket.upload_from_stream.assert_called_once()
    fake_bucket.delete.assert_called_once_with(new_file_id)

    # A failed metadata update must not trigger deletion of the old file.
    assert old_file_id != new_file_id
    assert fake_bucket.delete.call_args.args[0] != old_file_id
