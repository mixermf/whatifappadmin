from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from admin_api.auth import verify_admin
from admin_api.db import get_session
from admin_api.queries import (
    get_errors,
    get_funnel,
    get_job_events,
    get_overview_metrics,
    get_trace_events,
    get_user_credits,
    get_user_detail,
    get_user_events,
    get_user_iap,
    get_users,
)
from admin_api.schemas import (
    CreditLedgerEntry,
    ErrorGroup,
    ErrorsResponse,
    EventLogEntry,
    EventsResponse,
    FunnelResponse,
    FunnelStep,
    IapTransactionEntry,
    OverviewResponse,
    Segment,
    UserDetail,
    UserSummary,
    UsersResponse,
)


app = FastAPI(title="Admin API", version="1.0.0")
router = APIRouter(prefix="/admin/v1", dependencies=[Depends(verify_admin)])


@app.get("/admin/v1/health")
def health():
    return {"status": "ok"}


@router.get("/overview", response_model=OverviewResponse)
def overview(
    start: datetime,
    end: datetime,
    segment: Segment = Segment.all,
    session: Session = Depends(get_session),
):
    if start >= end:
        raise HTTPException(status_code=400, detail="Invalid date range")

    metrics = get_overview_metrics(session, start, end, segment)
    return OverviewResponse(start=start, end=end, segment=segment, **metrics)


@router.get("/funnel", response_model=FunnelResponse)
def funnel(
    start: datetime,
    end: datetime,
    segment: Segment = Segment.all,
    session: Session = Depends(get_session),
):
    if start >= end:
        raise HTTPException(status_code=400, detail="Invalid date range")

    steps = [FunnelStep(**step) for step in get_funnel(session, start, end, segment)]
    return FunnelResponse(start=start, end=end, segment=segment, steps=steps)


@router.get("/users", response_model=UsersResponse)
def users(
    query: str | None = None,
    segment: Segment = Segment.all,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    total, items = get_users(session, segment, query, limit, offset)
    return UsersResponse(total=total, items=[UserSummary(**item) for item in items])


@router.get("/users/{user_id}", response_model=UserDetail)
def user_detail(user_id: int, session: Session = Depends(get_session)):
    user = get_user_detail(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetail(user=UserSummary(**user))


@router.get("/users/{user_id}/events", response_model=EventsResponse)
def user_events(
    user_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    trace_id: str | None = None,
    job_id: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    total, items = get_user_events(
        session, user_id, start, end, trace_id, job_id, limit, offset
    )
    return EventsResponse(total=total, items=[EventLogEntry(**item) for item in items])


@router.get("/users/{user_id}/credits", response_model=list[CreditLedgerEntry])
def user_credits(
    user_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    session: Session = Depends(get_session),
):
    items = get_user_credits(session, user_id, start, end)
    return [CreditLedgerEntry(**item) for item in items]


@router.get("/users/{user_id}/iap", response_model=list[IapTransactionEntry])
def user_iap(
    user_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    session: Session = Depends(get_session),
):
    items = get_user_iap(session, user_id, start, end)
    return [IapTransactionEntry(**item) for item in items]


@router.get("/traces/{trace_id}/events", response_model=list[EventLogEntry])
def trace_events(trace_id: str, session: Session = Depends(get_session)):
    items = get_trace_events(session, trace_id)
    return [EventLogEntry(**item) for item in items]


@router.get("/jobs/{job_id}/events", response_model=list[EventLogEntry])
def job_events(job_id: str, session: Session = Depends(get_session)):
    items = get_job_events(session, job_id)
    return [EventLogEntry(**item) for item in items]


@router.get("/errors", response_model=ErrorsResponse)
def errors(
    start: datetime,
    end: datetime,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    if start >= end:
        raise HTTPException(status_code=400, detail="Invalid date range")

    total, items = get_errors(session, start, end, limit)
    return ErrorsResponse(
        total=total,
        items=[ErrorGroup(**item) for item in items],
    )


app.include_router(router)
