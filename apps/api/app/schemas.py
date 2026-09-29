from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["NEW", "CONTACTING", "CALLBACK", "IN_PROGRESS", "HOLD", "REJECTED", "COMPLETED"]
Source = Literal["NAVER", "KAKAO", "HOMEPAGE", "FORM", "PHONE", "REFERRAL", "ETC"]
Action = Literal[
    "CALL_ATTEMPT", "CALL_NO_ANSWER", "CALL_CONNECTED", "KAKAO_SENT", "CONSULTATION", "MEMO", "STATUS_CHANGE"
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def utc_dates(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("Datetime must include timezone")
            return value.astimezone(UTC)
        return value


class Login(Input):
    login_id: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(Input):
    login_id: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    role: Literal["ADMIN", "USER"] = "USER"
    status: Literal["ACTIVE", "INACTIVE", "DEPARTED"] = "ACTIVE"


class UserPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    password: str | None = Field(default=None, min_length=12, max_length=128)
    role: Literal["ADMIN", "USER"] | None = None
    status: Literal["ACTIVE", "INACTIVE", "DEPARTED"] | None = None


class LeadCreate(Input):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    source: Source | None = None
    source_detail: str | None = Field(default=None, max_length=255)
    initial_memo: str | None = Field(default=None, max_length=10000)
    acquired_at: datetime | None = None
    allow_duplicate: bool = False


class LeadPatch(Input):
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, min_length=7, max_length=30)
    source: Source | None = None
    source_detail: str | None = Field(default=None, max_length=255)
    initial_memo: str | None = Field(default=None, max_length=10000)
    acquired_at: datetime | None = None
    allow_duplicate: bool = False


class ActivityCreate(Input):
    version: int = Field(ge=1)
    activity_type: Action
    memo: str = Field(default="", max_length=10000)
    status: Status | None = None
    callback_at: datetime | None = None


class StatusCreate(Input):
    version: int = Field(ge=1)
    status: Status
    memo: str = Field(default="", max_length=10000)
    callback_at: datetime | None = None


class BulkAssign(Input):
    lead_ids: list[str] = Field(min_length=1, max_length=500)
    user_ids: list[str] = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)


class SingleAssign(Input):
    lead_id: str
    user_id: str
    reason: str | None = Field(default=None, max_length=1000)
