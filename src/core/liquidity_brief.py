from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from src.core.cash_actions import (
    CashAction,
    CashActionRegister,
)
from src.core.forecast_monitoring import (
    DirectCashForecastSnapshot,
)
from src.core.monitoring_triggers import (
    MonitoringTrigger,
    MonitoringTriggerEvaluation,
)
from src.core.recovery_engine import (
    RecoveryEvaluation,
)
from src.core.weekly_recovery_validation import (
    WeeklyRecoveryValidationResult,
)


class LiquidityPositionBrief(BaseModel):
    """
    Deterministic headline liquidity position.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    current_cash: float
    management_reserve: float

    minimum_closing_cash: float
    minimum_closing_cash_week: int = Field(
        ge=1,
        le=13,
    )

    minimum_headroom: float
    minimum_headroom_week: int = Field(
        ge=1,
        le=13,
    )

    first_reserve_breach_week: int | None = Field(
        default=None,
        ge=1,
        le=13,
    )

    closing_cash_13_week: float

    committed_evidence_amount: float = Field(
        ge=0.0,
    )
    modelled_residual_amount: float = Field(
        ge=0.0,
    )
    management_assumption_amount: float = Field(
        ge=0.0,
    )

    evidence_coverage_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class CashDriverBrief(BaseModel):
    """
    One material cash contribution ranked directly from the
    deterministic 13-week forecast.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_id: str
    category: str

    source_type: Literal[
        "COMMITTED",
        "MODELLED",
        "MANAGEMENT_ASSUMPTION",
    ]

    direction: Literal[
        "INFLOW",
        "OUTFLOW",
    ]

    week_number: int = Field(
        ge=1,
        le=13,
    )

    effective_cash_date: date

    gross_amount: float = Field(
        ge=0.0,
    )
    included_amount: float = Field(
        ge=0.0,
    )
    reconciled_coverage_amount: float = Field(
        ge=0.0,
    )

    signed_cash_effect: float


class RecoveryBrief(BaseModel):
    """
    Deterministic recovery evidence with optional probabilistic
    validation.

    Probability fields remain None until the recovery plan has
    actually been validated under weekly uncertainty.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    revenue_improvement_pct: float
    cost_reduction_pct: float
    receivable_acceleration_days: int
    external_liquidity: float

    deterministic_feasible: bool

    resulting_min_cash: float
    resulting_min_cash_week: int = Field(
        ge=1,
        le=13,
    )

    resulting_end_cash: float
    reserve_margin: float
    remaining_reserve_gap: float = Field(
        ge=0.0,
    )

    external_liquidity_week: int | None = Field(
        default=None,
        ge=1,
        le=13,
    )

    probabilistic_validation_status: str | None = None

    reserve_breach_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    maximum_acceptable_breach_probability: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    within_risk_appetite: bool | None = None

    median_min_cash: float | None = None
    p10_min_cash: float | None = None
    median_end_cash: float | None = None

    additional_upfront_buffer_at_confidence: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
    )

    risk_adjusted_breach_probability: (
        float | None
    ) = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    risk_adjusted_within_risk_appetite: (
        bool | None
    ) = None

    simulations: int | None = Field(
        default=None,
        ge=100,
    )


class CashActionBrief(BaseModel):
    """
    Management action summary.

    Expected benefits are kept distinct from realised,
    evidence-backed cash benefits.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    total_actions: int = Field(ge=0)

    planned_actions: int = Field(ge=0)
    in_progress_actions: int = Field(ge=0)
    completed_actions: int = Field(ge=0)
    cancelled_actions: int = Field(ge=0)

    open_expected_cash_impact: float = Field(
        ge=0.0,
    )

    evidenced_realised_cash_benefit: float = Field(
        ge=0.0,
    )

    actions: tuple[
        CashAction,
        ...,
    ] = ()


class MonitoringBrief(BaseModel):
    """
    Active deterministic monitoring signals.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    as_of_date: date

    active_trigger_count: int = Field(
        ge=0,
    )
    critical_trigger_count: int = Field(
        ge=0,
    )
    warning_trigger_count: int = Field(
        ge=0,
    )

    triggers: tuple[
        MonitoringTrigger,
        ...,
    ] = ()


class LiquidityDecisionBrief(BaseModel):
    """
    One-page evidence object for management and the V2 AI layer.

    This is calculated entirely from RiskPilot engine outputs.
    The language model must explain this object rather than
    calculate replacement financial values.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    brief_id: str
    created_at: datetime

    snapshot_id: str

    snapshot_type: Literal[
        "BASELINE",
        "SCENARIO",
    ]

    scenario_name: str | None = None

    forecast_start_date: date

    position: LiquidityPositionBrief

    cash_drivers: tuple[
        CashDriverBrief,
        ...,
    ] = ()

    recovery: RecoveryBrief | None = None

    actions: CashActionBrief

    monitoring: MonitoringBrief | None = None

    limitations: tuple[str, ...] = ()

    @field_validator("brief_id")
    @classmethod
    def _require_brief_id(
        cls,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "brief_id must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "brief_id must not be blank."
            )

        return cleaned

    @field_validator("created_at")
    @classmethod
    def _require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "created_at must be timezone-aware."
            )

        return value


def _build_cash_drivers(
    snapshot: DirectCashForecastSnapshot,
    *,
    max_cash_drivers: int,
) -> tuple[
    CashDriverBrief,
    ...,
]:
    if isinstance(max_cash_drivers, bool):
        raise ValueError(
            "max_cash_drivers must be an integer."
        )

    if (
        not isinstance(max_cash_drivers, int)
        or max_cash_drivers < 1
        or max_cash_drivers > 50
    ):
        raise ValueError(
            "max_cash_drivers must be between 1 and 50."
        )

    event_by_id = {
        event.event_id: event
        for event in snapshot.forecast_input.events
    }

    drivers: list[
        CashDriverBrief
    ] = []

    for week in snapshot.forecast.weeks:
        for contribution in week.contributions:
            event = event_by_id.get(
                contribution.event_id
            )

            if event is None:
                raise ValueError(
                    "Forecast contribution references "
                    "unknown source event ID: "
                    f"{contribution.event_id}"
                )

            signed_effect = (
                float(
                    contribution.included_amount
                )
                if contribution.direction == "INFLOW"
                else -float(
                    contribution.included_amount
                )
            )

            drivers.append(
                CashDriverBrief(
                    event_id=(
                        contribution.event_id
                    ),
                    category=event.category,
                    source_type=(
                        contribution.source_type
                    ),
                    direction=(
                        contribution.direction
                    ),
                    week_number=(
                        week.week_number
                    ),
                    effective_cash_date=(
                        contribution
                        .effective_cash_date
                    ),
                    gross_amount=float(
                        contribution.gross_amount
                    ),
                    included_amount=float(
                        contribution
                        .included_amount
                    ),
                    reconciled_coverage_amount=float(
                        contribution
                        .reconciled_coverage_amount
                    ),
                    signed_cash_effect=(
                        signed_effect
                    ),
                )
            )

    ranked = sorted(
        drivers,
        key=lambda item: (
            -item.included_amount,
            item.week_number,
            item.event_id,
        ),
    )

    return tuple(
        ranked[:max_cash_drivers]
    )


def _build_action_brief(
    register: CashActionRegister,
) -> CashActionBrief:
    planned = sum(
        action.status == "PLANNED"
        for action in register.actions
    )

    in_progress = sum(
        action.status == "IN_PROGRESS"
        for action in register.actions
    )

    completed = sum(
        action.status == "COMPLETED"
        for action in register.actions
    )

    cancelled = sum(
        action.status == "CANCELLED"
        for action in register.actions
    )

    open_expected_impact = sum(
        float(
            action.expected_cash_impact
        )
        for action in register.actions
        if action.status
        in (
            "PLANNED",
            "IN_PROGRESS",
        )
    )

    realised = sum(
        float(
            action.realised_cash_benefit
        )
        for action in register.actions
        if (
            action.realised_cash_benefit
            is not None
        )
    )

    return CashActionBrief(
        total_actions=len(
            register.actions
        ),
        planned_actions=planned,
        in_progress_actions=in_progress,
        completed_actions=completed,
        cancelled_actions=cancelled,
        open_expected_cash_impact=float(
            open_expected_impact
        ),
        evidenced_realised_cash_benefit=float(
            realised
        ),
        actions=register.actions,
    )


def _build_monitoring_brief(
    monitoring: MonitoringTriggerEvaluation,
) -> MonitoringBrief:
    critical = sum(
        trigger.severity == "CRITICAL"
        for trigger in monitoring.triggers
    )

    warnings = sum(
        trigger.severity == "WARNING"
        for trigger in monitoring.triggers
    )

    return MonitoringBrief(
        as_of_date=monitoring.as_of_date,
        active_trigger_count=len(
            monitoring.triggers
        ),
        critical_trigger_count=critical,
        warning_trigger_count=warnings,
        triggers=monitoring.triggers,
    )


def _build_recovery_brief(
    recovery: RecoveryEvaluation,
    validation: (
        WeeklyRecoveryValidationResult | None
    ),
) -> RecoveryBrief:
    plan = recovery.plan

    values = dict(
        revenue_improvement_pct=float(
            plan.revenue_improvement_pct
        ),
        cost_reduction_pct=float(
            plan.cost_reduction_pct
        ),
        receivable_acceleration_days=(
            plan.receivable_acceleration_days
        ),
        external_liquidity=float(
            plan.external_liquidity
        ),
        deterministic_feasible=(
            recovery.feasible
        ),
        resulting_min_cash=float(
            recovery.resulting_min_cash
        ),
        resulting_min_cash_week=(
            recovery.resulting_min_cash_week
        ),
        resulting_end_cash=float(
            recovery.resulting_end_cash
        ),
        reserve_margin=float(
            recovery.reserve_margin
        ),
        remaining_reserve_gap=float(
            recovery.remaining_reserve_gap
        ),
        external_liquidity_week=(
            recovery.external_liquidity_week
        ),
    )

    if validation is None:
        return RecoveryBrief(
            **values
        )

    return RecoveryBrief(
        **values,
        probabilistic_validation_status=(
            validation.status
        ),
        reserve_breach_probability=float(
            validation
            .reserve_breach_probability
        ),
        maximum_acceptable_breach_probability=float(
            validation
            .max_acceptable_breach_probability
        ),
        within_risk_appetite=(
            validation.within_risk_appetite
        ),
        median_min_cash=float(
            validation.median_min_cash
        ),
        p10_min_cash=float(
            validation.p10_min_cash
        ),
        median_end_cash=float(
            validation.median_end_cash
        ),
        additional_upfront_buffer_at_confidence=float(
            validation
            .additional_upfront_buffer_at_confidence
        ),
        risk_adjusted_breach_probability=float(
            validation
            .risk_adjusted_breach_probability
        ),
        risk_adjusted_within_risk_appetite=(
            validation
            .risk_adjusted_within_risk_appetite
        ),
        simulations=validation.simulations,
    )


def build_liquidity_decision_brief(
    snapshot: DirectCashForecastSnapshot,
    action_register: CashActionRegister,
    *,
    brief_id: str,
    created_at: datetime,
    recovery_evaluation: (
        RecoveryEvaluation | None
    ) = None,
    recovery_validation: (
        WeeklyRecoveryValidationResult | None
    ) = None,
    monitoring_evaluation: (
        MonitoringTriggerEvaluation | None
    ) = None,
    max_cash_drivers: int = 8,
) -> LiquidityDecisionBrief:
    """
    Assemble a deterministic management decision brief from
    verified V2 engine outputs.

    No new forecast, probability or recovery calculation occurs
    here.
    """
    metrics = snapshot.decision_metrics

    if (
        recovery_validation is not None
        and recovery_evaluation is None
    ):
        raise ValueError(
            "recovery_validation requires "
            "recovery_evaluation."
        )

    if recovery_evaluation is not None:
        if (
            recovery_evaluation.management_reserve
            != metrics.management_reserve
        ):
            raise ValueError(
                "Recovery evaluation management reserve "
                "does not match the forecast snapshot."
            )

    if recovery_validation is not None:
        if (
            recovery_validation.management_reserve
            != metrics.management_reserve
        ):
            raise ValueError(
                "Recovery validation management reserve "
                "does not match the forecast snapshot."
            )

        if (
            recovery_validation.deterministic_feasible
            != recovery_evaluation.feasible
        ):
            raise ValueError(
                "Recovery validation deterministic "
                "feasibility does not match the "
                "recovery evaluation."
            )

        if (
            recovery_validation
            .external_liquidity_already_in_plan
            != recovery_evaluation
            .plan.external_liquidity
        ):
            raise ValueError(
                "Recovery validation external liquidity "
                "does not match the recovery plan."
            )

        if (
            recovery_validation
            .external_liquidity_week
            != recovery_evaluation
            .external_liquidity_week
        ):
            raise ValueError(
                "Recovery validation funding week does "
                "not match the recovery evaluation."
            )

    if monitoring_evaluation is not None:
        if (
            monitoring_evaluation.snapshot_id
            != snapshot.snapshot_id
        ):
            raise ValueError(
                "Monitoring evaluation must refer to "
                "the supplied forecast snapshot."
            )

    position = LiquidityPositionBrief(
        current_cash=float(
            metrics.current_cash
        ),
        management_reserve=float(
            metrics.management_reserve
        ),
        minimum_closing_cash=float(
            metrics.minimum_closing_cash
        ),
        minimum_closing_cash_week=(
            metrics.minimum_closing_cash_week
        ),
        minimum_headroom=float(
            metrics.minimum_headroom
        ),
        minimum_headroom_week=(
            metrics.minimum_headroom_week
        ),
        first_reserve_breach_week=(
            metrics.first_reserve_breach_week
        ),
        closing_cash_13_week=float(
            metrics.closing_cash_13_week
        ),
        committed_evidence_amount=float(
            metrics.committed_evidence_amount
        ),
        modelled_residual_amount=float(
            metrics.modelled_residual_amount
        ),
        management_assumption_amount=float(
            metrics.management_assumption_amount
        ),
        evidence_coverage_ratio=(
            None
            if (
                metrics.evidence_coverage_ratio
                is None
            )
            else float(
                metrics.evidence_coverage_ratio
            )
        ),
    )

    recovery_brief = (
        None
        if recovery_evaluation is None
        else _build_recovery_brief(
            recovery_evaluation,
            recovery_validation,
        )
    )

    monitoring_brief = (
        None
        if monitoring_evaluation is None
        else _build_monitoring_brief(
            monitoring_evaluation
        )
    )

    limitations = (
        ()
        if recovery_validation is None
        else recovery_validation.limitations
    )

    return LiquidityDecisionBrief(
        brief_id=brief_id,
        created_at=created_at,
        snapshot_id=snapshot.snapshot_id,
        snapshot_type=snapshot.snapshot_type,
        scenario_name=snapshot.scenario_name,
        forecast_start_date=(
            snapshot.forecast_input
            .start_date
        ),
        position=position,
        cash_drivers=_build_cash_drivers(
            snapshot,
            max_cash_drivers=(
                max_cash_drivers
            ),
        ),
        recovery=recovery_brief,
        actions=_build_action_brief(
            action_register
        ),
        monitoring=monitoring_brief,
        limitations=limitations,
    )
