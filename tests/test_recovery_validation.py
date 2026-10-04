import pytest

from src.core.context import (
    build_forecast_context,
)
from src.ingestion.loader import (
    load_business_csv,
)
from src.ingestion.validator import (
    validate_business_data,
)
from src.scenarios.engine import (
    ScenarioInput,
    scenario_context_from_forecast_context,
)
from src.scenarios.recovery_optimizer import (
    RecoveryOptimizerConfig,
    optimize_recovery_from_context,
)
from src.simulation.recovery_validation import (
    validate_recovery_option_from_context,
)


@pytest.fixture(scope="module")
def setup():
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(raw)

    forecast_context = (
        build_forecast_context(
            df,
            horizon=3,
        )
    )

    scenario_context = (
        scenario_context_from_forecast_context(
            forecast_context
        )
    )

    scenario = ScenarioInput(
        revenue_change=-0.15,
        cost_change=0.10,
        receivable_delay_days=30,
        horizon=3,
    )

    optimization = (
        optimize_recovery_from_context(
            scenario_context,
            scenario,
            RecoveryOptimizerConfig(
                target_min_cash=20000.0,
                max_external_liquidity=50000.0,
            ),
        )
    )

    return (
        forecast_context,
        scenario,
        optimization,
    )


def test_recovery_validation_returns_probability(
    setup,
):
    context, scenario, optimization = setup

    option = optimization.recommended

    assert option is not None

    result = (
        validate_recovery_option_from_context(
            context=context,
            base_scenario=scenario,
            option=option,
            plan_name="Balanced",
            cash_floor=20000.0,
            max_shortfall_probability=0.05,
        )
    )

    assert (
        0.0
        <= result.reserve_breach_probability
        <= 1.0
    )

    assert (
        result.within_risk_appetite
        == (
            result.reserve_breach_probability
            <= 0.05
        )
    )


def test_validation_preserves_plan_funding(
    setup,
):
    context, scenario, optimization = setup

    option = optimization.recommended

    assert option is not None

    result = (
        validate_recovery_option_from_context(
            context=context,
            base_scenario=scenario,
            option=option,
            plan_name="Balanced",
            cash_floor=20000.0,
            max_shortfall_probability=0.05,
        )
    )

    assert (
        result.external_liquidity_already_in_plan
        == pytest.approx(
            option.external_liquidity
        )
    )


def test_additional_buffer_is_non_negative(
    setup,
):
    context, scenario, optimization = setup

    option = optimization.recommended

    assert option is not None

    result = (
        validate_recovery_option_from_context(
            context=context,
            base_scenario=scenario,
            option=option,
            plan_name="Balanced",
            cash_floor=20000.0,
            max_shortfall_probability=0.05,
        )
    )

    assert (
        result.additional_buffer_required
        >= 0.0
    )
