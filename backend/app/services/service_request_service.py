from datetime import datetime, timezone

from app.database.connection import get_database
from app.models.service_request import ServiceRequestModel


class ServiceRequestService:

    def __init__(self):
        self.db = get_database()
        self.requests = self.db[
            ServiceRequestModel.collection_name
        ]

    def create_request(
        self,
        customer_id: str,
        service: str,
        description: str | None,
        latitude: float,
        longitude: float,
    ) -> dict:

        document = ServiceRequestModel.create_document(
            customer_id=customer_id,
            service=service,
            description=description,
            latitude=latitude,
            longitude=longitude,
        )

        result = self.requests.insert_one(
            document
        )

        document["_id"] = result.inserted_id

        return ServiceRequestModel.serialize(
            document
        )

    def get_request(
        self,
        request_id,
    ) -> dict | None:

        from bson import ObjectId

        try:
            object_id = ObjectId(request_id)
        except Exception:
            return None

        request = self.requests.find_one(
            {"_id": object_id}
        )

        if not request:
            return None

        return ServiceRequestModel.serialize(
            request
        )

    def get_customer_requests(
        self,
        customer_id: str,
    ) -> list[dict]:

        cursor = self.requests.find(
            {"customer_id": customer_id}
        ).sort(
            "created_at",
            -1,
        )

        return [
            ServiceRequestModel.serialize(
                request
            )
            for request in cursor
        ]


    def match_request(
        self,
        request_id: str,
        workers: list[dict],
    ) -> dict | None:

        from bson import ObjectId

        try:
            object_id = ObjectId(request_id)
        except Exception:
            return None

        worker_ids = [
            worker["user_id"]
            for worker in workers
            if worker.get("user_id")
        ]

        now = datetime.now(timezone.utc)

        result = self.requests.find_one_and_update(
            {"_id": object_id},
            {
                "$set": {
                    "matched_worker_ids": worker_ids,
                    "match_status": (
                        "matched"
                        if worker_ids
                        else "no_match"
                    ),
                    "updated_at": now,
                }
            },
            return_document=True,
        )

        if not result:
            return None

        return ServiceRequestModel.serialize(
            result
        )


    def worker_action(
        self,
        request_id: str,
        worker_id: str,
        action: str,
    ) -> dict | None:
        from bson import ObjectId
        from pymongo import ReturnDocument

        try:
            object_id = ObjectId(request_id)
        except Exception:
            return None

        if action not in ("accept", "reject"):
            raise ValueError("Invalid worker action")

        now = datetime.now(timezone.utc)

        def transaction_work(session):
            request = self.requests.find_one(
                {"_id": object_id},
                session=session,
            )

            if not request:
                return None

            matched_worker_ids = request.get(
                "matched_worker_ids",
                [],
            )

            if worker_id not in matched_worker_ids:
                raise ValueError(
                    "Worker is not matched with this request"
                )

            if request.get("status", "requested") != "requested":
                raise ValueError(
                    "This request is no longer available"
                )

            if action == "reject":
                result = self.requests.find_one_and_update(
                    {
                        "_id": object_id,
                        "status": "requested",
                        "assigned_worker_id": None,
                        "matched_worker_ids": worker_id,
                    },
                    {
                        "$set": {
                            "status": "rejected",
                            "match_status": "rejected",
                            "updated_at": now,
                        }
                    },
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )

                if not result:
                    raise ValueError(
                        "Request was already processed"
                    )

                return result

            worker_result = self.db["workers"].update_one(
                {
                    "user_id": worker_id,
                    "availability": "available",
                    "is_active": True,
                },
                {
                    "$set": {
                        "availability": "busy",
                        "updated_at": now,
                    }
                },
                session=session,
            )

            if worker_result.modified_count != 1:
                raise ValueError(
                    "Worker is not available to accept requests"
                )

            result = self.requests.find_one_and_update(
                {
                    "_id": object_id,
                    "status": "requested",
                    "assigned_worker_id": None,
                    "matched_worker_ids": worker_id,
                },
                {
                    "$set": {
                        "status": "accepted",
                        "assigned_worker_id": worker_id,
                        "match_status": "assigned",
                        "updated_at": now,
                    }
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )

            if not result:
                raise ValueError(
                    "Request was already processed"
                )

            return result

        with self.db.client.start_session() as session:
            result = session.with_transaction(transaction_work)

        if result is None:
            return None

        return ServiceRequestModel.serialize(result)

    def transition_status(
        self,
        request_id: str,
        user_id: str,
        user_role: str,
        new_status: str,
    ) -> dict | None:
        from bson import ObjectId
        from pymongo import ReturnDocument

        try:
            object_id = ObjectId(request_id)
        except Exception:
            return None

        now = datetime.now(timezone.utc)

        def transaction_work(session):
            request = self.requests.find_one(
                {"_id": object_id},
                session=session,
            )

            if not request:
                return None

            customer_id = request.get("customer_id")
            assigned_worker_id = request.get("assigned_worker_id")

            if user_role == "customer":
                if customer_id != user_id:
                    raise ValueError(
                        "You do not have permission for this request"
                    )
                ownership_filter = {"customer_id": user_id}
            elif user_role == "worker":
                if assigned_worker_id != user_id:
                    raise ValueError("You are not the assigned worker")
                ownership_filter = {"assigned_worker_id": user_id}
            else:
                raise ValueError("This role cannot update booking status")

            current_status = request.get("status", "requested")

            allowed_transitions = {
                "accepted": ["confirmed", "cancelled"],
                "confirmed": ["on_the_way", "cancelled"],
                "on_the_way": ["arrived", "cancelled"],
                "arrived": ["in_progress", "cancelled"],
                "in_progress": ["completed", "cancelled"],
            }

            if new_status not in allowed_transitions.get(current_status, []):
                raise ValueError(
                    f"Cannot change status from {current_status} to {new_status}"
                )

            if new_status == "completed" and user_role != "worker":
                raise ValueError(
                    "Only the assigned worker can complete the service"
                )

            if new_status in ("on_the_way", "arrived", "in_progress"):
                if user_role != "worker":
                    messages = {
                        "on_the_way": "Only the assigned worker can go on the way",
                        "arrived": "Only the assigned worker can mark arrival",
                        "in_progress": "Only the assigned worker can start the service",
                    }
                    raise ValueError(messages[new_status])

            if new_status == "confirmed" and user_role != "customer":
                raise ValueError("Only the customer can confirm the request")

            result = self.requests.find_one_and_update(
                {
                    "_id": object_id,
                    "status": current_status,
                    **ownership_filter,
                },
                {
                    "$set": {
                        "status": new_status,
                        "updated_at": now,
                    }
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )

            if not result:
                raise ValueError(
                    "Request status was changed by another operation"
                )

            if assigned_worker_id and new_status in ("completed", "cancelled"):
                if new_status == "completed":
                    self.db["workers"].update_one(
                        {"user_id": assigned_worker_id},
                        {
                            "$inc": {"completed_services": 1},
                            "$set": {"updated_at": now},
                        },
                        session=session,
                    )

                active_request = self.requests.find_one(
                    {
                        "assigned_worker_id": assigned_worker_id,
                        "status": {
                            "$in": [
                                "accepted",
                                "confirmed",
                                "on_the_way",
                                "arrived",
                                "in_progress",
                            ]
                        },
                    },
                    {"_id": 1},
                    session=session,
                )

                if not active_request:
                    self.db["workers"].update_one(
                        {
                            "user_id": assigned_worker_id,
                            "availability": "busy",
                        },
                        {
                            "$set": {
                                "availability": "available",
                                "updated_at": now,
                            }
                        },
                        session=session,
                    )

            return result

        with self.db.client.start_session() as session:
            result = session.with_transaction(transaction_work)

        if result is None:
            return None

        return ServiceRequestModel.serialize(result)

    def get_worker_requests(
        self,
        worker_id: str,
    ) -> list[dict]:

        cursor = self.requests.find(
            {
                "$or": [
                    {
                        "matched_worker_ids": worker_id
                    },
                    {
                        "assigned_worker_id": worker_id
                    },
                ]
            }
        ).sort(
            "created_at",
            -1,
        )

        return [
            ServiceRequestModel.serialize(request)
            for request in cursor
        ]
