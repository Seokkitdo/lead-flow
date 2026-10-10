import re
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


class LeadInput(Input):
    @field_validator("name", mode="before", check_fields=False)
    @classmethod
    def clean_name(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("고객 이름을 입력해 주세요.")
        return value

    @field_validator("phone", mode="after", check_fields=False)
    @classmethod
    def check_phone(cls, value):
        if value is None:
            return value
        value = value.strip()
        compact = re.sub(r"[\s-]", "", value)
        pattern = (
            r"(?:02[0-9]{7,8}|01[016789][0-9]{7,8}|0[3-6][0-9]{8}|"
            r"070[0-9]{8}|080[0-9]{7}|1[0-9]{7}|\+[1-9][0-9]{7,14})"
        )
        if not re.fullmatch(r"\+?[0-9][0-9\s-]*", value) or not re.fullmatch(pattern, compact):
            raise ValueError("연락처를 확인해 주세요. 예: 010-1234-5678")
        return value


class LeadCreate(LeadInput):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    source: Source | None = None
    source_detail: str | None = Field(default=None, max_length=255)
    initial_memo: str | None = Field(default=None, max_length=10000)
    acquired_at: datetime | None = None
    allow_duplicate: bool = False
    assignee_id: str | None = None


class LeadPatch(LeadInput):
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


class AccountPatch(Input):
    version: str = Field(min_length=64, max_length=64)
    current_password: str = Field(min_length=1, max_length=128)
    phone: str | None = Field(default=None, max_length=30)
    password: str | None = Field(default=None, min_length=12, max_length=128)


class ActivityCorrection(Input):
    version: int = Field(ge=1)
    kind: Literal["CORRECTION", "CANCELLATION"]
    reason: str = Field(min_length=1, max_length=1000)
    memo: str = Field(default="", max_length=8000)
    status: Status
    callback_at: datetime | None = None
