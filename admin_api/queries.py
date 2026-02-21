from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, case, distinct, func, or_, select, union
from sqlalchemy.orm import Session

from admin_api.models import CreditLedger, EventLog, IapTransaction, User
from admin_api.schemas import Segment


FUNNEL_STEPS = [
    "upload_started",
    "face_analysis_success",
    "llm_core_generation_success",
    "llm_image_prompt_success",
    "image_generation_success",
]

JOB_STARTED_EVENTS = ["generate_requested", "upload_started"]
JOB_SUCCEEDED_EVENTS = ["job_succeeded", "image_generation_success"]
JOB_FAILED_EVENTS = ["job_failed", "image_generation_failed", "llm_generation_failed"]


def paying_user_ids_subquery():
    iap = select(IapTransaction.user_id).where(IapTransaction.status == "verified")
    topup = select(CreditLedger.user_id).where(
        CreditLedger.type.like("topup_%"), CreditLedger.delta > 0
    )
    return union(iap, topup).subquery()


def segment_clause(segment: Segment, column, paying_subquery):
    if segment == Segment.all:
        return None
    paying_ids = select(paying_subquery.c.user_id)
    if segment == Segment.paying:
        return column.in_(paying_ids)
    return ~column.in_(paying_ids)


def apply_filters(statement, *clauses):
    for clause in clauses:
        if clause is not None:
            statement = statement.where(clause)
    return statement


def get_overview_metrics(session: Session, start: datetime, end: datetime, segment: Segment):
    paying_subquery = paying_user_ids_subquery()
    user_segment = segment_clause(segment, User.id, paying_subquery)
    event_segment = segment_clause(segment, EventLog.user_id, paying_subquery)

    new_users_stmt = apply_filters(
        select(func.count(User.id)).where(User.created_at >= start, User.created_at < end),
        user_segment,
    )
    new_users = session.execute(new_users_stmt).scalar_one()

    active_users_stmt = apply_filters(
        select(func.count(distinct(EventLog.user_id))).where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            EventLog.user_id.isnot(None),
        ),
        event_segment,
    )
    active_users = session.execute(active_users_stmt).scalar_one()

    jobs_started_stmt = apply_filters(
        select(func.count()).select_from(EventLog).where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            EventLog.event.in_(JOB_STARTED_EVENTS),
        ),
        event_segment,
    )
    jobs_started = session.execute(jobs_started_stmt).scalar_one()

    jobs_succeeded_stmt = apply_filters(
        select(func.count()).select_from(EventLog).where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            EventLog.event.in_(JOB_SUCCEEDED_EVENTS),
        ),
        event_segment,
    )
    jobs_succeeded = session.execute(jobs_succeeded_stmt).scalar_one()

    jobs_failed_stmt = apply_filters(
        select(func.count()).select_from(EventLog).where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            EventLog.event.in_(JOB_FAILED_EVENTS),
        ),
        event_segment,
    )
    jobs_failed = session.execute(jobs_failed_stmt).scalar_one()

    paying_active_stmt = apply_filters(
        select(func.count(distinct(EventLog.user_id))).where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            EventLog.user_id.isnot(None),
        ),
        segment_clause(Segment.paying, EventLog.user_id, paying_subquery),
    )
    paying_active_users = session.execute(paying_active_stmt).scalar_one()

    if active_users == 0:
        conversion_to_pay = 0.0
    elif segment == Segment.all:
        conversion_to_pay = paying_active_users / active_users
    elif segment == Segment.paying:
        conversion_to_pay = 1.0
    else:
        conversion_to_pay = 0.0

    return {
        "new_users": new_users,
        "active_users": active_users,
        "jobs_started": jobs_started,
        "jobs_succeeded": jobs_succeeded,
        "jobs_failed": jobs_failed,
        "conversion_to_pay": conversion_to_pay,
    }


def get_funnel(session: Session, start: datetime, end: datetime, segment: Segment):
    paying_subquery = paying_user_ids_subquery()
    event_segment = segment_clause(segment, EventLog.user_id, paying_subquery)

    counts_stmt = apply_filters(
        select(EventLog.event, func.count(distinct(EventLog.user_id))).where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            EventLog.event.in_(FUNNEL_STEPS),
            EventLog.user_id.isnot(None),
        ),
        event_segment,
    ).group_by(EventLog.event)

    counts = {row[0]: row[1] for row in session.execute(counts_stmt).all()}

    steps = []
    previous_count = None
    for event in FUNNEL_STEPS:
        count = counts.get(event, 0)
        if previous_count in (None, 0):
            conversion = 1.0 if previous_count is None else 0.0
        else:
            conversion = count / previous_count
        steps.append({"event": event, "count": count, "conversion_from_prev": conversion})
        previous_count = count

    return steps


def get_users(
    session: Session,
    segment: Segment,
    query: str | None,
    limit: int,
    offset: int,
):
    paying_subquery = paying_user_ids_subquery()
    paying_ids = select(paying_subquery.c.user_id)
    is_paying = case((User.id.in_(paying_ids), True), else_=False).label("paying")

    stmt = select(User, is_paying)
    stmt = apply_filters(stmt, segment_clause(segment, User.id, paying_subquery))

    if query:
        filters = [User.install_id_hash.ilike(f"%{query}%"), User.google_sub.ilike(f"%{query}%")]
        if query.isdigit():
            filters.append(User.id == int(query))
        stmt = stmt.where(or_(*filters))

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.execute(total_stmt).scalar_one()

    rows = (
        session.execute(
            stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        ).all()
    )

    items = []
    for user, paying in rows:
        items.append({
            "id": user.id,
            "created_at": user.created_at,
            "install_id_hash": user.install_id_hash,
            "google_sub": user.google_sub,
            "credits_balance": user.credits_balance,
            "merged_into_user_id": user.merged_into_user_id,
            "last_seen_at": user.last_seen_at,
            "paying": bool(paying),
        })

    return total, items


def get_user_detail(session: Session, user_id: int):
    paying_subquery = paying_user_ids_subquery()
    paying_ids = select(paying_subquery.c.user_id)
    is_paying = case((User.id.in_(paying_ids), True), else_=False).label("paying")

    row = session.execute(select(User, is_paying).where(User.id == user_id)).first()
    if not row:
        return None

    user, paying = row
    return {
        "id": user.id,
        "created_at": user.created_at,
        "install_id_hash": user.install_id_hash,
        "google_sub": user.google_sub,
        "credits_balance": user.credits_balance,
        "merged_into_user_id": user.merged_into_user_id,
        "last_seen_at": user.last_seen_at,
        "paying": bool(paying),
    }


def get_user_events(
    session: Session,
    user_id: int,
    start: datetime | None,
    end: datetime | None,
    trace_id: str | None,
    job_id: str | None,
    limit: int,
    offset: int,
):
    stmt = select(EventLog).where(EventLog.user_id == user_id)
    if start:
        stmt = stmt.where(EventLog.created_at >= start)
    if end:
        stmt = stmt.where(EventLog.created_at < end)
    if trace_id:
        stmt = stmt.where(EventLog.trace_id == trace_id)
    if job_id:
        stmt = stmt.where(EventLog.job_id == job_id)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = session.execute(
        stmt.order_by(EventLog.created_at.desc()).offset(offset).limit(limit)
    ).scalars()

    items = [
        {
            "id": row.id,
            "created_at": row.created_at,
            "trace_id": row.trace_id,
            "user_id": row.user_id,
            "job_id": row.job_id,
            "event": row.event,
            "payload": row.payload,
        }
        for row in rows
    ]

    return total, items


def get_user_credits(
    session: Session,
    user_id: int,
    start: datetime | None,
    end: datetime | None,
):
    stmt = select(CreditLedger).where(CreditLedger.user_id == user_id)
    if start:
        stmt = stmt.where(CreditLedger.created_at >= start)
    if end:
        stmt = stmt.where(CreditLedger.created_at < end)

    rows = session.execute(stmt.order_by(CreditLedger.created_at.desc())).scalars()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "type": row.type,
            "delta": row.delta,
            "ref_type": row.ref_type,
            "ref_id": row.ref_id,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def get_user_iap(
    session: Session,
    user_id: int,
    start: datetime | None,
    end: datetime | None,
):
    stmt = select(IapTransaction).where(IapTransaction.user_id == user_id)
    if start:
        stmt = stmt.where(IapTransaction.created_at >= start)
    if end:
        stmt = stmt.where(IapTransaction.created_at < end)

    rows = session.execute(stmt.order_by(IapTransaction.created_at.desc())).scalars()
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "store": row.store,
            "product_id": row.product_id,
            "purchase_token": row.purchase_token,
            "status": row.status,
            "raw_payload": row.raw_payload,
            "created_at": row.created_at,
            "verified_at": row.verified_at,
        }
        for row in rows
    ]


def get_trace_events(session: Session, trace_id: str):
    rows = session.execute(
        select(EventLog)
        .where(EventLog.trace_id == trace_id)
        .order_by(EventLog.created_at.asc())
    ).scalars()

    return [
        {
            "id": row.id,
            "created_at": row.created_at,
            "trace_id": row.trace_id,
            "user_id": row.user_id,
            "job_id": row.job_id,
            "event": row.event,
            "payload": row.payload,
        }
        for row in rows
    ]


def get_job_events(session: Session, job_id: str):
    rows = session.execute(
        select(EventLog)
        .where(EventLog.job_id == job_id)
        .order_by(EventLog.created_at.asc())
    ).scalars()

    return [
        {
            "id": row.id,
            "created_at": row.created_at,
            "trace_id": row.trace_id,
            "user_id": row.user_id,
            "job_id": row.job_id,
            "event": row.event,
            "payload": row.payload,
        }
        for row in rows
    ]


def get_errors(
    session: Session,
    start: datetime,
    end: datetime,
    limit: int,
):
    error_type = EventLog.payload["error_type"].astext
    error_message = EventLog.payload["error_message"].astext

    stmt = (
        select(
            EventLog.event,
            error_type.label("error_type"),
            error_message.label("error_message"),
            func.count().label("count"),
            func.min(EventLog.trace_id).label("sample_trace_id"),
            func.min(EventLog.job_id).label("sample_job_id"),
        )
        .where(
            EventLog.created_at >= start,
            EventLog.created_at < end,
            or_(
                EventLog.event.ilike("%failed%"),
                error_type.isnot(None),
                error_message.isnot(None),
            ),
        )
        .group_by(EventLog.event, error_type, error_message)
        .order_by(func.count().desc())
        .limit(limit)
    )

    rows = session.execute(stmt).all()
    items = [
        {
            "event": row.event,
            "error_type": row.error_type,
            "error_message": row.error_message,
            "count": row.count,
            "sample_trace_id": row.sample_trace_id,
            "sample_job_id": row.sample_job_id,
        }
        for row in rows
    ]

    total_stmt = (
        select(func.count())
        .select_from(
            select(EventLog.event)
            .where(
                EventLog.created_at >= start,
                EventLog.created_at < end,
                or_(
                    EventLog.event.ilike("%failed%"),
                    error_type.isnot(None),
                    error_message.isnot(None),
                ),
            )
            .subquery()
        )
    )
    total = session.execute(total_stmt).scalar_one()

    return total, items
