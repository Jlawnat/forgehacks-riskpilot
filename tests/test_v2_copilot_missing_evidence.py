from datetime import datetime, timezone

from src.ai.v2_context import (
    V2CopilotContext,
)
from src.ai.v2_tools import (
    v2_actions_monitoring_snapshot,
    v2_cash_evidence_snapshot,
    v2_liquidity_position_snapshot,
    v2_recovery_evidence_snapshot,
)
from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)
from src.ui.v2_copilot import (
    evidence_items_for_tools,
    suggested_questions_for_brief,
)


CREATED_AT = datetime(
    2026,
    10,
    4,
    tzinfo=timezone.utc,
)


def _brief(
    scenario_id: str = "healthy",
):
    scenario = get_v2_demo_scenario(
        scenario_id
    )

    result = build_command_center(
        scenario,
        created_at=CREATED_AT,
        simulations=200,
        seed=42,
    )

    return result.brief


def test_all_scoped_snapshots_handle_missing_brief():
    context = V2CopilotContext(
        liquidity_brief=None
    )

    snapshots = (
        v2_liquidity_position_snapshot(
            context
        ),
        v2_cash_evidence_snapshot(
            context
        ),
        v2_recovery_evidence_snapshot(
            context
        ),
        v2_actions_monitoring_snapshot(
            context
        ),
    )

    for snapshot in snapshots:
        assert snapshot["available"] is False
        assert "reason" in snapshot


def test_position_snapshot_handles_missing_uncertainty():
    brief = _brief().model_copy(
        update={
            "uncertainty": None,
        }
    )

    context = V2CopilotContext(
        liquidity_brief=brief
    )

    snapshot = (
        v2_liquidity_position_snapshot(
            context
        )
    )

    assert snapshot["available"] is True
    assert (
        snapshot["baseline_uncertainty"]
        is None
    )

    assert (
        snapshot["position"][
            "management_reserve"
        ]
        == brief.position.management_reserve
    )


def test_cash_evidence_handles_missing_coverage_and_drivers():
    base = _brief()

    position = base.position.model_copy(
        update={
            "evidence_coverage_ratio":
                None,
        }
    )

    brief = base.model_copy(
        update={
            "position": position,
            "cash_drivers": (),
        }
    )

    context = V2CopilotContext(
        liquidity_brief=brief
    )

    snapshot = (
        v2_cash_evidence_snapshot(
            context
        )
    )

    assert snapshot["available"] is True

    assert (
        snapshot[
            "evidence_quality"
        ][
            "evidence_coverage_ratio"
        ]
        is None
    )

    assert snapshot[
        "cash_drivers"
    ] == []


def test_recovery_snapshot_handles_no_recovery_plan():
    brief = _brief().model_copy(
        update={
            "recovery": None,
        }
    )

    context = V2CopilotContext(
        liquidity_brief=brief
    )

    snapshot = (
        v2_recovery_evidence_snapshot(
            context
        )
    )

    assert snapshot["available"] is True
    assert snapshot["recovery"] is None


def test_actions_monitoring_snapshot_handles_no_monitoring():
    brief = _brief().model_copy(
        update={
            "monitoring": None,
        }
    )

    context = V2CopilotContext(
        liquidity_brief=brief
    )

    snapshot = (
        v2_actions_monitoring_snapshot(
            context
        )
    )

    assert snapshot["available"] is True
    assert snapshot["monitoring"] is None

    assert (
        snapshot["actions"][
            "total_actions"
        ]
        == 0
    )


def test_evidence_renderer_handles_missing_optional_sections():
    base = _brief()

    position = base.position.model_copy(
        update={
            "evidence_coverage_ratio":
                None,
        }
    )

    brief = base.model_copy(
        update={
            "position": position,
            "uncertainty": None,
            "recovery": None,
            "cash_drivers": (),
            "monitoring": None,
        }
    )

    items = evidence_items_for_tools(
        (
            "get_v2_liquidity_position",
            "get_v2_cash_evidence",
            "get_v2_recovery_evidence",
            "get_v2_actions_monitoring",
        ),
        brief,
    )

    joined = " | ".join(
        items
    )

    assert (
        "13-week direct cash forecast"
        in joined
    )

    assert (
        "Baseline uncertainty simulation"
        not in joined
    )

    assert (
        "Ranked cash drivers"
        not in joined
    )

    assert (
        "Recovery evidence checked"
        in joined
    )

    assert (
        "Cash Action Register checked"
        in joined
    )

    assert (
        "Monitoring triggers"
        not in joined
    )


def test_suggested_questions_survive_missing_uncertainty():
    brief = _brief().model_copy(
        update={
            "uncertainty": None,
        }
    )

    questions = (
        suggested_questions_for_brief(
            brief
        )
    )

    assert len(questions) == 3

    for label, question in questions:
        assert label
        assert question
