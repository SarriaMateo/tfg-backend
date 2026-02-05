from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
import re


class CompanyCreate(BaseModel):
    name: str
    email: EmailStr
    nif: Optional[str] = None

    @field_validator("nif")
    @classmethod
    def validate_nif(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.upper()
        if not re.match(r"^[A-Z]\d{8}$", value):
            raise ValueError("Invalid NIF format")
        return value


class CompanyResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    nif: Optional[str]

    class Config:
        from_attributes = True


class CompanyRegistrationResponse(BaseModel):
    company: CompanyResponse
    user: "UserResponse"  # noqa: F821


# Importar aquí para evitar circular imports
from .user import UserResponse  # noqa: E402, F401

CompanyRegistrationResponse.model_rebuild()
