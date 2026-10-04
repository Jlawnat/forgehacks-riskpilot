from datetime import datetime, timezone

from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)


def _now():
    return datetime(
        2026,
        10,
        4,
        10,
        0,
        tzinfo=timezone.utc,
    )


def _build(name):
    return build_command_center(
        get_v2_demo_scenario(name),
        created_at=_now(),
        simulations=1000,
        seed=42,
    )


def _trigger_types(result):
    return {
        item.trigger_type
        for item in result.monitoring.triggers
    }


def test_healthy_command_center_is_low_risk():
    result = _build("healthy")

    assert (
        result.snapshot
        .decision_metrics
        .first_reserve_breach_week
        is None
    )

    assert (
        result.simulation.shortfall_probability
        < 0.01
    )

    assert result.recovery_evaluation is None
    assert result.recovery_validation is None
    assert len(result.action_register.actions) == 0

    assert (
        "PROJECTED_RESERVE_BREACH"
        not in _trigger_types(result)
    )

    assert (
        "RISK_ABOVE_APPETITE"
        not in _trigger_types(result)
    )


def test_stressed_command_center_detects_breach():
    result = _build(
        "stressed_recoverable"
    )

    assert (
        result.snapshot
        .decision_metrics
        .first_reserve_breach_week
        is not None
    )

    assert (
        "PROJECTED_RESERVE_BREACH"
        in _trigger_types(result)
    )


def test_stressed_recovery_is_engine_verified():
    result = _build(
        "stressed_recoverable"
    )

    assert result.recovery_evaluation is not None

    assert (
        result.recovery_evaluation.feasible
        is True
    )

    assert (
        result.recovery_evaluation
        .plan.external_liquidity
        == 10000.0
    )

    assert (
        len(result.action_register.actions)
        == 1
    )

    assert (
        result.action_register
        .actions[0]
        .expected_cash_impact
        == 10000.0
    )


def test_severe_case_exposes_uncertainty_risk():
    result = _build(
        "severe_uncertain"
    )

    assert (
        result.snapshot
        .decision_metrics
        .first_reserve_breach_week
        is None
    )

    assert (
        result.simulation.shortfall_probability
        > 0.10
    )

    assert (
        "RISK_ABOVE_APPETITE"
        in _trigger_types(result)
    )


def test_severe_zero_plan_is_probabilistically_checked():
    result = _build(
        "severe_uncertain"
    )

    assert result.recovery_evaluation is not None
    assert result.recovery_validation is not None

    assert (
        result.recovery_evaluation.feasible
        is True
    )

    assert (
        result.recovery_validation
        .within_risk_appetite
        is False
    )

    assert (
        result.recovery_validation.status
        ==
        "DETERMINISTICALLY_SUFFICIENT_BUT_PROBABILISTICALLY_INADEQUATE"
    )


def test_brief_is_from_same_command_center_evidence():
    result = _build(
        "stressed_recoverable"
    )

    assert (
        result.brief.snapshot_id
        == result.snapshot.snapshot_id
    )

    assert (
        result.brief.position
        .management_reserve
        == result.snapshot
        .decision_metrics
        .management_reserve
    )

    assert (
        result.brief.recovery
        .deterministic_feasible
        == result.recovery_evaluation.feasible
    )


def test_command_center_is_reproducible():
    first = _build(
        "severe_uncertain"
    )

    second = _build(
        "severe_uncertain"
    )

    assert (
        first.simulation
        == second.simulation
    )

    assert first.brief == second.brief
