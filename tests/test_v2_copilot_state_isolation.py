from datetime import datetime, timezone

from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)
from src.ui.v2_copilot import (
    _copilot_signature,
    reset_copilot_state_for_signature,
)


CREATED_AT = datetime(
    2026,
    10,
    4,
    tzinfo=timezone.utc,
)


def _brief(
    scenario_id: str,
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


def test_different_v2_scenarios_have_different_copilot_signatures():
    healthy = _brief(
        "healthy"
    )

    severe = _brief(
        "severe_uncertain"
    )

    assert (
        _copilot_signature(
            healthy
        )
        !=
        _copilot_signature(
            severe
        )
    )


def test_same_brief_signature_preserves_current_response():
    brief = _brief(
        "healthy"
    )

    signature = _copilot_signature(
        brief
    )

    state = {
        "riskpilot_v2_ai_signature":
            signature,
        "riskpilot_v2_ai_question":
            "Do we need to act?",
        "riskpilot_v2_ai_answer":
            "Continue monitoring.",
        "riskpilot_v2_ai_tools": (
            "get_v2_liquidity_position",
        ),
        "riskpilot_v2_ai_asked_question":
            "Do we need to act?",
    }

    changed = (
        reset_copilot_state_for_signature(
            state,
            signature,
        )
    )

    assert changed is False

    assert (
        state[
            "riskpilot_v2_ai_answer"
        ]
        == "Continue monitoring."
    )

    assert (
        state[
            "riskpilot_v2_ai_question"
        ]
        == "Do we need to act?"
    )

    assert (
        state[
            "riskpilot_v2_ai_tools"
        ]
        == (
            "get_v2_liquidity_position",
        )
    )


def test_switching_scenario_clears_stale_ai_response_and_provenance():
    healthy = _brief(
        "healthy"
    )

    severe = _brief(
        "severe_uncertain"
    )

    state = {
        "riskpilot_v2_ai_signature":
            _copilot_signature(
                healthy
            ),
        "riskpilot_v2_ai_question":
            "Do we need to act?",
        "riskpilot_v2_ai_answer":
            "Continue monitoring.",
        "riskpilot_v2_ai_tools": (
            "get_v2_actions_monitoring",
        ),
        "riskpilot_v2_ai_asked_question":
            "Do we need to act?",
        "unrelated_application_state":
            "must survive",
    }

    changed = (
        reset_copilot_state_for_signature(
            state,
            _copilot_signature(
                severe
            ),
        )
    )

    assert changed is True

    assert (
        state[
            "riskpilot_v2_ai_signature"
        ]
        ==
        _copilot_signature(
            severe
        )
    )

    assert (
        state[
            "riskpilot_v2_ai_question"
        ]
        == ""
    )

    assert (
        "riskpilot_v2_ai_answer"
        not in state
    )

    assert (
        "riskpilot_v2_ai_tools"
        not in state
    )

    assert (
        "riskpilot_v2_ai_asked_question"
        not in state
    )

    assert (
        state[
            "unrelated_application_state"
        ]
        == "must survive"
    )


def test_switching_from_stressed_to_healthy_also_clears_state():
    stressed = _brief(
        "stressed_recoverable"
    )

    healthy = _brief(
        "healthy"
    )

    state = {
        "riskpilot_v2_ai_signature":
            _copilot_signature(
                stressed
            ),
        "riskpilot_v2_ai_question":
            "Is recovery adequate?",
        "riskpilot_v2_ai_answer":
            "Recovery is adequate.",
        "riskpilot_v2_ai_tools": (
            "get_v2_recovery_evidence",
        ),
        "riskpilot_v2_ai_asked_question":
            "Is recovery adequate?",
    }

    reset_copilot_state_for_signature(
        state,
        _copilot_signature(
            healthy
        ),
    )

    assert (
        state[
            "riskpilot_v2_ai_question"
        ]
        == ""
    )

    assert (
        "riskpilot_v2_ai_answer"
        not in state
    )

    assert (
        "riskpilot_v2_ai_tools"
        not in state
    )

    assert (
        "riskpilot_v2_ai_asked_question"
        not in state
    )
