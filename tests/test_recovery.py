from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data
from src.scenarios.engine import ScenarioInput
from src.scenarios.recovery import build_recovery_plan


def _load_demo():
    raw = load_business_csv(
        "data/demo/fragile_business.csv"
    )
    cleaned, _ = validate_business_data(raw)
    return cleaned


def _stress():
    return ScenarioInput(
        revenue_change=-0.15,
        cost_change=0.10,
        receivable_delay_days=30,
        horizon=3,
    )


def test_recovery_plan_returns_actions():
    plan = build_recovery_plan(
        _load_demo(),
        _stress(),
    )

    assert len(plan.actions) >= 4


def test_revenue_only_is_not_forced_unrealistically():
    plan = build_recovery_plan(
        _load_demo(),
        _stress(),
    )

    action = next(
        x for x in plan.actions
        if x.action == "revenue_recovery"
    )

    assert not action.feasible


def test_cost_only_is_not_forced_unrealistically():
    plan = build_recovery_plan(
        _load_demo(),
        _stress(),
    )

    action = next(
        x for x in plan.actions
        if x.action == "cost_reduction"
    )

    assert not action.feasible


def test_receivables_help_but_do_not_fix_structural_problem():
    plan = build_recovery_plan(
        _load_demo(),
        _stress(),
    )

    action = next(
        x for x in plan.actions
        if x.action == "receivable_acceleration"
    )

    assert not action.feasible
    assert action.resulting_min_cash is not None


def test_severe_scenario_requires_external_liquidity():
    plan = build_recovery_plan(
        _load_demo(),
        _stress(),
    )

    assert not plan.operational_recovery_possible

    action = next(
        x for x in plan.actions
        if x.action == "liquidity_buffer"
    )

    assert action.feasible
    assert action.magnitude is not None
    assert action.magnitude > 0


def test_liquidity_buffer_restores_target():
    plan = build_recovery_plan(
        _load_demo(),
        _stress(),
        target_min_cash=0,
    )

    action = next(
        x for x in plan.actions
        if x.action == "liquidity_buffer"
    )

    assert action.resulting_min_cash is not None
    assert action.resulting_min_cash >= 0
