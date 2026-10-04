from src.ui.v2_command_center import (
    build_v2_command_center_result,
)


def test_v2_ui_entry_builds_healthy_result():
    result = build_v2_command_center_result(
        "healthy"
    )

    assert result.scenario_id == "healthy"

    assert (
        result.brief.position
        .first_reserve_breach_week
        is None
    )


def test_v2_ui_entry_builds_stressed_result():
    result = build_v2_command_center_result(
        "stressed_recoverable"
    )

    assert (
        result.brief.position
        .first_reserve_breach_week
        is not None
    )


def test_v2_ui_entry_builds_severe_result():
    result = build_v2_command_center_result(
        "severe_uncertain"
    )

    assert (
        result.simulation
        .shortfall_probability
        > 0.10
    )


def test_liquidity_chart_contains_uncertainty_and_reserve():
    from src.ui.v2_command_center import (
        _build_liquidity_figure,
    )

    result = build_v2_command_center_result(
        "severe_uncertain"
    )

    figure = _build_liquidity_figure(
        result
    )

    names = {
        trace.name
        for trace in figure.data
        if trace.name
    }

    assert "Deterministic cash" in names
    assert "Simulated median" in names
    assert "P10–P90 uncertainty" in names
    assert "Management reserve" in names


def test_recovery_chart_contains_recovery_path():
    from src.ui.v2_command_center import (
        _build_liquidity_figure,
    )

    result = build_v2_command_center_result(
        "stressed_recoverable"
    )

    figure = _build_liquidity_figure(
        result
    )

    assert (
        "Recovery plan"
        in {
            trace.name
            for trace in figure.data
            if trace.name
        }
    )


def test_driver_display_hides_internal_event_ids():
    from src.ui.v2_command_center import (
        _driver_display_rows,
    )

    result = build_v2_command_center_result(
        "severe_uncertain"
    )

    rows = _driver_display_rows(
        result
    )

    assert rows
    assert "Cash driver" in rows[0]
    assert "Impact" in rows[0]
    assert "Event" not in rows[0]
    assert "event_id" not in rows[0]


def test_v2_command_center_render_entry_exists():
    from src.ui import v2_command_center

    assert hasattr(
        v2_command_center,
        "render_v2_command_center",
    )

    assert callable(
        v2_command_center
        .render_v2_command_center
    )


def test_v2_workspace_renderer_exists():
    from src.ui import v2_command_center

    assert hasattr(
        v2_command_center,
        "_render_v2_workspace",
    )

    assert callable(
        v2_command_center
        ._render_v2_workspace
    )


def test_severe_insight_uses_engine_values():
    from src.demo.v2_scenarios import (
        get_v2_demo_scenario,
    )
    from src.ui.v2_command_center import (
        _build_riskpilot_insight,
    )

    result = build_v2_command_center_result(
        "severe_uncertain"
    )

    scenario = get_v2_demo_scenario(
        "severe_uncertain"
    )

    title, body = _build_riskpilot_insight(
        result,
        scenario,
    )

    assert "Uncertainty" in title
    assert "58.7%" in body
    assert "10.0%" in body
    assert "$8,741" in body


def test_stressed_insight_explains_recovery_effect():
    from src.demo.v2_scenarios import (
        get_v2_demo_scenario,
    )
    from src.ui.v2_command_center import (
        _build_riskpilot_insight,
    )

    result = build_v2_command_center_result(
        "stressed_recoverable"
    )

    scenario = get_v2_demo_scenario(
        "stressed_recoverable"
    )

    title, body = _build_riskpilot_insight(
        result,
        scenario,
    )

    assert "Recovery" in title
    assert "Week 3" in body
    assert "$10,000" in body
    assert "100.0%" in body
    assert "0.0%" in body


def test_healthy_insight_reports_resilience():
    from src.demo.v2_scenarios import (
        get_v2_demo_scenario,
    )
    from src.ui.v2_command_center import (
        _build_riskpilot_insight,
    )

    result = build_v2_command_center_result(
        "healthy"
    )

    scenario = get_v2_demo_scenario(
        "healthy"
    )

    title, body = _build_riskpilot_insight(
        result,
        scenario,
    )

    assert "resilient" in title
    assert "0.0%" in body
    assert "10.0%" in body
