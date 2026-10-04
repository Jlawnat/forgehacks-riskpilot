from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from src.core.cash_events import (
    CashEvent,
    ensure_unique_cash_event_ids,
)


DIRECT_CASH_HORIZON_WEEKS = 13


class CashCoverageAllocation(BaseModel):
    """
    Explicit evidence that part of one committed CashEvent
    is already represented by one modelled CashEvent.

    Coverage is never inferred from dates, weeks or categories.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    coverage_id: str
    committed_event_id: str
    modelled_event_id: str

    amount: float = Field(
        gt=0.0,
        allow_inf_nan=False,
    )

    source_reference: str

    @field_validator(
        "coverage_id",
        "committed_event_id",
        "modelled_event_id",
        "source_reference",
    )
    @classmethod
    def _require_nonblank_string(
        cls,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "Value must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "Value must not be blank."
            )

        return cleaned

    @field_validator(
        "amount",
        mode="before",
    )
    @classmethod
    def _reject_boolean_amount(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "amount must be numeric, not boolean."
            )

        return value


class DirectCashForecastInput(BaseModel):
    """
    Validated input contract for the future 13-week direct
    cash-forecast engine.

    This model defines evidence and reconciliation semantics only.
    It does not perform weekly forecast calculations.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    start_date: date

    opening_cash: float = Field(
        allow_inf_nan=False,
    )

    horizon_weeks: Literal[13] = (
        DIRECT_CASH_HORIZON_WEEKS
    )

    events: tuple[CashEvent, ...] = ()
    coverage_allocations: tuple[
        CashCoverageAllocation,
        ...,
    ] = ()

    @field_validator(
        "opening_cash",
        mode="before",
    )
    @classmethod
    def _reject_boolean_opening_cash(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "opening_cash must be numeric, not boolean."
            )

        return value

    @model_validator(mode="after")
    def _validate_reconciliation(
        self,
    ) -> "DirectCashForecastInput":
        ensure_unique_cash_event_ids(
            self.events
        )

        events_by_id = {
            event.event_id: event
            for event in self.events
        }

        seen_coverage_ids: set[str] = set()
        covered_commitments: set[str] = set()

        for allocation in self.coverage_allocations:
            if (
                allocation.coverage_id
                in seen_coverage_ids
            ):
                raise ValueError(
                    "Duplicate cash coverage ID: "
                    f"{allocation.coverage_id}"
                )

            seen_coverage_ids.add(
                allocation.coverage_id
            )

            committed = events_by_id.get(
                allocation.committed_event_id
            )

            if committed is None:
                raise ValueError(
                    "Coverage references unknown committed "
                    "event ID: "
                    f"{allocation.committed_event_id}"
                )

            modelled = events_by_id.get(
                allocation.modelled_event_id
            )

            if modelled is None:
                raise ValueError(
                    "Coverage references unknown modelled "
                    "event ID: "
                    f"{allocation.modelled_event_id}"
                )

            if committed.source_type != "COMMITTED":
                raise ValueError(
                    "Coverage committed_event_id must "
                    "reference a COMMITTED event."
                )

            if modelled.source_type != "MODELLED":
                raise ValueError(
                    "Coverage modelled_event_id must "
                    "reference a MODELLED event."
                )

            if committed.status != "ACTIVE":
                raise ValueError(
                    "Coverage cannot reference a non-active "
                    "committed event."
                )

            if modelled.status != "ACTIVE":
                raise ValueError(
                    "Coverage cannot reference a non-active "
                    "modelled event."
                )

            if (
                committed.direction
                != modelled.direction
            ):
                raise ValueError(
                    "Coverage cannot reconcile events with "
                    "different cash directions."
                )

            if (
                allocation.committed_event_id
                in covered_commitments
            ):
                raise ValueError(
                    "A committed event may have at most one "
                    "coverage allocation."
                )

            covered_commitments.add(
                allocation.committed_event_id
            )

            if (
                allocation.amount
                > committed.amount
            ):
                raise ValueError(
                    "Coverage amount cannot exceed the "
                    "committed event amount."
                )

        return self



class DirectCashContribution(BaseModel):
    """
    Auditable cash contribution included in one forecast week.

    For MODELLED events, included_amount may be lower than
    gross_amount because of explicit commitment coverage.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_id: str
    effective_cash_date: date

    source_type: Literal[
        "COMMITTED",
        "MODELLED",
        "MANAGEMENT_ASSUMPTION",
    ]

    direction: Literal[
        "INFLOW",
        "OUTFLOW",
    ]

    gross_amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    included_amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    reconciled_coverage_amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )


class DirectCashWeek(BaseModel):
    """
    One seven-day period in the 13-week direct cash forecast.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    week_number: int = Field(
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    start_date: date
    end_date: date

    opening_cash: float = Field(
        allow_inf_nan=False,
    )

    committed_inflows: float = Field(ge=0.0)
    committed_outflows: float = Field(ge=0.0)

    modelled_inflows: float = Field(ge=0.0)
    modelled_outflows: float = Field(ge=0.0)

    management_assumption_inflows: float = Field(
        ge=0.0
    )
    management_assumption_outflows: float = Field(
        ge=0.0
    )

    total_inflows: float = Field(ge=0.0)
    total_outflows: float = Field(ge=0.0)

    net_cash_flow: float
    closing_cash: float

    contributions: tuple[
        DirectCashContribution,
        ...,
    ] = ()


class DirectCashForecastResult(BaseModel):
    """
    Deterministic 13-week direct cash forecast.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    start_date: date
    horizon_weeks: Literal[13]

    opening_cash: float = Field(
        allow_inf_nan=False,
    )

    weeks: tuple[
        DirectCashWeek,
        ...,
    ]

    minimum_closing_cash: float = Field(
        allow_inf_nan=False,
    )

    minimum_closing_cash_week: int = Field(
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    closing_cash: float = Field(
        allow_inf_nan=False,
    )


def _modelled_residual_amounts(
    forecast_input: DirectCashForecastInput,
) -> dict[str, float]:
    """
    Calculate residual modelled amounts after explicit coverage.

    Known commitments are never reduced. If explicit committed
    coverage exceeds the modelled amount, the modelled residual
    floors at zero.
    """
    coverage_by_modelled_id: dict[
        str,
        float,
    ] = {}

    for allocation in (
        forecast_input.coverage_allocations
    ):
        coverage_by_modelled_id[
            allocation.modelled_event_id
        ] = (
            coverage_by_modelled_id.get(
                allocation.modelled_event_id,
                0.0,
            )
            + float(allocation.amount)
        )

    residuals: dict[str, float] = {}

    for event in forecast_input.events:
        if event.source_type != "MODELLED":
            continue

        covered = coverage_by_modelled_id.get(
            event.event_id,
            0.0,
        )

        residuals[event.event_id] = max(
            0.0,
            float(event.amount) - covered,
        )

    return residuals


def _forecast_week_index(
    *,
    effective_cash_date: date,
    start_date: date,
) -> int | None:
    """
    Return the zero-based forecast-week index.

    Active forecast events before start_date are rejected rather
    than silently moved into week 1. Their timing should first be
    updated explicitly, for example with expected_cash_date.
    """
    if effective_cash_date < start_date:
        raise ValueError(
            "Active future cash event has an effective "
            "cash date before forecast start_date."
        )

    days_from_start = (
        effective_cash_date - start_date
    ).days

    horizon_days = (
        DIRECT_CASH_HORIZON_WEEKS * 7
    )

    if days_from_start >= horizon_days:
        return None

    return days_from_start // 7


def build_direct_cash_forecast(
    forecast_input: DirectCashForecastInput,
) -> DirectCashForecastResult:
    """
    Build a deterministic rolling 13-week direct cash forecast.

    Future cash includes:
    - ACTIVE COMMITTED events at full known amount;
    - ACTIVE MODELLED events only for their unreconciled residual;
    - ACTIVE MANAGEMENT_ASSUMPTION events at their stated amount.

    ACTUAL, SETTLED and CANCELLED events are excluded from future
    cash. Coverage is applied only through explicit validated
    CashCoverageAllocation relationships.
    """
    residuals = _modelled_residual_amounts(
        forecast_input
    )

    weekly_contributions: list[
        list[DirectCashContribution]
    ] = [
        []
        for _ in range(
            DIRECT_CASH_HORIZON_WEEKS
        )
    ]

    for event in forecast_input.events:
        if event.source_type == "ACTUAL":
            continue

        if event.status != "ACTIVE":
            continue

        week_index = _forecast_week_index(
            effective_cash_date=(
                event.effective_cash_date
            ),
            start_date=forecast_input.start_date,
        )

        if week_index is None:
            continue

        if event.source_type == "MODELLED":
            included_amount = residuals[
                event.event_id
            ]

            reconciled_amount = max(
                0.0,
                float(event.amount)
                - included_amount,
            )
        else:
            included_amount = float(
                event.amount
            )

            reconciled_amount = 0.0

        if included_amount <= 0.0:
            continue

        weekly_contributions[
            week_index
        ].append(
            DirectCashContribution(
                event_id=event.event_id,
                effective_cash_date=(
                    event.effective_cash_date
                ),
                source_type=event.source_type,
                direction=event.direction,
                gross_amount=float(
                    event.amount
                ),
                included_amount=(
                    included_amount
                ),
                reconciled_coverage_amount=(
                    reconciled_amount
                ),
            )
        )

    cash = float(
        forecast_input.opening_cash
    )

    weeks: list[DirectCashWeek] = []

    for week_index in range(
        DIRECT_CASH_HORIZON_WEEKS
    ):
        contributions = tuple(
            sorted(
                weekly_contributions[
                    week_index
                ],
                key=lambda item: (
                    item.effective_cash_date,
                    item.event_id,
                ),
            )
        )

        committed_inflows = sum(
            item.included_amount
            for item in contributions
            if (
                item.source_type == "COMMITTED"
                and item.direction == "INFLOW"
            )
        )

        committed_outflows = sum(
            item.included_amount
            for item in contributions
            if (
                item.source_type == "COMMITTED"
                and item.direction == "OUTFLOW"
            )
        )

        modelled_inflows = sum(
            item.included_amount
            for item in contributions
            if (
                item.source_type == "MODELLED"
                and item.direction == "INFLOW"
            )
        )

        modelled_outflows = sum(
            item.included_amount
            for item in contributions
            if (
                item.source_type == "MODELLED"
                and item.direction == "OUTFLOW"
            )
        )

        management_inflows = sum(
            item.included_amount
            for item in contributions
            if (
                item.source_type
                == "MANAGEMENT_ASSUMPTION"
                and item.direction == "INFLOW"
            )
        )

        management_outflows = sum(
            item.included_amount
            for item in contributions
            if (
                item.source_type
                == "MANAGEMENT_ASSUMPTION"
                and item.direction == "OUTFLOW"
            )
        )

        total_inflows = float(
            committed_inflows
            + modelled_inflows
            + management_inflows
        )

        total_outflows = float(
            committed_outflows
            + modelled_outflows
            + management_outflows
        )

        net_cash_flow = float(
            total_inflows
            - total_outflows
        )

        opening_cash = cash
        cash = float(
            cash + net_cash_flow
        )

        week_start = (
            forecast_input.start_date
            + timedelta(
                days=week_index * 7
            )
        )

        week_end = (
            week_start
            + timedelta(days=6)
        )

        weeks.append(
            DirectCashWeek(
                week_number=week_index + 1,
                start_date=week_start,
                end_date=week_end,
                opening_cash=opening_cash,
                committed_inflows=float(
                    committed_inflows
                ),
                committed_outflows=float(
                    committed_outflows
                ),
                modelled_inflows=float(
                    modelled_inflows
                ),
                modelled_outflows=float(
                    modelled_outflows
                ),
                management_assumption_inflows=float(
                    management_inflows
                ),
                management_assumption_outflows=float(
                    management_outflows
                ),
                total_inflows=total_inflows,
                total_outflows=total_outflows,
                net_cash_flow=net_cash_flow,
                closing_cash=cash,
                contributions=contributions,
            )
        )

    minimum_week = min(
        weeks,
        key=lambda week: (
            week.closing_cash,
            week.week_number,
        ),
    )

    return DirectCashForecastResult(
        start_date=forecast_input.start_date,
        horizon_weeks=(
            DIRECT_CASH_HORIZON_WEEKS
        ),
        opening_cash=float(
            forecast_input.opening_cash
        ),
        weeks=tuple(weeks),
        minimum_closing_cash=float(
            minimum_week.closing_cash
        ),
        minimum_closing_cash_week=(
            minimum_week.week_number
        ),
        closing_cash=float(
            weeks[-1].closing_cash
        ),
    )
