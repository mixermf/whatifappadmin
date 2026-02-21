from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import json
import os

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("ADMIN_API_URL", "").rstrip("/")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
ADMIN_API_BASIC_USERNAME = os.getenv("ADMIN_API_BASIC_USERNAME")
ADMIN_API_BASIC_PASSWORD = os.getenv("ADMIN_API_BASIC_PASSWORD")

UI_USERNAME = os.getenv("ADMIN_UI_USERNAME")
UI_PASSWORD = os.getenv("ADMIN_UI_PASSWORD")

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
    if not UI_USERNAME and not UI_PASSWORD:
        return True

    if st.session_state.get("ui_authenticated"):
        return True

    st.sidebar.warning("Admin UI protected. Please log in.")
    with st.sidebar.form("login_form", clear_on_submit=False):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

    if submitted:
        if username == UI_USERNAME and password == UI_PASSWORD:
            st.session_state["ui_authenticated"] = True
            st.sidebar.success("Authenticated")
            return True
        st.sidebar.error("Invalid credentials")

    return False


def api_get(path: str, params: dict | None = None):
    if not API_URL:
        st.error("ADMIN_API_URL is not configured.")
        st.stop()

    headers = {}
    if ADMIN_TOKEN:
        headers["X-Admin-Token"] = ADMIN_TOKEN

    auth = None
    if ADMIN_API_BASIC_USERNAME and ADMIN_API_BASIC_PASSWORD:
        auth = (ADMIN_API_BASIC_USERNAME, ADMIN_API_BASIC_PASSWORD)

    response = requests.get(
        f"{API_URL}{path}",
        headers=headers,
        params=params,
        auth=auth,
        timeout=30,
    )

    if response.status_code == 401:
        st.error("Unauthorized. Check ADMIN_TOKEN or Basic Auth settings.")
        st.stop()

    response.raise_for_status()
    return response.json()


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


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
def fetch_overview(start_iso: str, end_iso: str, segment: str):
    return api_get(
        "/admin/v1/overview",
        params={"start": start_iso, "end": end_iso, "segment": segment},
    )


@st.cache_data(ttl=60)
def fetch_funnel(start_iso: str, end_iso: str, segment: str):
    return api_get(
        "/admin/v1/funnel",
        params={"start": start_iso, "end": end_iso, "segment": segment},
    )


@st.cache_data(ttl=60)
def fetch_users(segment: str, query: str | None, limit: int, offset: int):
    return api_get(
        "/admin/v1/users",
        params={"segment": segment, "query": query, "limit": limit, "offset": offset},
    )


@st.cache_data(ttl=60)
def fetch_user_detail(user_id: int):
    return api_get(f"/admin/v1/users/{user_id}")


@st.cache_data(ttl=60)
def fetch_user_events(user_id: int, params: dict):
    return api_get(f"/admin/v1/users/{user_id}/events", params=params)


@st.cache_data(ttl=60)
def fetch_user_credits(user_id: int, params: dict):
    return api_get(f"/admin/v1/users/{user_id}/credits", params=params)


@st.cache_data(ttl=60)
def fetch_user_iap(user_id: int, params: dict):
    return api_get(f"/admin/v1/users/{user_id}/iap", params=params)


@st.cache_data(ttl=60)
def fetch_trace_events(trace_id: str):
    return api_get(f"/admin/v1/traces/{trace_id}/events")


@st.cache_data(ttl=60)
def fetch_job_events(job_id: str):
    return api_get(f"/admin/v1/jobs/{job_id}/events")


@st.cache_data(ttl=60)
def fetch_errors(start_iso: str, end_iso: str, limit: int):
    return api_get(
        "/admin/v1/errors",
        params={"start": start_iso, "end": end_iso, "limit": limit},
    )


def render_overview():
    st.header("Overview / KPI")
    start_dt, end_dt = utc_range_picker("overview")
    segment = st.selectbox("Segment", options=list(SEGMENTS.keys()), format_func=SEGMENTS.get)

    if start_dt >= end_dt:
        st.error("Start datetime must be earlier than end datetime.")
        return

    data = fetch_overview(to_iso(start_dt), to_iso(end_dt), segment)

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
            data = fetch_funnel(to_iso(start_dt), to_iso(end_dt), segment)
            steps = data.get("steps", [])
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
    user_id_input = st.text_input("User ID")
    if not user_id_input:
        st.info("Enter a user ID to load details.")
        return

    if not user_id_input.isdigit():
        st.error("User ID must be numeric.")
        return

    user_id = int(user_id_input)
    summary = fetch_user_detail(user_id)

    st.subheader("Summary")
    st.json(summary.get("user", {}))

    st.subheader("Credits Ledger")
    credit_start, credit_end = utc_range_picker("credits", default_days=30)
    credits = fetch_user_credits(
        user_id,
        {"start": to_iso(credit_start), "end": to_iso(credit_end)},
    )
    st.dataframe(pd.DataFrame(credits), use_container_width=True)

    st.subheader("IAP Transactions")
    iap_start, iap_end = utc_range_picker("iap", default_days=30)
    iap = fetch_user_iap(
        user_id,
        {"start": to_iso(iap_start), "end": to_iso(iap_end)},
    )
    st.dataframe(pd.DataFrame(iap), use_container_width=True)

    st.subheader("Event Log")
    events_start, events_end = utc_range_picker("user_events", default_days=7)
    trace_filter = st.text_input("Trace ID filter", key="user_trace_filter")
    job_filter = st.text_input("Job ID filter", key="user_job_filter")

    event_params = {
        "start": to_iso(events_start),
        "end": to_iso(events_end),
        "trace_id": trace_filter or None,
        "job_id": job_filter or None,
        "limit": 200,
        "offset": 0,
    }
    events_response = fetch_user_events(user_id, event_params)
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

    data = fetch_errors(to_iso(start_dt), to_iso(end_dt), limit)
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
