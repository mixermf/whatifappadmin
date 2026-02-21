from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import hmac
import os

import pandas as pd
import streamlit as st

from admin_db import get_session
from admin_queries import (
    Segment,
    get_errors,
    get_funnel,
    get_job_events,
    get_overview_metrics,
    get_recent_users,
    get_trace_events,
    get_user_credits,
    get_user_detail,
    get_user_events,
    get_user_iap,
    get_users,
)


LOGIN_USERNAME = os.getenv("ADMIN")
LOGIN_PASSWORD = os.getenv("ADMIN_PASS")

SEGMENTS = {
    "all": "All users",
    "paying": "Paying",
    "non_paying": "Non-paying",
}


def add_branding():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=Space+Grotesk:wght@500;700&display=swap');
        html, body, [class*="css"]  { font-family: 'IBM Plex Sans', sans-serif; }
        h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif; }
        .block-container { padding-top: 2rem; }
        .metric-label { font-size: 0.95rem; }
        .stMetricValue { font-size: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_login():
    if not LOGIN_USERNAME or not LOGIN_PASSWORD:
        return True

    if st.session_state.get("ui_authenticated"):
        return True

    st.sidebar.warning("Login required.")
    with st.sidebar.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if hmac.compare_digest(username, LOGIN_USERNAME) and hmac.compare_digest(
            password, LOGIN_PASSWORD
        ):
            st.session_state["ui_authenticated"] = True
            st.sidebar.success("Authenticated")
            return True
        st.sidebar.error("Invalid credentials")

    return False


def utc_range_picker(key: str, default_days: int = 7):
    today = datetime.now(timezone.utc).date()
    default_start = today - timedelta(days=default_days)

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start date (UTC)", value=default_start, key=f"{key}_start_date"
        )
        start_time = st.time_input(
            "Start time (UTC)", value=time(0, 0), key=f"{key}_start_time"
        )
    with col2:
        end_date = st.date_input(
            "End date (UTC)", value=today, key=f"{key}_end_date"
        )
        end_time = st.time_input(
            "End time (UTC)", value=time(23, 59), key=f"{key}_end_time"
        )

    start_dt = datetime.combine(start_date, start_time, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, end_time, tzinfo=timezone.utc)
    return start_dt, end_dt


@st.cache_data(ttl=60)
def fetch_overview(start_dt: datetime, end_dt: datetime, segment: str):
    with get_session() as session:
        return get_overview_metrics(session, start_dt, end_dt, Segment(segment))


@st.cache_data(ttl=60)
def fetch_funnel(start_dt: datetime, end_dt: datetime, segment: str):
    with get_session() as session:
        return get_funnel(session, start_dt, end_dt, Segment(segment))


@st.cache_data(ttl=60)
def fetch_users(segment: str, query: str | None, limit: int, offset: int):
    with get_session() as session:
        total, items = get_users(session, Segment(segment), query, limit, offset)
    return {"total": total, "items": items}


@st.cache_data(ttl=60)
def fetch_user_detail(user_id: int):
    with get_session() as session:
        return get_user_detail(session, user_id)


@st.cache_data(ttl=60)
def fetch_user_events(
    user_id: int,
    start_dt: datetime | None,
    end_dt: datetime | None,
    trace_id: str | None,
    job_id: str | None,
    limit: int,
    offset: int,
):
    with get_session() as session:
        total, items = get_user_events(
            session, user_id, start_dt, end_dt, trace_id, job_id, limit, offset
        )
    return {"total": total, "items": items}


@st.cache_data(ttl=60)
def fetch_user_credits(user_id: int, start_dt: datetime | None, end_dt: datetime | None):
    with get_session() as session:
        return get_user_credits(session, user_id, start_dt, end_dt)


@st.cache_data(ttl=60)
def fetch_user_iap(user_id: int, start_dt: datetime | None, end_dt: datetime | None):
    with get_session() as session:
        return get_user_iap(session, user_id, start_dt, end_dt)


@st.cache_data(ttl=60)
def fetch_trace_events(trace_id: str):
    with get_session() as session:
        return get_trace_events(session, trace_id)


@st.cache_data(ttl=60)
def fetch_job_events(job_id: str):
    with get_session() as session:
        return get_job_events(session, job_id)


@st.cache_data(ttl=60)
def fetch_errors(start_dt: datetime, end_dt: datetime, limit: int):
    with get_session() as session:
        total, items = get_errors(session, start_dt, end_dt, limit)
    return {"total": total, "items": items}


@st.cache_data(ttl=60)
def fetch_recent_users(limit: int = 10):
    with get_session() as session:
        return get_recent_users(session, limit)


def render_overview():
    st.header("Overview / KPI")
    start_dt, end_dt = utc_range_picker("overview")
    segment = st.selectbox("Segment", options=list(SEGMENTS.keys()), format_func=SEGMENTS.get)

    if start_dt >= end_dt:
        st.error("Start datetime must be earlier than end datetime.")
        return

    data = fetch_overview(start_dt, end_dt, segment)

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("New users", f"{data['new_users']:,}")
    col2.metric("Active users", f"{data['active_users']:,}")
    col3.metric("Jobs started", f"{data['jobs_started']:,}")
    col4.metric("Jobs succeeded", f"{data['jobs_succeeded']:,}")
    col5.metric("Jobs failed", f"{data['jobs_failed']:,}")
    col6.metric("Conversion to pay", f"{data['conversion_to_pay'] * 100:.1f}%")


def render_funnel():
    st.header("Funnel")
    start_dt, end_dt = utc_range_picker("funnel")

    if start_dt >= end_dt:
        st.error("Start datetime must be earlier than end datetime.")
        return

    tabs = st.tabs([SEGMENTS[key] for key in SEGMENTS])
    for tab, segment in zip(tabs, SEGMENTS, strict=False):
        with tab:
            steps = fetch_funnel(start_dt, end_dt, segment)
            df = pd.DataFrame(steps)
            if df.empty:
                st.info("No events in this period.")
                continue
            df["conversion_from_prev"] = df["conversion_from_prev"].apply(
                lambda value: f"{value * 100:.1f}%"
            )
            st.dataframe(df, use_container_width=True)


def render_users_explorer():
    st.header("Users Explorer")
    segment = st.selectbox("Segment", options=list(SEGMENTS.keys()), format_func=SEGMENTS.get)
    query = st.text_input("Search (user_id, install_id_hash, google_sub)")
    limit = st.slider("Rows", min_value=10, max_value=200, value=50, step=10)

    response = fetch_users(segment, query or None, limit, 0)
    df = pd.DataFrame(response.get("items", []))
    st.caption(f"Total matches: {response.get('total', 0)}")
    st.dataframe(df, use_container_width=True)


def render_user_details():
    st.header("User Details")
    recent_users = fetch_recent_users()
    options = ["(enter manually)"] + [item["id"] for item in recent_users]
    labels = ["(enter manually)"] + [
        f"{item['id']} · {item['created_at']}" for item in recent_users
    ]

    selected = st.selectbox(
        "Quick select recent users",
        options=options,
        format_func=lambda value: labels[options.index(value)],
    )
    if selected == "(enter manually)":
        user_id_input = st.text_input("User ID")
    else:
        user_id_input = selected

    if not user_id_input:
        st.info("Enter a user ID to load details.")
        return

    user_id = user_id_input.strip()
    if not user_id:
        st.error("User ID is required.")
        return
    summary = fetch_user_detail(user_id)
    if not summary:
        st.error("User not found.")
        return

    st.subheader("Summary")
    st.json(summary)

    st.subheader("Credits Ledger")
    credit_start, credit_end = utc_range_picker("credits", default_days=30)
    credits = fetch_user_credits(user_id, credit_start, credit_end)
    st.dataframe(pd.DataFrame(credits), use_container_width=True)

    st.subheader("IAP Transactions")
    iap_start, iap_end = utc_range_picker("iap", default_days=30)
    iap = fetch_user_iap(user_id, iap_start, iap_end)
    st.dataframe(pd.DataFrame(iap), use_container_width=True)

    st.subheader("Event Log")
    events_start, events_end = utc_range_picker("user_events", default_days=7)
    trace_filter = st.text_input("Trace ID filter", key="user_trace_filter")
    job_filter = st.text_input("Job ID filter", key="user_job_filter")

    events_response = fetch_user_events(
        user_id,
        events_start,
        events_end,
        trace_filter or None,
        job_filter or None,
        200,
        0,
    )
    events = events_response.get("items", [])

    st.caption(f"Total events: {events_response.get('total', 0)}")
    for event in events:
        title = f"{event['created_at']} · {event['event']}"
        with st.expander(title):
            st.write(
                f"Trace: {event.get('trace_id') or '-'} | Job: {event.get('job_id') or '-'}"
            )
            st.json(event.get("payload") or {})


def render_trace_job_debugger():
    st.header("Trace / Job Debugger")
    trace_id = st.text_input("Trace ID")
    job_id = st.text_input("Job ID")

    if not trace_id and not job_id:
        st.info("Enter a trace_id or job_id.")
        return

    if trace_id and job_id:
        st.warning("Both provided. Showing trace_id results.")

    events = fetch_trace_events(trace_id) if trace_id else fetch_job_events(job_id)

    if not events:
        st.info("No events found.")
        return

    for event in events:
        event_name = event.get("event", "")
        has_error = "failed" in event_name or (event.get("payload") or {}).get("error_type")
        container = st.error if has_error else st.container
        with container():
            st.markdown(f"**{event['created_at']} · {event_name}**")
            st.caption(
                f"User: {event.get('user_id') or '-'} | Trace: {event.get('trace_id') or '-'} | Job: {event.get('job_id') or '-'}"
            )
            st.json(event.get("payload") or {})


def render_errors():
    st.header("Errors")
    start_dt, end_dt = utc_range_picker("errors", default_days=7)
    limit = st.slider("Rows", min_value=10, max_value=200, value=50, step=10)

    if start_dt >= end_dt:
        st.error("Start datetime must be earlier than end datetime.")
        return

    data = fetch_errors(start_dt, end_dt, limit)
    df = pd.DataFrame(data.get("items", []))
    st.caption(f"Total error events: {data.get('total', 0)}")
    st.dataframe(df, use_container_width=True)


def main():
    st.set_page_config(page_title="WhatIf Admin Analytics", layout="wide")
    add_branding()

    st.sidebar.title("WhatIf Admin")
    st.sidebar.caption("Streamlit analytics console")

    if not require_login():
        st.stop()

    pages = {
        "Overview": render_overview,
        "Funnel": render_funnel,
        "Users Explorer": render_users_explorer,
        "User Details": render_user_details,
        "Trace / Job Debugger": render_trace_job_debugger,
        "Errors": render_errors,
    }
    selection = st.sidebar.radio("Navigation", list(pages.keys()))

    if st.sidebar.button("Clear cache"):
        st.cache_data.clear()
        st.success("Cache cleared")

    pages[selection]()


if __name__ == "__main__":
    main()
