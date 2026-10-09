from datetime import datetime, timezone
from typing import Optional


class WorkerModel:
    collection_name = "workers"

    @staticmethod
    def create_document(
        user_id: str,
        profession: str,
        skills: list[str],
        experience_years: float,
        service_radius_km: float,
        bio: Optional[str] = None,
    ) -> dict:
        now = datetime.now(timezone.utc)

        return {
            "user_id": user_id,
            "profession": profession.strip(),
            "skills": [skill.strip() for skill in skills if skill.strip()],
            "experience_years": experience_years,
            "service_radius_km": service_radius_km,
            "bio": bio.strip() if bio else None,
            "availability": "offline",
            "location": {
                "type": "Point",
                "coordinates": [0.0, 0.0],
            },
            "rating": 0.0,
            "total_reviews": 0,
            "completed_services": 0,
            "is_verified": False,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def serialize(document: dict) -> dict:
        return {
            "id": str(document["_id"]),
            "user_id": document["user_id"],
            "profession": document["profession"],
            "skills": document.get("skills", []),
            "experience_years": document.get("experience_years", 0),
            "service_radius_km": document.get("service_radius_km", 0),
            "bio": document.get("bio"),
            "availability": document.get("availability", "offline"),
            "location": document.get(
                "location",
                {
                    "type": "Point",
                    "coordinates": [0.0, 0.0],
                },
            ),
            "rating": document.get("rating", 0.0),
            "total_reviews": document.get("total_reviews", 0),
            "completed_services": document.get("completed_services", 0),
            "is_verified": document.get("is_verified", False),
            "is_active": document.get("is_active", True),
            "created_at": document.get("created_at"),
            "updated_at": document.get("updated_at"),
        }
