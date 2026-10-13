from pydantic import BaseModel, Field, StrictInt, field_validator


class CreateReviewRequest(BaseModel):
    rating: StrictInt = Field(..., ge=1, le=5)
    feedback: str = Field(default="", max_length=1000)

    @field_validator("feedback")
    @classmethod
    def normalize_feedback(cls, value: str) -> str:
        return value.strip()
