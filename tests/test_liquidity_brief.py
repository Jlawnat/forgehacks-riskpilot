from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.core.cash_actions import (
    CashAction,
    create_cash_action_register,
)
from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.forecast_monitoring import (
    create_forecast_snapshot,
)
from src.core.liquidity_brief import (
    LiquidityDecisionBrief,
    build_liquidity_decision_brief,
)
from src.core.monitoring_triggers import (
    MonitoringTrigger,
    MonitoringTriggerEvaluation,
)
from src.core.recovery_engine import (
    RecoveryEvaluation,
    RecoveryPlan,
)
from src.core.weekly_recovery_validation import (
    WeeklyRecoveryValidationResult,
)


def _event(
    event_id,
    *,
    date_value="2026-10-12",
    amount=10000.0,
    direction="INFLOW",
    source_type="COMMITTED",
    category="customer receipts",
):
    return CashEvent(
        event_id=event_id,
        date=date_value,
        amount=amount,
        direction=direction,
        category=category,
        source_type=source_type,
        status="ACTIVE",
        source_reference=f"source-{event_id}",
    )


def _snapshot(
    *,
    snapshot_id="snapshot-001",
    opening_cash=50000.0,
    reserve=20000.0,
    events=(),
    snapshot_type="BASELINE",
    scenario_name=None,
):
    return create_forecast_snapshot(
        DirectCashForecastInput(
            start_date="2026-10-05",
            opening_cash=opening_cash,
            events=tuple(events),
        ),
        snapshot_id=snapshot_id,
        created_at=datetime(
            2026,
            10,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        management_reserve=reserve,
        snapshot_type=snapshot_type,
        scenario_name=scenario_name,
    )


def _action(
    action_id,
    *,
    status="PLANNED",
    expected=5000.0,
    realised=None,
):
    return CashAction(
        action_id=action_id,
        action_type="COST_REDUCTION",
        action="Reduce discretionary spend",
        owner="CFO",
        target_date=date(
            2026,
            10,
            15,
        ),
        expected_cash_impact=expected,
        status=status,
        originating_recovery_plan_id=(
            "plan-001"
        ),
        realised_cash_benefit=realised,
        realised_benefit_evidence_reference=(
            None
            if realised is None
            else f"bank-{action_id}"
        ),
        created_at=datetime(
            2026,
            10,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )


def _recovery(
    *,
    reserve=20000.0,
    feasible=True,
    external=5000.0,
):
    plan = RecoveryPlan(
        revenue_improvement_pct=5.0,
        cost_reduction_pct=4.0,
        receivable_acceleration_days=7,
        external_liquidity=external,
    )

    return RecoveryEvaluation(
        plan=plan,
        management_reserve=reserve,
        baseline_min_cash=10000.0,
        operating_min_cash=17000.0,
        resulting_min_cash=22000.0,
        resulting_min_cash_week=3,
        resulting_end_cash=40000.0,
        reserve_margin=2000.0,
        remaining_reserve_gap=(
            0.0 if feasible else 1000.0
        ),
        feasible=feasible,
        first_reserve_breach_week=(
            None if feasible else 3
        ),
        external_liquidity_week=2,
        changed_event_ids=(
            "model-001",
        ),
        weekly_closing_cash=tuple(
            22000.0
            for _ in range(13)
        ),
    )


def _validation(
    *,
    reserve=20000.0,
    feasible=True,
    external=5000.0,
):
    return WeeklyRecoveryValidationResult(
        status=(
            "OPERATIONALLY_FEASIBLE_AND_PROBABILISTICALLY_ADEQUATE"
            if feasible
            else "EXECUTABLE_ACTIONS_WITH_FINANCIAL_SHORTFALL"
        ),
        deterministic_feasible=feasible,
        management_reserve=reserve,
        max_acceptable_breach_probability=0.10,
        reserve_breach_probability=0.08,
        within_risk_appetite=True,
        probability_excess=0.0,
        median_min_cash=25000.0,
        p10_min_cash=21000.0,
        median_end_cash=42000.0,
        external_liquidity_week=2,
        external_liquidity_already_in_plan=external,
        additional_upfront_buffer_at_confidence=3000.0,
        risk_adjusted_breach_probability=0.05,
        risk_adjusted_within_risk_appetite=True,
        simulations=5000,
        limitations=(
            "Small uncertainty evidence sample.",
        ),
    )


def _created_at():
    return datetime(
        2026,
        10,
        4,
        9,
        30,
        tzinfo=timezone.utc,
    )


def test_position_uses_snapshot_metrics():
    snapshot = _snapshot(
        events=(
            _event(
                "receipt-001",
                amount=10000.0,
            ),
        )
    )

    brief = build_liquidity_decision_brief(
        snapshot,
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
    )

    assert brief.position.current_cash == 50000.0
    assert (
        brief.position.management_reserve
        == 20000.0
    )
    assert (
        brief.position.closing_cash_13_week
        == 60000.0
    )


def test_cash_drivers_are_ranked_by_included_amount():
    snapshot = _snapshot(
        events=(
            _event(
                "small",
                amount=5000.0,
            ),
            _event(
                "large",
                amount=20000.0,
                direction="OUTFLOW",
                category="payroll",
            ),
        )
    )

    brief = build_liquidity_decision_brief(
        snapshot,
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
    )

    assert [
        driver.event_id
        for driver in brief.cash_drivers
    ] == [
        "large",
        "small",
    ]


def test_cash_driver_preserves_category_and_sign():
    snapshot = _snapshot(
        events=(
            _event(
                "payroll-001",
                amount=12000.0,
                direction="OUTFLOW",
                category="payroll",
            ),
        )
    )

    brief = build_liquidity_decision_brief(
        snapshot,
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
    )

    driver = brief.cash_drivers[0]

    assert driver.category == "payroll"
    assert driver.signed_cash_effect == -12000.0


def test_cash_driver_limit_is_respected():
    snapshot = _snapshot(
        events=tuple(
            _event(
                f"event-{index}",
                amount=float(
                    1000 + index
                ),
            )
            for index in range(5)
        )
    )

    brief = build_liquidity_decision_brief(
        snapshot,
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
        max_cash_drivers=3,
    )

    assert len(brief.cash_drivers) == 3


@pytest.mark.parametrize(
    "value",
    [
        0,
        51,
        True,
    ],
)
def test_invalid_cash_driver_limit_is_rejected(
    value,
):
    with pytest.raises(ValueError):
        build_liquidity_decision_brief(
            _snapshot(),
            create_cash_action_register(()),
            brief_id="brief-001",
            created_at=_created_at(),
            max_cash_drivers=value,
        )


def test_action_summary_separates_expected_and_realised():
    register = create_cash_action_register(
        (
            _action(
                "planned",
                status="PLANNED",
                expected=5000.0,
            ),
            _action(
                "progress",
                status="IN_PROGRESS",
                expected=3000.0,
            ),
            _action(
                "complete",
                status="COMPLETED",
                expected=4000.0,
                realised=3500.0,
            ),
        )
    )

    brief = build_liquidity_decision_brief(
        _snapshot(),
        register,
        brief_id="brief-001",
        created_at=_created_at(),
    )

    assert brief.actions.total_actions == 3
    assert brief.actions.planned_actions == 1
    assert brief.actions.in_progress_actions == 1
    assert brief.actions.completed_actions == 1
    assert (
        brief.actions.open_expected_cash_impact
        == 8000.0
    )
    assert (
        brief.actions
        .evidenced_realised_cash_benefit
        == 3500.0
    )


def test_monitoring_summary_preserves_active_triggers():
    snapshot = _snapshot()

    monitoring = MonitoringTriggerEvaluation(
        as_of_date=date(
            2026,
            10,
            5,
        ),
        snapshot_id=snapshot.snapshot_id,
        triggers=(
            MonitoringTrigger(
                trigger_id="risk",
                trigger_type="RISK_ABOVE_APPETITE",
                severity="CRITICAL",
                message="Risk exceeds appetite.",
            ),
            MonitoringTrigger(
                trigger_id="action",
                trigger_type="MISSED_ACTION",
                severity="WARNING",
                message="Action is overdue.",
            ),
        ),
    )

    brief = build_liquidity_decision_brief(
        snapshot,
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
        monitoring_evaluation=monitoring,
    )

    assert (
        brief.monitoring.active_trigger_count
        == 2
    )
    assert (
        brief.monitoring.critical_trigger_count
        == 1
    )
    assert (
        brief.monitoring.warning_trigger_count
        == 1
    )


def test_deterministic_recovery_is_reported_without_probability():
    brief = build_liquidity_decision_brief(
        _snapshot(),
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
        recovery_evaluation=_recovery(),
    )

    assert brief.recovery is not None
    assert brief.recovery.deterministic_feasible
    assert (
        brief.recovery.reserve_breach_probability
        is None
    )
    assert brief.recovery.simulations is None


def test_probabilistic_recovery_is_reported():
    brief = build_liquidity_decision_brief(
        _snapshot(),
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
        recovery_evaluation=_recovery(),
        recovery_validation=_validation(),
    )

    assert (
        brief.recovery.reserve_breach_probability
        == 0.08
    )
    assert (
        brief.recovery
        .maximum_acceptable_breach_probability
        == 0.10
    )
    assert (
        brief.recovery
        .additional_upfront_buffer_at_confidence
        == 3000.0
    )
    assert brief.recovery.simulations == 5000

    assert brief.limitations == (
        "Small uncertainty evidence sample.",
    )


def test_validation_requires_recovery_evaluation():
    with pytest.raises(
        ValueError,
        match="requires",
    ):
        build_liquidity_decision_brief(
            _snapshot(),
            create_cash_action_register(()),
            brief_id="brief-001",
            created_at=_created_at(),
            recovery_validation=_validation(),
        )


def test_recovery_reserve_must_match_snapshot():
    with pytest.raises(
        ValueError,
        match="management reserve",
    ):
        build_liquidity_decision_brief(
            _snapshot(
                reserve=20000.0,
            ),
            create_cash_action_register(()),
            brief_id="brief-001",
            created_at=_created_at(),
            recovery_evaluation=_recovery(
                reserve=25000.0,
            ),
        )


def test_validation_plan_must_match_recovery():
    with pytest.raises(
        ValueError,
        match="external liquidity",
    ):
        build_liquidity_decision_brief(
            _snapshot(),
            create_cash_action_register(()),
            brief_id="brief-001",
            created_at=_created_at(),
            recovery_evaluation=_recovery(
                external=5000.0,
            ),
            recovery_validation=_validation(
                external=6000.0,
            ),
        )


def test_monitoring_snapshot_must_match():
    with pytest.raises(
        ValueError,
        match="supplied forecast snapshot",
    ):
        build_liquidity_decision_brief(
            _snapshot(
                snapshot_id="snapshot-001",
            ),
            create_cash_action_register(()),
            brief_id="brief-001",
            created_at=_created_at(),
            monitoring_evaluation=(
                MonitoringTriggerEvaluation(
                    as_of_date=date(
                        2026,
                        10,
                        5,
                    ),
                    snapshot_id="different",
                    triggers=(),
                )
            ),
        )


def test_scenario_identity_is_preserved():
    brief = build_liquidity_decision_brief(
        _snapshot(
            snapshot_type="SCENARIO",
            scenario_name="Customer delay",
        ),
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
    )

    assert brief.snapshot_type == "SCENARIO"
    assert brief.scenario_name == "Customer delay"


def test_created_at_must_be_timezone_aware():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        build_liquidity_decision_brief(
            _snapshot(),
            create_cash_action_register(()),
            brief_id="brief-001",
            created_at=datetime(
                2026,
                10,
                4,
                9,
                30,
            ),
        )


def test_brief_is_immutable():
    brief = build_liquidity_decision_brief(
        _snapshot(),
        create_cash_action_register(()),
        brief_id="brief-001",
        created_at=_created_at(),
    )

    with pytest.raises(ValidationError):
        brief.brief_id = "changed"


def test_brief_round_trips_deterministically():
    brief = build_liquidity_decision_brief(
        _snapshot(
            events=(
                _event("receipt-001"),
            )
        ),
        create_cash_action_register(
            (
                _action("action-001"),
            )
        ),
        brief_id="brief-001",
        created_at=_created_at(),
        recovery_evaluation=_recovery(),
        recovery_validation=_validation(),
    )

    payload = brief.model_dump(
        mode="json"
    )

    restored = (
        LiquidityDecisionBrief
        .model_validate(payload)
    )

    assert restored == brief
    assert (
        restored.model_dump(mode="json")
        == payload
    )
