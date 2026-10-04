from __future__ import annotations

from datetime import timedelta

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DIRECT_CASH_HORIZON_WEEKS,
    DirectCashForecastInput,
    build_direct_cash_forecast,
)
from src.core.recovery_constraints import (
    RecoveryConstraintSet,
    validate_recovery_constraints,
)
from src.core.risk_policy import first_cash_breach


class RecoveryPlan(BaseModel):
    """
    One deterministic recovery candidate.

    Values describe the intervention actually attempted,
    not the maximum management capacity.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    revenue_improvement_pct: float = Field(
        default=0.0,
        ge=0.0,
        allow_inf_nan=False,
    )

    cost_reduction_pct: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        allow_inf_nan=False,
    )

    receivable_acceleration_days: int = Field(
        default=0,
        ge=0,
    )

    external_liquidity: float = Field(
        default=0.0,
        ge=0.0,
        allow_inf_nan=False,
    )

    @field_validator(
        "revenue_improvement_pct",
        "cost_reduction_pct",
        "external_liquidity",
        mode="before",
    )
    @classmethod
    def _reject_boolean_float(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Recovery values must be numeric, "
                "not boolean."
            )

        return value

    @field_validator(
        "receivable_acceleration_days",
        mode="before",
    )
    @classmethod
    def _reject_boolean_days(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Recovery days must be numeric, "
                "not boolean."
            )

        return value


class RecoveryEvaluation(BaseModel):
    """
    Deterministic evaluation of one recovery plan.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    plan: RecoveryPlan

    management_reserve: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    baseline_min_cash: float = Field(
        allow_inf_nan=False,
    )

    operating_min_cash: float = Field(
        allow_inf_nan=False,
    )

    resulting_min_cash: float = Field(
        allow_inf_nan=False,
    )

    resulting_min_cash_week: int = Field(
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    resulting_end_cash: float = Field(
        allow_inf_nan=False,
    )

    reserve_margin: float = Field(
        allow_inf_nan=False,
    )

    remaining_reserve_gap: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    feasible: bool

    first_reserve_breach_week: int | None = Field(
        default=None,
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    external_liquidity_week: int | None = Field(
        default=None,
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    changed_event_ids: tuple[str, ...] = ()

    weekly_closing_cash: tuple[float, ...]


def validate_recovery_plan(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    plan: RecoveryPlan,
) -> None:
    """
    Enforce hard management constraints before evaluation.
    """
    validate_recovery_constraints(
        forecast_input,
        constraints,
    )

    _validate_lever(
        name="Revenue improvement",
        value=plan.revenue_improvement_pct,
        enabled=(
            constraints
            .revenue_improvement
            .enabled
        ),
        maximum=(
            constraints
            .revenue_improvement
            .max_improvement_pct
        ),
        eligible_ids=(
            constraints
            .revenue_improvement
            .eligible_event_ids
        ),
    )

    _validate_lever(
        name="Cost reduction",
        value=plan.cost_reduction_pct,
        enabled=(
            constraints
            .cost_reduction
            .enabled
        ),
        maximum=(
            constraints
            .cost_reduction
            .max_reduction_pct
        ),
        eligible_ids=(
            constraints
            .cost_reduction
            .eligible_event_ids
        ),
    )

    _validate_lever(
        name="Receivable acceleration",
        value=float(
            plan.receivable_acceleration_days
        ),
        enabled=(
            constraints
            .receivable_acceleration
            .enabled
        ),
        maximum=float(
            constraints
            .receivable_acceleration
            .max_acceleration_days
        ),
        eligible_ids=(
            constraints
            .receivable_acceleration
            .eligible_event_ids
        ),
    )

    _validate_lever(
        name="External liquidity",
        value=plan.external_liquidity,
        enabled=(
            constraints
            .external_liquidity
            .enabled
        ),
        maximum=(
            constraints
            .external_liquidity
            .max_amount
        ),
        eligible_ids=None,
    )


def _validate_lever(
    *,
    name: str,
    value: float,
    enabled: bool,
    maximum: float,
    eligible_ids: tuple[str, ...] | None,
) -> None:
    if value <= 0.0:
        return

    if not enabled:
        raise ValueError(
            f"{name} is disabled."
        )

    if value > maximum:
        raise ValueError(
            f"{name} exceeds its management maximum."
        )

    if (
        eligible_ids is not None
        and not eligible_ids
    ):
        raise ValueError(
            f"{name} has no eligible cash events."
        )


def _rebuilt_event(
    event: CashEvent,
    **updates,
) -> CashEvent:
    payload = event.model_dump()
    payload.update(updates)

    return CashEvent.model_validate(
        payload
    )


def _apply_operating_recovery(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    plan: RecoveryPlan,
) -> tuple[
    DirectCashForecastInput,
    tuple[str, ...],
]:
    revenue_ids = set(
        constraints
        .revenue_improvement
        .eligible_event_ids
    )

    cost_ids = set(
        constraints
        .cost_reduction
        .eligible_event_ids
    )

    receivable_ids = set(
        constraints
        .receivable_acceleration
        .eligible_event_ids
    )

    changed_ids: list[str] = []
    adjusted_events: list[CashEvent] = []

    for event in forecast_input.events:
        adjusted = event

        if (
            plan.revenue_improvement_pct > 0.0
            and event.event_id in revenue_ids
            and event.effective_cash_date
            >= constraints
            .revenue_improvement
            .available_from
        ):
            adjusted = _rebuilt_event(
                adjusted,
                amount=(
                    float(adjusted.amount)
                    * (
                        1.0
                        + plan.revenue_improvement_pct
                        / 100.0
                    )
                ),
            )

        if (
            plan.cost_reduction_pct > 0.0
            and event.event_id in cost_ids
            and event.effective_cash_date
            >= constraints
            .cost_reduction
            .available_from
        ):
            adjusted = _rebuilt_event(
                adjusted,
                amount=(
                    float(adjusted.amount)
                    * (
                        1.0
                        - plan.cost_reduction_pct
                        / 100.0
                    )
                ),
            )

        if (
            plan.receivable_acceleration_days > 0
            and event.event_id in receivable_ids
        ):
            original_date = (
                adjusted.effective_cash_date
            )

            available_from = (
                constraints
                .receivable_acceleration
                .available_from
            )

            if original_date > available_from:
                candidate = (
                    original_date
                    - timedelta(
                        days=(
                            plan
                            .receivable_acceleration_days
                        )
                    )
                )

                earliest_allowed = max(
                    forecast_input.start_date,
                    available_from,
                )

                accelerated_date = max(
                    candidate,
                    earliest_allowed,
                )

                if accelerated_date < original_date:
                    adjusted = _rebuilt_event(
                        adjusted,
                        expected_cash_date=(
                            accelerated_date
                        ),
                    )

        if adjusted != event:
            changed_ids.append(
                event.event_id
            )

        adjusted_events.append(
            adjusted
        )

    adjusted_input = DirectCashForecastInput(
        start_date=forecast_input.start_date,
        opening_cash=forecast_input.opening_cash,
        horizon_weeks=(
            forecast_input.horizon_weeks
        ),
        events=tuple(adjusted_events),
        coverage_allocations=(
            forecast_input.coverage_allocations
        ),
    )

    return (
        adjusted_input,
        tuple(changed_ids),
    )



def apply_recovery_operating_actions(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    plan: RecoveryPlan,
) -> tuple[
    DirectCashForecastInput,
    tuple[str, ...],
]:
    """
    Public V2 recovery transformation used by downstream
    uncertainty validation.

    External liquidity is deliberately not inserted into the
    returned base cash-event set. It remains a separate recovery
    overlay with its own availability timing.
    """
    validate_recovery_plan(
        forecast_input,
        constraints,
        plan,
    )

    return _apply_operating_recovery(
        forecast_input,
        constraints,
        plan,
    )


def evaluate_recovery_plan(
    forecast_input: DirectCashForecastInput,
    constraints: RecoveryConstraintSet,
    plan: RecoveryPlan,
    *,
    management_reserve: float,
) -> RecoveryEvaluation:
    """
    Evaluate one recovery plan against the 13-week cash model.

    External liquidity is applied as a separate dated recovery
    overlay. It is not converted into a base CashEvent.

    Therefore funding that arrives after an earlier cash breach
    cannot repair that earlier breach.
    """
    if isinstance(
        management_reserve,
        bool,
    ):
        raise ValueError(
            "management_reserve must be numeric, "
            "not boolean."
        )

    reserve = float(
        management_reserve
    )

    if (
        reserve < 0.0
        or reserve != reserve
        or reserve in (
            float("inf"),
            float("-inf"),
        )
    ):
        raise ValueError(
            "management_reserve must be finite "
            "and nonnegative."
        )

    validate_recovery_plan(
        forecast_input,
        constraints,
        plan,
    )

    baseline = build_direct_cash_forecast(
        forecast_input
    )

    (
        adjusted_input,
        changed_event_ids,
    ) = _apply_operating_recovery(
        forecast_input,
        constraints,
        plan,
    )

    operating = build_direct_cash_forecast(
        adjusted_input
    )

    weekly_cash = [
        float(week.closing_cash)
        for week in operating.weeks
    ]

    external_week: int | None = None

    if plan.external_liquidity > 0.0:
        liquidity_date = max(
            forecast_input.start_date,
            constraints
            .external_liquidity
            .available_from,
        )

        days_from_start = (
            liquidity_date
            - forecast_input.start_date
        ).days

        horizon_days = (
            DIRECT_CASH_HORIZON_WEEKS
            * 7
        )

        if days_from_start < horizon_days:
            external_index = (
                days_from_start // 7
            )

            external_week = (
                external_index + 1
            )

            for index in range(
                external_index,
                DIRECT_CASH_HORIZON_WEEKS,
            ):
                weekly_cash[index] += (
                    plan.external_liquidity
                )

    resulting_min_cash = min(
        weekly_cash
    )

    resulting_min_week = (
        weekly_cash.index(
            resulting_min_cash
        )
        + 1
    )

    resulting_end_cash = (
        weekly_cash[-1]
    )

    reserve_margin = (
        resulting_min_cash
        - reserve
    )

    remaining_gap = max(
        0.0,
        reserve - resulting_min_cash,
    )

    first_breach = first_cash_breach(
        weekly_cash,
        reserve,
    )

    return RecoveryEvaluation(
        plan=plan,
        management_reserve=reserve,
        baseline_min_cash=float(
            baseline.minimum_closing_cash
        ),
        operating_min_cash=float(
            operating.minimum_closing_cash
        ),
        resulting_min_cash=float(
            resulting_min_cash
        ),
        resulting_min_cash_week=(
            resulting_min_week
        ),
        resulting_end_cash=float(
            resulting_end_cash
        ),
        reserve_margin=float(
            reserve_margin
        ),
        remaining_reserve_gap=float(
            remaining_gap
        ),
        feasible=(
            remaining_gap <= 0.0
        ),
        first_reserve_breach_week=(
            first_breach
        ),
        external_liquidity_week=(
            external_week
        ),
        changed_event_ids=(
            changed_event_ids
        ),
        weekly_closing_cash=tuple(
            float(value)
            for value in weekly_cash
        ),
    )
