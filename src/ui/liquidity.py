from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.core.context import ForecastContext

from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity_from_context,
)


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def probability(value: float) -> str:
    return f"{value * 100:.1f}%"


def _run_simulation(
    context: ForecastContext,
    revenue_change: float,
    cost_change: float,
    receivable_delay_days: int,
    horizon: int,
    simulations: int = 5000,
    seed: int = 42,
    cash_floor: float = 0.0,
):
    return simulate_liquidity_from_context(
        context,
        SimulationInput(
            revenue_change=revenue_change,
            cost_change=cost_change,
            receivable_delay_days=(
                receivable_delay_days
            ),
            horizon=horizon,
            simulations=simulations,
            seed=seed,
            confidence_level=0.95,
            cash_floor=cash_floor,
        ),
    )


def render_liquidity_risk(
    context: ForecastContext,
    cash_floor: float = 0.0,
    max_shortfall_probability: float = 0.05,
) -> None:
    st.subheader("Probabilistic Liquidity Risk")

    st.write(
        "RiskPilot bootstraps paired historical forecast errors "
        "to simulate 5,000 possible future cash paths. "
        "This estimates the probability and severity of a cash shortfall "
        "instead of relying on a single deterministic forecast."
    )

    with st.spinner("Simulating liquidity distributions..."):
        baseline = _run_simulation(
            context,
            revenue_change=0.0,
            cost_change=0.0,
            receivable_delay_days=0,
            horizon=3,
            cash_floor=cash_floor,
        )

        moderate = _run_simulation(
            context,
            revenue_change=-0.002,
            cost_change=0.004,
            receivable_delay_days=0,
            horizon=3,
            cash_floor=cash_floor,
        )

        severe = _run_simulation(
            context,
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
            cash_floor=cash_floor,
        )

    insolvency_baseline = _run_simulation(
        context,
        revenue_change=0.0,
        cost_change=0.0,
        receivable_delay_days=0,
        horizon=3,
        cash_floor=0.0,
    )

    # --------------------------------------------------------------
    # HEADLINE RISK
    # --------------------------------------------------------------

    st.markdown("### Baseline liquidity distribution")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Reserve-breach probability",
        probability(
            baseline.shortfall_probability
        ),
    )

    c2.metric(
        "Cash-negative probability",
        probability(
            insolvency_baseline
            .shortfall_probability
        ),
    )

    c3.metric(
        "P10 downside cash",
        money(
            baseline.p10_end_cash
        ),
    )

    c4.metric(
        "95% liquidity buffer",
        money(
            baseline.liquidity_buffer_at_confidence
        ),
    )

    if (
        baseline.shortfall_probability
        <= max_shortfall_probability
    ):
        st.success(
            "Liquidity risk is within the selected "
            "management appetite."
        )
    else:
        st.error(
            "Liquidity risk exceeds management appetite: "
            f"{probability(baseline.shortfall_probability)} "
            "reserve-breach probability versus "
            f"{probability(max_shortfall_probability)} allowed."
        )

    if baseline.residual_pairs_available < 20:
        st.warning(
            "Low-sample simulation: only "
            f"{baseline.residual_pairs_available} paired rolling "
            "forecast errors are available. "
            "Treat these probabilities as indicative rather than "
            "production-grade estimates."
        )

    # --------------------------------------------------------------
    # FAN CHART
    # --------------------------------------------------------------

    st.markdown("### Probabilistic cash fan")

    periods = [
        f"P{point.period}"
        for point in baseline.cash_path_quantiles
    ]

    p10 = [
        point.p10_cash
        for point in baseline.cash_path_quantiles
    ]

    p50 = [
        point.p50_cash
        for point in baseline.cash_path_quantiles
    ]

    p90 = [
        point.p90_cash
        for point in baseline.cash_path_quantiles
    ]

    severe_p50 = [
        point.p50_cash
        for point in severe.cash_path_quantiles
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=periods,
            y=p90,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=periods,
            y=p10,
            mode="lines",
            fill="tonexty",
            name="Baseline P10–P90 range",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=periods,
            y=p50,
            mode="lines+markers",
            name="Baseline median",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=periods,
            y=severe_p50,
            mode="lines+markers",
            name="Severe median",
            line=dict(dash="dash"),
        )
    )

    if cash_floor > 0:
        fig.add_hline(
            y=cash_floor,
            line_dash="dash",
            annotation_text=(
                f"Management reserve ${cash_floor:,.0f}"
            ),
        )

    fig.add_hline(
        y=0,
        line_dash="dot",
        annotation_text="Cash exhaustion $0",
    )

    fig.update_layout(
        yaxis_title="Cash balance",
        xaxis_title="Forecast period",
        hovermode="x unified",
        height=470,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    # --------------------------------------------------------------
    # FAILURE PROBABILITY BY PERIOD
    # --------------------------------------------------------------

    left, right = st.columns(2)

    with left:
        st.markdown("### Reserve-breach probability by period")

        failure_df = pd.DataFrame(
            {
                "Period": periods,
                "Probability": [
                    point.shortfall_probability * 100
                    for point
                    in baseline.cash_path_quantiles
                ],
            }
        )

        failure_fig = go.Figure(
            go.Bar(
                x=failure_df["Period"],
                y=failure_df["Probability"],
                text=[
                    f"{value:.1f}%"
                    for value
                    in failure_df["Probability"]
                ],
                textposition="auto",
            )
        )

        failure_fig.update_layout(
            yaxis=dict(
                title="Probability",
                range=[0, 100],
            ),
            height=360,
        )

        st.plotly_chart(
            failure_fig,
            use_container_width=True,
        )

    # --------------------------------------------------------------
    # SCENARIO COMPARISON
    # --------------------------------------------------------------

    with right:
        st.markdown("### Scenario risk comparison")

        scenarios = {
            "Baseline": baseline,
            "Moderate Downside": moderate,
            "Severe": severe,
        }

        comparison_df = pd.DataFrame(
            [
                {
                    "Scenario": name,
                    "Reserve-breach probability":
                        result.shortfall_probability * 100,
                    "Median end cash":
                        result.median_end_cash,
                    "P10 end cash":
                        result.p10_end_cash,
                    "95% liquidity buffer":
                        result.liquidity_buffer_at_confidence,
                }
                for name, result
                in scenarios.items()
            ]
        )

        comparison_fig = go.Figure(
            go.Bar(
                x=comparison_df["Scenario"],
                y=comparison_df[
                    "Reserve-breach probability"
                ],
                text=[
                    f"{value:.1f}%"
                    for value
                    in comparison_df[
                        "Reserve-breach probability"
                    ]
                ],
                textposition="auto",
            )
        )

        comparison_fig.update_layout(
            yaxis=dict(
                title="Reserve-breach probability",
                range=[0, 100],
            ),
            height=360,
        )

        st.plotly_chart(
            comparison_fig,
            use_container_width=True,
        )

    st.markdown("### Scenario distribution table")

    st.dataframe(
        comparison_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Reserve-breach probability":
                st.column_config.NumberColumn(
                    format="%.1f%%"
                ),
            "Median end cash":
                st.column_config.NumberColumn(
                    format="$%.0f"
                ),
            "P10 end cash":
                st.column_config.NumberColumn(
                    format="$%.0f"
                ),
            "95% liquidity buffer":
                st.column_config.NumberColumn(
                    format="$%.0f"
                ),
        },
    )

    st.caption(
        "Simulation method: empirical paired-residual bootstrap. "
        "Revenue and operating-cost forecast errors are sampled together "
        "to retain their observed co-movement. "
        "The simulation uses a fixed seed for reproducible judging."
    )
