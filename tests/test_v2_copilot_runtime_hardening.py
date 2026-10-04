from datetime import datetime, timezone
from types import SimpleNamespace

from src.core.command_center import (
    build_command_center,
)
from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)
from src.ui.v2_copilot import (
    classify_v2_copilot_error,
    execute_v2_copilot_request,
)


CREATED_AT = datetime(
    2026,
    10,
    4,
    tzinfo=timezone.utc,
)


def _brief():
    scenario = get_v2_demo_scenario(
        "healthy"
    )

    return build_command_center(
        scenario,
        created_at=CREATED_AT,
        simulations=200,
        seed=42,
    ).brief


def test_successful_copilot_response_preserves_answer_and_tools():
    brief = _brief()

    def runner(context, question):
        assert (
            context.liquidity_brief
            is brief
        )

        assert (
            question
            == "Do we need to act?"
        )

        return SimpleNamespace(
            answer=(
                "No immediate intervention "
                "is required."
            ),
            tools_used=(
                "get_v2_liquidity_position",
                "get_v2_actions_monitoring",
            ),
        )

    result = execute_v2_copilot_request(
        brief,
        "  Do we need to act?  ",
        runner=runner,
    )

    assert result.succeeded is True

    assert result.answer == (
        "No immediate intervention "
        "is required."
    )

    assert result.tools_used == (
        "get_v2_liquidity_position",
        "get_v2_actions_monitoring",
    )

    assert result.error_kind is None


def test_empty_question_never_calls_model_runner():
    brief = _brief()

    called = False

    def runner(context, question):
        nonlocal called
        called = True

        raise AssertionError(
            "Runner must not be called."
        )

    result = execute_v2_copilot_request(
        brief,
        "   ",
        runner=runner,
    )

    assert called is False
    assert result.succeeded is False
    assert (
        result.error_kind
        == "EMPTY_QUESTION"
    )


def test_empty_model_response_is_contained():
    brief = _brief()

    def runner(context, question):
        return SimpleNamespace(
            answer="   ",
            tools_used=(),
        )

    result = execute_v2_copilot_request(
        brief,
        "Why is risk high?",
        runner=runner,
    )

    assert result.succeeded is False

    assert (
        result.error_kind
        == "EMPTY_RESPONSE"
    )

    assert result.answer is None


def test_auth_failure_is_contained():
    brief = _brief()

    def runner(context, question):
        raise RuntimeError(
            "OPENAI_API_KEY authentication failed"
        )

    result = execute_v2_copilot_request(
        brief,
        "Do we need to act?",
        runner=runner,
    )

    assert result.succeeded is False

    assert (
        result.error_kind
        == "CONFIGURATION_OR_AUTH"
    )

    assert (
        "RuntimeError"
        in result.technical_details
    )


def test_timeout_failure_is_contained():
    brief = _brief()

    def runner(context, question):
        raise TimeoutError(
            "Model request timed out"
        )

    result = execute_v2_copilot_request(
        brief,
        "Do we need to act?",
        runner=runner,
    )

    assert result.succeeded is False
    assert result.error_kind == "TIMEOUT"

    assert (
        "TimeoutError"
        in result.technical_details
    )


def test_generic_runtime_failure_is_contained():
    brief = _brief()

    def runner(context, question):
        raise RuntimeError(
            "Unexpected provider failure"
        )

    result = execute_v2_copilot_request(
        brief,
        "Do we need to act?",
        runner=runner,
    )

    assert result.succeeded is False

    assert (
        result.error_kind
        == "RUNTIME_ERROR"
    )


def test_ai_failure_does_not_mutate_financial_brief():
    brief = _brief()

    before = brief.model_dump()

    def runner(context, question):
        raise RuntimeError(
            "Provider unavailable"
        )

    result = execute_v2_copilot_request(
        brief,
        "What should management do?",
        runner=runner,
    )

    after = brief.model_dump()

    assert result.succeeded is False
    assert after == before


def test_error_classifier_distinguishes_failure_classes():
    assert (
        classify_v2_copilot_error(
            RuntimeError(
                "Invalid API key"
            )
        )
        == "CONFIGURATION_OR_AUTH"
    )

    assert (
        classify_v2_copilot_error(
            TimeoutError(
                "Request timed out"
            )
        )
        == "TIMEOUT"
    )

    assert (
        classify_v2_copilot_error(
            RuntimeError(
                "Provider crashed"
            )
        )
        == "RUNTIME_ERROR"
    )

    # Substrings such as "api" in "rapid" and
    # "key" in "monkey" must not look like auth errors.
    assert (
        classify_v2_copilot_error(
            RuntimeError(
                "Rapid provider failure"
            )
        )
        == "RUNTIME_ERROR"
    )

    assert (
        classify_v2_copilot_error(
            RuntimeError(
                "Monkey patch failed"
            )
        )
        == "RUNTIME_ERROR"
    )
