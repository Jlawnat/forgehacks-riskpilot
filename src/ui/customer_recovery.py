from __future__ import annotations

from datetime import timedelta

import streamlit as st

from src.core.recovery_constraints import (
    CostReductionConstraint,
    ExternalLiquidityConstraint,
    ReceivableAccelerationConstraint,
    RecoveryConstraintSet,
    RevenueImprovementConstraint,
)
from src.core.recovery_engine import (
    RecoveryPlan,
)
from src.demo.v2_scenarios import (
    V2DemoScenario,
)


def _compatible_event_ids(
    scenario: V2DemoScenario,
    *,
    source_type: str,
    direction: str,
) -> tuple[str, ...]:
    return tuple(
        event.event_id
        for event in (
            scenario
            .forecast_input
            .events
        )
        if (
            event.status
            == "ACTIVE"
            and event.source_type
            == source_type
            and event.direction
            == direction
        )
    )


def render_customer_recovery_controls(
    scenario: V2DemoScenario,
) -> V2DemoScenario:
    start = (
        scenario
        .forecast_input
        .start_date
    )

    modelled_inflows = (
        _compatible_event_ids(
            scenario,
            source_type="MODELLED",
            direction="INFLOW",
        )
    )

    modelled_outflows = (
        _compatible_event_ids(
            scenario,
            source_type="MODELLED",
            direction="OUTFLOW",
        )
    )

    committed_inflows = (
        _compatible_event_ids(
            scenario,
            source_type="COMMITTED",
            direction="INFLOW",
        )
    )

    with st.expander(
        "Management recovery plan",
        expanded=False,
    ):
        st.caption(
            "Test executable management actions "
            "against the same 13-week cash forecast. "
            "RiskPilot only applies operating levers "
            "to explicitly selected eligible events."
        )

        recovery_enabled = st.toggle(
            "Evaluate a recovery plan",
            value=False,
            key=(
                "riskpilot_customer_"
                "recovery_enabled"
            ),
        )

        if not recovery_enabled:
            return scenario.model_copy(
                update={
                    "recovery_constraints": None,
                    "recovery_plan": None,
                }
            )

        available_from = st.date_input(
            "Actions available from",
            value=start,
            min_value=start,
            max_value=(
                start
                + timedelta(
                    days=90
                )
            ),
            key=(
                "riskpilot_customer_"
                "recovery_available"
            ),
        )

        st.markdown(
            "##### Operating levers"
        )

        c1, c2 = st.columns(2)

        with c1:
            revenue_max = st.number_input(
                "Maximum revenue improvement (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
                key=(
                    "riskpilot_recovery_"
                    "revenue_max"
                ),
                disabled=(
                    not modelled_inflows
                ),
            )

            revenue_plan = st.number_input(
                "Planned revenue improvement (%)",
                min_value=0.0,
                max_value=float(
                    max(
                        revenue_max,
                        0.0,
                    )
                ),
                value=0.0,
                step=1.0,
                key=(
                    "riskpilot_recovery_"
                    "revenue_plan"
                ),
                disabled=(
                    not modelled_inflows
                    or revenue_max <= 0
                ),
            )

            revenue_ids = (
                st.multiselect(
                    "Eligible modelled inflows",
                    list(
                        modelled_inflows
                    ),
                    default=list(
                        modelled_inflows
                    ),
                    key=(
                        "riskpilot_recovery_"
                        "revenue_ids"
                    ),
                    disabled=(
                        not modelled_inflows
                    ),
                )
            )

        with c2:
            cost_max = st.number_input(
                "Maximum cost reduction (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=1.0,
                key=(
                    "riskpilot_recovery_"
                    "cost_max"
                ),
                disabled=(
                    not modelled_outflows
                ),
            )

            cost_plan = st.number_input(
                "Planned cost reduction (%)",
                min_value=0.0,
                max_value=float(
                    max(
                        cost_max,
                        0.0,
                    )
                ),
                value=0.0,
                step=1.0,
                key=(
                    "riskpilot_recovery_"
                    "cost_plan"
                ),
                disabled=(
                    not modelled_outflows
                    or cost_max <= 0
                ),
            )

            cost_ids = st.multiselect(
                "Eligible modelled outflows",
                list(
                    modelled_outflows
                ),
                default=list(
                    modelled_outflows
                ),
                key=(
                    "riskpilot_recovery_"
                    "cost_ids"
                ),
                disabled=(
                    not modelled_outflows
                ),
            )

        st.markdown(
            "##### Liquidity & collections"
        )

        c3, c4 = st.columns(2)

        with c3:
            acceleration_max = (
                st.number_input(
                    "Maximum receivable acceleration (days)",
                    min_value=0,
                    max_value=90,
                    value=0,
                    step=1,
                    key=(
                        "riskpilot_recovery_"
                        "acceleration_max"
                    ),
                    disabled=(
                        not committed_inflows
                    ),
                )
            )

            acceleration_plan = (
                st.number_input(
                    "Planned receivable acceleration (days)",
                    min_value=0,
                    max_value=int(
                        max(
                            acceleration_max,
                            0,
                        )
                    ),
                    value=0,
                    step=1,
                    key=(
                        "riskpilot_recovery_"
                        "acceleration_plan"
                    ),
                    disabled=(
                        not committed_inflows
                        or (
                            acceleration_max
                            <= 0
                        )
                    ),
                )
            )

            receivable_ids = (
                st.multiselect(
                    "Eligible committed receipts",
                    list(
                        committed_inflows
                    ),
                    default=list(
                        committed_inflows
                    ),
                    key=(
                        "riskpilot_recovery_"
                        "receivable_ids"
                    ),
                    disabled=(
                        not committed_inflows
                    ),
                )
            )

        with c4:
            external_max = (
                st.number_input(
                    "Maximum external liquidity",
                    min_value=0.0,
                    value=0.0,
                    step=5000.0,
                    key=(
                        "riskpilot_recovery_"
                        "external_max"
                    ),
                )
            )

            external_plan = (
                st.number_input(
                    "Planned external liquidity",
                    min_value=0.0,
                    max_value=float(
                        max(
                            external_max,
                            0.0,
                        )
                    ),
                    value=0.0,
                    step=5000.0,
                    key=(
                        "riskpilot_recovery_"
                        "external_plan"
                    ),
                    disabled=(
                        external_max <= 0
                    ),
                )
            )

        st.caption(
            "Recovery controls do not rewrite "
            "the baseline evidence. They create "
            "a separate management-action overlay."
        )

    constraints = (
        RecoveryConstraintSet(
            revenue_improvement=(
                RevenueImprovementConstraint(
                    enabled=(
                        revenue_max > 0
                    ),
                    max_improvement_pct=float(
                        revenue_max
                    ),
                    available_from=(
                        available_from
                    ),
                    eligible_event_ids=tuple(
                        revenue_ids
                    ),
                )
            ),
            cost_reduction=(
                CostReductionConstraint(
                    enabled=(
                        cost_max > 0
                    ),
                    max_reduction_pct=float(
                        cost_max
                    ),
                    available_from=(
                        available_from
                    ),
                    eligible_event_ids=tuple(
                        cost_ids
                    ),
                )
            ),
            receivable_acceleration=(
                ReceivableAccelerationConstraint(
                    enabled=(
                        acceleration_max
                        > 0
                    ),
                    max_acceleration_days=int(
                        acceleration_max
                    ),
                    available_from=(
                        available_from
                    ),
                    eligible_event_ids=tuple(
                        receivable_ids
                    ),
                )
            ),
            external_liquidity=(
                ExternalLiquidityConstraint(
                    enabled=(
                        external_max > 0
                    ),
                    max_amount=float(
                        external_max
                    ),
                    available_from=(
                        available_from
                    ),
                )
            ),
        )
    )

    plan = RecoveryPlan(
        revenue_improvement_pct=float(
            revenue_plan
        ),
        cost_reduction_pct=float(
            cost_plan
        ),
        receivable_acceleration_days=int(
            acceleration_plan
        ),
        external_liquidity=float(
            external_plan
        ),
    )

    return scenario.model_copy(
        update={
            "recovery_constraints": (
                constraints
            ),
            "recovery_plan": plan,
        }
    )
