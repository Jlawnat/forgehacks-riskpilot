from src.ai.v2_context import V2CopilotContext


def test_v2_copilot_context_can_represent_missing_brief():
    context = V2CopilotContext(
        liquidity_brief=None
    )

    assert context.liquidity_brief is None
    assert context.tool_calls == []


def test_v2_copilot_context_records_scoped_tools():
    context = V2CopilotContext(
        liquidity_brief=None
    )

    context.record_tool(
        "get_v2_liquidity_position"
    )

    assert context.tool_calls == [
        "get_v2_liquidity_position"
    ]
