from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


RequestStatus = Literal[
    "requested",
    "accepted",
    "confirmed",
    "on_the_way",
    "arrived",
    "in_progress",
    "completed",
    "rejected",
    "cancelled",
    "expired",
]


class CreateServiceRequest(BaseModel):
    service: str = Field(
        ...,
        min_length=2,
        max_length=100,
    )

    description: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

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

    @field_validator("service")
    @classmethod
    def validate_service(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Service cannot be empty"
            )

        return value

    @field_validator("description")
    @classmethod
    def validate_description(
        cls,
        value: Optional[str],
    ) -> Optional[str]:

        if value is None:
            return None

        value = value.strip()

        return value if value else None


class WorkerRequestAction(BaseModel):
    action: Literal[
        "accept",
        "reject",
    ]


class StatusTransitionRequest(BaseModel):
    status: Literal[
        "confirmed",
        "on_the_way",
        "arrived",
        "in_progress",
        "completed",
        "cancelled",
    ]
