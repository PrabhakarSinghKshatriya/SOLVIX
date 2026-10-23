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
                        },
                        "$push": {
                            "status_history": {
                                "status": "rejected",
                                "timestamp": now,
                                "actor_id": worker_id,
                                "actor_role": "worker",
                            }
                        },
                    },
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )

                if not result:
                    raise ValueError(
                        "Request was already processed"
                    )

                return result

            # SOLVIX_FREE_QUOTA_ENFORCEMENT_V1
            from app.config import settings

            worker_profile = self.db["workers"].find_one(
                {"user_id": worker_id, "is_active": True},
                session=session,
            )

            if not worker_profile:
                raise ValueError("Active worker profile not found")

            active_subscription = self.db["subscriptions"].find_one(
                {
                    "worker_id": worker_id,
                    "status": "active",
                    "expires_at": {"$gt": now},
                },
                sort=[("expires_at", -1)],
                session=session,
            )

            free_used = int(worker_profile.get("free_opportunities_used", 0))
            free_limit = settings.worker_free_opportunities

            if not active_subscription and free_used >= free_limit:
                raise ValueError(
                    "You have used all free opportunities. "
                    "Subscribe to continue accepting jobs."
                )

            # SOLVIX_AADHAAR_PAID_ACCESS_GATE_V2
            # Once a subscription is active, Aadhaar verification is mandatory
            # before accepting any new service request, regardless of the
            # remaining free-opportunity count. The free counter stays frozen
            # while the subscription is active.
            if active_subscription:
                aadhaar_record = self.db["aadhaar_verifications"].find_one(
                    {
                        "worker_id": worker_id,
                        "status": "verified",
                    },
                    session=session,
                )
                if not aadhaar_record:
                    raise ValueError(
                        "Please upload Aadhaar before using services. "
                        "Admin verification is required before you can "
                        "accept service requests with your subscription."
                    )

            worker_result = self.db["workers"].update_one(
                {
                    "user_id": worker_id,
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

            if worker_result.matched_count != 1:
                raise ValueError(
                    "Active worker profile not found"
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
                    },
                    "$push": {
                        "status_history": {
                            "status": "accepted",
                            "timestamp": now,
                            "actor_id": worker_id,
                            "actor_role": "worker",
                        }
                    },
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )

            if not result:
                raise ValueError(
                    "Request was already processed"
                )

            if not active_subscription:
                quota_update = self.db["workers"].update_one(
                    {
                        "user_id": worker_id,
                        "is_active": True,
                        "$or": (
                            [
                                {"free_opportunities_used": 0},
                                {"free_opportunities_used": {"$exists": False}},
                            ]
                            if free_used == 0
                            else [{"free_opportunities_used": free_used}]
                        ),
                    },
                    {
                        "$inc": {"free_opportunities_used": 1},
                        "$set": {"updated_at": now},
                    },
                    session=session,
                )

                if quota_update.modified_count != 1:
                    raise ValueError(
                        "Free quota update failed. Please retry."
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
            valid_statuses = {
                "requested",
                "accepted",
                "confirmed",
                "on_the_way",
                "arrived",
                "in_progress",
                "completed",
                "cancelled",
                "rejected",
            }

            if new_status not in valid_statuses:
                raise ValueError("Invalid request status")

            # Preserve role permissions even for same-status selections.
            # Re-selecting the existing status is a successful no-op.
            if new_status == current_status:
                return request, False, current_status

            # Completed and rejected requests are terminal.
            if current_status in ("completed", "rejected"):
                raise ValueError(
                    f"Cannot change status from {current_status} to {new_status}"
                )

            allowed_transitions = {
                "requested": ["accepted", "cancelled", "rejected"],
                "accepted": ["confirmed", "cancelled", "rejected"],
                "confirmed": ["on_the_way", "cancelled"],
                "on_the_way": ["arrived", "cancelled"],
                "arrived": ["in_progress", "cancelled"],
                "in_progress": ["completed", "cancelled"],
                "cancelled": [],
            }

            if new_status not in allowed_transitions.get(current_status, []):
                raise ValueError(
                    f"Cannot change status from {current_status} to {new_status}"
                )

            if new_status == "confirmed" and user_role != "customer":
                raise ValueError("Only the customer can confirm a request")

            if new_status == "accepted" and user_role != "worker":
                raise ValueError("Only a worker can accept a request")

            if new_status in ("on_the_way", "arrived", "in_progress", "completed") and user_role != "worker":
                raise ValueError("Only the assigned worker can update this status")

            update_fields = {
                "status": new_status,
                "updated_at": now,
            }
            if new_status == "completed":
                update_fields["completed_counted"] = True

            result = self.requests.find_one_and_update(
                {
                    "_id": object_id,
                    "status": current_status,
                    **ownership_filter,
                },
                {
                    "$set": update_fields,
                    "$push": {
                        "status_history": {
                            "status": new_status,
                            "timestamp": now,
                            "actor_id": user_id,
                            "actor_role": user_role,
                        }
                    },
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )

            if not result:
                raise ValueError(
                    "Request status was changed by another operation"
                )

            if assigned_worker_id and new_status in ("completed", "cancelled"):
                # Never count the same booking as completed more than once.
                if (
                    new_status == "completed"
                    and not request.get("completed_counted", False)
                ):
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

            return result, True, current_status

        with self.db.client.start_session() as session:
            result = session.with_transaction(transaction_work)

        if result is None:
            return None

        document, status_changed, previous_status = result
        serialized = ServiceRequestModel.serialize(document)
        serialized['_status_changed'] = status_changed
        serialized['_previous_status'] = previous_status
        return serialized

    def get_worker_requests(
        self,
        worker_id: str,
    ) -> list[dict]:
        from app.services.worker_service import WorkerService

        worker_service = WorkerService()

        cursor = self.requests.find(
            {
                "$or": [
                    {"status": "requested"},
                    {"matched_worker_ids": worker_id},
                    {"assigned_worker_id": worker_id},
                ]
            }
        ).sort("created_at", -1)

        visible_requests = []

        for request in cursor:
            request_status = request.get("status", "requested")
            assigned_worker_id = request.get("assigned_worker_id")
            matched_ids = list(request.get("matched_worker_ids") or [])

            # Already assigned requests are visible only to the assigned
            # worker and workers who were previously matched to them.
            if assigned_worker_id and assigned_worker_id != worker_id:
                if worker_id in matched_ids:
                    visible_requests.append(
                        ServiceRequestModel.serialize(request)
                    )
                continue

            # Keep the worker's own assigned requests visible.
            if assigned_worker_id == worker_id:
                visible_requests.append(
                    ServiceRequestModel.serialize(request)
                )
                continue

            # Only pending, unassigned requests can be newly matched.
            if request_status != "requested":
                if worker_id in matched_ids:
                    visible_requests.append(
                        ServiceRequestModel.serialize(request)
                    )
                continue

            location = request.get("location") or {}
            coordinates = location.get("coordinates") or []

            if len(coordinates) != 2:
                if worker_id in matched_ids:
                    visible_requests.append(
                        ServiceRequestModel.serialize(request)
                    )
                continue

            try:
                longitude, latitude = map(float, coordinates)
                eligible_workers = worker_service.match_workers(
                    latitude=latitude,
                    longitude=longitude,
                    service=str(request.get("service") or ""),
                )
            except (TypeError, ValueError):
                if worker_id in matched_ids:
                    visible_requests.append(
                        ServiceRequestModel.serialize(request)
                    )
                continue

            eligible_ids = [
                str(worker.get("user_id"))
                for worker in eligible_workers
                if worker.get("user_id")
            ]

            # Persist the currently eligible worker IDs so request-detail
            # authorization and worker acceptance use the same match list.
            if eligible_ids:
                self.requests.update_one(
                    {
                        "_id": request["_id"],
                        "status": "requested",
                        "assigned_worker_id": None,
                    },
                    {
                        "$addToSet": {
                            "matched_worker_ids": {
                                "$each": eligible_ids
                            }
                        },
                        "$set": {
                            "match_status": "matched",
                            "updated_at": datetime.now(timezone.utc),
                        },
                    },
                )

            if worker_id in eligible_ids or worker_id in matched_ids:
                request["matched_worker_ids"] = list(
                    dict.fromkeys(matched_ids + eligible_ids)
                )
                visible_requests.append(
                    ServiceRequestModel.serialize(request)
                )

        return visible_requests
