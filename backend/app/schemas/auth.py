from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    student_identifier: str | None = Field(default=None, max_length=80)

    @field_validator("student_identifier", mode="before")
    @classmethod
    def empty_student_identifier_is_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value or None


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequestInput(BaseModel):
    email: EmailStr


class PasswordResetConfirmInput(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserView(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    role: str
    department_id: UUID | None
    student_identifier: str | None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class TokenView(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserView


class StaffCreateInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(pattern="^(STUDENT|STAFF|ADMIN|SUPER_ADMIN)$")
    department_id: UUID | None = None
    student_identifier: str | None = Field(default=None, max_length=80)

    @field_validator("student_identifier", mode="before")
    @classmethod
    def empty_student_identifier_is_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
        return value or None
