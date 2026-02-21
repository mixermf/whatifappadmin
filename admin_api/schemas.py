from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Segment(str, Enum):
    all = "all"
    paying = "paying"
    non_paying = "non_paying"


class OverviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: datetime
    end: datetime
    segment: Segment
    new_users: int
    active_users: int
    jobs_started: int
    jobs_succeeded: int
    jobs_failed: int
    conversion_to_pay: float


class FunnelStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: str
    count: int
    conversion_from_prev: float


class FunnelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: datetime
    end: datetime
    segment: Segment
    steps: list[FunnelStep]


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    install_id_hash: str | None
    google_sub: str | None
    credits_balance: int
    merged_into_user_id: int | None
    last_seen_at: datetime | None
    paying: bool


class UsersResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    items: list[UserSummary]


class CreditLedgerEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    delta: int
    ref_type: str | None
    ref_id: str | None
    created_at: datetime


class IapTransactionEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    store: str
    product_id: str | None
    purchase_token: str | None
    status: str
    raw_payload: dict[str, Any] | None
    created_at: datetime
    verified_at: datetime | None


class EventLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    trace_id: str | None
    user_id: int | None
    job_id: str | None
    event: str
    payload: dict[str, Any] | None


class UserDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserSummary


class EventsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    items: list[EventLogEntry]


class ErrorsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int
    items: list["ErrorGroup"]


class ErrorGroup(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event: str
    error_type: str | None
    error_message: str | None
    count: int
    sample_trace_id: str | None
    sample_job_id: str | None


ErrorsResponse.model_rebuild()
