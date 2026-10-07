from __future__ import annotations

from datetime import datetime, timezone
import json

import pandas as pd
import streamlit as st

from src.core.forecast_monitoring import (
    DirectCashForecastSnapshot,
    compare_forecast_snapshots,
    create_forecast_snapshot,
)
from src.demo.v2_scenarios import V2DemoScenario


CUSTOMER_HISTORY_KEY = (
    "riskpilot_customer_forecast_history"
)


def _money(
    value: float,
) -> str:
    sign = ""

    if value > 0:
        sign = "+"

    return (
        f"{sign}${value:,.0f}"
        if value >= 0
        else f"-${abs(value):,.0f}"
    )


def _history_payloads(
) -> list[dict]:
    value = st.session_state.get(
        CUSTOMER_HISTORY_KEY
    )

    if not isinstance(
        value,
        list,
    ):
        value = []

        st.session_state[
            CUSTOMER_HISTORY_KEY
        ] = value

    return value


def _restore_history(
) -> list[
    DirectCashForecastSnapshot
]:
    restored: list[
        DirectCashForecastSnapshot
    ] = []

    for payload in _history_payloads():
        try:
            restored.append(
                DirectCashForecastSnapshot
                .model_validate(
                    payload
                )
            )
        except Exception:
            continue

    return restored


def _build_current_snapshot(
    scenario: V2DemoScenario,
) -> DirectCashForecastSnapshot:
    now = datetime.now(
        timezone.utc
    )

    return create_forecast_snapshot(
        scenario.forecast_input,
        snapshot_id=(
            "customer-current-preview"
        ),
        created_at=now,
        management_reserve=(
            scenario.management_reserve
        ),
    )


def save_customer_snapshot(
    scenario: V2DemoScenario,
) -> DirectCashForecastSnapshot:
    history = _restore_history()

    sequence = (
        len(history)
        + 1
    )

    now = datetime.now(
        timezone.utc
    )

    snapshot = create_forecast_snapshot(
        scenario.forecast_input,
        snapshot_id=(
            f"{scenario.scenario_id}-"
            f"forecast-v{sequence:03d}"
        ),
        created_at=now,
        management_reserve=(
            scenario.management_reserve
        ),
    )

    payloads = _history_payloads()

    payloads.append(
        snapshot.model_dump(
            mode="json"
        )
    )

    st.session_state[
        CUSTOMER_HISTORY_KEY
    ] = payloads

    return snapshot


def clear_customer_history() -> None:
    st.session_state[
        CUSTOMER_HISTORY_KEY
    ] = []


def _comparison_rows(
    comparison,
) -> pd.DataFrame:
    rows = []

    for item in comparison.variances:
        rows.append(
            {
                "Event": (
                    item.event_id
                ),
                "Change type": (
                    item.category
                ),
                "Prior amount": (
                    item.prior_amount
                ),
                "Current amount": (
                    item.current_amount
                ),
                "Prior cash date": (
                    item
                    .prior_effective_cash_date
                ),
                "Current cash date": (
                    item
                    .current_effective_cash_date
                ),
                "Prior evidence": (
                    item.prior_source_type
                ),
                "Current evidence": (
                    item.current_source_type
                ),
                "Explanation": (
                    item.detail
                ),
            }
        )

    return pd.DataFrame(
        rows
    )


def render_customer_forecast_history(
    scenario: V2DemoScenario,
) -> None:
    current = (
        _build_current_snapshot(
            scenario
        )
    )

    history = _restore_history()

    st.markdown(
        """
        <style>
        .rp-history-shell {
            margin: 0.55rem 0 0.75rem;
            padding: 0.72rem 0.82rem;
            border: 1px solid #dce6f3;
            border-radius: 9px;
            background:
                linear-gradient(
                    90deg,
                    #f8fbff 0%,
                    #ffffff 100%
                );
        }

        .rp-history-kicker {
            color: #2563eb;
            font-size: 0.56rem;
            font-weight: 820;
            letter-spacing: 0.10em;
            text-transform: uppercase;
        }

        .rp-history-title {
            margin-top: 0.15rem;
            color: #0b1739;
            font-size: 0.82rem;
            font-weight: 740;
        }

        .rp-history-copy {
            margin-top: 0.12rem;
            color: #718198;
            font-size: 0.64rem;
            line-height: 1.4;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, save_col = st.columns(
        [5, 1.15],
        vertical_alignment="center",
    )

    with left:
        if history:
            latest = history[-1]

            current_is_saved = (
                latest
                .forecast_basis_fingerprint
                == current
                .forecast_basis_fingerprint
            )

            state = (
                "No unsaved forecast changes"
                if current_is_saved
                else "Forecast has changed since last save"
            )

            st.markdown(
                (
                    '<div class="rp-history-shell">'
                    '<div class="rp-history-kicker">'
                    'FORECAST CONTROL'
                    '</div>'
                    '<div class="rp-history-title">'
                    f'{state}'
                    '</div>'
                    '<div class="rp-history-copy">'
                    f'{len(history)} saved version(s) · '
                    f'Latest: {latest.snapshot_id}'
                    '</div>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                (
                    '<div class="rp-history-shell">'
                    '<div class="rp-history-kicker">'
                    'FORECAST CONTROL'
                    '</div>'
                    '<div class="rp-history-title">'
                    'No baseline snapshot saved yet'
                    '</div>'
                    '<div class="rp-history-copy">'
                    'Save an immutable forecast version '
                    'before management review.'
                    '</div>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )

    with save_col:
        if st.button(
            "Save forecast",
            type="primary",
            use_container_width=True,
            key=(
                "riskpilot_save_"
                "customer_forecast"
            ),
        ):
            snapshot = (
                save_customer_snapshot(
                    scenario
                )
            )

            st.success(
                "Saved "
                f"{snapshot.snapshot_id}"
            )

            st.rerun()

    history = _restore_history()

    if not history:
        return

    with st.expander(
        "Forecast history & changes",
        expanded=False,
    ):
        history_rows = []

        for snapshot in reversed(
            history
        ):
            history_rows.append(
                {
                    "Version": (
                        snapshot.snapshot_id
                    ),
                    "Saved at": (
                        snapshot.created_at
                        .astimezone(
                            timezone.utc
                        )
                        .strftime(
                            "%Y-%m-%d %H:%M UTC"
                        )
                    ),
                    "Opening cash": (
                        snapshot.forecast
                        .opening_cash
                    ),
                    "Minimum cash": (
                        snapshot.forecast
                        .minimum_closing_cash
                    ),
                    "Minimum week": (
                        snapshot.forecast
                        .minimum_closing_cash_week
                    ),
                    "Closing cash": (
                        snapshot.forecast
                        .closing_cash
                    ),
                    "Reserve": (
                        snapshot
                        .decision_metrics
                        .management_reserve
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(
                history_rows
            ),
            use_container_width=True,
            hide_index=True,
        )

        latest = history[-1]

        comparison = (
            compare_forecast_snapshots(
                latest,
                current,
            )
        )

        st.markdown(
            "#### Current forecast vs latest saved version"
        )

        if (
            comparison.same_forecast_basis
        ):
            st.success(
                "Current forecast evidence and reserve "
                "policy match the latest saved version."
            )

        else:
            st.warning(
                "Current forecast differs from the "
                "latest saved version."
            )

        c1, c2, c3, c4 = (
            st.columns(4)
        )

        c1.metric(
            "Opening cash change",
            _money(
                comparison
                .opening_cash_change
            ),
        )

        c2.metric(
            "Minimum cash change",
            _money(
                comparison
                .minimum_cash_change
            ),
        )

        c3.metric(
            "Closing cash change",
            _money(
                comparison
                .closing_cash_change
            ),
        )

        c4.metric(
            "Evidence changes",
            len(
                comparison.variances
            ),
        )

        if (
            comparison
            .management_reserve_changed
        ):
            st.info(
                "Management reserve changed from "
                f"${comparison.prior_management_reserve:,.0f} "
                "to "
                f"${comparison.current_management_reserve:,.0f}."
            )

        variance_df = (
            _comparison_rows(
                comparison
            )
        )

        if variance_df.empty:
            st.caption(
                "No event-level forecast revisions "
                "detected."
            )

        else:
            st.markdown(
                "##### Forecast revision drivers"
            )

            st.dataframe(
                variance_df,
                use_container_width=True,
                hide_index=True,
            )

        audit_payload = {
            "workspace": (
                scenario.name
            ),
            "current_forecast": (
                current.model_dump(
                    mode="json"
                )
            ),
            "saved_history": [
                item.model_dump(
                    mode="json"
                )
                for item in history
            ],
            "comparison_to_latest": (
                comparison.model_dump(
                    mode="json"
                )
            ),
        }

        download_col, clear_col = (
            st.columns(
                [3, 1]
            )
        )

        with download_col:
            st.download_button(
                "Download forecast audit JSON",
                data=json.dumps(
                    audit_payload,
                    indent=2,
                ),
                file_name=(
                    "riskpilot_forecast_"
                    "audit.json"
                ),
                mime=(
                    "application/json"
                ),
                use_container_width=True,
            )

        with clear_col:
            if st.button(
                "Clear history",
                use_container_width=True,
                key=(
                    "riskpilot_clear_"
                    "forecast_history"
                ),
            ):
                clear_customer_history()
                st.rerun()
