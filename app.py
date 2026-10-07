from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import textwrap

import streamlit as st

from src.analytics.metrics import calculate_business_metrics
from src.analytics.risk import assess_business_risk
from src.core.context import build_forecast_context
from src.core.risk_policy import (
    RiskPolicy,
    first_cash_breach,
    reserve_headroom,
)
from src.forecasting.forecast import forecast_metric
from src.forecasting.validation import (
    evaluate_candidate_models,
    evaluate_models,
)
from src.ingestion.loader import (
    load_business_csv,
    normalize_business_dataframe,
)
from src.ingestion.validator import validate_business_data
from src.scenarios.decomposition import (
    decompose_scenario_from_context,
)
from src.scenarios.engine import (
    ScenarioInput,
    run_scenario_from_context,
    scenario_context_from_forecast_context,
)
from src.scenarios.recovery import (
    build_recovery_plan_from_context,
)
from src.scenarios.recovery_optimizer import (
    RecoveryOptimizerConfig,
    optimize_recovery_from_context,
)
from src.scenarios.reverse_stress import (
    ReverseStressConfig,
    reverse_stress_from_context,
)
from src.simulation.recovery_validation import (
    validate_recovery_option_from_context,
)
from src.ui.liquidity import render_liquidity_risk
from src.ui.v2_command_center import (
    render_v2_command_center,
)
from src.ui.ai_analyst import render_ai_risk_analyst


st.set_page_config(
    page_title="RiskPilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def _inject_product_shell_styles() -> None:
    st.markdown(
        """
        <style>
        /* RiskPilot final product shell */

        #MainMenu {
            visibility: hidden !important;
        }

        footer {
            visibility: hidden !important;
        }

        [data-testid="stToolbar"] {
            display: none !important;
        }

        [data-testid="stDecoration"] {
            display: none !important;
        }

        [data-testid="stStatusWidget"] {
            display: none !important;
        }

        header[data-testid="stHeader"] {
            height: 0 !important;
            min-height: 0 !important;
            background: transparent !important;
        }

        .block-container {
            max-width: 1520px;
            padding-top: 1.25rem;
            padding-bottom: 2.5rem;
        }

        .stButton > button {
            border-radius: 10px;
            font-weight: 600;
            transition:
                border-color 120ms ease,
                background 120ms ease,
                box-shadow 120ms ease;
        }

        .stButton > button[kind="primary"] {
            box-shadow:
                0 1px 2px rgba(15, 23, 42, 0.06),
                0 4px 12px rgba(37, 99, 235, 0.10);
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"],
        div[data-baseweb="select"] > div {
            border-radius: 10px !important;
        }

        .modebar {
            opacity: 0 !important;
            transition: opacity 120ms ease;
        }

        .js-plotly-plot:hover .modebar {
            opacity: 0.35 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_product_shell_styles()


# ---------------------------------------------------------------------
# STYLE
# ---------------------------------------------------------------------

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 4rem;
        padding-bottom: 3rem;
        max-width: 1500px;
    }

    .riskpilot-hero {
        padding: 1.2rem 1.4rem;
        border: 1px solid #e7e7e7;
        border-radius: 14px;
        margin-bottom: 1rem;
        background: linear-gradient(
            135deg,
            rgba(245,247,250,1) 0%,
            rgba(255,255,255,1) 100%
        );
    }

    .riskpilot-title {
        font-size: 2.5rem;
        font-weight: 750;
        margin-bottom: 0.15rem;
    }

    .riskpilot-subtitle {
        color: #666;
        font-size: 1rem;
    }

    .risk-card {
        border: 1px solid #e6e6e6;
        border-radius: 12px;
        padding: 1rem;
        height: 100%;
        background: white;
    }

    .risk-card-label {
        color: #6c6c6c;
        font-size: 0.85rem;
        margin-bottom: 0.3rem;
    }

    .risk-card-value {
        font-size: 1.7rem;
        font-weight: 700;
    }

    .risk-high {
        color: #b42318;
        font-weight: 700;
    }

    .risk-medium {
        color: #b76e00;
        font-weight: 700;
    }

    .risk-low {
        color: #027a48;
        font-weight: 700;
    }

    .small-note {
        color: #777;
        font-size: 0.82rem;
    }


    /* ---------------------------------------------------------
       RiskPilot commercial product shell
       --------------------------------------------------------- */

    .riskpilot-product-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1.5rem;
        margin: 0 0 1rem 0;
        padding: 1rem 1.15rem;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        background:
            linear-gradient(
                135deg,
                #ffffff 0%,
                #f8fbff 58%,
                #f5f7ff 100%
            );
        box-shadow:
            0 1px 2px rgba(15, 23, 42, 0.025),
            0 8px 24px rgba(15, 23, 42, 0.025);
    }

    .riskpilot-brand-lockup {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        min-width: 0;
    }

    .riskpilot-brand-mark {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 2.65rem;
        height: 2.65rem;
        flex: 0 0 2.65rem;
        border-radius: 11px;
        background: #1d4ed8;
        color: #ffffff;
        font-size: 1.25rem;
        font-weight: 800;
        box-shadow:
            0 5px 14px rgba(29, 78, 216, 0.16);
    }

    .riskpilot-brand-text {
        min-width: 0;
    }

    .riskpilot-product-brand {
        color: #0f172a;
        font-size: 1.55rem;
        line-height: 1.05;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin-bottom: 0.22rem;
    }

    .riskpilot-product-tagline {
        color: #475569;
        font-size: 0.86rem;
        line-height: 1.35;
        font-weight: 500;
    }

    .riskpilot-product-capabilities {
        color: #94a3b8;
        font-size: 0.74rem;
        line-height: 1.35;
        margin-top: 0.18rem;
    }

    .riskpilot-product-badge {
        display: inline-flex;
        align-items: center;
        white-space: nowrap;
        padding: 0.42rem 0.7rem;
        border-radius: 999px;
        border: 1px solid #dbeafe;
        background: #eff6ff;
        color: #1d4ed8;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.055em;
        text-transform: uppercase;
    }

    @media (max-width: 800px) {
        .riskpilot-product-header {
            align-items: flex-start;
            flex-direction: column;
        }

        .riskpilot-product-badge {
            display: none;
        }
    }

    .riskpilot-legacy-context {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.42rem;
        margin: 0.8rem 0 1.15rem 0;
        padding: 0.68rem 0.85rem;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: #f8fafc;
        color: #475569;
        font-size: 0.82rem;
        line-height: 1.35;
    }

    .riskpilot-legacy-context strong {
        color: #0f172a;
        font-weight: 700;
    }

    .riskpilot-context-dot {
        color: #cbd5e1;
    }

    /* Primary actions */
    [data-testid="stBaseButton-primary"] {
        background: #1d4ed8 !important;
        border-color: #1d4ed8 !important;
        color: #ffffff !important;
    }

    [data-testid="stBaseButton-primary"]:hover {
        background: #1e40af !important;
        border-color: #1e40af !important;
    }

    /* Text inputs / text areas */
    textarea:focus,
    input:focus {
        border-color: #93c5fd !important;
        box-shadow: 0 0 0 1px #93c5fd !important;
        outline: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def money(value: float | None) -> str:
    if value is None:
        return "N/A"

    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def percent(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{value * 100:.1f}%"


def risk_class(level: str) -> str:
    return f"risk-{level.lower()}"




def card(label: str, value: str, extra: str = "") -> None:
    st.markdown(
        f"""
        <div class="risk-card">
            <div class="risk-card-label">{label}</div>
            <div class="risk-card-value">{value}</div>
            <div class="small-note">{extra}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(
    show_spinner=False,
)
def get_forecast_context(
    dataframe: pd.DataFrame,
    horizon: int,
):
    """
    Cached expensive model preparation.

    The same validated dataset + horizon reuses:
    - model validation
    - champion forecasts
    - paired residuals
    """
    return build_forecast_context(
        dataframe,
        horizon=horizon,
    )


# ---------------------------------------------------------------------
# DATA INPUT
# ---------------------------------------------------------------------

st.sidebar.header("Monthly analytics inputs")

st.sidebar.caption(
    "These inputs power the separate monthly Forecast, "
    "Liquidity Risk, Stress Lab and Monthly Analysis. "
    "The V2 13-week Command Center uses its own "
    "scenario evidence and policy settings."
)

source = st.sidebar.radio(
    "Data source",
    ["Demo business", "Upload CSV"],
)

try:
    if source == "Demo business":
        demo_name = st.sidebar.selectbox(
            "Demo profile",
            [
                "Borderline Business",
                "Fragile Business",
            ],
        )

        demo_paths = {
            "Borderline Business":
                "data/demo/borderline_business.csv",
            "Fragile Business":
                "data/demo/fragile_business.csv",
        }

        raw_df = load_business_csv(
            demo_paths[demo_name]
        )

        st.sidebar.success(
            f"Demo loaded: {demo_name}"
        )

    else:
        uploaded = st.sidebar.file_uploader(
            "Upload a CSV",
            type=["csv"],
        )

        if uploaded is None:
            st.warning(
                "Upload a business CSV or select the demo."
            )
            st.stop()

        raw_df = normalize_business_dataframe(
            pd.read_csv(uploaded)
        )

    df, data_quality = validate_business_data(
        raw_df
    )

except Exception as exc:
    st.error(f"Data validation failed: {exc}")
    st.stop()


metrics = calculate_business_metrics(df)
risks = assess_business_risk(metrics)


# ---------------------------------------------------------------------
# MANAGEMENT RISK APPETITE
# ---------------------------------------------------------------------

st.sidebar.divider()
st.sidebar.subheader("Monthly risk policy")

default_reserve = min(
    20000.0,
    max(
        0.0,
        float(metrics.latest_cash_balance) * 0.40,
    ),
)

minimum_cash_reserve = st.sidebar.number_input(
    "Minimum liquidity reserve",
    min_value=0.0,
    value=float(
        round(
            default_reserve / 1000
        ) * 1000
    ),
    step=1000.0,
    help=(
        "Cash level management wants to preserve. "
        "RiskPilot treats falling below this level "
        "as a liquidity-policy breach."
    ),
)

max_shortfall_probability_pct = (
    st.sidebar.slider(
        "Maximum acceptable breach probability",
        min_value=1,
        max_value=50,
        value=5,
        step=1,
        format="%d%%",
        help=(
            "Maximum probability management is willing "
            "to accept that future cash falls below "
            "the selected reserve."
        ),
    )
)

risk_policy = RiskPolicy(
    minimum_cash_reserve=(
        minimum_cash_reserve
    ),
    max_shortfall_probability=(
        max_shortfall_probability_pct
        / 100
    ),
)

headroom = reserve_headroom(
    metrics.latest_cash_balance,
    risk_policy.minimum_cash_reserve,
)

st.sidebar.caption(
    "Current reserve headroom: "
    f"${headroom:,.0f}"
)


# ---------------------------------------------------------------------
# PRODUCT SHELL
# ---------------------------------------------------------------------

st.markdown(
    (
        '<div class="riskpilot-product-header">'
        '<div class="riskpilot-brand-lockup">'
        '<div class="riskpilot-brand-mark">◈</div>'
        '<div class="riskpilot-brand-text">'
        '<div class="riskpilot-product-brand">RiskPilot</div>'
        '<div class="riskpilot-product-tagline">'
        'AI-powered liquidity decision intelligence'
        '</div>'
        '<div class="riskpilot-product-capabilities">'
        'Forecast · uncertainty · recovery · grounded AI'
        '</div>'
        '</div>'
        '</div>'
        '<div class="riskpilot-product-badge">'
        'Decision Intelligence'
        '</div>'
        '</div>'
    ),
    unsafe_allow_html=True,
)


product_area = st.segmented_control(
    "RiskPilot workspace",
    [
        "Command Center",
        "Advanced Analytics",
        "Methodology & Evidence",
    ],
    default="Command Center",
    label_visibility="collapsed",
    key="riskpilot_product_area",
)

advanced_area = None

if product_area == "Advanced Analytics":
    advanced_area = st.segmented_control(
        "Advanced analytics",
        [
            "Forecast Intelligence",
            "Liquidity Risk",
            "Stress Lab",
            "Monthly Analysis",
        ],
        default="Forecast Intelligence",
        label_visibility="collapsed",
        key="riskpilot_advanced_area",
    )

if product_area == "Command Center":
    page = "Command Center"

elif product_area == "Methodology & Evidence":
    page = "Model & Data"

elif advanced_area == "Monthly Analysis":
    page = "Command Center"

elif advanced_area == "Legacy AI Analyst":
    page = "AI Risk Analyst"

else:
    page = (
        advanced_area
        or "Forecast Intelligence"
    )


# ---------------------------------------------------------------------
# LEGACY MONTHLY CONTEXT
# ---------------------------------------------------------------------

if product_area in {
    "Advanced Analytics",
    "Methodology & Evidence",
}:
    legacy_business_name = (
        demo_name
        if source == "Demo business"
        else "Uploaded business data"
    )

    legacy_context_label = (
        "Monthly Analytics Layer"
        if product_area == "Advanced Analytics"
        else "Monthly Model & Evidence Layer"
    )

    st.markdown(
        f"""
        <div class="riskpilot-legacy-context">
            <strong>{legacy_context_label}</strong>
            <span class="riskpilot-context-dot">·</span>
            <span>{legacy_business_name}</span>
            <span class="riskpilot-context-dot">·</span>
            <span>
                Reserve
                {money(risk_policy.minimum_cash_reserve)}
            </span>
            <span class="riskpilot-context-dot">·</span>
            <span>
                Risk appetite
                {percent(risk_policy.max_shortfall_probability)}
            </span>
            <span class="riskpilot-context-dot">·</span>
            <span>
                Separate monthly layer · own reserve and risk policy
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =====================================================================
# COMMAND CENTER
# =====================================================================

if page == "Command Center":
    command_center_mode = (
        "Monthly Analysis"
        if (
            product_area
            == "Advanced Analytics"
            and advanced_area
            == "Monthly Analysis"
        )
        else "V2 13-Week Liquidity"
    )

    if (
        command_center_mode
        == "V2 13-Week Liquidity"
    ):
        render_v2_command_center()
        st.stop()

    command_context = get_forecast_context(
        df,
        horizon=6,
    )

    revenue_forecast = (
        command_context.revenue_forecast
    )

    revenue_scores = list(
        command_context.revenue_scores
    )

    command_scenario_context = (
        scenario_context_from_forecast_context(
            command_context
        )
    )

    baseline_outlook = (
        run_scenario_from_context(
            command_scenario_context,
            ScenarioInput(
                horizon=6,
            ),
        )
    )

    st.subheader("Executive Risk Command Center")

    failure_period = (
        first_cash_breach(
            [
                point.baseline_cash
                for point
                in baseline_outlook.trajectory
            ],
            risk_policy.minimum_cash_reserve,
        )
        if baseline_outlook is not None
        else None
    )

    forecast_failure = (
        f"Period {failure_period}"
        if failure_period is not None
        else "Not within horizon"
    )

    model_gain = None

    if revenue_scores:
        score_lookup = {
            item.name: item.mae
            for item in revenue_scores
        }

        naive_mae = score_lookup.get("naive")

        if (
            naive_mae is not None
            and naive_mae > 0
            and revenue_forecast is not None
        ):
            model_gain = (
                (
                    naive_mae
                    - revenue_forecast.validation_mae
                )
                / naive_mae
            )

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        card(
            "Overall risk",
            risks.overall_risk.upper(),
            "Deterministic risk assessment",
        )

    with c2:
        card(
            "Current cash",
            money(metrics.latest_cash_balance),
            "Latest observed balance",
        )

    with c3:
        card(
            "Run-rate runway",
            (
                f"{metrics.cash_runway_months:.1f} mo"
                if metrics.cash_runway_months is not None
                else "No current burn"
            ),
            "Historical recent burn",
        )

    with c4:
        card(
            "Forecast reserve breach",
            forecast_failure,
            f"Below ${risk_policy.minimum_cash_reserve:,.0f} reserve",
        )

    with c5:
        card(
            "Forecast advantage",
            (
                percent(model_gain)
                if model_gain is not None
                else "N/A"
            ),
            "MAE improvement vs naive",
        )

    st.divider()

    left, right = st.columns([1.05, 1])

    with left:
        st.markdown("### Risk indicators")

        current_receivable_ratio = (
            metrics.latest_receivables
            / metrics.latest_revenue
            if metrics.latest_revenue > 0
            else None
        )

        risk_rows = [
            {
                "Dimension": "Liquidity",
                "Status": risks.liquidity_risk.upper(),
                "Observed indicator": (
                    f"{metrics.cash_runway_months:.1f} months runway"
                    if metrics.cash_runway_months is not None
                    else "Unavailable"
                ),
            },
            {
                "Dimension": "Revenue",
                "Status": risks.revenue_risk.upper(),
                "Observed indicator": (
                    f"{metrics.revenue_growth:.1%} recent growth"
                    if metrics.revenue_growth is not None
                    else "Unavailable"
                ),
            },
            {
                "Dimension": "Cost pressure",
                "Status": risks.cost_pressure_risk.upper(),
                "Observed indicator": (
                    f"{metrics.cost_to_revenue_ratio:.2f}× cost / revenue"
                    if metrics.cost_to_revenue_ratio is not None
                    else "Unavailable"
                ),
            },
            {
                "Dimension": "Receivables",
                "Status": risks.receivables_risk.upper(),
                "Observed indicator": (
                    f"{current_receivable_ratio:.2f}× receivables / revenue"
                    if current_receivable_ratio is not None
                    else "Unavailable"
                ),
            },
        ]

        st.dataframe(
            pd.DataFrame(risk_rows),
            hide_index=True,
            use_container_width=True,
        )

        st.caption(
            "Risk statuses are categorical assessments derived "
            "from the observed business metrics shown above. "
            "RiskPilot does not convert these categories into "
            "arbitrary numerical intensity scores."
        )

    with right:
        st.markdown("### Key observations")

        observations = []

        if (
            metrics.cost_to_revenue_ratio is not None
            and metrics.cost_to_revenue_ratio >= 1
        ):
            observations.append(
                "Operating costs currently exceed revenue."
            )

        if (
            metrics.revenue_growth is not None
            and metrics.revenue_growth < 0
        ):
            observations.append(
                "Recent revenue momentum is negative "
                f"({percent(metrics.revenue_growth)})."
            )

        if (
            metrics.cash_runway_months is not None
            and metrics.cash_runway_months < 3
        ):
            observations.append(
                "Historical run-rate cash runway is below "
                "three months."
            )

        receivable_ratio = (
            metrics.latest_receivables
            / metrics.latest_revenue
            if metrics.latest_revenue > 0
            else None
        )

        if (
            receivable_ratio is not None
            and receivable_ratio >= 0.6
        ):
            observations.append(
                "Receivables are unusually large relative "
                "to current revenue."
            )

        if failure_period is not None:
            observations.append(
                "Baseline forecast indicates cash may breach "
                f"the ${risk_policy.minimum_cash_reserve:,.0f} "
                f"management reserve in period {failure_period}."
            )

        for obs in observations:
            st.warning(obs)

        if not observations:
            st.success(
                "No major deterministic warning conditions "
                "were triggered."
            )

    st.markdown("### Financial trajectory")

    trajectory_fig = go.Figure()

    trajectory_fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["revenue"],
            mode="lines+markers",
            name="Revenue",
        )
    )

    trajectory_fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["operating_cost"],
            mode="lines+markers",
            name="Operating cost",
        )
    )

    trajectory_fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cash_balance"],
            mode="lines+markers",
            name="Cash balance",
        )
    )

    trajectory_fig.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Amount",
        height=430,
    )

    st.plotly_chart(
        trajectory_fig,
        use_container_width=True,
    )


# =====================================================================
# FORECAST INTELLIGENCE
# =====================================================================

if page == "Forecast Intelligence":
    forecast_context = get_forecast_context(
        df,
        horizon=3,
    )

    revenue_forecast = (
        forecast_context.revenue_forecast
    )

    cost_forecast = (
        forecast_context.cost_forecast
    )

    revenue_scores = list(
        forecast_context.revenue_scores
    )

    st.subheader("Forecast Intelligence")

    if revenue_forecast is None:
        st.warning(
            "Forecasting is unavailable for this dataset."
        )

    else:
        f1, f2, f3, f4 = st.columns(4)

        f1.metric(
            "Production model",
            revenue_forecast.selected_model.upper(),
        )

        f2.metric(
            "Production MAE",
            money(revenue_forecast.validation_mae),
        )

        f3.metric(
            "Forecast revenue +3",
            money(
                revenue_forecast.forecasts[-1].value
            ),
        )

        f4.metric(
            "Recent revenue trend",
            percent(metrics.revenue_growth),
        )

        st.markdown(
            "### Forecast model governance"
        )

        st.caption(
            "Five transparent forecasting structures are evaluated "
            "under rolling-origin out-of-sample validation. The "
            "production model remains frozen at this checkpoint; "
            "shadow challengers require stability and regression "
            "review before promotion."
        )

        governance_cols = st.columns(4)

        governance_cols[0].metric(
            "Validation method",
            "Rolling-origin",
        )

        governance_cols[1].metric(
            "Candidate pool",
            "5 models",
        )

        governance_cols[2].metric(
            "Production policy",
            "Frozen",
        )

        governance_cols[3].metric(
            "Promotion gate",
            "Stability review",
        )

        model_roles = {
            "naive": "Persistence benchmark",
            "drift": "Trend benchmark",
            "ses": "Level smoothing",
            "holt": "Linear trend",
            "damped_holt": "Damped trend",
        }

        production_models = {
            "holt",
            "naive",
        }

        def _governance_rows(
            scores,
            selected_model,
        ):
            naive_mae = next(
                (
                    item.mae
                    for item in scores
                    if item.name == "naive"
                ),
                None,
            )

            rows = []

            best_candidate_name = min(
                scores,
                key=lambda item: item.mae,
            ).name

            for score in scores:
                improvement = None

                if (
                    naive_mae is not None
                    and naive_mae > 0
                ):
                    improvement = (
                        naive_mae
                        - score.mae
                    ) / naive_mae

                if (
                    score.name
                    == selected_model
                ):
                    status = "PRODUCTION"
                elif (
                    score.name
                    == best_candidate_name
                ):
                    status = "SHADOW LEADER"
                elif (
                    score.name
                    in production_models
                ):
                    status = "APPROVED ALTERNATIVE"
                else:
                    status = "SHADOW"

                rows.append(
                    {
                        "Model":
                            score.name
                            .replace(
                                "_",
                                " ",
                            )
                            .title(),
                        "Role":
                            model_roles.get(
                                score.name,
                                "Candidate",
                            ),
                        "Rolling MAE":
                            score.mae,
                        "Improvement vs Naive":
                            (
                                improvement * 100
                                if improvement
                                is not None
                                else None
                            ),
                        "Governance status":
                            status,
                    }
                )

            return rows

        revenue_candidate_scores = (
            evaluate_candidate_models(
                df["revenue"]
            )
        )

        cost_candidate_scores = (
            evaluate_candidate_models(
                df["operating_cost"]
            )
        )

        st.markdown(
            "#### Revenue validation"
        )

        st.dataframe(
            pd.DataFrame(
                _governance_rows(
                    revenue_candidate_scores,
                    revenue_forecast.selected_model,
                )
            ),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Rolling MAE":
                    st.column_config.NumberColumn(
                        format="$%.0f"
                    ),
                "Improvement vs Naive":
                    st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
            },
        )

        st.markdown(
            "#### Operating-cost validation"
        )

        st.dataframe(
            pd.DataFrame(
                _governance_rows(
                    cost_candidate_scores,
                    cost_forecast.selected_model,
                )
            ),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Rolling MAE":
                    st.column_config.NumberColumn(
                        format="$%.0f"
                    ),
                "Improvement vs Naive":
                    st.column_config.NumberColumn(
                        format="%.1f%%"
                    ),
            },
        )

        st.info(
            "Model promotion is deliberately conservative. A shadow "
            "challenger may achieve lower MAE than the current "
            "production model, but lower error alone is not sufficient "
            "for promotion. RiskPilot also requires fit stability, "
            "regression testing and downstream financial consistency."
        )

        st.markdown("### Actual + forecast")

        historical_df = (
            df[["date", "revenue"]]
            .tail(8)
            .copy()
        )

        historical_df["date"] = pd.to_datetime(
            historical_df["date"]
        )

        last_observed_date = pd.to_datetime(
            df["date"].max()
        )

        last_observed_revenue = float(
            df.loc[
                df["date"] == df["date"].max(),
                "revenue",
            ].iloc[-1]
        )

        future_dates = [
            last_observed_date
            + pd.DateOffset(
                months=int(point.period)
            )
            for point in revenue_forecast.forecasts
        ]

        forecast_values = [
            float(point.value)
            for point in revenue_forecast.forecasts
        ]

        lower_values = [
            float(point.lower)
            for point in revenue_forecast.forecasts
        ]

        upper_values = [
            float(point.upper)
            for point in revenue_forecast.forecasts
        ]

        forecast_fig = go.Figure()

        forecast_fig.add_trace(
            go.Scatter(
                x=historical_df["date"],
                y=historical_df["revenue"],
                mode="lines+markers",
                name="Observed revenue",
            )
        )

        # Upper bound first, then lower bound fills back to it.
        forecast_fig.add_trace(
            go.Scatter(
                x=future_dates,
                y=upper_values,
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )

        forecast_fig.add_trace(
            go.Scatter(
                x=future_dates,
                y=lower_values,
                mode="lines",
                fill="tonexty",
                name="Forecast interval",
                hovertemplate=(
                    "Date: %{x|%b %Y}"
                    "<br>Lower bound: $%{y:,.0f}"
                    "<extra></extra>"
                ),
            )
        )

        forecast_fig.add_trace(
            go.Scatter(
                x=[
                    last_observed_date,
                    *future_dates,
                ],
                y=[
                    last_observed_revenue,
                    *forecast_values,
                ],
                mode="lines+markers",
                name="Forecast revenue",
                line=dict(
                    dash="dash",
                ),
                hovertemplate=(
                    "Date: %{x|%b %Y}"
                    "<br>Revenue: $%{y:,.0f}"
                    "<extra></extra>"
                ),
            )
        )

        if future_dates:
            forecast_fig.add_vline(
                x=future_dates[0],
                line_dash="dot",
                annotation_text="Forecast begins",
                annotation_position="top",
            )

        forecast_fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Revenue",
            hovermode="x unified",
            height=460,
        )

        st.plotly_chart(
            forecast_fig,
            use_container_width=True,
        )

        if future_dates:
            st.caption(
                "Observed data end "
                f"{last_observed_date.strftime('%b %Y')}. "
                "Forecast periods correspond to "
                + ", ".join(
                    value.strftime("%b %Y")
                    for value in future_dates
                )
                + ". The shaded region represents the "
                "model uncertainty interval."
            )


if page == "Liquidity Risk":
    liquidity_context = (
        get_forecast_context(
            df,
            horizon=3,
        )
    )

    render_liquidity_risk(
        liquidity_context,
        cash_floor=(
            risk_policy.minimum_cash_reserve
        ),
        max_shortfall_probability=(
            risk_policy
            .max_shortfall_probability
        ),
    )


# =====================================================================
# STRESS LAB
# =====================================================================

if page == "Stress Lab":
    st.subheader("Stress Lab")

    st.write(
        "Simulate revenue shocks, cost inflation and "
        "receivable delays. RiskPilot recomputes cash "
        "trajectory, liquidity failure and recovery options."
    )

    # ==============================================================
    # REVERSE STRESS
    # ==============================================================

    st.markdown("### Reverse Stress Test")

    st.write(
        "Instead of choosing a shock first, reverse stress testing "
        "finds the deterioration required to breach the selected "
        "management liquidity reserve."
    )

    reverse_forecast_context = get_forecast_context(
        df,
        horizon=3,
    )

    reverse_scenario_context = (
        scenario_context_from_forecast_context(
            reverse_forecast_context
        )
    )

    reverse_result = reverse_stress_from_context(
        reverse_scenario_context,
        ReverseStressConfig(
            target_min_cash=(
                risk_policy.minimum_cash_reserve
            ),
            horizon=3,
            max_revenue_decline=0.30,
            max_cost_increase=0.30,
            max_receivable_delay_days=90,
            grid_step=0.01,
        ),
    )

    rr1, rr2, rr3, rr4 = st.columns(4)

    rr1.metric(
        "Reserve headroom",
        money(
            reverse_result.baseline_margin_to_target
        ),
        help=(
            "Minimum deterministic forecast cash minus "
            "the management liquidity reserve."
        ),
    )

    rr2.metric(
        "Revenue decline capacity",
        (
            "Already breached"
            if reverse_result.baseline_breached
            else (
                "Beyond search range"
                if (
                    reverse_result
                    .revenue_decline_breakpoint
                    is None
                )
                else (
                    f"{reverse_result.revenue_decline_breakpoint:.2%}"
                )
            )
        ),
        help=(
            "Approximate revenue decline that first pushes "
            "minimum cash below the management reserve."
        ),
    )

    rr3.metric(
        "Cost inflation capacity",
        (
            "Already breached"
            if reverse_result.baseline_breached
            else (
                "Beyond search range"
                if (
                    reverse_result
                    .cost_increase_breakpoint
                    is None
                )
                else (
                    f"{reverse_result.cost_increase_breakpoint:.2%}"
                )
            )
        ),
        help=(
            "Approximate operating-cost increase that first "
            "pushes minimum cash below the reserve."
        ),
    )

    rr4.metric(
        "Collection-delay capacity",
        (
            "Already breached"
            if reverse_result.baseline_breached
            else (
                "Beyond search range"
                if (
                    reverse_result
                    .receivable_delay_breakpoint_days
                    is None
                )
                else (
                    f"{reverse_result.receivable_delay_breakpoint_days} days"
                )
            )
        ),
        help=(
            "Approximate additional receivables delay that "
            "first pushes minimum cash below the reserve."
        ),
    )

    if reverse_result.baseline_breached:
        st.error(
            "The deterministic baseline already breaches the "
            f"${risk_policy.minimum_cash_reserve:,.0f} management "
            "reserve. There is no remaining policy shock capacity."
        )
    else:
        st.info(
            "The deterministic baseline remains above the "
            f"\\${risk_policy.minimum_cash_reserve:,.0f} reserve by "
            f"\\${reverse_result.baseline_margin_to_target:,.0f}. "
            "The breakpoints below measure how little additional "
            "deterioration is required to exhaust that cushion."
        )

    # --------------------------------------------------------------
    # Zoomed revenue x cost survival boundary
    # --------------------------------------------------------------

    boundary_result = reverse_stress_from_context(
        reverse_scenario_context,
        ReverseStressConfig(
            target_min_cash=(
                risk_policy.minimum_cash_reserve
            ),
            horizon=3,
            max_revenue_decline=0.05,
            max_cost_increase=0.05,
            max_receivable_delay_days=90,
            grid_step=0.0025,
        ),
    )

    boundary_df = pd.DataFrame(
        [
            {
                "Revenue decline (%)":
                    point.revenue_decline * 100,
                "Cost increase (%)":
                    point.cost_increase * 100,
                "Reserve margin":
                    point.margin_to_target,
            }
            for point in boundary_result.grid
        ]
    )

    boundary_matrix = boundary_df.pivot(
        index="Revenue decline (%)",
        columns="Cost increase (%)",
        values="Reserve margin",
    )

    st.markdown(
        "#### Revenue decline × cost inflation survival boundary"
    )

    st.caption(
        "Each cell shows deterministic minimum-cash margin "
        "relative to the management reserve. Positive values "
        "remain inside policy; negative values breach it. "
        "The heatmap is intentionally zoomed to small shocks "
        "because this business currently has limited headroom."
    )

    boundary_fig = go.Figure()

    boundary_fig.add_trace(
        go.Heatmap(
            x=boundary_matrix.columns,
            y=boundary_matrix.index,
            z=boundary_matrix.values,
            colorscale="RdYlGn",
            zmid=0,
            colorbar=dict(
                title="Reserve margin ($)",
            ),
            hovertemplate=(
                "Revenue decline: %{y:.2f}%"
                "<br>Cost increase: %{x:.2f}%"
                "<br>Reserve margin: $%{z:,.0f}"
                "<extra></extra>"
            ),
        )
    )

    boundary_fig.add_trace(
        go.Contour(
            x=boundary_matrix.columns,
            y=boundary_matrix.index,
            z=boundary_matrix.values,
            contours=dict(
                start=0,
                end=0,
                size=1,
                coloring="lines",
                showlabels=True,
            ),
            showscale=False,
            hoverinfo="skip",
            line=dict(
                width=4,
                color="black",
            ),
            name="Reserve boundary",
        )
    )

    boundary_fig.update_layout(
        xaxis_title="Cost increase (%)",
        yaxis_title="Revenue decline (%)",
        height=500,
        hovermode="closest",
    )

    st.plotly_chart(
        boundary_fig,
        use_container_width=True,
    )

    st.caption(
        "Headline breakpoints use a finer numerical search. "
        "The heatmap is a visual combination grid and should "
        "not be interpreted as the source of the exact "
        "breakpoint estimates."
    )

    st.divider()

    st.markdown("### Manual Stress Scenario")

    with st.form("stress_form"):
        s1, s2, s3, s4 = st.columns(4)

        with s1:
            revenue_change_pct = st.slider(
                "Revenue shock",
                min_value=-50,
                max_value=25,
                value=-15,
                step=1,
                format="%d%%",
            )

        with s2:
            cost_change_pct = st.slider(
                "Cost shock",
                min_value=-20,
                max_value=50,
                value=10,
                step=1,
                format="%d%%",
            )

        with s3:
            receivable_delay_days = st.slider(
                "Receivable delay",
                min_value=0,
                max_value=90,
                value=30,
                step=15,
                format="%d days",
            )

        with s4:
            horizon = st.slider(
                "Forecast horizon",
                min_value=3,
                max_value=6,
                value=3,
                step=1,
            )

        run_stress = st.form_submit_button(
            "Run Stress Simulation",
            use_container_width=True,
        )

    if run_stress:
        with st.spinner(
            "Running forecasts, scenario engine, "
            "liquidity decomposition and recovery optimiser..."
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

            stress_context = (
                get_forecast_context(
                    df,
                    horizon=horizon,
                )
            )

            stress_scenario_context = (
                scenario_context_from_forecast_context(
                    stress_context
                )
            )

            scenario_result = (
                run_scenario_from_context(
                    stress_scenario_context,
                    scenario,
                )
            )

            decomposition = (
                decompose_scenario_from_context(
                    stress_scenario_context,
                    scenario,
                )
            )

            recovery = (
                build_recovery_plan_from_context(
                    stress_scenario_context,
                    scenario,
                    target_min_cash=(
                        risk_policy.minimum_cash_reserve
                    ),
                )
            )

            recovery_decision = (
                optimize_recovery_from_context(
                    stress_scenario_context,
                    scenario,
                    RecoveryOptimizerConfig(
                        target_min_cash=(
                            risk_policy.minimum_cash_reserve
                        ),
                        max_revenue_improvement_pct=20,
                        max_cost_reduction_pct=15,
                        max_receivable_acceleration_days=90,
                        max_external_liquidity=50000.0,
                        revenue_step_pct=1,
                        cost_step_pct=1,
                        receivable_step_days=1,
                    ),
                )
            )

            recovery_validations = {}

            validation_plans = [
                (
                    "Balanced",
                    recovery_decision.recommended,
                ),
                (
                    "Lowest Funding",
                    recovery_decision
                    .lowest_external_liquidity,
                ),
                (
                    "Lowest Operational Disruption",
                    recovery_decision
                    .lowest_operational_disruption,
                ),
            ]

            for (
                plan_name,
                option,
            ) in validation_plans:

                if option is None:
                    continue

                recovery_validations[
                    plan_name
                ] = (
                    validate_recovery_option_from_context(
                        context=stress_context,
                        base_scenario=scenario,
                        option=option,
                        plan_name=plan_name,
                        cash_floor=(
                            risk_policy
                            .minimum_cash_reserve
                        ),
                        max_shortfall_probability=(
                            risk_policy
                            .max_shortfall_probability
                        ),
                        simulations=5000,
                        seed=42,
                    )
                )

        st.session_state["scenario_result"] = (
            scenario_result
        )

        st.session_state["decomposition"] = (
            decomposition
        )

        st.session_state["recovery"] = (
            recovery
        )

        st.session_state["recovery_decision"] = (
            recovery_decision
        )

        st.session_state["recovery_validations"] = (
            recovery_validations
        )

    if "scenario_result" in st.session_state:
        result = st.session_state[
            "scenario_result"
        ]

        decomposition = st.session_state[
            "decomposition"
        ]

        recovery = st.session_state[
            "recovery"
        ]

        recovery_decision = st.session_state.get(
            "recovery_decision"
        )

        recovery_validations = (
            st.session_state.get(
                "recovery_validations",
                {},
            )
        )

        st.markdown("### Stress result")

        r1, r2, r3, r4, r5 = st.columns(5)

        r1.metric(
            "Baseline end cash",
            money(result.baseline_end_cash),
        )

        r2.metric(
            "Stressed end cash",
            money(result.stressed_end_cash),
        )

        r3.metric(
            "Peak liquidity gap",
            money(result.peak_liquidity_gap),
        )

        r4.metric(
            "Baseline failure",
            (
                f"Period "
                f"{result.baseline_first_negative_period}"
                if result.baseline_first_negative_period
                else "None"
            ),
        )

        r5.metric(
            "Stressed failure",
            (
                f"Period "
                f"{result.stressed_first_negative_period}"
                if result.stressed_first_negative_period
                else "None"
            ),
        )

        st.markdown("### Cash trajectory")

        trajectory_df = pd.DataFrame(
            {
                "Period": [
                    point.period
                    for point in result.trajectory
                ],
                "Baseline": [
                    point.baseline_cash
                    for point in result.trajectory
                ],
                "Stressed": [
                    point.stressed_cash
                    for point in result.trajectory
                ],
            }
        )

        cash_fig = go.Figure()

        cash_fig.add_trace(
            go.Scatter(
                x=trajectory_df["Period"],
                y=trajectory_df["Baseline"],
                mode="lines+markers",
                name="Baseline cash",
            )
        )

        cash_fig.add_trace(
            go.Scatter(
                x=trajectory_df["Period"],
                y=trajectory_df["Stressed"],
                mode="lines+markers",
                name="Stressed cash",
            )
        )

        cash_fig.add_hline(
            y=0,
            line_dash="dash",
        )

        cash_fig.update_layout(
            xaxis_title="Forecast period",
            yaxis_title="Cash balance",
            height=430,
        )

        st.plotly_chart(
            cash_fig,
            use_container_width=True,
        )

        dleft, dright = st.columns(2)

        with dleft:
            st.markdown("### Peak-liquidity drivers")

            driver_names = [
                item.driver.replace(
                    "_",
                    " ",
                ).title()
                for item in decomposition.drivers
            ]

            driver_values = [
                item.peak_liquidity_impact
                for item in decomposition.drivers
            ]

            driver_fig = go.Figure(
                go.Bar(
                    x=driver_values,
                    y=driver_names,
                    orientation="h",
                    text=[
                        f"{item.contribution_share * 100:.1f}%"
                        for item
                        in decomposition.drivers
                    ],
                    textposition="auto",
                )
            )

            driver_fig.update_layout(
                xaxis_title="Liquidity impact",
                yaxis_title="",
                height=330,
            )

            st.plotly_chart(
                driver_fig,
                use_container_width=True,
            )

        with dright:
            st.markdown("### Shock waterfall")

            waterfall_fig = go.Figure(
                go.Waterfall(
                    orientation="v",
                    measure=[
                        "relative",
                        "relative",
                        "relative",
                        "total",
                    ],
                    x=[
                        "Revenue shock",
                        "Cost shock",
                        "Receivable delay",
                        "Peak gap",
                    ],
                    y=[
                        -next(
                            item.peak_liquidity_impact
                            for item
                            in decomposition.drivers
                            if item.driver
                            == "revenue_shock"
                        ),
                        -next(
                            item.peak_liquidity_impact
                            for item
                            in decomposition.drivers
                            if item.driver
                            == "cost_shock"
                        ),
                        -next(
                            item.peak_liquidity_impact
                            for item
                            in decomposition.drivers
                            if item.driver
                            == "receivable_delay"
                        ),
                        -decomposition.peak_liquidity_gap,
                    ],
                )
            )

            waterfall_fig.update_layout(
                yaxis_title="Cash impact",
                height=330,
            )

            st.plotly_chart(
                waterfall_fig,
                use_container_width=True,
            )

        # ==========================================================
        # RECOVERY DECISION CENTER V2
        # ==========================================================

        st.markdown("### Recovery Decision Center")

        st.write(
            "RiskPilot searches thousands of feasible recovery "
            "combinations and compares the trade-off between "
            "operating intervention and external liquidity."
        )

        if recovery_decision is not None:

            dc1, dc2, dc3 = st.columns(3)

            dc1.metric(
                "Stressed reserve gap",
                money(
                    recovery_decision.initial_reserve_gap
                ),
                help=(
                    "Additional cash required to restore the "
                    "management reserve before recovery actions."
                ),
            )

            dc2.metric(
                "Candidates evaluated",
                f"{recovery_decision.candidates_evaluated:,}",
            )

            dc3.metric(
                "Recovery available",
                (
                    "YES"
                    if recovery_decision.feasible
                    else "NO"
                ),
            )

            if recovery_decision.feasible:

                balanced = (
                    recovery_decision.recommended
                )

                lowest_funding = (
                    recovery_decision
                    .lowest_external_liquidity
                )

                lowest_disruption = (
                    recovery_decision
                    .lowest_operational_disruption
                )

                plan_columns = st.columns(3)

                def render_plan(
                    column,
                    title,
                    option,
                    description,
                ):
                    with column:
                        with st.container(
                            border=True
                        ):
                            st.markdown(
                                f"#### {title}"
                            )

                            st.caption(
                                description
                            )

                            if option is None:
                                st.warning(
                                    "No feasible plan found."
                                )
                                return

                            st.metric(
                                "External liquidity",
                                money(
                                    option
                                    .external_liquidity
                                ),
                            )

                            st.metric(
                                "Resulting minimum cash",
                                money(
                                    option
                                    .resulting_min_cash
                                ),
                            )

                            st.metric(
                                "Maximum lever use",
                                (
                                    f"{option.maximum_lever_utilisation:.1%}"
                                ),
                            )

                            st.markdown(
                                "**Recovery actions**"
                            )

                            st.write(
                                "Revenue recovery: "
                                f"**{option.revenue_improvement_pct:.0f}%**"
                            )

                            st.write(
                                "Cost reduction: "
                                f"**{option.cost_reduction_pct:.0f}%**"
                            )

                            st.write(
                                "Collections faster: "
                                f"**{option.receivable_acceleration_days} days**"
                            )

                            st.caption(
                                "Deterministic reserve margin: "
                                f"{money(option.reserve_margin)}"
                            )

                render_plan(
                    plan_columns[0],
                    "Balanced",
                    balanced,
                    (
                        "Minimises dependence on any "
                        "single recovery lever."
                    ),
                )

                render_plan(
                    plan_columns[1],
                    "Lowest Funding",
                    lowest_funding,
                    (
                        "Minimises the amount of external "
                        "liquidity required."
                    ),
                )

                render_plan(
                    plan_columns[2],
                    "Lowest Operational Disruption",
                    lowest_disruption,
                    (
                        "Minimises changes to revenue, "
                        "costs and collections."
                    ),
                )

                # --------------------------------------------------
                # Management trade-off comparison
                # --------------------------------------------------

                st.markdown(
                    "#### Management trade-offs"
                )

                tradeoff_options = [
                    (
                        "Balanced",
                        recovery_decision.recommended,
                    ),
                    (
                        "Lowest Funding",
                        recovery_decision
                        .lowest_external_liquidity,
                    ),
                    (
                        "Lowest Operational Disruption",
                        recovery_decision
                        .lowest_operational_disruption,
                    ),
                    (
                        "No External Funding",
                        (
                            None
                            if (
                                recovery_decision
                                .no_external_liquidity
                                is not None
                                and recovery_decision
                                .lowest_external_liquidity
                                is not None
                                and recovery_decision
                                .no_external_liquidity
                                .model_dump()
                                == recovery_decision
                                .lowest_external_liquidity
                                .model_dump()
                            )
                            else recovery_decision
                            .no_external_liquidity
                        ),
                    ),
                ]

                tradeoff_rows = []

                for (
                    plan_name,
                    option,
                ) in tradeoff_options:

                    if option is None:
                        continue

                    tradeoff_rows.append(
                        {
                            "Plan": plan_name,
                            "Revenue recovery":
                                (
                                    f"{option.revenue_improvement_pct:.0f}%"
                                ),
                            "Cost reduction":
                                (
                                    f"{option.cost_reduction_pct:.0f}%"
                                ),
                            "Collections faster":
                                (
                                    f"{option.receivable_acceleration_days} days"
                                ),
                            "External liquidity":
                                money(
                                    option.external_liquidity
                                ),
                            "Min cash":
                                money(
                                    option.resulting_min_cash
                                ),
                            "Max lever use":
                                (
                                    f"{option.maximum_lever_utilisation:.1%}"
                                ),
                        }
                    )

                st.dataframe(
                    pd.DataFrame(
                        tradeoff_rows
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

                if balanced is not None:
                    balanced_validation = (
                        recovery_validations.get(
                            "Balanced"
                        )
                    )

                    if balanced_validation is not None:
                        st.success(
                            "Balanced plan: combine "
                            f"{balanced.revenue_improvement_pct:.0f}% "
                            "revenue recovery, "
                            f"{balanced.cost_reduction_pct:.0f}% "
                            "cost reduction and "
                            f"{balanced.receivable_acceleration_days} "
                            "days faster collections. "
                            f"Deterministic funding is "
                            f"\\{money(balanced.external_liquidity)}; "
                            "after adding the "
                            f"\\{money(balanced_validation.additional_buffer_required)} "
                            "uncertainty buffer, total risk-adjusted "
                            "liquidity is "
                            f"\\{money(balanced_validation.risk_adjusted_total_liquidity)}, "
                            "bringing modeled reserve-breach risk to "
                            f"{balanced_validation.risk_adjusted_breach_probability:.1%}."
                        )
                    else:
                        st.success(
                            "Balanced recommendation: combine "
                            f"{balanced.revenue_improvement_pct:.0f}% "
                            "revenue recovery, "
                            f"{balanced.cost_reduction_pct:.0f}% "
                            "cost reduction, "
                            f"{balanced.receivable_acceleration_days} "
                            "days faster collections and "
                            f"{money(balanced.external_liquidity)} "
                            "of external liquidity."
                        )

                st.markdown(
                    "#### Probabilistic validation"
                )

                st.caption(
                    "Deterministic recovery plans are re-tested "
                    "against forecast uncertainty using 5,000 "
                    "paired-residual cash simulations."
                )

                validation_rows = []

                for (
                    plan_name,
                    validation,
                ) in recovery_validations.items():

                    validation_rows.append(
                        {
                            "Plan":
                                plan_name,
                            "Breach risk before":
                                (
                                    f"{validation.reserve_breach_probability:.1%}"
                                ),
                            "Allowed":
                                (
                                    f"{validation.max_acceptable_breach_probability:.1%}"
                                ),
                            "Uncertainty buffer":
                                money(
                                    validation
                                    .additional_buffer_required
                                ),
                            "Risk-adjusted funding":
                                money(
                                    validation
                                    .risk_adjusted_total_liquidity
                                ),
                            "Breach risk after":
                                (
                                    f"{validation.risk_adjusted_breach_probability:.1%}"
                                ),
                            "Within appetite":
                                (
                                    "YES"
                                    if validation
                                    .risk_adjusted_within_appetite
                                    else "NO"
                                ),
                        }
                    )

                st.dataframe(
                    pd.DataFrame(
                        validation_rows
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

                if (
                    recovery_validations
                    and all(
                        validation
                        .risk_adjusted_within_appetite
                        for validation
                        in recovery_validations.values()
                    )
                ):
                    st.success(
                        "All shortlisted recovery plans can be "
                        "brought within the selected probabilistic "
                        "risk appetite by adding their calculated "
                        "uncertainty buffers."
                    )

                st.caption(
                    "Decision-model scope: recovery options are first "
                    "generated using deterministic cash-flow constraints, "
                    "then the shortlisted plans are re-tested against "
                    "forecast uncertainty and the selected probabilistic "
                    "risk appetite."
                )

            else:
                st.error(
                    "No recovery combination within the configured "
                    "operating and funding limits restores the "
                    "management liquidity reserve."
                )

                best_effort = (
                    recovery_decision.best_effort
                )

                st.write(
                    "Best achievable minimum cash under the "
                    "current limits: "
                    f"**{money(best_effort.resulting_min_cash)}**"
                )

        st.divider()

        with st.expander(
            "Detailed recovery diagnostics",
            expanded=False,
        ):
            st.caption(
                "Legacy operating-recovery diagnostics retained "
                "for transparency and comparison with the newer "
                "Recovery Decision Center."
            )

            if recovery.operational_recovery_possible:
                st.success(
                    "A practical operating response can "
                    "restore the cash target."
                )
            else:
                st.warning(
                    "Operating changes within practical limits "
                    "are not enough to fully restore liquidity."
                )

            best_mix = next(
                (
                    action
                    for action in recovery.actions
                    if action.action
                    == "best_operating_mix"
                ),
                None,
            )

            liquidity = next(
                (
                    action
                    for action in recovery.actions
                    if action.action
                    == "liquidity_buffer"
                ),
                None,
            )

            if best_mix is not None:
                b1, b2, b3 = st.columns(3)

                b1.metric(
                    "Revenue improvement",
                    (
                        f"{best_mix.components.get('revenue_improvement_pct', 0):.0f}%"
                    ),
                )

                b2.metric(
                    "Cost reduction",
                    (
                        f"{best_mix.components.get('cost_reduction_pct', 0):.0f}%"
                    ),
                )

                b3.metric(
                    "Collections accelerated",
                    (
                        f"{best_mix.components.get('receivable_days_faster', 0):.0f} days"
                    ),
                )

                st.info(best_mix.explanation)

            if liquidity is not None:
                st.error(
                    "Remaining external liquidity required: "
                    f"**{money(liquidity.magnitude)}**"
                )

            recovery_rows = []

            for action in recovery.actions:
                recovery_rows.append(
                    {
                        "Strategy":
                            action.action.replace(
                                "_",
                                " ",
                            ).title(),
                        "Feasible":
                            "YES"
                            if action.feasible
                            else "NO",
                        "Magnitude":
                            (
                                f"{action.magnitude:,.1f} "
                                f"{action.unit}"
                                if action.magnitude is not None
                                else "—"
                            ),
                        "Outcome":
                            action.explanation,
                    }
                )

            st.dataframe(
                pd.DataFrame(recovery_rows),
                hide_index=True,
                use_container_width=True,
            )



# =====================================================================
# AI RISK ANALYST
# =====================================================================

if page == "AI Risk Analyst":
    ai_forecast_context = get_forecast_context(
        df,
        horizon=3,
    )

    render_ai_risk_analyst(
        dataframe=df,
        policy=risk_policy,
        forecast_context=ai_forecast_context,
        metrics=metrics,
        risks=risks,
    )


# =====================================================================
# MODEL & DATA DIAGNOSTICS
# =====================================================================

if page == "Model & Data":
    st.subheader("Model & Data Diagnostics")

    d1, d2, d3, d4 = st.columns(4)

    d1.metric(
        "Periods loaded",
        data_quality.periods_loaded,
    )

    d2.metric(
        "Frequency",
        data_quality.frequency,
    )

    d3.metric(
        "Missing values",
        data_quality.missing_values,
    )

    d4.metric(
        "Duplicate periods",
        data_quality.duplicate_periods,
    )

    st.markdown("### Input diagnostics")

    st.write(
        f"**Coverage:** "
        f"{data_quality.start_date} → "
        f"{data_quality.end_date}"
    )

    if data_quality.warnings:
        for warning in data_quality.warnings:
            st.warning(warning)
    else:
        st.success(
            "No critical input-quality warnings."
        )

    st.markdown("### Quantitative indicators")

    metrics_df = pd.DataFrame(
        [
            {
                "Metric": "Revenue growth",
                "Value": percent(
                    metrics.revenue_growth
                ),
            },
            {
                "Metric": "Cost / revenue ratio",
                "Value": (
                    f"{metrics.cost_to_revenue_ratio:.2f}"
                    if metrics.cost_to_revenue_ratio
                    is not None
                    else "N/A"
                ),
            },
            {
                "Metric": "Revenue volatility",
                "Value": percent(
                    metrics.revenue_volatility
                ),
            },
            {
                "Metric": "Historical runway",
                "Value": (
                    f"{metrics.cash_runway_months:.2f} months"
                    if metrics.cash_runway_months
                    is not None
                    else "N/A"
                ),
            },
            {
                "Metric": "Receivables / revenue",
                "Value": (
                    f"{metrics.latest_receivables / metrics.latest_revenue:.2f}"
                    if metrics.latest_revenue > 0
                    else "N/A"
                ),
            },
        ]
    )

    st.dataframe(
        metrics_df,
        hide_index=True,
        use_container_width=True,
    )

    st.html(
        textwrap.dedent(
            """
        <style>
        .rp-arch {
            margin-top: 0.4rem;
            margin-bottom: 2rem;
            padding: 1.35rem;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 8px 26px rgba(15, 23, 42, 0.04);
        }

        .rp-arch-head {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 1.25rem;
        }

        .rp-arch-kicker {
            color: #2563eb;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.09em;
            margin-bottom: 0.35rem;
        }

        .rp-arch-title {
            color: #0f172a;
            font-size: 1.35rem;
            font-weight: 750;
            line-height: 1.25;
            margin-bottom: 0.35rem;
        }

        .rp-arch-subtitle {
            color: #64748b;
            font-size: 0.9rem;
            line-height: 1.55;
            max-width: 850px;
        }

        .rp-arch-badge {
            flex: 0 0 auto;
            border: 1px solid #bfdbfe;
            border-radius: 999px;
            padding: 0.42rem 0.72rem;
            background: #eff6ff;
            color: #1d4ed8;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.06em;
        }

        .rp-arch-flow {
            display: grid;
            grid-template-columns:
                minmax(0, 1fr)
                26px
                minmax(0, 1fr)
                26px
                minmax(0, 1fr)
                26px
                minmax(0, 1fr);
            gap: 0.4rem;
            align-items: stretch;
        }

        .rp-arch-stage {
            border: 1px solid #e2e8f0;
            border-radius: 13px;
            padding: 1rem;
            min-height: 185px;
            background: #ffffff;
        }

        .rp-arch-number {
            color: #bfdbfe;
            font-size: 1.45rem;
            font-weight: 800;
            line-height: 1;
            margin-bottom: 0.55rem;
        }

        .rp-arch-label {
            color: #2563eb;
            font-size: 0.67rem;
            font-weight: 800;
            letter-spacing: 0.07em;
            margin-bottom: 0.4rem;
        }

        .rp-arch-name {
            color: #0f172a;
            font-size: 0.96rem;
            font-weight: 700;
            line-height: 1.35;
            margin-bottom: 0.75rem;
        }

        .rp-arch-items {
            display: flex;
            flex-direction: column;
            gap: 0.42rem;
            color: #64748b;
            font-size: 0.79rem;
            line-height: 1.4;
        }

        .rp-arch-arrow {
            display: flex;
            align-items: center;
            justify-content: center;
            color: #94a3b8;
            font-size: 1.2rem;
        }

        .rp-ai-strip {
            display: flex;
            align-items: flex-start;
            gap: 0.9rem;
            margin-top: 1rem;
            padding: 1rem 1.1rem;
            border: 1px solid #bfdbfe;
            border-radius: 13px;
            background: #f8fbff;
        }

        .rp-ai-mark {
            width: 38px;
            height: 38px;
            flex: 0 0 38px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            background: #2563eb;
            color: white;
            font-size: 1rem;
            font-weight: 800;
        }

        .rp-ai-label {
            color: #1d4ed8;
            font-size: 0.7rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            margin-bottom: 0.3rem;
        }

        .rp-ai-flow {
            color: #0f172a;
            font-size: 0.95rem;
            font-weight: 700;
            line-height: 1.5;
            margin-bottom: 0.25rem;
        }

        .rp-ai-flow b {
            color: #60a5fa;
            padding: 0 0.25rem;
        }

        .rp-ai-note {
            color: #64748b;
            font-size: 0.82rem;
            line-height: 1.5;
        }

        @media (max-width: 1100px) {
            .rp-arch-flow {
                grid-template-columns:
                    repeat(2, minmax(0, 1fr));
            }

            .rp-arch-arrow {
                display: none;
            }
        }
        </style>

        <div class="rp-arch">

            <div class="rp-arch-head">
                <div>
                    <div class="rp-arch-kicker">
                        VERIFIED DECISION ARCHITECTURE
                    </div>

                    <div class="rp-arch-title">
                        From financial evidence to management action
                    </div>

                    <div class="rp-arch-subtitle">
                        RiskPilot separates quantitative calculation from
                        AI interpretation so every recommendation remains
                        grounded in verified financial evidence.
                    </div>
                </div>

                <div class="rp-arch-badge">
                    ENGINE-GROUNDED
                </div>
            </div>

            <div class="rp-arch-flow">

                <div class="rp-arch-stage">
                    <div class="rp-arch-number">01</div>
                    <div class="rp-arch-label">
                        DATA FOUNDATION
                    </div>
                    <div class="rp-arch-name">
                        Trusted financial evidence
                    </div>
                    <div class="rp-arch-items">
                        <span>✓ Schema & input validation</span>
                        <span>✓ Cash evidence classification</span>
                        <span>✓ Business health metrics</span>
                    </div>
                </div>

                <div class="rp-arch-arrow">→</div>

                <div class="rp-arch-stage">
                    <div class="rp-arch-number">02</div>
                    <div class="rp-arch-label">
                        FORECAST & UNCERTAINTY
                    </div>
                    <div class="rp-arch-name">
                        Validated forward view
                    </div>
                    <div class="rp-arch-items">
                        <span>✓ Rolling model validation</span>
                        <span>✓ Champion forecast</span>
                        <span>✓ Paired-residual simulation</span>
                    </div>
                </div>

                <div class="rp-arch-arrow">→</div>

                <div class="rp-arch-stage">
                    <div class="rp-arch-number">03</div>
                    <div class="rp-arch-label">
                        RISK & RESILIENCE
                    </div>
                    <div class="rp-arch-name">
                        Management risk boundary
                    </div>
                    <div class="rp-arch-items">
                        <span>✓ Liquidity risk appetite</span>
                        <span>✓ Forward stress testing</span>
                        <span>✓ Reverse stress & survival boundary</span>
                    </div>
                </div>

                <div class="rp-arch-arrow">→</div>

                <div class="rp-arch-stage">
                    <div class="rp-arch-number">04</div>
                    <div class="rp-arch-label">
                        RECOVERY & DECISION
                    </div>
                    <div class="rp-arch-name">
                        Executable management response
                    </div>
                    <div class="rp-arch-items">
                        <span>✓ Recovery optimisation</span>
                        <span>✓ Probabilistic validation</span>
                        <span>✓ Actions & monitoring</span>
                    </div>
                </div>

            </div>

            <div class="rp-ai-strip">

                <div class="rp-ai-mark">✦</div>

                <div>
                    <div class="rp-ai-label">
                        RISKPILOT AI DECISION LAYER
                    </div>

                    <div class="rp-ai-flow">
                        Verified engine outputs
                        <b>→</b>
                        Liquidity Decision Brief
                        <b>→</b>
                        Grounded AI interpretation
                        <b>→</b>
                        Management action
                    </div>

                    <div class="rp-ai-note">
                        Financial engines calculate.
                        RiskPilot AI interprets verified evidence,
                        explains the decision context and recommends
                        the next management step.
                    </div>
                </div>

            </div>

        </div>
            """
        ),
    )
