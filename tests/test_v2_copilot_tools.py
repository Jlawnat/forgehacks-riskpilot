from datetime import datetime, timezone

from src.ai.v2_context import V2CopilotContext
from src.ai.v2_tools import (
    v2_liquidity_decision_brief_snapshot,
)
from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)


def test_v2_brief_snapshot_handles_missing_brief():
    context = V2CopilotContext(
        liquidity_brief=None
    )

    result = (
        v2_liquidity_decision_brief_snapshot(
            context
        )
    )

    assert result["available"] is False
    assert "reason" in result


def test_v2_brief_snapshot_returns_engine_brief_without_recalculation():
    scenario = get_v2_demo_scenario(
        "healthy"
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

    context = V2CopilotContext(
        liquidity_brief=result.brief
    )

    snapshot = (
        v2_liquidity_decision_brief_snapshot(
            context
        )
    )

    assert snapshot["available"] is True
    assert (
        snapshot["brief"]
        == result.brief.model_dump(
            mode="json"
        )
    )

    assert (
        snapshot["brief"]["brief_id"]
        == result.brief.brief_id
    )

    assert (
        snapshot["brief"]["position"][
            "management_reserve"
        ]
        == result.brief.position.management_reserve
    )


def test_v2_snapshot_declares_critical_grounding_semantics():
    context = V2CopilotContext(
        liquidity_brief=None
    )

    result = (
        v2_liquidity_decision_brief_snapshot(
            context
        )
    )

    assert result["available"] is False

    scenario = get_v2_demo_scenario(
        "healthy"
    )

    command_center = build_command_center(
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

    context = V2CopilotContext(
        liquidity_brief=command_center.brief
    )

    result = (
        v2_liquidity_decision_brief_snapshot(
            context
        )
    )

    notes = result["grounding_notes"]

    assert "not a probability" in (
        notes["evidence_coverage"]
    )
    assert "separate conclusions" in (
        notes["recovery"]
    )
    assert "not realised cash benefit" in (
        notes["actions"]
    )
    assert "legacy monthly" in (
        notes["forecast"]
    )


def test_v2_snapshot_exposes_baseline_uncertainty_separately():
    scenario = get_v2_demo_scenario(
        "severe_uncertain"
    )

    command_center = build_command_center(
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

    context = V2CopilotContext(
        liquidity_brief=command_center.brief
    )

    result = (
        v2_liquidity_decision_brief_snapshot(
            context
        )
    )

    uncertainty = result["brief"][
        "uncertainty"
    ]

    assert uncertainty is not None

    assert (
        uncertainty[
            "reserve_breach_probability"
        ]
        == command_center
        .simulation
        .shortfall_probability
    )

    assert (
        uncertainty[
            "maximum_acceptable_breach_probability"
        ]
        == scenario
        .max_reserve_breach_probability
    )

    baseline_note = (
        result["grounding_notes"][
            "baseline_uncertainty"
        ]
    )

    assert (
        "pre-recovery probabilistic"
        in baseline_note
    )

    assert (
        "post-recovery validation"
        in baseline_note
    )


def test_scoped_position_snapshot_does_not_leak_recovery():
    from src.ai.v2_tools import (
        v2_liquidity_position_snapshot,
    )

    scenario = get_v2_demo_scenario(
        "severe_uncertain"
    )

    command_center = build_command_center(
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

    context = V2CopilotContext(
        liquidity_brief=command_center.brief
    )

    result = v2_liquidity_position_snapshot(
        context
    )

    assert result["available"] is True
    assert "recovery" not in result
    assert "cash_drivers" not in result
    assert "actions" not in result
    assert "monitoring" not in result

    uncertainty = result[
        "baseline_uncertainty"
    ]

    assert (
        uncertainty[
            "reserve_breach_probability"
        ]
        == command_center
        .simulation
        .shortfall_probability
    )

    assert (
        "first_week_reserve_breach_probability"
        not in uncertainty
    )


def test_scoped_cash_evidence_snapshot_contains_no_recovery():
    from src.ai.v2_tools import (
        v2_cash_evidence_snapshot,
    )

    scenario = get_v2_demo_scenario(
        "severe_uncertain"
    )

    command_center = build_command_center(
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

    context = V2CopilotContext(
        liquidity_brief=command_center.brief
    )

    result = v2_cash_evidence_snapshot(
        context
    )

    assert result["available"] is True
    assert (
        result["evidence_quality"][
            "evidence_coverage_ratio"
        ]
        == command_center
        .brief
        .position
        .evidence_coverage_ratio
    )

    assert "recovery" not in result
    assert "baseline_uncertainty" not in result
    assert "monitoring" not in result
