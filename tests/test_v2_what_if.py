from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.ai.v2_context import V2CopilotContext
from src.ai.v2_tools import run_v2_what_if_snapshot
from src.core.v2_what_if import (
    UnsupportedV2WhatIfError,
    V2WhatIfRequest,
    run_v2_what_if,
)
from src.demo.v2_scenarios import get_v2_demo_scenario


CREATED_AT = datetime(2026, 10, 4, tzinfo=timezone.utc)


def _run(request: V2WhatIfRequest):
    return run_v2_what_if(
        get_v2_demo_scenario("healthy"),
        request,
        created_at=CREATED_AT,
        simulations=200,
        seed=42,
    )


def _events(scenario):
    return {event.event_id: event for event in scenario.forecast_input.events}


def test_reserve_what_if_reruns_engine_without_mutating_baseline():
    baseline = get_v2_demo_scenario("healthy")
    before = baseline.model_dump()
    outcome = _run(V2WhatIfRequest(management_reserve=175000.0))

    assert outcome.scenario.management_reserve == 175000.0
    assert outcome.command_center.brief.position.management_reserve == 175000.0
    assert outcome.command_center.brief.position.first_reserve_breach_week is not None
    assert baseline.model_dump() == before
    assert baseline.management_reserve == 40000.0


def test_revenue_shock_changes_only_modelled_residual_sales():
    baseline = get_v2_demo_scenario("healthy")
    outcome = _run(V2WhatIfRequest(revenue_change_pct=-20.0))
    original = _events(baseline)
    changed = _events(outcome.scenario)

    for event_id, event in original.items():
        if (
            event.source_type == "MODELLED"
            and event.direction == "INFLOW"
            and event.category == "residual sales receipts"
        ):
            assert changed[event_id].amount == pytest.approx(event.amount * 0.8)
        else:
            assert changed[event_id] == event

    assert all(
        changed[event_id] == event
        for event_id, event in original.items()
        if event.source_type == "COMMITTED" and event.direction == "INFLOW"
    )


def test_cost_shock_changes_only_modelled_variable_costs():
    baseline = get_v2_demo_scenario("healthy")
    outcome = _run(V2WhatIfRequest(cost_change_pct=10.0))
    original = _events(baseline)
    changed = _events(outcome.scenario)

    for event_id, event in original.items():
        if (
            event.source_type == "MODELLED"
            and event.direction == "OUTFLOW"
            and event.category == "variable operating costs"
        ):
            assert changed[event_id].amount == pytest.approx(event.amount * 1.1)
        else:
            assert changed[event_id] == event

    assert all(
        changed[event_id] == event
        for event_id, event in original.items()
        if event.source_type == "COMMITTED" and event.direction == "OUTFLOW"
    )


def test_combined_supported_shocks_are_deterministic():
    request = V2WhatIfRequest(
        management_reserve=75000.0,
        revenue_change_pct=-20.0,
        cost_change_pct=10.0,
    )
    first = _run(request)
    second = _run(request)

    assert first == second
    assert first.command_center.scenario_id == second.command_center.scenario_id
    assert len(first.applied_changes) == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"management_reserve": -1.0},
        {"revenue_change_pct": -100.1},
        {"revenue_change_pct": 100.1},
        {"cost_change_pct": -100.1},
        {"cost_change_pct": 100.1},
        {"management_reserve": True},
        {},
    ],
)
def test_invalid_what_if_requests_are_rejected(payload):
    with pytest.raises(ValidationError):
        V2WhatIfRequest(**payload)


def test_unsupported_fields_are_rejected():
    with pytest.raises(ValidationError):
        V2WhatIfRequest(opening_cash=1.0)


def test_receivable_delay_is_explicitly_unsupported_without_date_mutation():
    baseline = get_v2_demo_scenario("healthy")
    before_dates = tuple(
        (event.date, event.due_date, event.expected_cash_date)
        for event in baseline.forecast_input.events
    )

    with pytest.raises(UnsupportedV2WhatIfError, match="timing-overlay"):
        _run(V2WhatIfRequest(receivable_delay_days=14))

    assert tuple(
        (event.date, event.due_date, event.expected_cash_date)
        for event in baseline.forecast_input.events
    ) == before_dates


def test_what_if_tool_records_provenance_and_updates_runtime_evidence():
    baseline = get_v2_demo_scenario("healthy")
    context = V2CopilotContext(
        liquidity_brief=None,
        baseline_scenario=baseline,
        what_if_created_at=CREATED_AT,
        what_if_simulations=200,
    )
    context.record_tool("run_v2_what_if_scenario")
    payload = run_v2_what_if_snapshot(
        context,
        V2WhatIfRequest(management_reserve=75000.0),
    )

    assert payload["available"] is True
    assert payload["baseline_unchanged"] is True
    assert context.what_if_result is not None
    assert context.liquidity_brief is context.what_if_result.command_center.brief
    assert context.tool_calls == ["run_v2_what_if_scenario"]


def test_unsupported_delay_returns_structured_tool_response():
    baseline = get_v2_demo_scenario("healthy")
    context = V2CopilotContext(
        liquidity_brief=None,
        baseline_scenario=baseline,
        what_if_created_at=CREATED_AT,
    )
    payload = run_v2_what_if_snapshot(
        context,
        V2WhatIfRequest(receivable_delay_days=14),
    )

    assert payload["available"] is False
    assert payload["supported"] is False
    assert payload["baseline_unchanged"] is True
    assert context.what_if_result is None

