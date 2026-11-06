from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

import streamlit as st
from gtm_analytics.db.config import get_engine

st.set_page_config(page_title="GTM Analytics", page_icon="📊", layout="wide")

WEEKLY_USAGE_SQL = """
select
    account_id,
    week_start_date,
    activity_count,
    feature_used_count,
    campaign_published_count,
    report_viewed_count,
    meeting_count,
    email_count
from mart.account_weekly_usage
order by account_id, week_start_date
"""

FOLLOW_UP_PRIORITY_SQL = """
select
    account_key,
    account_id,
    account_name,
    industry,
    opportunity_key,
    opportunity_id,
    opportunity_name,
    current_stage,
    latest_snapshot_date,
    current_stage_start_date,
    days_in_current_stage,
    recent_four_week_average,
    prior_four_week_average,
    weekly_activity_average_change,
    weekly_activity_average_change_percent,
    has_complete_usage_windows,
    is_usage_increasing,
    is_open_opportunity,
    is_stalled_opportunity,
    is_primary_follow_up,
    follow_up_reason
from mart.account_follow_up_priority
order by is_primary_follow_up desc, account_name, opportunity_name
"""


@st.cache_resource
def get_database_engine() -> Engine:
    return get_engine()


@st.cache_data(ttl=60)
def load_mart_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    with get_database_engine().connect() as connection:
        weekly_usage = pd.read_sql_query(WEEKLY_USAGE_SQL, connection)
        follow_up_priority = pd.read_sql_query(FOLLOW_UP_PRIORITY_SQL, connection)
    return weekly_usage, follow_up_priority


st.title("GTM Analytics")
st.caption(
    "Explore account activity trends and the opportunities prioritized for follow-up."
)

if st.sidebar.button("Refresh data"):
    st.cache_data.clear()
    st.rerun()

try:
    weekly_usage, follow_up_priority = load_mart_data()
except (KeyError, ValueError) as error:
    st.error(f"Analytics PostgreSQL configuration is missing or invalid: {error}")
    st.stop()
except SQLAlchemyError as error:
    st.error(f"Could not load the mart tables from PostgreSQL: {error}")
    st.stop()

if weekly_usage.empty and follow_up_priority.empty:
    st.warning("The mart tables are empty. Run `make dbt-build` to create the models.")
    st.stop()

account_names = dict(
    zip(
        follow_up_priority["account_id"].astype(str),
        follow_up_priority["account_name"].fillna("").astype(str),
        strict=False,
    )
)
account_ids = sorted(
    set(weekly_usage.get("account_id", pd.Series(dtype=str)).dropna().astype(str))
    | set(
        follow_up_priority.get("account_id", pd.Series(dtype=str)).dropna().astype(str)
    )
)

selected_account_id = st.sidebar.selectbox(
    "Account",
    options=[None, *account_ids],
    format_func=lambda account_id: (
        "All accounts"
        if account_id is None
        else f"{account_names.get(account_id) or account_id} ({account_id})"
    ),
)
primary_only = st.sidebar.checkbox("Show primary follow-ups only", value=True)
st.sidebar.caption("Dashboard data is cached for up to 60 seconds.")

primary_count = int(follow_up_priority["is_primary_follow_up"].fillna(False).sum())
stalled_count = int(follow_up_priority["is_stalled_opportunity"].fillna(False).sum())
increasing_count = int(follow_up_priority["is_usage_increasing"].fillna(False).sum())
total_activity = int(weekly_usage["activity_count"].sum())

metric_columns = st.columns(4)
metric_columns[0].metric("Primary follow-ups", primary_count)
metric_columns[1].metric("Stalled open opportunities", stalled_count)
metric_columns[2].metric("Opportunities with rising usage", increasing_count)
metric_columns[3].metric("Activity events", f"{total_activity:,}")

follow_up_tab, weekly_usage_tab = st.tabs(["Follow-up priority", "Weekly usage"])

with follow_up_tab:
    filtered_priority = follow_up_priority.copy()
    if selected_account_id is not None:
        filtered_priority = filtered_priority[
            filtered_priority["account_id"] == selected_account_id
        ]
    if primary_only:
        filtered_priority = filtered_priority[
            filtered_priority["is_primary_follow_up"].fillna(False)
        ]

    st.subheader("Account and opportunity signals")
    if filtered_priority.empty:
        st.info("No follow-up records match the selected filters.")
    else:
        chart_data = filtered_priority[
            [
                "account_name",
                "opportunity_name",
                "prior_four_week_average",
                "recent_four_week_average",
            ]
        ].copy()
        chart_data["record"] = (
            chart_data["account_name"].fillna(chart_data["opportunity_name"])
            + " — "
            + chart_data["opportunity_name"].fillna("No opportunity")
        )
        for column in ("prior_four_week_average", "recent_four_week_average"):
            chart_data[column] = pd.to_numeric(chart_data[column], errors="coerce")

        st.bar_chart(
            chart_data,
            x="record",
            y=["prior_four_week_average", "recent_four_week_average"],
            x_label="Account — opportunity",
            y_label="Average activity per week",
        )

        display_columns = [
            "account_name",
            "opportunity_name",
            "current_stage",
            "days_in_current_stage",
            "prior_four_week_average",
            "recent_four_week_average",
            "weekly_activity_average_change_percent",
            "is_primary_follow_up",
            "follow_up_reason",
        ]
        st.dataframe(
            filtered_priority[display_columns],
            hide_index=True,
            width="stretch",
            column_config={
                "days_in_current_stage": st.column_config.NumberColumn(
                    "Days in stage", format="%d"
                ),
                "prior_four_week_average": st.column_config.NumberColumn(
                    "Prior 4-week average", format="%.1f"
                ),
                "recent_four_week_average": st.column_config.NumberColumn(
                    "Recent 4-week average", format="%.1f"
                ),
                "weekly_activity_average_change_percent": (
                    st.column_config.NumberColumn(
                        "Activity change (%)", format="%.1f%%"
                    )
                ),
                "is_primary_follow_up": st.column_config.CheckboxColumn(
                    "Primary follow-up"
                ),
            },
        )

with weekly_usage_tab:
    filtered_usage = weekly_usage.copy()
    if selected_account_id is not None:
        filtered_usage = filtered_usage[
            filtered_usage["account_id"] == selected_account_id
        ]

    st.subheader("Weekly product activity")
    if filtered_usage.empty:
        st.info("No weekly activity matches the selected account.")
    else:
        weekly_chart = (
            filtered_usage.groupby("week_start_date", as_index=False)["activity_count"]
            .sum()
            .sort_values("week_start_date")
        )
        chart_label = (
            account_names.get(selected_account_id, selected_account_id)
            if selected_account_id is not None
            else "All accounts"
        )
        st.caption(f"Activity counts for {chart_label}.")
        st.line_chart(
            weekly_chart,
            x="week_start_date",
            y="activity_count",
            x_label="Week starting",
            y_label="Activity events",
        )

        display_usage = filtered_usage.copy()
        display_usage.insert(
            1,
            "account_name",
            display_usage["account_id"].map(account_names).fillna(""),
        )
        st.dataframe(
            display_usage[
                [
                    "account_name",
                    "account_id",
                    "week_start_date",
                    "activity_count",
                    "feature_used_count",
                    "campaign_published_count",
                    "report_viewed_count",
                    "meeting_count",
                    "email_count",
                ]
            ],
            hide_index=True,
            width="stretch",
        )
