from src.ui.v2_agent_trace import (
    agent_tool_display,
    build_agent_execution_steps,
)


def test_agent_trace_maps_verified_tools_to_business_steps():
    steps = build_agent_execution_steps(
        (
            "get_v2_liquidity_position",
            "get_v2_cash_evidence",
        ),
        has_what_if=False,
    )

    titles = [
        title
        for _, title, _ in steps
    ]

    assert titles[0] == (
        "Interpret management request"
    )

    assert "Liquidity position" in titles
    assert "Cash evidence" in titles

    assert titles[-1] == (
        "Ground recommendation"
    )


def test_agent_trace_deduplicates_repeated_tool_calls():
    steps = build_agent_execution_steps(
        (
            "get_v2_liquidity_position",
            "get_v2_liquidity_position",
        ),
        has_what_if=False,
    )

    titles = [
        title
        for _, title, _ in steps
    ]

    assert (
        titles.count(
            "Liquidity position"
        )
        == 1
    )


def test_agent_trace_marks_temporary_what_if_baseline_isolation():
    steps = build_agent_execution_steps(
        (
            "run_v2_what_if_scenario",
        ),
        has_what_if=True,
    )

    titles = [
        title
        for _, title, _ in steps
    ]

    assert "Scenario orchestration" in titles
    assert "Preserve baseline" in titles


def test_agent_tool_display_uses_real_engine_names():
    display = agent_tool_display(
        "get_v2_recovery_evidence"
    )

    assert (
        display.engine
        == "Recovery Engine"
    )

    assert (
        display.label
        == "Recovery validation"
    )
