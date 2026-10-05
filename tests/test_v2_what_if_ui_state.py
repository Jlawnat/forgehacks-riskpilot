from src.ui.v2_copilot import (
    V2_WHAT_IF_BASELINE_KEY,
    V2_WHAT_IF_RESULT_KEY,
    reset_v2_what_if_state,
    sync_v2_what_if_state,
)


def _state():
    return {
        V2_WHAT_IF_BASELINE_KEY: "healthy",
        V2_WHAT_IF_RESULT_KEY: object(),
        "riskpilot_v2_ai_answer": "temporary answer",
        "riskpilot_v2_ai_tools": ("run_v2_what_if_scenario",),
        "riskpilot_v2_ai_asked_question": "What if?",
        "riskpilot_v2_ai_signature": "temporary",
        "riskpilot_v2_ai_question": "What if?",
        "unrelated": "preserved",
    }


def test_what_if_state_is_stable_for_same_baseline():
    state = _state()
    assert sync_v2_what_if_state(state, "healthy") is False
    assert V2_WHAT_IF_RESULT_KEY in state


def test_switching_baseline_invalidates_what_if_and_stale_ai_state():
    state = _state()
    assert sync_v2_what_if_state(state, "severe_uncertain") is True
    assert state[V2_WHAT_IF_BASELINE_KEY] == "severe_uncertain"
    assert V2_WHAT_IF_RESULT_KEY not in state
    assert "riskpilot_v2_ai_answer" not in state
    assert "riskpilot_v2_ai_tools" not in state
    assert "riskpilot_v2_ai_signature" not in state
    assert state["riskpilot_v2_ai_question"] == ""
    assert state["unrelated"] == "preserved"


def test_reset_restores_baseline_state_and_clears_provenance():
    state = _state()
    reset_v2_what_if_state(state, "healthy")
    assert state[V2_WHAT_IF_BASELINE_KEY] == "healthy"
    assert V2_WHAT_IF_RESULT_KEY not in state
    assert "riskpilot_v2_ai_answer" not in state
    assert "riskpilot_v2_ai_tools" not in state
    assert state["unrelated"] == "preserved"
