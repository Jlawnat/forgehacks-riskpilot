"""Clearly labelled synthetic scenario for premium product walkthroughs.

This is a fixture made from existing V2 demo cash flows, not public filings,
customer evidence, or a change to any financial engine.
"""
from functools import lru_cache

from src.core.recovery_constraints import (
    CostReductionConstraint, ExternalLiquidityConstraint,
    ReceivableAccelerationConstraint, RecoveryConstraintSet,
    RevenueImprovementConstraint,
)
from src.core.recovery_engine import RecoveryPlan
from src.core.cash_events import CashEvent
from src.demo.v2_scenarios import V2DemoScenario, get_v2_demo_scenario, get_v2_demo_scenarios

DEMO_ID = "harborview_synthetic"


@lru_cache(maxsize=1)
def synthetic_management_demo() -> V2DemoScenario:
    original = get_v2_demo_scenario("stressed_recoverable")
    raw_cash = original.forecast_input
    events = tuple(CashEvent.model_validate({
        **e.model_dump(mode="python"),
        "event_id": e.event_id.replace("stressed-", "harborview-"),
        "source_reference": (e.source_reference or "").replace("stressed-", "harborview-") or None,
    }) for e in raw_cash.events)
    cash = raw_cash.model_copy(update={"events": events})
    start = cash.start_date
    modelled_receipts = tuple(e.event_id for e in events if
        e.status == "ACTIVE" and e.source_type == "MODELLED"
        and e.direction == "INFLOW" and e.category == "residual sales receipts")
    modelled_costs = tuple(e.event_id for e in events if
        e.status == "ACTIVE" and e.source_type == "MODELLED"
        and e.direction == "OUTFLOW" and e.category == "variable operating costs")
    contracted_receipts = tuple(e.event_id for e in events if
        e.status == "ACTIVE" and e.source_type == "COMMITTED"
        and e.direction == "INFLOW" and e.category == "customer receipts")

    constraints = RecoveryConstraintSet(
        revenue_improvement=RevenueImprovementConstraint(
            enabled=True, max_improvement_pct=30,
            available_from=start, eligible_event_ids=modelled_receipts),
        cost_reduction=CostReductionConstraint(
            enabled=True, max_reduction_pct=25,
            available_from=start, eligible_event_ids=modelled_costs),
        receivable_acceleration=ReceivableAccelerationConstraint(
            enabled=True, max_acceleration_days=7,
            available_from=start, eligible_event_ids=contracted_receipts),
        external_liquidity=ExternalLiquidityConstraint(
            enabled=True, max_amount=18000, available_from=start),
    )
    return V2DemoScenario.model_validate({
        **original.model_dump(mode="python"),
        "scenario_id": DEMO_ID,
        "name": "Harborview Components (Synthetic Demo)",
        "description": (
            "Fictional 13-week manufacturing cash scenario with committed invoices, "
            "modelled sales and costs, moderate simulated liquidity risk, and "
            "explicitly scoped recovery interventions. Not SEC or customer data."
        ),
        "management_reserve": 42500.0,
        "forecast_input": {**cash.model_dump(mode="python"), "opening_cash": 72000.0},
        "recovery_constraints": constraints.model_dump(mode="python"),
        "recovery_plan": RecoveryPlan(
            revenue_improvement_pct=10, cost_reduction_pct=10,
            external_liquidity=5000).model_dump(mode="python"),
    })


def available_premium_scenarios():
    return (synthetic_management_demo(), *get_v2_demo_scenarios())


def resolve_premium_scenario(scenario_id):
    if scenario_id == DEMO_ID:
        return synthetic_management_demo()
    return get_v2_demo_scenario(scenario_id)
