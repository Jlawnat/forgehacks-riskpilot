from datetime import datetime, timezone

from src.ai.v2_context import V2CopilotContext
from src.ai.v2_copilot import V2_COPILOT_INSTRUCTIONS
from src.ai.v2_tools import (
    run_v2_what_if_snapshot,
    v2_recovery_evidence_snapshot,
)
from src.core.command_center import build_command_center
from src.core.v2_what_if import V2WhatIfRequest, run_v2_what_if
from src.demo.v2_scenarios import get_v2_demo_scenario
from src.ui.v2_command_center import (
    _build_riskpilot_insight,
    _monitoring_heading,
    _pct,
    _pre_recovery_risk_label,
)
from src.ui.v2_copilot import evidence_items_for_tools


CREATED_AT = datetime(2026, 10, 4, tzinfo=timezone.utc)


def _severe_revenue_what_if():
    return run_v2_what_if(
        get_v2_demo_scenario("severe_uncertain"),
        V2WhatIfRequest(revenue_change_pct=-20.0),
        created_at=CREATED_AT,
        simulations=2000,
        seed=42,
    )


def test_infeasible_current_recovery_is_distinct_from_buffered_result():
    outcome = _severe_revenue_what_if()
    snapshot = v2_recovery_evidence_snapshot(
        V2CopilotContext(liquidity_brief=outcome.command_center.brief)
    )
    evidence = snapshot["recovery"]
    current = evidence["current_recovery_plan"]
    additional = evidence["additional_liquidity_requirement"]

    assert current["deterministic_feasible"] is False
    assert current["remaining_reserve_gap"] == 12000.0
    assert current["reserve_breach_probability"] == 1.0
    assert current["within_risk_appetite"] is False
    assert additional["additional_upfront_buffer_at_confidence"] > 0.0
    assert additional["breach_probability_with_additional_buffer"] < 1.0
    assert additional["within_risk_appetite_with_additional_buffer"] is True
    assert "not the outcome of the current recovery plan" in additional["dependency"]


def test_recovery_grounding_requires_inadequacy_first_and_buffer_dependency():
    outcome = _severe_revenue_what_if()
    snapshot = v2_recovery_evidence_snapshot(
        V2CopilotContext(liquidity_brief=outcome.command_center.brief)
    )
    notes = snapshot["grounding_notes"]

    assert "lead" in notes["current_plan"].lower()
    assert "remains inadequate" in notes["current_plan"]
    assert "Never describe" in notes["additional_liquidity"]
    assert "current recovery plan succeeding" in notes["additional_liquidity"]

    assert "Never describe" in V2_COPILOT_INSTRUCTIONS
    assert "current recovery plan remains inadequate" in V2_COPILOT_INSTRUCTIONS
    assert "only if the stated additional upfront buffer is added" in (
        V2_COPILOT_INSTRUCTIONS
    )


def test_what_if_tool_returns_grouped_recovery_semantics():
    baseline = get_v2_demo_scenario("severe_uncertain")
    context = V2CopilotContext(
        liquidity_brief=None,
        baseline_scenario=baseline,
        what_if_created_at=CREATED_AT,
        what_if_simulations=2000,
    )
    payload = run_v2_what_if_snapshot(
        context,
        V2WhatIfRequest(revenue_change_pct=-20.0),
    )
    recovery = payload["verified_brief"]["recovery"]

    assert recovery["current_recovery_plan"][
        "reserve_breach_probability"
    ] == 1.0
    assert recovery["additional_liquidity_requirement"][
        "breach_probability_with_additional_buffer"
    ] == 0.0995
    assert "not baseline breach risk" in payload["grounding_note"]


def test_temporary_what_if_uses_what_if_risk_and_cash_labels():
    outcome = _severe_revenue_what_if()
    title, body = _build_riskpilot_insight(
        outcome.command_center,
        outcome.scenario,
        is_temporary_what_if=True,
    )

    assert title == "Near-term liquidity action is required"
    assert "What-if cash falls" in body
    assert "Baseline cash" not in body
    assert _pre_recovery_risk_label(True) == "What-if breach risk"


def test_baseline_ui_labels_remain_unchanged():
    scenario = get_v2_demo_scenario("stressed_recoverable")
    result = build_command_center(
        scenario,
        created_at=CREATED_AT,
        simulations=2000,
        seed=42,
    )
    _, body = _build_riskpilot_insight(result, scenario)

    assert "Baseline cash falls" in body
    assert "What-if cash" not in body
    assert _pre_recovery_risk_label(False) == "Baseline breach risk"
    assert _monitoring_heading(False) == "Baseline monitoring"


def test_cost_what_if_copilot_percentage_matches_ui_display():
    baseline = get_v2_demo_scenario("severe_uncertain")
    context = V2CopilotContext(
        liquidity_brief=None,
        baseline_scenario=baseline,
        what_if_created_at=CREATED_AT,
        what_if_simulations=2000,
    )
    payload = run_v2_what_if_snapshot(
        context,
        V2WhatIfRequest(cost_change_pct=10.0),
    )
    raw_probability = (
        context.what_if_result.command_center.simulation.shortfall_probability
    )

    assert raw_probability == 0.9225
    assert payload["canonical_display_values"][
        "scenario_breach_probability"
    ] == _pct(raw_probability) == "92.2%"
    assert "Quote canonical_display_values exactly" in payload["grounding_note"]


def test_temporary_monitoring_and_provenance_use_what_if_labels():
    outcome = _severe_revenue_what_if()
    items = evidence_items_for_tools(
        ("get_v2_liquidity_position",),
        outcome.command_center.brief,
        is_temporary_what_if=True,
    )

    assert _monitoring_heading(True) == "What-if monitoring"
    assert any("What-if uncertainty simulation" in item for item in items)
    assert not any("Baseline uncertainty simulation" in item for item in items)
