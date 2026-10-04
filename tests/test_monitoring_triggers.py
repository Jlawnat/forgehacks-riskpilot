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
    ActualCashObservation,
    compare_forecast_snapshots,
    compare_forecast_to_actual,
    create_forecast_snapshot,
)
from src.core.monitoring_triggers import (
    MonitoringTriggerEvaluation,
    MonitoringTriggerPolicy,
    evaluate_monitoring_triggers,
)


def _event(
    event_id,
    *,
    date_value="2026-10-05",
    amount=10000.0,
    direction="INFLOW",
    source_type="COMMITTED",
):
    return CashEvent(
        event_id=event_id,
        date=date_value,
        amount=amount,
        direction=direction,
        category="cash",
        source_type=source_type,
        status="ACTIVE",
        source_reference=f"source-{event_id}",
    )


def _snapshot(
    snapshot_id="snapshot-001",
    *,
    opening_cash=50000.0,
    events=(),
    reserve=20000.0,
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
    )


def _action(
    action_id="action-001",
    *,
    target_date=date(2026, 10, 10),
    status="PLANNED",
):
    return CashAction(
        action_id=action_id,
        action_type="COST_REDUCTION",
        action="Reduce discretionary spending",
        owner="CFO",
        target_date=target_date,
        expected_cash_impact=5000.0,
        status=status,
        originating_recovery_plan_id="plan-001",
        created_at=datetime(
            2026,
            10,
            4,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )


def _policy(
    threshold=10000.0,
):
    return MonitoringTriggerPolicy(
        major_forecast_variance_threshold=(
            threshold
        )
    )


def _types(result):
    return [
        trigger.trigger_type
        for trigger in result.triggers
    ]


def test_projected_reserve_breach_triggers():
    snapshot = _snapshot(
        opening_cash=10000.0,
        reserve=5000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
    )

    assert (
        "PROJECTED_RESERVE_BREACH"
        in _types(result)
    )

    assert result.has_critical_triggers


def test_no_reserve_breach_no_trigger():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
    )

    assert (
        "PROJECTED_RESERVE_BREACH"
        not in _types(result)
    )


def test_risk_above_appetite_triggers():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
        breach_probability=0.30,
        maximum_acceptable_breach_probability=0.10,
    )

    assert (
        "RISK_ABOVE_APPETITE"
        in _types(result)
    )


def test_risk_equal_to_appetite_does_not_trigger():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
        breach_probability=0.10,
        maximum_acceptable_breach_probability=0.10,
    )

    assert (
        "RISK_ABOVE_APPETITE"
        not in _types(result)
    )


def test_probability_inputs_must_be_paired():
    with pytest.raises(
        ValueError,
        match="provided together",
    ):
        evaluate_monitoring_triggers(
            _snapshot(),
            create_cash_action_register(()),
            as_of_date=date(2026, 10, 5),
            policy=_policy(),
            breach_probability=0.20,
        )


def test_missed_open_action_triggers():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(
            (
                _action(
                    target_date=date(
                        2026,
                        10,
                        4,
                    )
                ),
            )
        ),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
    )

    assert "MISSED_ACTION" in _types(result)


def test_completed_action_does_not_trigger():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(
            (
                _action(
                    target_date=date(
                        2026,
                        10,
                        1,
                    ),
                    status="COMPLETED",
                ),
            )
        ),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
    )

    assert "MISSED_ACTION" not in _types(result)


def test_action_due_today_is_not_missed():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(
            (
                _action(
                    target_date=date(
                        2026,
                        10,
                        5,
                    )
                ),
            )
        ),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
    )

    assert "MISSED_ACTION" not in _types(result)


def test_major_forecast_deterioration_triggers():
    prior = _snapshot(
        "prior",
        opening_cash=50000.0,
    )

    current = _snapshot(
        "current",
        opening_cash=35000.0,
    )

    comparison = compare_forecast_snapshots(
        prior,
        current,
    )

    result = evaluate_monitoring_triggers(
        current,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(
            threshold=10000.0
        ),
        forecast_comparison=comparison,
    )

    assert (
        "MAJOR_FORECAST_VARIANCE"
        in _types(result)
    )


def test_forecast_change_below_threshold_does_not_trigger():
    prior = _snapshot(
        "prior",
        opening_cash=50000.0,
    )

    current = _snapshot(
        "current",
        opening_cash=45001.0,
    )

    comparison = compare_forecast_snapshots(
        prior,
        current,
    )

    result = evaluate_monitoring_triggers(
        current,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(
            threshold=5000.0
        ),
        forecast_comparison=comparison,
    )

    assert (
        "MAJOR_FORECAST_VARIANCE"
        not in _types(result)
    )


def test_missing_committed_receipt_triggers_delay():
    snapshot = _snapshot(
        events=(
            _event("invoice-001"),
        )
    )

    actual_comparison = (
        compare_forecast_to_actual(
            snapshot,
            (),
            through_date=date(
                2026,
                10,
                11,
            ),
        )
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 11),
        policy=_policy(),
        actual_comparison=actual_comparison,
    )

    assert (
        "DELAYED_COMMITTED_RECEIPT"
        in _types(result)
    )


def test_late_committed_receipt_triggers_delay():
    snapshot = _snapshot(
        events=(
            _event(
                "invoice-001",
                date_value="2026-10-05",
            ),
        )
    )

    actual_comparison = (
        compare_forecast_to_actual(
            snapshot,
            (
                ActualCashObservation(
                    actual_id="actual-001",
                    date="2026-10-08",
                    amount=10000.0,
                    direction="INFLOW",
                    source_reference="bank-001",
                    forecast_event_id=(
                        "invoice-001"
                    ),
                ),
            ),
            through_date=date(
                2026,
                10,
                11,
            ),
        )
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 11),
        policy=_policy(),
        actual_comparison=actual_comparison,
    )

    assert (
        "DELAYED_COMMITTED_RECEIPT"
        in _types(result)
    )


def test_early_receipt_does_not_trigger_delay():
    snapshot = _snapshot(
        events=(
            _event(
                "invoice-001",
                date_value="2026-10-08",
            ),
        )
    )

    actual_comparison = (
        compare_forecast_to_actual(
            snapshot,
            (
                ActualCashObservation(
                    actual_id="actual-001",
                    date="2026-10-05",
                    amount=10000.0,
                    direction="INFLOW",
                    source_reference="bank-001",
                    forecast_event_id=(
                        "invoice-001"
                    ),
                ),
            ),
            through_date=date(
                2026,
                10,
                11,
            ),
        )
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 11),
        policy=_policy(),
        actual_comparison=actual_comparison,
    )

    assert (
        "DELAYED_COMMITTED_RECEIPT"
        not in _types(result)
    )


def test_missing_modelled_inflow_is_not_called_delayed_commitment():
    snapshot = _snapshot(
        events=(
            _event(
                "model-001",
                source_type="MODELLED",
            ),
        )
    )

    actual_comparison = (
        compare_forecast_to_actual(
            snapshot,
            (),
            through_date=date(
                2026,
                10,
                11,
            ),
        )
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 11),
        policy=_policy(),
        actual_comparison=actual_comparison,
    )

    assert (
        "DELAYED_COMMITTED_RECEIPT"
        not in _types(result)
    )


def test_lost_recovery_feasibility_triggers():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
        prior_recovery_feasible=True,
        current_recovery_feasible=False,
    )

    assert (
        "LOST_RECOVERY_FEASIBILITY"
        in _types(result)
    )


def test_existing_infeasibility_is_not_called_lost():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
        prior_recovery_feasible=False,
        current_recovery_feasible=False,
    )

    assert (
        "LOST_RECOVERY_FEASIBILITY"
        not in _types(result)
    )


@pytest.mark.parametrize(
    "value",
    [
        -0.1,
        1.1,
        float("inf"),
        True,
    ],
)
def test_invalid_probability_is_rejected(
    value,
):
    with pytest.raises(ValueError):
        evaluate_monitoring_triggers(
            _snapshot(),
            create_cash_action_register(()),
            as_of_date=date(2026, 10, 5),
            policy=_policy(),
            breach_probability=value,
            maximum_acceptable_breach_probability=0.1,
        )


def test_policy_rejects_invalid_threshold():
    with pytest.raises(ValidationError):
        _policy(
            threshold=-1.0
        )


def test_evaluation_round_trips():
    result = evaluate_monitoring_triggers(
        _snapshot(),
        create_cash_action_register(()),
        as_of_date=date(2026, 10, 5),
        policy=_policy(),
    )

    payload = result.model_dump(
        mode="json"
    )

    restored = (
        MonitoringTriggerEvaluation
        .model_validate(payload)
    )

    assert restored == result


def test_forecast_comparison_must_match_current_snapshot():
    prior = _snapshot(
        "prior",
        opening_cash=50000.0,
    )

    other_current = _snapshot(
        "other-current",
        opening_cash=40000.0,
    )

    comparison = compare_forecast_snapshots(
        prior,
        other_current,
    )

    supplied_snapshot = _snapshot(
        "supplied-current",
        opening_cash=40000.0,
    )

    with pytest.raises(
        ValueError,
        match="current snapshot",
    ):
        evaluate_monitoring_triggers(
            supplied_snapshot,
            create_cash_action_register(()),
            as_of_date=date(
                2026,
                10,
                5,
            ),
            policy=_policy(),
            forecast_comparison=comparison,
        )


def test_actual_comparison_must_match_snapshot():
    first = _snapshot(
        "first",
        events=(
            _event("invoice-001"),
        ),
    )

    comparison = compare_forecast_to_actual(
        first,
        (),
        through_date=date(
            2026,
            10,
            5,
        ),
    )

    second = _snapshot(
        "second",
        events=(
            _event("invoice-001"),
        ),
    )

    with pytest.raises(
        ValueError,
        match="supplied snapshot",
    ):
        evaluate_monitoring_triggers(
            second,
            create_cash_action_register(()),
            as_of_date=date(
                2026,
                10,
                5,
            ),
            policy=_policy(),
            actual_comparison=comparison,
        )


def test_actual_evidence_cannot_be_from_future_monitoring_date():
    snapshot = _snapshot(
        events=(
            _event(
                "invoice-001",
                date_value="2026-10-05",
            ),
        ),
    )

    comparison = compare_forecast_to_actual(
        snapshot,
        (),
        through_date=date(
            2026,
            10,
            10,
        ),
    )

    with pytest.raises(
        ValueError,
        match="beyond as_of_date",
    ):
        evaluate_monitoring_triggers(
            snapshot,
            create_cash_action_register(()),
            as_of_date=date(
                2026,
                10,
                8,
            ),
            policy=_policy(),
            actual_comparison=comparison,
        )


def test_monitoring_date_cannot_precede_forecast_start():
    with pytest.raises(
        ValueError,
        match="forecast start date",
    ):
        evaluate_monitoring_triggers(
            _snapshot(),
            create_cash_action_register(()),
            as_of_date=date(
                2026,
                10,
                4,
            ),
            policy=_policy(),
        )


def test_multiple_triggers_have_deterministic_priority():
    snapshot = _snapshot(
        opening_cash=10000.0,
        reserve=5000.0,
        events=(
            _event(
                "payment-001",
                amount=10000.0,
                direction="OUTFLOW",
            ),
        ),
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(
            (
                _action(
                    action_id="action-001",
                    target_date=date(
                        2026,
                        10,
                        4,
                    ),
                ),
            )
        ),
        as_of_date=date(
            2026,
            10,
            5,
        ),
        policy=_policy(),
        breach_probability=0.30,
        maximum_acceptable_breach_probability=0.10,
        prior_recovery_feasible=True,
        current_recovery_feasible=False,
    )

    assert _types(result) == [
        "PROJECTED_RESERVE_BREACH",
        "RISK_ABOVE_APPETITE",
        "LOST_RECOVERY_FEASIBILITY",
        "MISSED_ACTION",
    ]


def test_zero_major_variance_threshold_does_not_trigger_no_change():
    snapshot = _snapshot()

    comparison = compare_forecast_snapshots(
        snapshot,
        _snapshot("snapshot-001"),
    )

    result = evaluate_monitoring_triggers(
        snapshot,
        create_cash_action_register(()),
        as_of_date=date(
            2026,
            10,
            5,
        ),
        policy=_policy(
            threshold=0.0,
        ),
        forecast_comparison=comparison,
    )

    assert (
        "MAJOR_FORECAST_VARIANCE"
        not in _types(result)
    )
