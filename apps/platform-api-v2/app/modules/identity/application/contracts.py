from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoginCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)


class RefreshSessionCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    refresh_token: str = Field(min_length=1)


class LogoutCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    refresh_token: str = Field(min_length=1)


class ChangePasswordCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class UpdateCurrentUserProfileCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    username: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)
