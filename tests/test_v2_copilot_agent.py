from src.ai.v2_copilot import (
    V2_COPILOT_INSTRUCTIONS,
    V2CopilotResponse,
    build_v2_copilot,
)


def test_v2_copilot_instructions_enforce_grounding():
    instructions = V2_COPILOT_INSTRUCTIONS

    assert "financial engines calculate" in instructions
    assert "smallest sufficient set" in instructions
    assert "legacy monthly" in instructions
    assert "Evidence coverage is not a probability" in instructions
    assert "recovery-plan" in instructions
    assert "evaluation only" in instructions
    assert "private reasoning or chain-of-thought" in instructions


def test_v2_copilot_agent_exposes_only_scoped_v2_tools():
    agent = build_v2_copilot()

    assert agent.name == (
        "RiskPilot AI Decision Copilot"
    )

    tool_names = {
        tool.name
        for tool in agent.tools
    }

    assert tool_names == {
        "get_v2_liquidity_position",
        "get_v2_cash_evidence",
        "get_v2_recovery_evidence",
        "get_v2_actions_monitoring",
        "run_v2_what_if_scenario",
    }

    assert (
        "get_v2_liquidity_decision_brief"
        not in tool_names
    )


def test_v2_copilot_routes_general_risk_question_narrowly():
    instructions = V2_COPILOT_INSTRUCTIONS

    assert (
        'For "Why is risk high?"'
        in instructions
    )
    assert (
        "Do NOT call recovery or actions/monitoring tools"
        in instructions
    )
    assert (
        "secondary simulation statistics"
        in instructions
    )


def test_v2_copilot_response_preserves_tool_provenance():
    response = V2CopilotResponse(
        answer="Liquidity risk exceeds appetite.",
        tools_used=(
            "get_v2_liquidity_position",
            "get_v2_cash_evidence",
        ),
    )

    assert response.tools_used == (
        "get_v2_liquidity_position",
        "get_v2_cash_evidence",
    )


def test_v2_copilot_routes_healthy_action_question_without_recovery():
    instructions = V2_COPILOT_INSTRUCTIONS

    assert (
        'For "Do we need to act?"'
        in instructions
    )
    assert (
        "use get_v2_liquidity_position and"
        in instructions
    )
    assert (
        "Do NOT call get_v2_recovery_evidence"
        in instructions
    )
