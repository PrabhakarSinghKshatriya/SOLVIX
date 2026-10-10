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


    @staticmethod
    def _distance_km(lat1, lon1, lat2, lon2):
        """Calculate great-circle distance between two GPS points."""
        import math

        values = (lat1, lon1, lat2, lon2)
        try:
            if not all(math.isfinite(float(v)) for v in values):
                return None
            lat1, lon1, lat2, lon2 = map(float, values)
        except (TypeError, ValueError):
            return None

        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90):
            return None
        if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            return None

        lat1, lat2 = math.radians(lat1), math.radians(lat2)
        dlat = lat2 - lat1
        dlon = math.radians(lon2 - lon1)

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2)
            * math.sin(dlon / 2) ** 2
        )
        a = min(1.0, max(0.0, a))

        return 6371.0088 * 2 * math.atan2(
            math.sqrt(a), math.sqrt(1 - a)
        )

    @staticmethod
    def _coordinates(worker):
        location = worker.get("location") or {}
        coordinates = location.get("coordinates") or []

        if len(coordinates) != 2:
            return None

        try:
            longitude, latitude = map(float, coordinates)
        except (TypeError, ValueError):
            return None

        if not (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            return None

        # The default profile location is not a real GPS fix.
        if latitude == 0 and longitude == 0:
            return None

        return latitude, longitude

    @staticmethod
    def _within_service_radius(worker, distance_km):
        try:
            radius = float(worker.get("service_radius_km", 0))
        except (TypeError, ValueError):
            return False

        return radius > 0 and distance_km <= radius

    def find_nearby_workers(
        self,
        latitude: float,
        longitude: float,
        max_distance_km: float = 10,
    ) -> list[dict]:
        if not (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError("Invalid customer coordinates")

        if not 1 <= max_distance_km <= 100:
            raise ValueError("Search radius must be between 1 and 100 km")

        cursor = self.workers.find({
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    },
                    "$maxDistance": max_distance_km * 1000,
                }
            },
            "is_active": True,
        })

        results = []

        for worker in cursor:
            coordinates = self._coordinates(worker)
            if coordinates is None:
                continue

            worker_lat, worker_lon = coordinates
            distance = self._distance_km(
                latitude, longitude, worker_lat, worker_lon
            )

            if distance is None or distance > max_distance_km:
                continue

            if not self._within_service_radius(worker, distance):
                continue

            result = WorkerModel.serialize(worker)
            result["distance_km"] = round(distance, 2)
            results.append(result)

        results.sort(key=lambda item: item["distance_km"])
        return results

    def match_workers(
        self,
        latitude: float,
        longitude: float,
        service: str,
        radius_km: float = 10,
    ) -> list[dict]:
        if not (
            -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError("Invalid customer coordinates")

        if not 1 <= radius_km <= 100:
            raise ValueError("Search radius must be between 1 and 100 km")

        service_text = service.strip().lower()
        if not service_text:
            return []

        cursor = self.workers.find({
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    },
                    "$maxDistance": radius_km * 1000,
                }
            },
            "is_active": True,
        })

        matched_workers = []

        for worker in cursor:
            coordinates = self._coordinates(worker)
            if coordinates is None:
                continue

            worker_lat, worker_lon = coordinates
            distance = self._distance_km(
                latitude, longitude, worker_lat, worker_lon
            )

            if distance is None or distance > radius_km:
                continue

            if not self._within_service_radius(worker, distance):
                continue

            profession = str(worker.get("profession") or "").lower()
            skills = [
                str(skill).lower()
                for skill in worker.get("skills", [])
            ]

            skill_match = (
                service_text in profession
                or any(
                    service_text in skill or skill in service_text
                    for skill in skills
                )
            )

            if not skill_match:
                continue

            rating = float(worker.get("rating", 0) or 0)
            experience = float(worker.get("experience_years", 0) or 0)
            completed = int(worker.get("completed_services", 0) or 0)

            score = 50
            if rating > 0:
                score += min(rating * 4, 20)

            score += min(experience, 15)

            if worker.get("is_verified", False):
                score += 10

            score += min(completed / 20, 5)

            result = WorkerModel.serialize(worker)
            result["match_score"] = round(score, 2)
            result["distance_km"] = round(distance, 2)
            matched_workers.append(result)

        matched_workers.sort(
            key=lambda item: (-item["match_score"], item["distance_km"])
        )
        return matched_workers
