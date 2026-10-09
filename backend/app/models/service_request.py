from datetime import datetime, timezone


class ServiceRequestModel:
    collection_name = "service_requests"

    @staticmethod
    def create_document(
        customer_id: str,
        service: str,
        description: str | None,
        latitude: float,
        longitude: float,
    ) -> dict:

        now = datetime.now(timezone.utc)

        return {
            "customer_id": customer_id,

            "service": service.strip(),

            "description": (
                description.strip()
                if description
                else None
            ),

            "location": {
                "type": "Point",
                "coordinates": [
                    longitude,
                    latitude,
                ],
            },

            "status": "requested",

            "assigned_worker_id": None,

            "matched_worker_ids": [],

            "match_status": "pending",

            "matched_worker_ids": [],

            "match_status": "pending",

            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def serialize(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "customer_id": document["customer_id"],
            "service": document["service"],
            "description": document.get(
                "description"
            ),
            "location": document["location"],
            "status": document.get(
                "status",
                "requested",
            ),
            "assigned_worker_id": document.get(
                "assigned_worker_id"
            ),
            "matched_worker_ids": document.get(
                "matched_worker_ids",
                []
            ),
            "match_status": document.get(
                "match_status",
                "pending"
            ),
            "matched_worker_ids": document.get(
                "matched_worker_ids",
                []
            ),
            "match_status": document.get(
                "match_status",
                "pending"
            ),
            "created_at": document.get(
                "created_at"
            ),
            "updated_at": document.get(
                "updated_at"
            ),
        }
