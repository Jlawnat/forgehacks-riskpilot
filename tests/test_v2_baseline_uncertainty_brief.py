from datetime import datetime, timezone

from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)


def _build(scenario_id: str):
    scenario = get_v2_demo_scenario(
        scenario_id
    )

    result = build_command_center(
        scenario,
        created_at=datetime(
            2026,
            10,
            4,
            tzinfo=timezone.utc,
        ),
        simulations=200,
        seed=42,
    )

    return scenario, result


def test_command_center_brief_carries_baseline_uncertainty():
    scenario, result = _build(
        "severe_uncertain"
    )

    uncertainty = result.brief.uncertainty

    assert uncertainty is not None

    assert (
        uncertainty.reserve_breach_probability
        == result.simulation.shortfall_probability
    )

    assert (
        uncertainty.maximum_acceptable_breach_probability
        == scenario.max_reserve_breach_probability
    )

    assert (
        uncertainty.within_risk_appetite
        == (
            result.simulation.shortfall_probability
            <= scenario.max_reserve_breach_probability
        )
    )

    assert (
        uncertainty.liquidity_buffer_at_confidence
        == result.simulation.liquidity_buffer_at_confidence
    )

    assert (
        uncertainty.expected_tail_buffer
        == result.simulation.expected_tail_buffer
    )


def test_baseline_and_post_recovery_probability_are_separate():
    _, result = _build(
        "stressed_recoverable"
    )

    assert result.brief.uncertainty is not None
    assert result.brief.recovery is not None

    assert (
        result.brief.uncertainty
        .reserve_breach_probability
        == result.simulation.shortfall_probability
    )

    assert (
        result.brief.recovery
        .reserve_breach_probability
        == result.recovery_validation
        .reserve_breach_probability
    )
