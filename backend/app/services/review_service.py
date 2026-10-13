from datetime import datetime, timezone

from bson import ObjectId

from app.database.connection import get_database


class ReviewService:
    def __init__(self):
        self.db = get_database()
        self.requests = self.db["service_requests"]
        self.reviews = self.db["reviews"]
        self.workers = self.db["workers"]

    def create_review(
        self,
        request_id: str,
        customer_id: str,
        rating: int,
        feedback: str = "",
    ) -> dict:
        if not ObjectId.is_valid(request_id):
            raise ValueError("Invalid service request ID")

        if not isinstance(rating, int) or isinstance(rating, bool):
            raise ValueError("Rating must be an integer from 1 to 5")

        if not 1 <= rating <= 5:
            raise ValueError("Rating must be from 1 to 5")

        feedback = (feedback or "").strip()

        if len(feedback) > 1000:
            raise ValueError("Feedback cannot exceed 1000 characters")

        request_object_id = ObjectId(request_id)
        now = datetime.now(timezone.utc)

        def transaction_work(session):
            request = self.requests.find_one(
                {"_id": request_object_id},
                session=session,
            )

            if not request:
                raise ValueError("Service request not found")

            if str(request.get("customer_id", "")) != str(customer_id):
                raise PermissionError(
                    "Only the customer who created this booking can review it"
                )

            if request.get("status") != "completed":
                raise ValueError(
                    "You can review a service only after it is completed"
                )

            worker_id = request.get("assigned_worker_id")

            if not worker_id:
                raise ValueError(
                    "This completed request has no assigned worker"
                )

            worker = self.workers.find_one(
                {"user_id": str(worker_id), "is_active": True},
                session=session,
            )

            if not worker:
                raise ValueError("Assigned worker profile not found")

            existing = self.reviews.find_one(
                {"request_id": request_object_id},
                session=session,
            )

            if existing:
                raise ValueError(
                    "A review has already been submitted for this booking"
                )

            review = {
                "request_id": request_object_id,
                "customer_id": str(customer_id),
                "worker_id": str(worker_id),
                "rating": rating,
                "feedback": feedback,
                "created_at": now,
                "updated_at": now,
            }

            insert_result = self.reviews.insert_one(
                review,
                session=session,
            )
            review["_id"] = insert_result.inserted_id

            # Calculate the authoritative average from saved reviews.
            pipeline = [
                {"$match": {"worker_id": str(worker_id)}},
                {
                    "$group": {
                        "_id": None,
                        "average": {"$avg": "$rating"},
                        "count": {"$sum": 1},
                    }
                },
            ]

            summary = list(
                self.reviews.aggregate(pipeline, session=session)
            )

            average = round(float(summary[0]["average"]), 2)
            count = int(summary[0]["count"])

            update = self.workers.update_one(
                {"_id": worker["_id"]},
                {
                    "$set": {
                        "rating": average,
                        "total_reviews": count,
                        "updated_at": now,
                    }
                },
                session=session,
            )

            if update.matched_count != 1:
                raise ValueError("Could not update worker rating")

            return {
                "id": str(review["_id"]),
                "request_id": request_id,
                "worker_id": str(worker_id),
                "rating": rating,
                "feedback": feedback,
                "created_at": now,
                "worker_rating": average,
                "worker_total_reviews": count,
            }

        # A transaction keeps the review and aggregate rating consistent.
        with self.db.client.start_session() as session:
            return session.with_transaction(transaction_work)

    def get_worker_reviews(self, worker_id: str) -> list[dict]:
        cursor = self.reviews.find(
            {"worker_id": str(worker_id)}
        ).sort("created_at", -1)

        results = []

        for review in cursor:
            request_id = review.get("request_id")
            request = None

            if request_id:
                request = self.requests.find_one(
                    {"_id": request_id},
                    {"service": 1},
                )

            results.append({
                "id": str(review["_id"]),
                "request_id": str(request_id) if request_id else None,
                "service": (request or {}).get("service", "Service"),
                "rating": review.get("rating", 0),
                "feedback": review.get("feedback", ""),
                "created_at": review.get("created_at"),
            })

        return results
