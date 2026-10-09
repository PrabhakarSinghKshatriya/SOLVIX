from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.database.connection import get_database
from app.models.worker import WorkerModel


class WorkerService:
    def __init__(self):
        self.db = get_database()
        self.workers = self.db[WorkerModel.collection_name]

    def create_profile(
        self,
        user_id: str,
        profession: str,
        skills: list[str],
        experience_years: float,
        service_radius_km: float,
        bio: str | None = None,
    ) -> dict:

        existing_profile = self.workers.find_one(
            {"user_id": user_id}
        )

        if existing_profile:
            raise ValueError(
                "Worker profile already exists"
            )

        document = WorkerModel.create_document(
            user_id=user_id,
            profession=profession,
            skills=skills,
            experience_years=experience_years,
            service_radius_km=service_radius_km,
            bio=bio,
        )

        try:
            result = self.workers.insert_one(document)
        except DuplicateKeyError as exc:
            raise ValueError(
                "Worker profile already exists"
            ) from exc

        document["_id"] = result.inserted_id

        return WorkerModel.serialize(document)

    def get_profile(
        self,
        user_id: str,
    ) -> dict | None:

        worker = self.workers.find_one(
            {"user_id": user_id}
        )

        if not worker:
            return None

        return WorkerModel.serialize(worker)

    def update_profile(
        self,
        user_id: str,
        updates: dict,
    ) -> dict | None:

        cleaned_updates = {
            key: value
            for key, value in updates.items()
            if value is not None
        }

        if not cleaned_updates:
            return self.get_profile(user_id)

        cleaned_updates["updated_at"] = (
            datetime.now(timezone.utc)
        )

        result = self.workers.find_one_and_update(
            {"user_id": user_id},
            {"$set": cleaned_updates},
            return_document=True,
        )

        if not result:
            return None

        return WorkerModel.serialize(result)


    def update_location(
        self,
        user_id: str,
        latitude: float,
        longitude: float,
    ) -> dict | None:

        now = datetime.now(timezone.utc)

        result = self.workers.find_one_and_update(
            {"user_id": user_id},
            {
                "$set": {
                    "location": {
                        "type": "Point",
                        "coordinates": [
                            longitude,
                            latitude,
                        ],
                    },
                    "updated_at": now,
                }
            },
            return_document=True,
        )

        if not result:
            return None

        return WorkerModel.serialize(result)


    def find_nearby_workers(
        self,
        latitude: float,
        longitude: float,
        max_distance_km: float = 10,
    ) -> list[dict]:

        max_distance_meters = max_distance_km * 1000

        cursor = self.workers.find(
            {
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [
                                longitude,
                                latitude,
                            ],
                        },
                        "$maxDistance": max_distance_meters,
                    }
                },
                "is_active": True,
                "availability": "available",
            }
        )

        workers = []

        for worker in cursor:
            serialized = WorkerModel.serialize(worker)
            workers.append(serialized)

        return workers


    def match_workers(
        self,
        latitude: float,
        longitude: float,
        service: str,
        radius_km: float = 10,
    ) -> list[dict]:

        max_distance_meters = radius_km * 1000

        service_text = service.strip().lower()

        cursor = self.workers.find(
            {
                "location": {
                    "$near": {
                        "$geometry": {
                            "type": "Point",
                            "coordinates": [
                                longitude,
                                latitude,
                            ],
                        },
                        "$maxDistance": max_distance_meters,
                    }
                },
                "is_active": True,
                "availability": "available",
            }
        )

        matched_workers = []

        for worker in cursor:

            profession = worker.get(
                "profession",
                "",
            ).lower()

            skills = [
                skill.lower()
                for skill in worker.get(
                    "skills",
                    [],
                )
            ]

            skill_match = (
                service_text in profession
                or any(
                    service_text in skill
                    or skill in service_text
                    for skill in skills
                )
            )

            if not skill_match:
                continue

            score = 50

            rating = float(
                worker.get("rating", 0)
            )

            experience = float(
                worker.get("experience_years", 0)
            )

            completed_services = int(
                worker.get(
                    "completed_services",
                    0,
                )
            )

            if rating > 0:
                score += min(
                    rating * 4,
                    20,
                )

            score += min(
                experience,
                15,
            )

            if worker.get(
                "is_verified",
                False,
            ):
                score += 10

            score += min(
                completed_services / 20,
                5,
            )

            result = WorkerModel.serialize(
                worker
            )

            result["match_score"] = round(
                score,
                2,
            )

            matched_workers.append(result)

        matched_workers.sort(
            key=lambda worker: worker[
                "match_score"
            ],
            reverse=True,
        )

        return matched_workers
