from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


AvailabilityStatus = Literal[
    "available",
    "busy",
    "offline",
]


class LocationUpdateRequest(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
    )


class CreateWorkerProfileRequest(BaseModel):
    profession: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    skills: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    experience_years: float = Field(
        ...,
        ge=0,
        le=60,
    )

    service_radius_km: float = Field(
        default=10,
        ge=1,
        le=100,
    )

    bio: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    @field_validator("profession")
    @classmethod
    def validate_profession(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Profession cannot be empty")

        return value

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, value: list[str]) -> list[str]:
        cleaned_skills = []

        for skill in value:
            skill = skill.strip()

            if skill and skill not in cleaned_skills:
                cleaned_skills.append(skill)

        if not cleaned_skills:
            raise ValueError("At least one valid skill is required")

        return cleaned_skills

    @field_validator("bio")
    @classmethod
    def validate_bio(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        return value if value else None


class UpdateWorkerProfileRequest(BaseModel):
    profession: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    skills: Optional[list[str]] = Field(
        default=None,
        min_length=1,
        max_length=20,
    )

    experience_years: Optional[float] = Field(
        default=None,
        ge=0,
        le=60,
    )

    service_radius_km: Optional[float] = Field(
        default=None,
        ge=1,
        le=100,
    )

    bio: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

    availability: Optional[AvailabilityStatus] = None


class WorkerResponse(BaseModel):
    id: str
    user_id: str
    profession: str
    skills: list[str]
    experience_years: float
    service_radius_km: float
    bio: Optional[str]

    availability: AvailabilityStatus

    location: dict

    rating: float
    total_reviews: int
    completed_services: int

    is_verified: bool
    is_active: bool


class NearbyWorkersRequest(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
    )

    radius_km: float = Field(
        default=10,
        ge=1,
        le=100,
    )


class WorkerMatchingRequest(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
    )

    service: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    radius_km: float = Field(
        default=10,
        ge=1,
        le=100,
    )

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Service cannot be empty")

        return value
