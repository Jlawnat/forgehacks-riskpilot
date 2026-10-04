from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity,
)


def money(value: float) -> str:
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def probability(value: float) -> str:
    return f"{value * 100:.1f}%"


@st.cache_data(show_spinner=False)
def _cached_simulation(
    df: pd.DataFrame,
    revenue_change: float,
    cost_change: float,
    receivable_delay_days: int,
    horizon: int,
    simulations: int = 5000,
    seed: int = 42,
):
    return simulate_liquidity(
        df,
        SimulationInput(
            revenue_change=revenue_change,
            cost_change=cost_change,
            receivable_delay_days=receivable_delay_days,
            horizon=horizon,
            simulations=simulations,
            seed=seed,
            confidence_level=0.95,
        ),
    )


def render_liquidity_risk(
    df: pd.DataFrame,
) -> None:
    st.subheader("Probabilistic Liquidity Risk")

    st.write(
        "RiskPilot bootstraps paired historical forecast errors "
        "to simulate 5,000 possible future cash paths. "
        "This estimates the probability and severity of a cash shortfall "
        "instead of relying on a single deterministic forecast."
    )

    with st.spinner("Simulating liquidity distributions..."):
        baseline = _cached_simulation(
            df,
            revenue_change=0.0,
            cost_change=0.0,
            receivable_delay_days=0,
            horizon=3,
        )

        management = _cached_simulation(
            df,
            revenue_change=-0.05,
            cost_change=0.05,
            receivable_delay_days=15,
            horizon=3,
        )

        severe = _cached_simulation(
            df,
            revenue_change=-0.15,
            cost_change=0.10,
            receivable_delay_days=30,
            horizon=3,
        )

    # --------------------------------------------------------------
    # HEADLINE RISK
    # --------------------------------------------------------------

    st.markdown("### Baseline liquidity distribution")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "3-period shortfall probability",
        probability(
            baseline.shortfall_probability
        ),
    )

    c2.metric(
        "Median ending cash",
        money(
            baseline.median_end_cash
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

    fig.add_hline(
        y=0,
        line_dash="dot",
        annotation_text="Cash floor",
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
        st.markdown("### Shortfall probability by period")

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
            "Management": management,
            "Severe": severe,
        }

        comparison_df = pd.DataFrame(
            [
                {
                    "Scenario": name,
                    "Shortfall probability":
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
                    "Shortfall probability"
                ],
                text=[
                    f"{value:.1f}%"
                    for value
                    in comparison_df[
                        "Shortfall probability"
                    ]
                ],
                textposition="auto",
            )
        )

        comparison_fig.update_layout(
            yaxis=dict(
                title="Shortfall probability",
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
            "Shortfall probability":
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
