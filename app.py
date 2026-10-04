from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analytics.metrics import calculate_business_metrics
from src.analytics.risk import assess_business_risk
from src.forecasting.forecast import forecast_metric
from src.ingestion.loader import (
    load_business_csv,
    normalize_business_dataframe,
)
from src.ingestion.validator import validate_business_data
from src.scenarios.decomposition import decompose_scenario
from src.scenarios.engine import ScenarioInput, run_scenario
from src.scenarios.recovery import build_recovery_plan


st.set_page_config(
    page_title="RiskPilot",
    page_icon="📊",
    layout="wide",
)


def money(value: float | None) -> str:
    if value is None:
        return "N/A"

    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def percent(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.1f}%"


def risk_label(level: str) -> str:
    return level.upper()


st.title("RiskPilot")
st.caption(
    "Explainable AI-ready business risk intelligence: "
    "forecast, stress-test, and plan before cash pressure becomes a crisis."
)

st.info(
    "RiskPilot is a decision-support prototype. "
    "It does not provide accounting, tax, legal, or investment advice."
)


# ---------------------------------------------------------------------
# DATA INPUT
# ---------------------------------------------------------------------

st.sidebar.header("Business data")

source = st.sidebar.radio(
    "Choose a data source",
    [
        "Try demo business",
        "Upload CSV",
    ],
)

try:
    if source == "Try demo business":
        raw_df = load_business_csv(
            "data/demo/fragile_business.csv"
        )

        st.sidebar.success(
            "Loaded demo: Fragile Business"
        )

    else:
        uploaded = st.sidebar.file_uploader(
            "Upload business CSV",
            type=["csv"],
        )

        if uploaded is None:
            st.warning(
                "Upload a CSV or choose the demo business "
                "from the sidebar."
            )
            st.stop()

        raw_df = normalize_business_dataframe(
            pd.read_csv(uploaded)
        )

    df, data_quality = validate_business_data(raw_df)

except Exception as exc:
    st.error(f"Could not analyse the data: {exc}")
    st.stop()


metrics = calculate_business_metrics(df)
risks = assess_business_risk(metrics)


# ---------------------------------------------------------------------
# MAIN TABS
# ---------------------------------------------------------------------

overview_tab, forecast_tab, stress_tab = st.tabs(
    [
        "Business Health",
        "Forecast",
        "Stress Lab",
    ]
)


# ---------------------------------------------------------------------
# BUSINESS HEALTH
# ---------------------------------------------------------------------

with overview_tab:
    st.subheader("Current business health")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Overall risk",
        risk_label(risks.overall_risk),
    )

    col2.metric(
        "Latest cash",
        money(metrics.latest_cash_balance),
    )

    runway_text = (
        f"{metrics.cash_runway_months:.1f} months"
        if metrics.cash_runway_months is not None
        else "No current burn"
    )

    col3.metric(
        "Historical run-rate runway",
        runway_text,
    )

    col4.metric(
        "Recent revenue trend",
        percent(metrics.revenue_growth),
    )

    st.subheader("Risk dimensions")

    risk_df = pd.DataFrame(
        {
            "Risk area": [
                "Liquidity",
                "Revenue",
                "Cost pressure",
                "Receivables",
            ],
            "Status": [
                risks.liquidity_risk.upper(),
                risks.revenue_risk.upper(),
                risks.cost_pressure_risk.upper(),
                risks.receivables_risk.upper(),
            ],
        }
    )

    st.dataframe(
        risk_df,
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Financial trajectory")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["revenue"],
            mode="lines+markers",
            name="Revenue",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["operating_cost"],
            mode="lines+markers",
            name="Operating cost",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cash_balance"],
            mode="lines+markers",
            name="Cash balance",
        )
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Amount",
        hovermode="x unified",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    with st.expander("Data quality"):
        st.write(
            f"**Periods loaded:** "
            f"{data_quality.periods_loaded}"
        )

        st.write(
            f"**Coverage:** "
            f"{data_quality.start_date} → "
            f"{data_quality.end_date}"
        )

        st.write(
            f"**Detected frequency:** "
            f"{data_quality.frequency}"
        )

        st.write(
            f"**Missing numeric values:** "
            f"{data_quality.missing_values}"
        )

        st.write(
            f"**Duplicate periods:** "
            f"{data_quality.duplicate_periods}"
        )

        if data_quality.warnings:
            for warning in data_quality.warnings:
                st.warning(warning)
        else:
            st.success(
                "No critical data-quality warnings."
            )


# ---------------------------------------------------------------------
# FORECAST
# ---------------------------------------------------------------------

with forecast_tab:
    st.subheader("Forward outlook")

    try:
        revenue_forecast = forecast_metric(
            df,
            "revenue",
            horizon=3,
        )

        cost_forecast = forecast_metric(
            df,
            "operating_cost",
            horizon=3,
        )

        f1, f2, f3 = st.columns(3)

        f1.metric(
            "Revenue model",
            revenue_forecast.selected_model.upper(),
        )

        f2.metric(
            "Revenue validation MAE",
            money(revenue_forecast.validation_mae),
        )

        f3.metric(
            "3-period revenue forecast",
            money(
                revenue_forecast.forecasts[-1].value
            ),
        )

        forecast_df = pd.DataFrame(
            {
                "Period": [
                    f"+{point.period}"
                    for point
                    in revenue_forecast.forecasts
                ],
                "Revenue": [
                    point.value
                    for point
                    in revenue_forecast.forecasts
                ],
                "Lower": [
                    point.lower
                    for point
                    in revenue_forecast.forecasts
                ],
                "Upper": [
                    point.upper
                    for point
                    in revenue_forecast.forecasts
                ],
                "Operating cost": [
                    point.value
                    for point
                    in cost_forecast.forecasts
                ],
            }
        )

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=forecast_df["Period"],
                y=forecast_df["Upper"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
            )
        )

        fig.add_trace(
            go.Scatter(
                x=forecast_df["Period"],
                y=forecast_df["Lower"],
                mode="lines",
                fill="tonexty",
                name="Revenue uncertainty",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=forecast_df["Period"],
                y=forecast_df["Revenue"],
                mode="lines+markers",
                name="Forecast revenue",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=forecast_df["Period"],
                y=forecast_df["Operating cost"],
                mode="lines+markers",
                name="Forecast operating cost",
            )
        )

        fig.update_layout(
            xaxis_title="Forecast period",
            yaxis_title="Amount",
            hovermode="x unified",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        st.caption(
            "RiskPilot evaluates candidate forecasting models "
            "using rolling validation and selects the model "
            "with the lowest validation error."
        )

    except Exception as exc:
        st.warning(
            f"Forecast unavailable: {exc}"
        )


# ---------------------------------------------------------------------
# STRESS LAB
# ---------------------------------------------------------------------

with stress_tab:
    st.subheader("Stress Lab")

    st.write(
        "Test how changes in revenue, operating costs, "
        "and receivable timing affect future cash."
    )

    with st.form("stress_form"):
        revenue_change_pct = st.slider(
            "Revenue change",
            min_value=-50,
            max_value=25,
            value=-15,
            step=1,
            format="%d%%",
        )

        cost_change_pct = st.slider(
            "Operating cost change",
            min_value=-20,
            max_value=50,
            value=10,
            step=1,
            format="%d%%",
        )

        receivable_delay_days = st.slider(
            "Receivable collection delay",
            min_value=0,
            max_value=90,
            value=30,
            step=15,
            format="%d days",
        )

        horizon = st.slider(
            "Forecast horizon",
            min_value=3,
            max_value=6,
            value=3,
            step=1,
        )

        run_stress = st.form_submit_button(
            "Run stress test",
            use_container_width=True,
        )

    if run_stress:
        with st.spinner(
            "Running forecast and stress analysis..."
        ):
            scenario = ScenarioInput(
                revenue_change=(
                    revenue_change_pct / 100
                ),
                cost_change=(
                    cost_change_pct / 100
                ),
                receivable_delay_days=(
                    receivable_delay_days
                ),
                horizon=horizon,
            )

            scenario_result = run_scenario(
                df,
                scenario,
            )

            decomposition = decompose_scenario(
                df,
                scenario,
            )

            recovery = build_recovery_plan(
                df,
                scenario,
                target_min_cash=0,
            )

        st.session_state["scenario_result"] = (
            scenario_result
        )
        st.session_state["decomposition"] = (
            decomposition
        )
        st.session_state["recovery"] = recovery

    if "scenario_result" in st.session_state:
        scenario_result = (
            st.session_state["scenario_result"]
        )

        decomposition = (
            st.session_state["decomposition"]
        )

        recovery = (
            st.session_state["recovery"]
        )

        st.subheader("Stress result")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Baseline end cash",
            money(
                scenario_result.baseline_end_cash
            ),
        )

        c2.metric(
            "Stressed end cash",
            money(
                scenario_result.stressed_end_cash
            ),
        )

        c3.metric(
            "Peak liquidity gap",
            money(
                scenario_result.peak_liquidity_gap
            ),
        )

        failure_text = (
            f"Period "
            f"{scenario_result.stressed_first_negative_period}"
            if (
                scenario_result
                .stressed_first_negative_period
                is not None
            )
            else "No failure"
        )

        c4.metric(
            "First cash failure",
            failure_text,
        )

        trajectory_df = pd.DataFrame(
            {
                "Period": [
                    point.period
                    for point
                    in scenario_result.trajectory
                ],
                "Baseline cash": [
                    point.baseline_cash
                    for point
                    in scenario_result.trajectory
                ],
                "Stressed cash": [
                    point.stressed_cash
                    for point
                    in scenario_result.trajectory
                ],
            }
        )

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=trajectory_df["Period"],
                y=trajectory_df["Baseline cash"],
                mode="lines+markers",
                name="Baseline cash",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=trajectory_df["Period"],
                y=trajectory_df["Stressed cash"],
                mode="lines+markers",
                name="Stressed cash",
            )
        )

        fig.add_hline(
            y=0,
            line_dash="dash",
        )

        fig.update_layout(
            xaxis_title="Forecast period",
            yaxis_title="Cash balance",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

        st.subheader("What is driving the risk?")

        driver_df = pd.DataFrame(
            {
                "Driver": [
                    item.driver.replace(
                        "_",
                        " ",
                    ).title()
                    for item
                    in decomposition.drivers
                ],
                "Peak liquidity impact": [
                    item.peak_liquidity_impact
                    for item
                    in decomposition.drivers
                ],
                "Contribution": [
                    item.contribution_share * 100
                    for item
                    in decomposition.drivers
                ],
            }
        )

        st.dataframe(
            driver_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Peak liquidity impact":
                    st.column_config.NumberColumn(
                        format="$%.0f"
                    ),
                "Contribution":
                    st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
            },
        )

        st.subheader("Recovery Planner")

        if recovery.operational_recovery_possible:
            st.success(
                "RiskPilot found an operating response "
                "that restores the selected cash target."
            )
        else:
            st.warning(
                "Practical operating changes alone are "
                "not enough under this scenario."
            )

        recovery_rows = []

        for action in recovery.actions:
            recovery_rows.append(
                {
                    "Action":
                        action.action.replace(
                            "_",
                            " ",
                        ).title(),
                    "Feasible":
                        "Yes"
                        if action.feasible
                        else "No",
                    "Magnitude":
                        (
                            f"{action.magnitude:,.1f} "
                            f"{action.unit}"
                            if action.magnitude is not None
                            else "—"
                        ),
                    "Explanation":
                        action.explanation,
                }
            )

        st.dataframe(
            pd.DataFrame(recovery_rows),
            hide_index=True,
            use_container_width=True,
        )

        liquidity_action = next(
            (
                item
                for item in recovery.actions
                if item.action
                == "liquidity_buffer"
            ),
            None,
        )

        if liquidity_action is not None:
            st.error(
                "Additional liquidity required after "
                "the strongest practical operating response: "
                f"**{money(liquidity_action.magnitude)}**"
            )
