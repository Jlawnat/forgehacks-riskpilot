from src.core.direct_cash import (
    build_direct_cash_forecast,
)
from src.core.liquidity_metrics import (
    build_liquidity_decision_metrics,
)
from src.core.weekly_simulation import (
    WeeklySimulationConfig,
    simulate_weekly_liquidity,
)
from src.core.weekly_uncertainty import (
    validate_weekly_uncertainty_profile,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
    get_v2_demo_scenarios,
)


def _metrics(scenario):
    forecast = build_direct_cash_forecast(
        scenario.forecast_input
    )

    return build_liquidity_decision_metrics(
        forecast,
        management_reserve=(
            scenario.management_reserve
        ),
    )


def _simulation(scenario):
    return simulate_weekly_liquidity(
        scenario.forecast_input,
        scenario.uncertainty_profile,
        WeeklySimulationConfig(
            simulations=2000,
            seed=42,
            cash_floor=(
                scenario.management_reserve
            ),
            confidence_level=0.90,
        ),
    )


def test_four_demo_scenarios_exist():
    scenarios = get_v2_demo_scenarios()

    assert len(scenarios) == 4

    assert {
        scenario.scenario_id
        for scenario in scenarios
    } == {
        "healthy",
        "stressed_recoverable",
        "severe_uncertain",
        "public_sec_cenveo",
    }


def test_all_demo_uncertainty_profiles_are_valid():
    for scenario in get_v2_demo_scenarios():
        validate_weekly_uncertainty_profile(
            scenario.forecast_input,
            scenario.uncertainty_profile,
        )


def test_healthy_business_has_no_deterministic_breach():
    scenario = get_v2_demo_scenario(
        "healthy"
    )

    metrics = _metrics(scenario)

    assert (
        metrics.first_reserve_breach_week
        is None
    )

    assert metrics.minimum_headroom > 0.0

    assert (
        metrics.evidence_coverage_ratio
        is not None
    )

    assert (
        metrics.evidence_coverage_ratio
        > 0.70
    )


def test_stressed_business_has_near_term_breach():
    scenario = get_v2_demo_scenario(
        "stressed_recoverable"
    )

    metrics = _metrics(scenario)

    assert (
        metrics.first_reserve_breach_week
        is not None
    )

    assert metrics.minimum_headroom < 0.0


def test_severe_business_is_deterministically_above_reserve():
    scenario = get_v2_demo_scenario(
        "severe_uncertain"
    )

    metrics = _metrics(scenario)

    assert (
        metrics.first_reserve_breach_week
        is None
    )

    assert metrics.minimum_headroom > 0.0

    assert metrics.minimum_headroom < 10000.0


def test_healthy_simulated_breach_risk_is_negligible():
    scenario = get_v2_demo_scenario(
        "healthy"
    )

    result = _simulation(scenario)

    assert result.shortfall_probability < 0.01


def test_severe_uncertainty_reveals_material_risk():
    healthy = _simulation(
        get_v2_demo_scenario(
            "healthy"
        )
    )

    severe = _simulation(
        get_v2_demo_scenario(
            "severe_uncertain"
        )
    )

    assert severe.shortfall_probability > 0.10

    assert (
        severe.shortfall_probability
        > healthy.shortfall_probability
    )


def test_public_sec_case_preserves_disclosed_liquidity_shape():
    scenario = get_v2_demo_scenario(
        "public_sec_cenveo"
    )

    forecast = build_direct_cash_forecast(
        scenario.forecast_input
    )

    closing = tuple(
        week.closing_cash
        for week in forecast.weeks
    )

    assert closing == (
        26749000.0,
        21120000.0,
        17393000.0,
        9315000.0,
        53229000.0,
        56960000.0,
        104966000.0,
        106507000.0,
        92176000.0,
        87969000.0,
        92041000.0,
        119004000.0,
        122706000.0,
    )

    assert all(
        event.source_type == "MODELLED"
        for event in scenario.forecast_input.events
    )

    assert (
        scenario.management_reserve
        == 20000000.0
    )


def test_unknown_demo_is_rejected():
    try:
        get_v2_demo_scenario(
            "does-not-exist"
        )
    except ValueError as exc:
        assert "Unknown V2 demo scenario" in str(
            exc
        )
    else:
        raise AssertionError(
            "Expected ValueError."
        )
