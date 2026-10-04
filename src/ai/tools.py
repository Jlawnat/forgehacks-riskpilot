from __future__ import annotations

import json
from typing import Any

from agents import RunContextWrapper
from agents.decorators import tool

from src.ai.context import (
    RiskAnalystContext,
)
from src.scenarios.decomposition import (
    decompose_scenario_from_context,
)
from src.scenarios.engine import (
    ScenarioInput,
    scenario_context_from_forecast_context,
    run_scenario_from_context,
)
from src.scenarios.reverse_stress import (
    ReverseStressConfig,
    reverse_stress_from_context,
)
from src.simulation.liquidity import (
    SimulationInput,
    simulate_liquidity_from_context,
)


def _clean_number(
    value: float | None,
) -> float | None:
    if value is None:
        return None

    return round(
        float(value),
        6,
    )


def _json(
    payload: dict[str, Any],
) -> str:
    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )


# ============================================================
# PURE SNAPSHOT FUNCTIONS
# These are independently testable without calling OpenAI.
# ============================================================


def business_health_snapshot(
    context: RiskAnalystContext,
) -> dict[str, Any]:
    metrics = context.metrics
    risks = context.risks

    receivable_ratio = (
        metrics.latest_receivables
        / metrics.latest_revenue
        if metrics.latest_revenue > 0
        else None
    )

    reserve_headroom = (
        metrics.latest_cash_balance
        - context.policy.minimum_cash_reserve
    )

    return {
        "current_position": {
            "revenue":
                _clean_number(
                    metrics.latest_revenue
                ),
            "operating_cost":
                _clean_number(
                    metrics.latest_operating_cost
                ),
            "cash_balance":
                _clean_number(
                    metrics.latest_cash_balance
                ),
            "receivables":
                _clean_number(
                    metrics.latest_receivables
                ),
        },
        "indicators": {
            "recent_revenue_growth":
                _clean_number(
                    metrics.revenue_growth
                ),
            "cost_to_revenue_ratio":
                _clean_number(
                    metrics.cost_to_revenue_ratio
                ),
            "revenue_volatility":
                _clean_number(
                    metrics.revenue_volatility
                ),
            "historical_run_rate_cash_runway_months":
                _clean_number(
                    metrics.cash_runway_months
                ),
            "receivables_to_revenue_ratio":
                _clean_number(
                    receivable_ratio
                ),
        },
        "risk_assessment": {
            "overall":
                risks.overall_risk,
            "liquidity":
                risks.liquidity_risk,
            "revenue":
                risks.revenue_risk,
            "cost_pressure":
                risks.cost_pressure_risk,
            "receivables":
                risks.receivables_risk,
        },
        "risk_policy": {
            "minimum_cash_reserve":
                context.policy.minimum_cash_reserve,
            "maximum_breach_probability":
                context.policy.max_shortfall_probability,
            "current_reserve_headroom":
                _clean_number(
                    reserve_headroom
                ),
        },
    }


def forecast_outlook_snapshot(
    context: RiskAnalystContext,
) -> dict[str, Any]:
    revenue = context.forecast.revenue_forecast
    cost = context.forecast.cost_forecast

    return {
        "horizon":
            context.forecast.horizon,
        "revenue": {
            "selected_model":
                revenue.selected_model,
            "validation_mae":
                _clean_number(
                    revenue.validation_mae
                ),
            "forecast": [
                {
                    "period": point.period,
                    "value":
                        _clean_number(
                            point.value
                        ),
                    "lower":
                        _clean_number(
                            point.lower
                        ),
                    "upper":
                        _clean_number(
                            point.upper
                        ),
                }
                for point
                in revenue.forecasts
            ],
        },
        "operating_cost": {
            "selected_model":
                cost.selected_model,
            "validation_mae":
                _clean_number(
                    cost.validation_mae
                ),
            "forecast": [
                {
                    "period": point.period,
                    "value":
                        _clean_number(
                            point.value
                        ),
                    "lower":
                        _clean_number(
                            point.lower
                        ),
                    "upper":
                        _clean_number(
                            point.upper
                        ),
                }
                for point
                in cost.forecasts
            ],
        },
        "paired_forecast_errors_available":
            len(
                context.forecast.paired_residuals
            ),
    }


def liquidity_risk_snapshot(
    context: RiskAnalystContext,
) -> dict[str, Any]:
    horizon = context.forecast.horizon

    reserve = (
        simulate_liquidity_from_context(
            context.forecast,
            SimulationInput(
                horizon=horizon,
                simulations=5000,
                seed=42,
                cash_floor=(
                    context.policy
                    .minimum_cash_reserve
                ),
                confidence_level=0.95,
            ),
        )
    )

    insolvency = (
        simulate_liquidity_from_context(
            context.forecast,
            SimulationInput(
                horizon=horizon,
                simulations=5000,
                seed=42,
                cash_floor=0.0,
                confidence_level=0.95,
            ),
        )
    )

    return {
        "simulation_method":
            "paired empirical forecast-error bootstrap",
        "simulations":
            reserve.simulations,
        "paired_residuals_available":
            reserve.residual_pairs_available,
        "management_reserve":
            context.policy.minimum_cash_reserve,
        "maximum_acceptable_breach_probability":
            context.policy.max_shortfall_probability,
        "reserve_breach_probability":
            _clean_number(
                reserve.shortfall_probability
            ),
        "cash_negative_probability":
            _clean_number(
                insolvency.shortfall_probability
            ),
        "within_management_appetite":
            (
                reserve.shortfall_probability
                <= context.policy
                .max_shortfall_probability
            ),
        "median_end_cash":
            _clean_number(
                reserve.median_end_cash
            ),
        "p10_end_cash":
            _clean_number(
                reserve.p10_end_cash
            ),
        "median_min_cash":
            _clean_number(
                reserve.median_min_cash
            ),
        "p10_min_cash":
            _clean_number(
                reserve.p10_min_cash
            ),
        "liquidity_buffer_95":
            _clean_number(
                reserve
                .liquidity_buffer_at_confidence
            ),
        "low_sample_warning":
            (
                reserve.residual_pairs_available
                < 30
            ),
    }


def stress_test_snapshot(
    context: RiskAnalystContext,
    revenue_change_pct: float,
    cost_change_pct: float,
    receivable_delay_days: int,
) -> dict[str, Any]:
    scenario_context = (
        scenario_context_from_forecast_context(
            context.forecast
        )
    )

    scenario = ScenarioInput(
        revenue_change=(
            revenue_change_pct / 100.0
        ),
        cost_change=(
            cost_change_pct / 100.0
        ),
        receivable_delay_days=(
            receivable_delay_days
        ),
        horizon=context.forecast.horizon,
    )

    result = run_scenario_from_context(
        scenario_context,
        scenario,
    )

    decomposition = (
        decompose_scenario_from_context(
            scenario_context,
            scenario,
        )
    )

    return {
        "scenario": {
            "revenue_change_pct":
                revenue_change_pct,
            "cost_change_pct":
                cost_change_pct,
            "receivable_delay_days":
                receivable_delay_days,
            "horizon":
                context.forecast.horizon,
        },
        "results": {
            "baseline_end_cash":
                _clean_number(
                    result.baseline_end_cash
                ),
            "stressed_end_cash":
                _clean_number(
                    result.stressed_end_cash
                ),
            "baseline_min_cash":
                _clean_number(
                    result.baseline_min_cash
                ),
            "stressed_min_cash":
                _clean_number(
                    result.stressed_min_cash
                ),
            "peak_liquidity_gap":
                _clean_number(
                    result.peak_liquidity_gap
                ),
            "baseline_first_negative_period":
                result.baseline_first_negative_period,
            "stressed_first_negative_period":
                result.stressed_first_negative_period,
        },
        "peak_liquidity_drivers": [
            {
                "driver":
                    item.driver,
                "impact":
                    _clean_number(
                        item.peak_liquidity_impact
                    ),
                "contribution_share":
                    _clean_number(
                        item.contribution_share
                    ),
            }
            for item
            in decomposition.drivers
        ],
    }


def reverse_stress_snapshot(
    context: RiskAnalystContext,
) -> dict[str, Any]:
    scenario_context = (
        scenario_context_from_forecast_context(
            context.forecast
        )
    )

    result = reverse_stress_from_context(
        scenario_context,
        ReverseStressConfig(
            target_min_cash=(
                context.policy
                .minimum_cash_reserve
            ),
            horizon=context.forecast.horizon,
            max_revenue_decline=0.30,
            max_cost_increase=0.30,
            max_receivable_delay_days=90,
            grid_step=0.01,
        ),
    )

    nearest = (
        result.nearest_combined_failure
    )

    return {
        "management_reserve":
            context.policy.minimum_cash_reserve,
        "baseline_min_cash":
            _clean_number(
                result.baseline_min_cash
            ),
        "baseline_margin_to_reserve":
            _clean_number(
                result.baseline_margin_to_target
            ),
        "baseline_already_breached":
            result.baseline_breached,
        "revenue_decline_breakpoint":
            _clean_number(
                result.revenue_decline_breakpoint
            ),
        "cost_increase_breakpoint":
            _clean_number(
                result.cost_increase_breakpoint
            ),
        "receivable_delay_breakpoint_days":
            result.receivable_delay_breakpoint_days,
        "nearest_combined_failure": (
            None
            if nearest is None
            else {
                "revenue_decline":
                    _clean_number(
                        nearest.revenue_decline
                    ),
                "cost_increase":
                    _clean_number(
                        nearest.cost_increase
                    ),
                "minimum_cash":
                    _clean_number(
                        nearest.min_cash
                    ),
            }
        ),
    }


# ============================================================
# AGENT TOOLS
# ============================================================


@tool
def get_business_health(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
) -> str:
    """
    Get current business health, quantitative indicators,
    deterministic risk levels and management risk policy.

    Use this for questions about the current financial
    position or overall risk.
    """

    ctx.context.record_tool(
        "get_business_health"
    )

    return _json(
        business_health_snapshot(
            ctx.context
        )
    )


@tool
def get_forecast_outlook(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
) -> str:
    """
    Get validated revenue and operating-cost forecasts,
    uncertainty intervals and selected forecasting models.

    Use this for forward-looking questions.
    """

    ctx.context.record_tool(
        "get_forecast_outlook"
    )

    return _json(
        forecast_outlook_snapshot(
            ctx.context
        )
    )


@tool
def get_liquidity_risk(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
) -> str:
    """
    Get probabilistic liquidity risk using RiskPilot's
    paired historical forecast-error bootstrap.

    Use this for reserve-breach probability, negative-cash
    probability, downside cash or liquidity-buffer questions.

    This tool already returns the management cash reserve and
    maximum acceptable breach probability, so it is sufficient
    by itself for comparing reserve-breach risk with cash-negative
    risk.
    """

    ctx.context.record_tool(
        "get_liquidity_risk"
    )

    return _json(
        liquidity_risk_snapshot(
            ctx.context
        )
    )


@tool
def run_stress_test(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
    revenue_change_pct: float,
    cost_change_pct: float,
    receivable_delay_days: int,
) -> str:
    """
    Run a deterministic business stress scenario.

    Args:
        revenue_change_pct:
            Percentage-point change in revenue. Use negative
            values for a revenue decline, for example -15.
        cost_change_pct:
            Percentage-point change in operating costs. Use
            positive values for cost inflation, for example 10.
        receivable_delay_days:
            Additional collection delay in days.
    """

    ctx.context.record_tool(
        "run_stress_test"
    )

    return _json(
        stress_test_snapshot(
            ctx.context,
            revenue_change_pct=(
                revenue_change_pct
            ),
            cost_change_pct=(
                cost_change_pct
            ),
            receivable_delay_days=(
                receivable_delay_days
            ),
        )
    )


@tool
def run_reverse_stress(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
) -> str:
    """
    Find the deterioration required to breach the
    management liquidity reserve.

    Use this for resilience, tolerance, survival-capacity
    or breakpoint questions.
    """

    ctx.context.record_tool(
        "run_reverse_stress"
    )

    return _json(
        reverse_stress_snapshot(
            ctx.context
        )
    )


# ============================================================
# RECOVERY DECISION TOOLS
# ============================================================

from src.scenarios.recovery_optimizer import (
    RecoveryOptimizerConfig,
    RecoveryOption,
    optimize_recovery_from_context,
)
from src.simulation.recovery_validation import (
    validate_recovery_option_from_context,
)


def _recovery_option_payload(
    option: RecoveryOption | None,
) -> dict[str, Any] | None:
    if option is None:
        return None

    return {
        "revenue_improvement_pct":
            _clean_number(
                option.revenue_improvement_pct
            ),
        "cost_reduction_pct":
            _clean_number(
                option.cost_reduction_pct
            ),
        "receivable_acceleration_days":
            option.receivable_acceleration_days,
        "external_liquidity":
            _clean_number(
                option.external_liquidity
            ),
        "operating_min_cash":
            _clean_number(
                option.operating_min_cash
            ),
        "resulting_min_cash":
            _clean_number(
                option.resulting_min_cash
            ),
        "resulting_end_cash":
            _clean_number(
                option.resulting_end_cash
            ),
        "reserve_margin":
            _clean_number(
                option.reserve_margin
            ),
        "operational_disruption_score":
            _clean_number(
                option.operational_disruption_score
            ),
        "total_intervention_score":
            _clean_number(
                option.total_intervention_score
            ),
        "maximum_lever_utilisation":
            _clean_number(
                option.maximum_lever_utilisation
            ),
    }


def recovery_options_snapshot(
    context: RiskAnalystContext,
    revenue_change_pct: float,
    cost_change_pct: float,
    receivable_delay_days: int,
) -> dict[str, Any]:
    scenario_context = (
        scenario_context_from_forecast_context(
            context.forecast
        )
    )

    scenario = ScenarioInput(
        revenue_change=(
            revenue_change_pct / 100.0
        ),
        cost_change=(
            cost_change_pct / 100.0
        ),
        receivable_delay_days=(
            receivable_delay_days
        ),
        horizon=context.forecast.horizon,
    )

    result = optimize_recovery_from_context(
        scenario_context,
        scenario,
        RecoveryOptimizerConfig(
            target_min_cash=(
                context.policy
                .minimum_cash_reserve
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

    return {
        "scenario": {
            "revenue_change_pct":
                revenue_change_pct,
            "cost_change_pct":
                cost_change_pct,
            "receivable_delay_days":
                receivable_delay_days,
            "horizon":
                context.forecast.horizon,
        },
        "management_reserve":
            context.policy.minimum_cash_reserve,
        "stressed_min_cash":
            _clean_number(
                result.stressed_min_cash
            ),
        "initial_reserve_gap":
            _clean_number(
                result.initial_reserve_gap
            ),
        "candidates_evaluated":
            result.candidates_evaluated,
        "recovery_available":
            result.feasible,
        "balanced":
            _recovery_option_payload(
                result.recommended
            ),
        "lowest_funding":
            _recovery_option_payload(
                result.lowest_external_liquidity
            ),
        "lowest_operational_disruption":
            _recovery_option_payload(
                result.lowest_operational_disruption
            ),
        "no_external_funding":
            _recovery_option_payload(
                result.no_external_liquidity
            ),
        "best_effort":
            _recovery_option_payload(
                result.best_effort
            ),
    }


def recovery_validation_snapshot(
    context: RiskAnalystContext,
    revenue_change_pct: float,
    cost_change_pct: float,
    receivable_delay_days: int,
) -> dict[str, Any]:
    scenario_context = (
        scenario_context_from_forecast_context(
            context.forecast
        )
    )

    scenario = ScenarioInput(
        revenue_change=(
            revenue_change_pct / 100.0
        ),
        cost_change=(
            cost_change_pct / 100.0
        ),
        receivable_delay_days=(
            receivable_delay_days
        ),
        horizon=context.forecast.horizon,
    )

    optimization = optimize_recovery_from_context(
        scenario_context,
        scenario,
        RecoveryOptimizerConfig(
            target_min_cash=(
                context.policy
                .minimum_cash_reserve
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

    plans = [
        (
            "Balanced",
            optimization.recommended,
        ),
        (
            "Lowest Funding",
            optimization
            .lowest_external_liquidity,
        ),
        (
            "Lowest Operational Disruption",
            optimization
            .lowest_operational_disruption,
        ),
    ]

    validations = []

    for plan_name, option in plans:
        if option is None:
            continue

        result = (
            validate_recovery_option_from_context(
                context=context.forecast,
                base_scenario=scenario,
                option=option,
                plan_name=plan_name,
                cash_floor=(
                    context.policy
                    .minimum_cash_reserve
                ),
                max_shortfall_probability=(
                    context.policy
                    .max_shortfall_probability
                ),
                simulations=5000,
                seed=42,
            )
        )

        validations.append(
            {
                "plan":
                    plan_name,
                "deterministic_external_liquidity":
                    _clean_number(
                        option.external_liquidity
                    ),
                "reserve_breach_probability_before_buffer":
                    _clean_number(
                        result
                        .reserve_breach_probability
                    ),
                "maximum_acceptable_breach_probability":
                    _clean_number(
                        result
                        .max_acceptable_breach_probability
                    ),
                "within_appetite_before_buffer":
                    result.within_risk_appetite,
                "additional_uncertainty_buffer":
                    _clean_number(
                        result
                        .additional_buffer_required
                    ),
                "risk_adjusted_total_liquidity":
                    _clean_number(
                        result
                        .risk_adjusted_total_liquidity
                    ),
                "reserve_breach_probability_after_buffer":
                    _clean_number(
                        result
                        .risk_adjusted_breach_probability
                    ),
                "within_appetite_after_buffer":
                    result
                    .risk_adjusted_within_appetite,
                "risk_adjusted_median_min_cash":
                    _clean_number(
                        result
                        .risk_adjusted_median_min_cash
                    ),
                "risk_adjusted_p10_min_cash":
                    _clean_number(
                        result
                        .risk_adjusted_p10_min_cash
                    ),
            }
        )

    return {
        "scenario": {
            "revenue_change_pct":
                revenue_change_pct,
            "cost_change_pct":
                cost_change_pct,
            "receivable_delay_days":
                receivable_delay_days,
        },
        "management_reserve":
            context.policy.minimum_cash_reserve,
        "maximum_acceptable_breach_probability":
            context.policy.max_shortfall_probability,
        "simulation_method":
            "paired empirical forecast-error bootstrap",
        "paired_residuals_available":
            len(
                context.forecast.paired_residuals
            ),
        "plans":
            validations,
    }


@tool
def get_recovery_options(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
    revenue_change_pct: float,
    cost_change_pct: float,
    receivable_delay_days: int,
) -> str:
    """
    Find deterministic management recovery alternatives
    for a specified stress scenario.

    Returns a balanced plan, lowest-funding plan and
    lowest-operational-disruption plan.

    Args:
        revenue_change_pct:
            Revenue shock in percentage points.
            Example: -15 means revenue falls 15%.
        cost_change_pct:
            Cost shock in percentage points.
            Example: 10 means costs rise 10%.
        receivable_delay_days:
            Additional receivable collection delay.
    """

    ctx.context.record_tool(
        "get_recovery_options"
    )

    return _json(
        recovery_options_snapshot(
            ctx.context,
            revenue_change_pct,
            cost_change_pct,
            receivable_delay_days,
        )
    )


@tool
def validate_recovery_options(
    ctx: RunContextWrapper[
        RiskAnalystContext
    ],
    revenue_change_pct: float,
    cost_change_pct: float,
    receivable_delay_days: int,
) -> str:
    """
    Probabilistically validate RiskPilot's shortlisted
    recovery alternatives against management risk appetite.

    Use this after get_recovery_options when deciding
    whether recovery plans remain adequate after forecast
    uncertainty is considered.

    Args:
        revenue_change_pct:
            Revenue shock in percentage points.
        cost_change_pct:
            Cost shock in percentage points.
        receivable_delay_days:
            Additional collection delay in days.
    """

    ctx.context.record_tool(
        "validate_recovery_options"
    )

    return _json(
        recovery_validation_snapshot(
            ctx.context,
            revenue_change_pct,
            cost_change_pct,
            receivable_delay_days,
        )
    )
