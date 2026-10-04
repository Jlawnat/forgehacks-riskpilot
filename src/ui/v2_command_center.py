from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.core.command_center import (
    CommandCenterResult,
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
    get_v2_demo_scenarios,
)
from src.ui.v2_copilot import (
    render_v2_copilot,
)


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _pct(value: float) -> str:
    return f"{value:.1%}"


def build_v2_command_center_result(
    scenario_id: str,
) -> CommandCenterResult:
    """
    Deterministic V2 demo entry point used by the UI.

    The UI does not recalculate financial values.
    """
    scenario = get_v2_demo_scenario(
        scenario_id
    )

    return build_command_center(
        scenario,
        created_at=datetime(
            2026,
            10,
            4,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        simulations=2000,
        seed=42,
    )



def _inject_v2_styles() -> None:
    st.markdown(
        """
        <style>
        /* -------------------------------------------------
           RiskPilot V2 visual system
           ------------------------------------------------- */

        .rp-shell {
            margin-top: 0.25rem;
            margin-bottom: 1.25rem;
        }

        .rp-context-bar {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.42rem;
            min-height: 2.75rem;
            margin-top: 1.45rem;
            padding: 0.68rem 0.9rem;
            border: 1px solid #e2e8f0;
            border-radius: 11px;
            background: #f8fafc;
            color: #475569;
            font-size: 0.84rem;
            line-height: 1.35;
        }

        .rp-context-primary {
            color: #0f172a;
            font-weight: 700;
        }

        .rp-context-dot {
            color: #cbd5e1;
            padding: 0 0.08rem;
        }

        .rp-context-value {
            color: #475569;
            font-weight: 500;
        }

        .rp-eyebrow {
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 0.35rem;
        }

        .rp-title-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.25rem;
        }

        .rp-title {
            font-size: 2rem;
            line-height: 1.12;
            font-weight: 700;
            letter-spacing: -0.035em;
            color: #0f172a;
            margin: 0;
        }

        .rp-subtitle {
            color: #64748b;
            font-size: 0.96rem;
            line-height: 1.55;
            max-width: 850px;
            margin-top: 0.5rem;
        }

        .rp-status {
            display: inline-flex;
            align-items: center;
            white-space: nowrap;
            padding: 0.42rem 0.72rem;
            border-radius: 999px;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.035em;
        }

        .rp-status-safe {
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
        }

        .rp-status-watch {
            background: #fffbeb;
            color: #b45309;
            border: 1px solid #fde68a;
        }

        .rp-status-critical {
            background: #fef2f2;
            color: #b91c1c;
            border: 1px solid #fecaca;
        }

        .rp-kpi {
            min-height: 154px;
            padding: 1.05rem 1.1rem 0.95rem 1.1rem;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            background: #ffffff;
            box-shadow:
                0 1px 2px rgba(15, 23, 42, 0.03),
                0 4px 12px rgba(15, 23, 42, 0.025);
        }

        .rp-kpi-label {
            color: #64748b;
            font-size: 0.79rem;
            font-weight: 600;
            margin-bottom: 0.55rem;
        }

        .rp-kpi-value {
            color: #0f172a;
            font-size: 1.85rem;
            line-height: 1.1;
            font-weight: 700;
            letter-spacing: -0.035em;
            margin-bottom: 0.55rem;
        }

        .rp-kpi-note {
            color: #64748b;
            font-size: 0.78rem;
            line-height: 1.35;
        }

        .rp-kpi-note-positive {
            color: #047857;
        }

        .rp-kpi-note-warning {
            color: #b45309;
        }

        .rp-kpi-note-critical {
            color: #b91c1c;
        }

        .rp-decision {
            padding: 1rem 1.1rem;
            border-radius: 12px;
            margin: 0.9rem 0 1.2rem 0;
            border: 1px solid;
        }

        .rp-decision-title {
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            margin-bottom: 0.28rem;
        }

        .rp-decision-text {
            font-size: 0.94rem;
            line-height: 1.5;
            font-weight: 500;
        }

        .rp-decision-safe {
            background: #f0fdf4;
            border-color: #bbf7d0;
            color: #166534;
        }

        .rp-decision-watch {
            background: #fffbeb;
            border-color: #fde68a;
            color: #92400e;
        }

        .rp-decision-critical {
            background: #fef2f2;
            border-color: #fecaca;
            color: #991b1b;
        }

        .rp-section-label {
            color: #64748b;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.07em;
            text-transform: uppercase;
            margin-top: 1.25rem;
            margin-bottom: 0.15rem;
        }

        /* Make V2 selectbox feel less like raw Streamlit */
        div[data-baseweb="select"] > div {
            border-radius: 10px;
        }

        /* Slightly tighter V2 page rhythm */
        div[data-testid="stVerticalBlock"] {
            gap: 0.8rem;
        }
        /* V2 focus mode ----------------------------------- */

        [data-testid="stSidebar"] {
            display: none !important;
        }

        [data-testid="stSidebarCollapsedControl"] {
            display: none !important;
        }

        .riskpilot-hero,
        .riskpilot-disclaimer {
            display: none !important;
        }

        /* RiskPilot workspace tabs -------------------------- */

        .stTabs [data-baseweb="tab-list"] {
            gap: 1.35rem;
            border-bottom: 1px solid #e2e8f0;
        }

        .stTabs [data-baseweb="tab"] {
            height: 46px;
            padding-left: 0;
            padding-right: 0;
            font-weight: 600;
            color: #64748b;
        }

        .stTabs [aria-selected="true"] {
            color: #1d4ed8 !important;
        }

        .stTabs [data-baseweb="tab-highlight"] {
            background-color: #1d4ed8 !important;
        }

        /* RiskPilot insight -------------------------------- */

        .rp-insight {
            border: 1px solid #dbeafe;
            background:
                linear-gradient(
                    135deg,
                    #f8fbff 0%,
                    #f5f7ff 100%
                );
            border-radius: 14px;
            padding: 1.15rem 1.2rem;
            margin: 0.8rem 0 1.35rem 0;
            box-shadow:
                0 1px 2px rgba(15, 23, 42, 0.03);
        }

        .rp-insight-eyebrow {
            color: #1d4ed8;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.075em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .rp-insight-title {
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .rp-insight-body {
            color: #475569;
            font-size: 0.91rem;
            line-height: 1.55;
        }

        .rp-insight-source {
            color: #94a3b8;
            font-size: 0.73rem;
            margin-top: 0.55rem;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def _status_for_result(
    result: CommandCenterResult,
    risk_appetite: float,
) -> tuple[str, str]:
    breach_week = (
        result.brief.position
        .first_reserve_breach_week
    )

    probability = (
        result.simulation
        .shortfall_probability
    )

    if breach_week is not None:
        return (
            "ACTION REQUIRED",
            "critical",
        )

    if probability > risk_appetite:
        return (
            "RISK ABOVE APPETITE",
            "watch",
        )

    return (
        "LIQUIDITY HEALTHY",
        "safe",
    )


def _kpi_card(
    label: str,
    value: str,
    note: str,
    *,
    tone: str = "neutral",
) -> None:
    note_class = ""

    if tone == "positive":
        note_class = " rp-kpi-note-positive"
    elif tone == "warning":
        note_class = " rp-kpi-note-warning"
    elif tone == "critical":
        note_class = " rp-kpi-note-critical"

    st.markdown(
        f"""
        <div class="rp-kpi">
            <div class="rp-kpi-label">{label}</div>
            <div class="rp-kpi-value">{value}</div>
            <div class="rp-kpi-note{note_class}">
                {note}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def _build_liquidity_figure(
    result: CommandCenterResult,
) -> go.Figure:
    """
    Build the V2 liquidity outlook from already-calculated
    deterministic and probabilistic engine outputs.
    """
    weeks = [
        week.week_number
        for week in result.snapshot.forecast.weeks
    ]

    deterministic_cash = [
        float(week.closing_cash)
        for week in result.snapshot.forecast.weeks
    ]

    quantiles = (
        result.simulation.cash_path_quantiles
    )

    p10 = [
        float(point.p10_cash)
        for point in quantiles
    ]

    p50 = [
        float(point.p50_cash)
        for point in quantiles
    ]

    p90 = [
        float(point.p90_cash)
        for point in quantiles
    ]

    reserve = float(
        result.brief.position.management_reserve
    )

    recovery_cash = None

    if result.recovery_evaluation is not None:
        candidate_recovery_cash = [
            float(value)
            for value in (
                result.recovery_evaluation
                .weekly_closing_cash
            )
        ]

        recovery_changes_cash = any(
            abs(recovery_value - baseline_value)
            > 1e-9
            for recovery_value, baseline_value
            in zip(
                candidate_recovery_cash,
                deterministic_cash,
            )
        )

        if recovery_changes_cash:
            recovery_cash = (
                candidate_recovery_cash
            )

    all_values = (
        deterministic_cash
        + p10
        + p90
        + [reserve]
    )

    if recovery_cash is not None:
        all_values += recovery_cash

    lower_bound = min(
        0.0,
        min(all_values),
    )

    upper_bound = max(all_values)

    padding = max(
        5000.0,
        (upper_bound - lower_bound) * 0.08,
    )

    fig = go.Figure()

    # Risk zone below management reserve.
    fig.add_hrect(
        y0=lower_bound - padding,
        y1=reserve,
        fillcolor="rgba(239, 68, 68, 0.045)",
        line_width=0,
        layer="below",
    )

    # P90 first, then P10 filled back to it.
    fig.add_trace(
        go.Scatter(
            x=weeks,
            y=p90,
            mode="lines",
            line=dict(
                width=0,
            ),
            hoverinfo="skip",
            showlegend=False,
            name="P90",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=weeks,
            y=p10,
            mode="lines",
            line=dict(
                width=0,
            ),
            fill="tonexty",
            fillcolor="rgba(59, 130, 246, 0.12)",
            hoverinfo="skip",
            name="P10–P90 uncertainty",
        )
    )

    # Simulated median path.
    fig.add_trace(
        go.Scatter(
            x=weeks,
            y=p50,
            mode="lines",
            name="Simulated median",
            line=dict(
                color="#64748b",
                width=2,
                dash="dot",
            ),
            hovertemplate=(
                "Week %{x}<br>"
                "Median simulated cash: "
                "$%{y:,.0f}<extra></extra>"
            ),
        )
    )

    # Deterministic baseline.
    fig.add_trace(
        go.Scatter(
            x=weeks,
            y=deterministic_cash,
            mode="lines+markers",
            name="Deterministic cash",
            line=dict(
                color="#1d4ed8",
                width=3,
            ),
            marker=dict(
                size=6,
            ),
            hovertemplate=(
                "Week %{x}<br>"
                "Deterministic closing cash: "
                "$%{y:,.0f}<extra></extra>"
            ),
        )
    )

    # Recovery path only when one exists.
    if recovery_cash is not None:
        fig.add_trace(
            go.Scatter(
                x=weeks,
                y=recovery_cash,
                mode="lines",
                name="Recovery plan",
                line=dict(
                    color="#059669",
                    width=3,
                    dash="dash",
                ),
                hovertemplate=(
                    "Week %{x}<br>"
                    "Recovery closing cash: "
                    "$%{y:,.0f}<extra></extra>"
                ),
            )
        )

    # Explicit reserve line.
    fig.add_trace(
        go.Scatter(
            x=weeks,
            y=[
                reserve
                for _ in weeks
            ],
            mode="lines",
            name="Management reserve",
            line=dict(
                color="#dc2626",
                width=2,
                dash="dash",
            ),
            hovertemplate=(
                "Week %{x}<br>"
                "Management reserve: "
                "$%{y:,.0f}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=480,
        margin=dict(
            l=10,
            r=10,
            t=20,
            b=10,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(
                size=12,
                color="#475569",
            ),
        ),
        xaxis=dict(
            title=None,
            tickmode="array",
            tickvals=weeks,
            ticktext=[
                f"W{week}"
                for week in weeks
            ],
            showgrid=False,
            zeroline=False,
            tickfont=dict(
                color="#64748b",
            ),
        ),
        yaxis=dict(
            title=None,
            tickprefix="$",
            tickformat=",.0f",
            gridcolor="rgba(148, 163, 184, 0.18)",
            zeroline=False,
            tickfont=dict(
                color="#64748b",
            ),
            range=[
                lower_bound - padding,
                upper_bound + padding,
            ],
        ),
    )

    fig.add_annotation(
        x=weeks[-1],
        y=reserve,
        text=(
            f"Reserve ${reserve:,.0f}"
        ),
        showarrow=False,
        xanchor="right",
        yshift=12,
        font=dict(
            size=11,
            color="#b91c1c",
        ),
    )

    return fig



def _driver_display_rows(
    result: CommandCenterResult,
) -> list[dict[str, object]]:
    """
    Human-facing cash-driver rows.

    Internal event IDs stay out of the primary table and remain
    available separately for auditability.
    """
    rows: list[dict[str, object]] = []

    for driver in result.brief.cash_drivers:
        effect = float(
            driver.signed_cash_effect
        )

        impact = (
            f"+{_money(effect)}"
            if effect >= 0.0
            else f"-{_money(abs(effect))}"
        )

        rows.append(
            {
                "Cash driver": (
                    driver.category
                    .replace("_", " ")
                    .title()
                ),
                "Timing": (
                    f"Week {driver.week_number}"
                ),
                "Evidence": (
                    driver.source_type
                    .replace("_", " ")
                    .title()
                ),
                "Direction": (
                    driver.direction.title()
                ),
                "Impact": impact,
            }
        )

    return rows



def _build_riskpilot_insight(
    result: CommandCenterResult,
    scenario,
) -> tuple[str, str]:
    """
    Build a management-facing insight using only values already
    calculated by the V2 engines.

    No AI-generated or replacement financial values are created.
    """
    position = result.brief.position

    breach_probability = float(
        result.simulation.shortfall_probability
    )

    appetite = float(
        scenario.max_reserve_breach_probability
    )

    evidence = (
        position.evidence_coverage_ratio
    )

    recovery = result.brief.recovery

    if (
        position.first_reserve_breach_week
        is not None
    ):
        week = (
            position.first_reserve_breach_week
        )

        gap = abs(
            float(position.minimum_headroom)
        )

        if (
            recovery is not None
            and recovery.deterministic_feasible
            and recovery.reserve_breach_probability
            is not None
        ):
            return (
                "Recovery can restore the liquidity position",
                (
                    "Baseline cash falls "
                    f"{_money(gap)} below reserve in Week "
                    f"{week}. The current recovery plan uses "
                    f"{_money(recovery.external_liquidity)} "
                    "of external liquidity and reduces "
                    "modelled breach risk from "
                    f"{_pct(breach_probability)} to "
                    f"{_pct(recovery.reserve_breach_probability)}."
                ),
            )

        return (
            "Near-term liquidity action is required",
            (
                "Baseline cash falls "
                f"{_money(gap)} below the management "
                f"reserve in Week {week}. Current simulated "
                f"breach risk is {_pct(breach_probability)} "
                f"against a {_pct(appetite)} management "
                "risk appetite."
            ),
        )

    if breach_probability > appetite:
        headroom = float(
            position.minimum_headroom
        )

        evidence_text = (
            (
                f"{_pct(evidence)} of forecast evidence "
                "is committed"
            )
            if evidence is not None
            else
            "forecast evidence coverage is unavailable"
        )

        if (
            recovery is not None
            and recovery
            .additional_upfront_buffer_at_confidence
            is not None
            and recovery
            .risk_adjusted_breach_probability
            is not None
        ):
            return (
                "Uncertainty—not the base forecast—is the main risk",
                (
                    "Deterministic cash keeps "
                    f"{_money(headroom)} of minimum reserve "
                    "headroom, but simulated breach risk is "
                    f"{_pct(breach_probability)} versus a "
                    f"{_pct(appetite)} appetite. "
                    f"{evidence_text}. An additional "
                    f"{_money(recovery.additional_upfront_buffer_at_confidence)} "
                    "upfront liquidity buffer reduces modelled "
                    "breach risk to "
                    f"{_pct(recovery.risk_adjusted_breach_probability)}."
                ),
            )

        return (
            "Uncertainty—not the base forecast—is the main risk",
            (
                "Deterministic cash remains above reserve, "
                f"but simulated breach risk is "
                f"{_pct(breach_probability)} versus a "
                f"{_pct(appetite)} management appetite. "
                f"{evidence_text}."
            ),
        )

    headroom = float(
        position.minimum_headroom
    )

    evidence_text = (
        (
            f"Evidence coverage is {_pct(evidence)}."
        )
        if evidence is not None
        else
        ""
    )

    return (
        "Liquidity remains resilient over the 13-week horizon",
        (
            "The deterministic forecast maintains "
            f"{_money(headroom)} of minimum reserve headroom "
            f"and simulated breach risk is "
            f"{_pct(breach_probability)}, within the "
            f"{_pct(appetite)} management appetite. "
            f"{evidence_text}"
        ),
    )


def _render_riskpilot_insight(
    result: CommandCenterResult,
    scenario,
) -> None:
    title, body = _build_riskpilot_insight(
        result,
        scenario,
    )

    st.markdown(
        f"""
        <div class="rp-insight">
            <div class="rp-insight-eyebrow">
                RiskPilot Insight
            </div>
            <div class="rp-insight-title">
                {title}
            </div>
            <div class="rp-insight-body">
                {body}
            </div>
            <div class="rp-insight-source">
                Grounded in the V2 forecast, uncertainty,
                recovery and evidence engines.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_overview_tab(
    result: CommandCenterResult,
    scenario,
) -> None:
    brief = result.brief
    position = brief.position

    st.markdown("### Risk posture")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Baseline breach risk",
        _pct(
            result.simulation
            .shortfall_probability
        ),
    )

    c2.metric(
        "Risk appetite",
        _pct(
            scenario
            .max_reserve_breach_probability
        ),
    )

    c3.metric(
        "Confidence liquidity buffer",
        _money(
            result.simulation
            .liquidity_buffer_at_confidence
        ),
    )

    st.markdown("### Evidence quality")

    evidence = (
        position.evidence_coverage_ratio
    )

    if evidence is not None:
        st.progress(
            float(evidence)
        )

        st.caption(
            f"{_pct(evidence)} of committed + "
            "unreconciled modelled forecast evidence "
            "is committed evidence."
        )
    else:
        st.caption(
            "Evidence coverage is not available "
            "for this forecast."
        )

    e1, e2, e3 = st.columns(3)

    e1.metric(
        "Committed evidence",
        _money(
            position.committed_evidence_amount
        ),
    )

    e2.metric(
        "Modelled residual",
        _money(
            position.modelled_residual_amount
        ),
    )

    e3.metric(
        "Management assumptions",
        _money(
            position.management_assumption_amount
        ),
    )

    st.caption(
        "Evidence coverage measures forecast evidence "
        "quality. It is not a probability or confidence score."
    )


def _render_drivers_tab(
    result: CommandCenterResult,
) -> None:
    rows = _driver_display_rows(
        result
    )

    st.markdown("### Material cash drivers")

    st.caption(
        "Largest forecast cash movements are shown in "
        "management-friendly form. Internal references remain "
        "available for audit."
    )

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info(
            "No material future cash drivers are present."
        )

    if result.brief.cash_drivers:
        with st.expander(
            "Audit references"
        ):
            for driver in (
                result.brief.cash_drivers
            ):
                st.code(
                    (
                        f"{driver.category} · "
                        f"Week {driver.week_number} · "
                        f"{driver.event_id}"
                    ),
                    language=None,
                )


def _render_recovery_tab(
    result: CommandCenterResult,
) -> None:
    recovery = result.brief.recovery

    if recovery is None:
        st.success(
            "No recovery intervention is currently "
            "required for this scenario."
        )
        return

    st.markdown("### Recovery assessment")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Deterministic feasibility",
        (
            "Feasible"
            if recovery.deterministic_feasible
            else "Shortfall"
        ),
    )

    c2.metric(
        "External liquidity",
        _money(
            recovery.external_liquidity
        ),
    )

    c3.metric(
        "Plan breach risk",
        (
            _pct(
                recovery
                .reserve_breach_probability
            )
            if (
                recovery
                .reserve_breach_probability
                is not None
            )
            else "Not assessed"
        ),
    )

    c4.metric(
        "Uncertainty buffer",
        (
            _money(
                recovery
                .additional_upfront_buffer_at_confidence
            )
            if (
                recovery
                .additional_upfront_buffer_at_confidence
                is not None
            )
            else "Not assessed"
        ),
    )

    status = (
        recovery
        .probabilistic_validation_status
    )

    if status == (
        "OPERATIONALLY_FEASIBLE_AND_"
        "PROBABILISTICALLY_ADEQUATE"
    ):
        st.success(
            "The current recovery plan restores liquidity "
            "and remains within management risk appetite "
            "under the uncertainty test."
        )

    elif status == (
        "DETERMINISTICALLY_SUFFICIENT_BUT_"
        "PROBABILISTICALLY_INADEQUATE"
    ):
        st.warning(
            "The deterministic plan preserves the reserve, "
            "but uncertainty leaves breach risk above "
            "management appetite."
        )

    elif status == (
        "EXECUTABLE_ACTIONS_WITH_"
        "FINANCIAL_SHORTFALL"
    ):
        st.error(
            "The proposed actions are executable but still "
            "leave a liquidity shortfall."
        )

    if (
        recovery
        .risk_adjusted_breach_probability
        is not None
        and recovery
        .additional_upfront_buffer_at_confidence
        is not None
        and recovery
        .additional_upfront_buffer_at_confidence
        > 0.0
    ):
        st.markdown("#### With uncertainty buffer")

        b1, b2 = st.columns(2)

        b1.metric(
            "Risk-adjusted breach probability",
            _pct(
                recovery
                .risk_adjusted_breach_probability
            ),
        )

        b2.metric(
            "Within appetite",
            (
                "Yes"
                if (
                    recovery
                    .risk_adjusted_within_risk_appetite
                )
                else "No"
            ),
        )

    if result.brief.limitations:
        with st.expander(
            "Recovery model limitations"
        ):
            for limitation in (
                result.brief.limitations
            ):
                st.write(
                    f"- {limitation}"
                )


def _render_actions_monitoring_tab(
    result: CommandCenterResult,
    scenario,
) -> None:
    brief = result.brief

    left, right = st.columns(2)

    with left:
        st.markdown("### Management actions")

        if not brief.actions.actions:
            if (
                result.simulation.shortfall_probability
                > scenario.max_reserve_breach_probability
            ):
                st.warning(
                    "No management action is currently "
                    "registered while liquidity risk remains "
                    "above management appetite."
                )
            else:
                st.info(
                    "No active recovery action is "
                    "currently required."
                )
        else:
            for action in brief.actions.actions:
                st.markdown(
                    f"**{action.action}**"
                )

                st.caption(
                    f"Owner: {action.owner} · "
                    f"Target: {action.target_date} · "
                    f"Expected impact: "
                    f"{_money(action.expected_cash_impact)} · "
                    f"Status: "
                    f"{action.status.replace('_', ' ').title()}"
                )

    with right:
        st.markdown("### Baseline monitoring")

        st.caption(
            "Triggers reflect the current forecast before "
            "proposed recovery actions."
        )

        if (
            brief.monitoring is None
            or not brief.monitoring.triggers
        ):
            st.success(
                "No active monitoring triggers."
            )
        else:
            for trigger in brief.monitoring.triggers:
                if trigger.severity == "CRITICAL":
                    st.error(
                        trigger.message
                    )
                else:
                    st.warning(
                        trigger.message
                    )

                st.caption(
                    trigger.trigger_type
                    .replace("_", " ")
                    .title()
                )


def _render_v2_workspace(
    result: CommandCenterResult,
    scenario,
) -> None:
    (
        overview_tab,
        drivers_tab,
        recovery_tab,
        actions_tab,
    ) = st.tabs(
        [
            "Overview",
            "Cash Drivers",
            "Recovery",
            "Actions & Monitoring",
        ]
    )

    with overview_tab:
        _render_overview_tab(
            result,
            scenario,
        )

    with drivers_tab:
        _render_drivers_tab(
            result
        )

    with recovery_tab:
        _render_recovery_tab(
            result
        )

    with actions_tab:
        _render_actions_monitoring_tab(
            result,
            scenario,
        )


def render_v2_command_center() -> None:
    _inject_v2_styles()

    scenarios = get_v2_demo_scenarios()

    name_to_id = {
        scenario.name: scenario.scenario_id
        for scenario in scenarios
    }

    scenario_names = list(
        name_to_id
    )

    (
        context_col,
        selector_col,
    ) = st.columns(
        [4.8, 1.6],
        vertical_alignment="center",
    )

    with selector_col:
        selected_name = st.selectbox(
            "Change scenario",
            scenario_names,
            index=0,
            key="riskpilot_v2_scenario",
        )

    scenario_id = name_to_id[
        selected_name
    ]

    scenario = get_v2_demo_scenario(
        scenario_id
    )

    result = build_v2_command_center_result(
        scenario_id
    )

    brief = result.brief
    position = brief.position

    forecast_weeks = len(
        result.snapshot.forecast.weeks
    )

    with context_col:
        st.markdown(
            f"""
            <div class="rp-context-bar">
                <span class="rp-context-primary">
                    {scenario.name}
                </span>
                <span class="rp-context-dot">·</span>
                <span class="rp-context-value">
                    {forecast_weeks}-week forecast
                </span>
                <span class="rp-context-dot">·</span>
                <span class="rp-context-value">
                    Reserve {_money(position.management_reserve)}
                </span>
                <span class="rp-context-dot">·</span>
                <span class="rp-context-value">
                    Risk appetite
                    {_pct(scenario.max_reserve_breach_probability)}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    status_label, status_tone = (
        _status_for_result(
            result,
            scenario.max_reserve_breach_probability,
        )
    )

    status_class = (
        f"rp-status rp-status-{status_tone}"
    )

    st.markdown(
        f"""
        <div class="rp-shell">
            <div class="rp-eyebrow">
                RiskPilot · Liquidity Intelligence
            </div>
            <div class="rp-title-row">
                <h1 class="rp-title">
                    13-Week Liquidity Command Center
                </h1>
                <span class="{status_class}">
                    {status_label}
                </span>
            </div>
            <div class="rp-subtitle">
                {scenario.description}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    breach_week = (
        position.first_reserve_breach_week
    )

    breach_probability = (
        result.simulation.shortfall_probability
    )

    risk_appetite = (
        scenario.max_reserve_breach_probability
    )

    if breach_week is not None:
        decision_class = (
            "rp-decision rp-decision-critical"
        )
        decision_title = "Action required"
        decision_text = (
            "Cash is projected to fall "
            f"{_money(abs(position.minimum_headroom))} "
            "below the management reserve in "
            f"Week {breach_week}. Review the "
            "recovery plan now."
        )

    elif breach_probability > risk_appetite:
        decision_class = (
            "rp-decision rp-decision-watch"
        )
        decision_title = "Risk requires attention"
        decision_text = (
            "The deterministic forecast remains "
            "above reserve, but simulated breach risk "
            f"is {_pct(breach_probability)} versus a "
            f"{_pct(risk_appetite)} management appetite."
        )

    else:
        decision_class = (
            "rp-decision rp-decision-safe"
        )
        decision_title = (
            "Liquidity position healthy"
        )
        decision_text = (
            "Projected cash remains above the "
            "management reserve throughout the "
            "13-week horizon and simulated breach "
            "risk remains within appetite."
        )

    st.markdown(
        f"""
        <div class="{decision_class}">
            <div class="rp-decision-title">
                {decision_title}
            </div>
            <div class="rp-decision-text">
                {decision_text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="rp-section-label">'
        'Liquidity snapshot'
        '</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        headroom_today = (
            position.current_cash
            - position.management_reserve
        )

        _kpi_card(
            "Current cash",
            _money(
                position.current_cash
            ),
            (
                f"{_money(headroom_today)} "
                "above reserve today"
                if headroom_today >= 0
                else
                f"{_money(abs(headroom_today))} "
                "below reserve today"
            ),
            tone=(
                "positive"
                if headroom_today >= 0
                else "critical"
            ),
        )

    with c2:
        minimum_note = (
            f"Week "
            f"{position.minimum_closing_cash_week}"
        )

        if position.minimum_headroom < 0:
            minimum_note += (
                f" · "
                f"{_money(abs(position.minimum_headroom))} "
                "below reserve"
            )
            minimum_tone = "critical"
        else:
            minimum_note += (
                f" · "
                f"{_money(position.minimum_headroom)} "
                "headroom"
            )
            minimum_tone = "positive"

        _kpi_card(
            "Minimum projected cash",
            _money(
                position.minimum_closing_cash
            ),
            minimum_note,
            tone=minimum_tone,
        )

    with c3:
        _kpi_card(
            "Reserve-breach probability",
            _pct(
                breach_probability
            ),
            (
                "Management appetite "
                f"{_pct(risk_appetite)}"
            ),
            tone=(
                "critical"
                if (
                    breach_probability
                    > risk_appetite
                )
                else "positive"
            ),
        )

    with c4:
        evidence = (
            position.evidence_coverage_ratio
        )

        _kpi_card(
            "Evidence coverage",
            (
                _pct(evidence)
                if evidence is not None
                else "N/A"
            ),
            (
                "Committed vs modelled "
                "forecast evidence"
            ),
            tone=(
                "positive"
                if (
                    evidence is not None
                    and evidence >= 0.70
                )
                else "warning"
            ),
        )

    st.markdown(
        '<div class="rp-section-label">'
        'Liquidity outlook'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        "## 13-week cash trajectory"
    )

    st.caption(
        "The shaded band shows the simulated P10–P90 "
        "cash range. The red area is below the management "
        "reserve. A recovery path appears only when a "
        "recovery plan changes the projected cash path."
    )

    st.plotly_chart(
        _build_liquidity_figure(
            result
        ),
        use_container_width=True,
        config={
            "displaylogo": False,
            "displayModeBar": False,
        },
    )

    _render_riskpilot_insight(
        result,
        scenario,
    )

    render_v2_copilot(
        result.brief
    )

    st.markdown(
        '<div class="rp-section-label">'
        'Decision workspace'
        '</div>',
        unsafe_allow_html=True,
    )

    _render_v2_workspace(
        result,
        scenario,
    )

    st.caption(
        "All financial values are calculated by "
        "RiskPilot's V2 engines. AI explanations do not "
        "replace or recalculate these values."
    )
