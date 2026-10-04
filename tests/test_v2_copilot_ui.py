from datetime import datetime, timezone

from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)
from src.ui.v2_copilot import (
    suggested_questions_for_brief,
)


def _brief(scenario_id: str):
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

    return result.brief


def test_stressed_questions_prioritise_action_and_recovery():
    questions = (
        suggested_questions_for_brief(
            _brief(
                "stressed_recoverable"
            )
        )
    )

    labels = tuple(
        label
        for label, _
        in questions
    )

    assert labels == (
        "What should we do first?",
        "Is recovery adequate?",
        "What supports this?",
    )


def test_severe_questions_explain_probabilistic_risk():
    questions = (
        suggested_questions_for_brief(
            _brief(
                "severe_uncertain"
            )
        )
    )

    labels = tuple(
        label
        for label, _
        in questions
    )

    assert labels == (
        "Why is risk high?",
        "How much buffer?",
        "What supports this?",
    )


def test_healthy_questions_do_not_push_recovery_action():
    questions = (
        suggested_questions_for_brief(
            _brief(
                "healthy"
            )
        )
    )

    labels = tuple(
        label
        for label, _
        in questions
    )

    assert labels == (
        "Do we need to act?",
        "Why is this healthy?",
        "What should we monitor?",
    )


def test_safe_ai_markdown_escapes_currency_dollars():
    from src.ui.v2_copilot import (
        _safe_ai_markdown,
    )

    rendered = _safe_ai_markdown(
        "Minimum cash is $43,000 and buffer is $8,741."
    )

    assert rendered == (
        r"Minimum cash is \$43,000 and buffer is \$8,741."
    )


def test_evidence_provenance_matches_actual_scoped_tools():
    from src.ui.v2_copilot import (
        evidence_items_for_tools,
    )

    brief = _brief(
        "severe_uncertain"
    )

    items = evidence_items_for_tools(
        (
            "get_v2_liquidity_position",
            "get_v2_cash_evidence",
        ),
        brief,
    )

    joined = " | ".join(items)

    assert "13-week direct cash forecast" in joined
    assert "Baseline uncertainty simulation" in joined
    assert "Management reserve and risk appetite" in joined
    assert "Forecast evidence coverage" in joined
    assert "Ranked cash drivers" in joined

    assert "Recovery" not in joined
    assert "Monitoring" not in joined
    assert "Cash Action Register" not in joined


def test_recovery_provenance_requires_recovery_tool_call():
    from src.ui.v2_copilot import (
        evidence_items_for_tools,
    )

    brief = _brief(
        "stressed_recoverable"
    )

    without_recovery = evidence_items_for_tools(
        (
            "get_v2_liquidity_position",
        ),
        brief,
    )

    assert not any(
        "Recovery" in item
        for item in without_recovery
    )

    with_recovery = evidence_items_for_tools(
        (
            "get_v2_recovery_evidence",
        ),
        brief,
    )

    assert any(
        "Recovery evaluation" in item
        for item in with_recovery
    )
