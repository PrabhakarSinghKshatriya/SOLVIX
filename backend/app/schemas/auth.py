from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


UserRole = Literal["customer", "worker"]


class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    phone: str = Field(..., min_length=10, max_length=10)
    role: UserRole

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Name cannot be empty")

        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()

        if not value.isdigit():
            raise ValueError("Phone must contain only digits")

        if len(value) != 10:
            raise ValueError("Phone must contain exactly 10 digits")

        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class VerifyLoginOTPRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("OTP must contain exactly 6 digits")
        return value


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("otp")
    @classmethod
    def validate_reset_otp(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("OTP must contain exactly 6 digits")
        return value
