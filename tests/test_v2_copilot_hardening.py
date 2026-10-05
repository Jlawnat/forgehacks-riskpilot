from src.ai.v2_copilot import (
    V2_COPILOT_INSTRUCTIONS,
    build_v2_copilot,
)


def test_copilot_exposes_only_scoped_v2_evidence_and_what_if_tools():
    agent = build_v2_copilot()

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

    forbidden = {
        "run_stress_test",
        "run_reverse_stress",
        "get_forecast_outlook",
        "get_liquidity_risk",
        "get_recovery_options",
        "validate_recovery_options",
    }

    assert tool_names.isdisjoint(
        forbidden
    )


def test_copilot_forbids_new_financial_calculation():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    )

    required_concepts = (
        "Never calculate",
        "estimate",
        "derive",
        "invent",
    )

    for concept in required_concepts:
        assert concept in instructions


def test_copilot_has_explicit_unsupported_value_boundary():
    instructions = V2_COPILOT_INSTRUCTIONS

    assert (
        "available Copilot tools do not surface evidence"
        in instructions
    )

    assert (
        "RiskPilot has not surfaced that value"
        in instructions
    )

def test_copilot_keeps_legacy_monthly_context_separate():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    )

    assert "legacy monthly" in (
        instructions.lower()
    )

    assert (
        "Never silently combine"
        in instructions
    )


def test_copilot_rejects_advisory_domain_overreach():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    ).lower()

    for domain in (
        "accounting",
        "tax",
        "legal",
        "investment",
    ):
        assert domain in instructions


def test_general_risk_question_does_not_route_to_recovery():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    )

    assert (
        'For "Why is risk high?"'
        in instructions
    )

    assert (
        "Do NOT call recovery or actions/monitoring tools"
        in instructions
    )


def test_healthy_action_question_does_not_route_to_recovery():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    )

    assert (
        'For "Do we need to act?"'
        in instructions
    )

    assert (
        "Do NOT call get_v2_recovery_evidence"
        in instructions
    )


def test_recovery_question_routes_to_recovery_evidence():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    )

    assert (
        'For "Is recovery adequate?"'
        in instructions
    )

    assert (
        "use get_v2_recovery_evidence"
        in instructions
    )


def test_monitoring_question_routes_to_monitoring_evidence():
    instructions = (
        V2_COPILOT_INSTRUCTIONS
    )

    assert (
        'For "What should we monitor?"'
        in instructions
    )

    assert (
        "get_v2_actions_monitoring"
        in instructions
    )
