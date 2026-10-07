from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.command_center import (
    CommandCenterResult,
)


def _money(
    value: float,
) -> str:
    return f"${value:,.0f}"


def _event_lookup(
    result: CommandCenterResult,
):
    return {
        event.event_id: event
        for event in (
            result.snapshot
            .forecast_input
            .events
        )
    }


def _week_rows(
    result: CommandCenterResult,
    *,
    week_number: int,
) -> pd.DataFrame:
    event_lookup = _event_lookup(
        result
    )

    week = next(
        item
        for item in (
            result.snapshot
            .forecast.weeks
        )
        if (
            item.week_number
            == week_number
        )
    )

    rows = []

    for contribution in (
        week.contributions
    ):
        event = event_lookup.get(
            contribution.event_id
        )

        signed = (
            contribution.included_amount
            if (
                contribution.direction
                == "INFLOW"
            )
            else (
                -contribution
                .included_amount
            )
        )

        rows.append(
            {
                "Cash event": (
                    contribution
                    .event_id
                ),
                "Category": (
                    event.category
                    if event is not None
                    else "Unknown"
                ),
                "Direction": (
                    contribution
                    .direction
                ),
                "Evidence": (
                    contribution
                    .source_type
                ),
                "Gross amount": (
                    contribution
                    .gross_amount
                ),
                "Included amount": (
                    contribution
                    .included_amount
                ),
                "Cash impact": signed,
                "Effective date": (
                    contribution
                    .effective_cash_date
                    .isoformat()
                ),
                "Source": (
                    event
                    .source_reference
                    if event is not None
                    else "Unknown"
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


def render_customer_evidence_drilldown(
    result: CommandCenterResult,
) -> None:
    forecast = (
        result.snapshot
        .forecast
    )

    with st.expander(
        "Evidence drill-down · Explain the cash forecast",
        expanded=False,
    ):
        st.caption(
            "Trace every weekly closing-cash value "
            "back to the cash events included by "
            "RiskPilot's direct-cash engine."
        )

        week_numbers = [
            week.week_number
            for week in (
                forecast.weeks
            )
        ]

        selected_week = st.selectbox(
            "Inspect forecast week",
            week_numbers,
            index=(
                forecast
                .minimum_closing_cash_week
                - 1
            ),
            format_func=(
                lambda value: (
                    f"Week {value}"
                )
            ),
            key=(
                "riskpilot_evidence_"
                "drill_week"
            ),
        )

        week = next(
            item
            for item in (
                forecast.weeks
            )
            if (
                item.week_number
                == selected_week
            )
        )

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        c1.metric(
            "Opening cash",
            _money(
                week.opening_cash
            ),
        )

        c2.metric(
            "Total inflows",
            _money(
                week.total_inflows
            ),
        )

        c3.metric(
            "Total outflows",
            _money(
                week.total_outflows
            ),
        )

        c4.metric(
            "Closing cash",
            _money(
                week.closing_cash
            ),
        )

        evidence_cols = st.columns(
            3
        )

        evidence_cols[0].metric(
            "Committed inflows",
            _money(
                week.committed_inflows
            ),
        )

        evidence_cols[1].metric(
            "Modelled inflows",
            _money(
                week.modelled_inflows
            ),
        )

        evidence_cols[2].metric(
            "Committed outflows",
            _money(
                week.committed_outflows
            ),
        )

        rows = _week_rows(
            result,
            week_number=(
                selected_week
            ),
        )

        if rows.empty:
            st.info(
                "No cash events are included "
                "in this week."
            )

        else:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Gross amount": (
                        st.column_config
                        .NumberColumn(
                            format="$%.2f"
                        )
                    ),
                    "Included amount": (
                        st.column_config
                        .NumberColumn(
                            format="$%.2f"
                        )
                    ),
                    "Cash impact": (
                        st.column_config
                        .NumberColumn(
                            format="$%.2f"
                        )
                    ),
                },
            )

        st.caption(
            "Included amount reflects RiskPilot's "
            "validated reconciliation rules. "
            "COMMITTED evidence is not silently "
            "reduced by modelled assumptions."
        )
