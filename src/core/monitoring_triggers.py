from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from src.core.cash_actions import (
    CashActionRegister,
)
from src.core.forecast_monitoring import (
    DirectCashForecastSnapshot,
    ForecastActualComparison,
    ForecastSnapshotComparison,
)


MonitoringTriggerType = Literal[
    "PROJECTED_RESERVE_BREACH",
    "RISK_ABOVE_APPETITE",
    "MISSED_ACTION",
    "MAJOR_FORECAST_VARIANCE",
    "DELAYED_COMMITTED_RECEIPT",
    "LOST_RECOVERY_FEASIBILITY",
]


MonitoringTriggerSeverity = Literal[
    "WARNING",
    "CRITICAL",
]


class MonitoringTriggerPolicy(BaseModel):
    """
    Explicit management policy for monitoring.

    major_forecast_variance_threshold is an absolute cash
    threshold applied to the change in minimum projected cash.
    No materiality threshold is guessed internally.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    major_forecast_variance_threshold: float

    @field_validator(
        "major_forecast_variance_threshold",
        mode="before",
    )
    @classmethod
    def _validate_threshold(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Variance threshold must be numeric, "
                "not boolean."
            )

        numeric = float(value)

        if (
            not isfinite(numeric)
            or numeric < 0.0
        ):
            raise ValueError(
                "Variance threshold must be finite "
                "and nonnegative."
            )

        return value


class MonitoringTrigger(BaseModel):
    """
    One active, explainable monitoring trigger.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    trigger_id: str
    trigger_type: MonitoringTriggerType
    severity: MonitoringTriggerSeverity

    message: str

    reference_ids: tuple[str, ...] = ()

    metric_value: float | None = None
    threshold_value: float | None = None


class MonitoringTriggerEvaluation(BaseModel):
    """
    Deterministic trigger evaluation at one monitoring date.

    Only active triggers are stored.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    as_of_date: date

    snapshot_id: str

    triggers: tuple[
        MonitoringTrigger,
        ...,
    ] = ()

    @property
    def has_active_triggers(
        self,
    ) -> bool:
        return bool(self.triggers)

    @property
    def has_critical_triggers(
        self,
    ) -> bool:
        return any(
            trigger.severity == "CRITICAL"
            for trigger in self.triggers
        )


def _validate_probability(
    value: float,
    *,
    name: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            f"{name} must be numeric, not boolean."
        )

    numeric = float(value)

    if (
        not isfinite(numeric)
        or numeric < 0.0
        or numeric > 1.0
    ):
        raise ValueError(
            f"{name} must be between 0 and 1."
        )

    return numeric


def _delayed_committed_receipt_triggers(
    snapshot: DirectCashForecastSnapshot,
    actual_comparison: ForecastActualComparison,
) -> list[MonitoringTrigger]:
    event_by_id = {
        event.event_id: event
        for event in (
            snapshot.forecast_input.events
        )
    }

    triggers: list[
        MonitoringTrigger
    ] = []

    seen_event_ids: set[str] = set()

    for variance in (
        actual_comparison.variances
    ):
        event_id = (
            variance.forecast_event_id
        )

        if (
            event_id is None
            or event_id in seen_event_ids
        ):
            continue

        event = event_by_id.get(
            event_id
        )

        if event is None:
            continue

        if (
            event.source_type != "COMMITTED"
            or event.direction != "INFLOW"
        ):
            continue

        delayed = False

        if variance.category == "MISSING_EVENT":
            delayed = True

        elif variance.category == "TIMING":
            if (
                variance.forecast_effective_cash_date
                is not None
                and variance.actual_dates
            ):
                forecast_date = (
                    date.fromisoformat(
                        variance
                        .forecast_effective_cash_date
                    )
                )

                actual_dates = tuple(
                    date.fromisoformat(
                        value
                    )
                    for value in (
                        variance.actual_dates
                    )
                )

                delayed = (
                    max(actual_dates)
                    > forecast_date
                )

        if not delayed:
            continue

        seen_event_ids.add(
            event_id
        )

        triggers.append(
            MonitoringTrigger(
                trigger_id=(
                    "DELAYED_COMMITTED_RECEIPT:"
                    f"{event_id}"
                ),
                trigger_type=(
                    "DELAYED_COMMITTED_RECEIPT"
                ),
                severity="WARNING",
                message=(
                    "Committed customer receipt is later "
                    "than the forecast cash timing or has "
                    "not been observed by the monitoring "
                    "date."
                ),
                reference_ids=(
                    event_id,
                ),
            )
        )

    return triggers


def evaluate_monitoring_triggers(
    snapshot: DirectCashForecastSnapshot,
    action_register: CashActionRegister,
    *,
    as_of_date: date,
    policy: MonitoringTriggerPolicy,
    forecast_comparison: (
        ForecastSnapshotComparison | None
    ) = None,
    actual_comparison: (
        ForecastActualComparison | None
    ) = None,
    breach_probability: float | None = None,
    maximum_acceptable_breach_probability: (
        float | None
    ) = None,
    prior_recovery_feasible: bool | None = None,
    current_recovery_feasible: bool | None = None,
) -> MonitoringTriggerEvaluation:
    """
    Evaluate active liquidity-management triggers.

    Probability and recovery-feasibility inputs are explicit
    because this layer consumes evidence from the uncertainty
    and recovery engines rather than recalculating it.

    No risk appetite or materiality threshold is invented.
    """
    if (
        breach_probability is None
    ) != (
        maximum_acceptable_breach_probability
        is None
    ):
        raise ValueError(
            "breach_probability and "
            "maximum_acceptable_breach_probability "
            "must be provided together."
        )

    if breach_probability is not None:
        probability = _validate_probability(
            breach_probability,
            name="breach_probability",
        )

        appetite = _validate_probability(
            maximum_acceptable_breach_probability,
            name=(
                "maximum_acceptable_"
                "breach_probability"
            ),
        )
    else:
        probability = None
        appetite = None

    if (
        prior_recovery_feasible is None
    ) != (
        current_recovery_feasible is None
    ):
        raise ValueError(
            "prior_recovery_feasible and "
            "current_recovery_feasible must be "
            "provided together."
        )

    if (
        prior_recovery_feasible is not None
        and (
            not isinstance(
                prior_recovery_feasible,
                bool,
            )
            or not isinstance(
                current_recovery_feasible,
                bool,
            )
        )
    ):
        raise ValueError(
            "Recovery feasibility inputs must "
            "be boolean."
        )

    if as_of_date < snapshot.forecast_input.start_date:
        raise ValueError(
            "as_of_date cannot be before the "
            "forecast start date."
        )

    if forecast_comparison is not None:
        if (
            forecast_comparison.current_snapshot_id
            != snapshot.snapshot_id
        ):
            raise ValueError(
                "forecast_comparison current snapshot "
                "must match the supplied snapshot."
            )

    if actual_comparison is not None:
        if (
            actual_comparison.snapshot_id
            != snapshot.snapshot_id
        ):
            raise ValueError(
                "actual_comparison must refer to "
                "the supplied snapshot."
            )

        if (
            actual_comparison.through_date
            > as_of_date
        ):
            raise ValueError(
                "actual_comparison cannot contain "
                "evidence beyond as_of_date."
            )

    triggers: list[
        MonitoringTrigger
    ] = []

    breach_week = (
        snapshot.decision_metrics
        .first_reserve_breach_week
    )

    if breach_week is not None:
        triggers.append(
            MonitoringTrigger(
                trigger_id=(
                    "PROJECTED_RESERVE_BREACH"
                ),
                trigger_type=(
                    "PROJECTED_RESERVE_BREACH"
                ),
                severity="CRITICAL",
                message=(
                    "The current 13-week forecast "
                    "projects cash below the management "
                    "reserve."
                ),
                reference_ids=(
                    f"week-{breach_week}",
                ),
                metric_value=float(
                    snapshot.decision_metrics
                    .minimum_headroom
                ),
                threshold_value=0.0,
            )
        )

    if (
        probability is not None
        and appetite is not None
        and probability > appetite
    ):
        triggers.append(
            MonitoringTrigger(
                trigger_id=(
                    "RISK_ABOVE_APPETITE"
                ),
                trigger_type=(
                    "RISK_ABOVE_APPETITE"
                ),
                severity="CRITICAL",
                message=(
                    "Estimated reserve-breach "
                    "probability exceeds the explicit "
                    "management risk appetite."
                ),
                metric_value=probability,
                threshold_value=appetite,
            )
        )

    for action in action_register.actions:
        if (
            action.status
            in (
                "PLANNED",
                "IN_PROGRESS",
            )
            and action.target_date
            < as_of_date
        ):
            triggers.append(
                MonitoringTrigger(
                    trigger_id=(
                        "MISSED_ACTION:"
                        f"{action.action_id}"
                    ),
                    trigger_type="MISSED_ACTION",
                    severity="WARNING",
                    message=(
                        "Liquidity action is past its "
                        "target date and remains open."
                    ),
                    reference_ids=(
                        action.action_id,
                    ),
                    metric_value=float(
                        (
                            as_of_date
                            - action.target_date
                        ).days
                    ),
                    threshold_value=0.0,
                )
            )

    if forecast_comparison is not None:
        minimum_cash_change = float(
            forecast_comparison
            .minimum_cash_change
        )

        threshold = float(
            policy
            .major_forecast_variance_threshold
        )

        if (
            abs(minimum_cash_change)
            >= threshold
            and (
                threshold > 0.0
                or minimum_cash_change != 0.0
            )
        ):
            direction = (
                "improved"
                if minimum_cash_change > 0.0
                else "deteriorated"
            )

            triggers.append(
                MonitoringTrigger(
                    trigger_id=(
                        "MAJOR_FORECAST_VARIANCE"
                    ),
                    trigger_type=(
                        "MAJOR_FORECAST_VARIANCE"
                    ),
                    severity="WARNING",
                    message=(
                        "Minimum projected cash has "
                        f"{direction} materially versus "
                        "the prior forecast."
                    ),
                    reference_ids=(
                        forecast_comparison
                        .prior_snapshot_id,
                        forecast_comparison
                        .current_snapshot_id,
                    ),
                    metric_value=(
                        minimum_cash_change
                    ),
                    threshold_value=threshold,
                )
            )

    if actual_comparison is not None:
        triggers.extend(
            _delayed_committed_receipt_triggers(
                snapshot,
                actual_comparison,
            )
        )

    if (
        prior_recovery_feasible is True
        and current_recovery_feasible is False
    ):
        triggers.append(
            MonitoringTrigger(
                trigger_id=(
                    "LOST_RECOVERY_FEASIBILITY"
                ),
                trigger_type=(
                    "LOST_RECOVERY_FEASIBILITY"
                ),
                severity="CRITICAL",
                message=(
                    "A recovery position that was "
                    "previously feasible is no longer "
                    "feasible under current evidence."
                ),
            )
        )

    trigger_order = {
        "PROJECTED_RESERVE_BREACH": 0,
        "RISK_ABOVE_APPETITE": 1,
        "LOST_RECOVERY_FEASIBILITY": 2,
        "DELAYED_COMMITTED_RECEIPT": 3,
        "MISSED_ACTION": 4,
        "MAJOR_FORECAST_VARIANCE": 5,
    }

    ordered = tuple(
        sorted(
            triggers,
            key=lambda trigger: (
                trigger_order[
                    trigger.trigger_type
                ],
                trigger.trigger_id,
            ),
        )
    )

    return MonitoringTriggerEvaluation(
        as_of_date=as_of_date,
        snapshot_id=snapshot.snapshot_id,
        triggers=ordered,
    )
