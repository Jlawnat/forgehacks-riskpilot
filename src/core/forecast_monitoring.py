from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    CashCoverageAllocation,
    DirectCashForecastInput,
    DirectCashForecastResult,
    build_direct_cash_forecast,
)
from src.core.liquidity_metrics import (
    LiquidityDecisionMetrics,
    build_liquidity_decision_metrics,
)


ForecastSnapshotType = Literal[
    "BASELINE",
    "SCENARIO",
]


class DirectCashForecastSnapshot(BaseModel):
    """
    Immutable audit record of one 13-week direct cash forecast.

    The snapshot stores both its source evidence and calculated
    outputs so future monitoring can compare:

    - forecast versus actual;
    - forecast versus prior forecast;
    - saved scenarios versus baseline.

    created_at must be supplied explicitly and must include
    timezone information.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    snapshot_id: str
    snapshot_type: ForecastSnapshotType = "BASELINE"

    scenario_name: str | None = None

    created_at: datetime

    forecast_basis_fingerprint: str

    forecast_input: DirectCashForecastInput
    forecast: DirectCashForecastResult
    decision_metrics: LiquidityDecisionMetrics

    @field_validator(
        "snapshot_id",
        "forecast_basis_fingerprint",
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

    @model_validator(mode="after")
    def _validate_snapshot_type(
        self,
    ) -> "DirectCashForecastSnapshot":
        if self.snapshot_type == "SCENARIO":
            if (
                self.scenario_name is None
                or not self.scenario_name.strip()
            ):
                raise ValueError(
                    "SCENARIO snapshots require a "
                    "nonblank scenario_name."
                )

        if (
            self.snapshot_type == "BASELINE"
            and self.scenario_name is not None
        ):
            raise ValueError(
                "BASELINE snapshots must not define "
                "scenario_name."
            )

        return self


def forecast_basis_fingerprint(
    forecast_input: DirectCashForecastInput,
    *,
    management_reserve: float,
) -> str:
    """
    Stable fingerprint of the exact evidence and reserve policy
    used to build a snapshot.
    """
    payload = {
        "forecast_input": (
            forecast_input.model_dump(
                mode="json"
            )
        ),
        "management_reserve": float(
            management_reserve
        ),
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    return sha256(
        encoded
    ).hexdigest()


def create_forecast_snapshot(
    forecast_input: DirectCashForecastInput,
    *,
    snapshot_id: str,
    created_at: datetime,
    management_reserve: float,
    snapshot_type: ForecastSnapshotType = "BASELINE",
    scenario_name: str | None = None,
) -> DirectCashForecastSnapshot:
    """
    Build one immutable forecast snapshot.

    Existing forecast inputs are not mutated.
    """
    forecast = build_direct_cash_forecast(
        forecast_input
    )

    metrics = (
        build_liquidity_decision_metrics(
            forecast,
            management_reserve=(
                management_reserve
            ),
        )
    )

    fingerprint = (
        forecast_basis_fingerprint(
            forecast_input,
            management_reserve=(
                metrics.management_reserve
            ),
        )
    )

    return DirectCashForecastSnapshot(
        snapshot_id=snapshot_id,
        snapshot_type=snapshot_type,
        scenario_name=scenario_name,
        created_at=created_at,
        forecast_basis_fingerprint=(
            fingerprint
        ),
        forecast_input=forecast_input,
        forecast=forecast,
        decision_metrics=metrics,
    )


ForecastVarianceCategory = Literal[
    "TIMING",
    "AMOUNT",
    "NEW_EVENT",
    "MISSING_EVENT",
    "ASSUMPTION_CHANGE",
    "MODEL_ERROR",
]


class ForecastVarianceItem(BaseModel):
    """
    One explainable change between two forecast snapshots.

    MODEL_ERROR is part of the common variance taxonomy but is
    intentionally reserved for forecast-versus-actual monitoring.
    A normal forecast revision is not automatically a model error.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event_id: str
    category: ForecastVarianceCategory

    prior_amount: float | None = None
    current_amount: float | None = None

    prior_effective_cash_date: str | None = None
    current_effective_cash_date: str | None = None

    prior_source_type: str | None = None
    current_source_type: str | None = None

    detail: str


class ForecastSnapshotComparison(BaseModel):
    """
    Auditable comparison of a prior forecast snapshot with
    a newer forecast snapshot.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    prior_snapshot_id: str
    current_snapshot_id: str

    same_forecast_basis: bool

    prior_start_date: str
    current_start_date: str

    prior_management_reserve: float
    current_management_reserve: float
    management_reserve_changed: bool

    opening_cash_change: float
    closing_cash_change: float
    minimum_cash_change: float
    minimum_headroom_change: float

    prior_first_reserve_breach_week: int | None
    current_first_reserve_breach_week: int | None

    variances: tuple[
        ForecastVarianceItem,
        ...,
    ] = ()


def _is_future_cash_event(
    event,
) -> bool:
    return (
        event.status == "ACTIVE"
        and event.source_type != "ACTUAL"
    )


def _variance_item(
    *,
    event_id: str,
    category: ForecastVarianceCategory,
    prior_event=None,
    current_event=None,
    detail: str,
) -> ForecastVarianceItem:
    return ForecastVarianceItem(
        event_id=event_id,
        category=category,
        prior_amount=(
            float(prior_event.amount)
            if prior_event is not None
            else None
        ),
        current_amount=(
            float(current_event.amount)
            if current_event is not None
            else None
        ),
        prior_effective_cash_date=(
            prior_event
            .effective_cash_date
            .isoformat()
            if prior_event is not None
            else None
        ),
        current_effective_cash_date=(
            current_event
            .effective_cash_date
            .isoformat()
            if current_event is not None
            else None
        ),
        prior_source_type=(
            prior_event.source_type
            if prior_event is not None
            else None
        ),
        current_source_type=(
            current_event.source_type
            if current_event is not None
            else None
        ),
        detail=detail,
    )


def _event_variances(
    prior_event,
    current_event,
) -> tuple[
    ForecastVarianceItem,
    ...,
]:
    event_id = (
        prior_event.event_id
        if prior_event is not None
        else current_event.event_id
    )

    if prior_event is None:
        if not _is_future_cash_event(
            current_event
        ):
            return ()

        return (
            _variance_item(
                event_id=event_id,
                category="NEW_EVENT",
                current_event=current_event,
                detail=(
                    "Future cash event is present in the "
                    "current forecast but not the prior forecast."
                ),
            ),
        )

    if current_event is None:
        if not _is_future_cash_event(
            prior_event
        ):
            return ()

        return (
            _variance_item(
                event_id=event_id,
                category="MISSING_EVENT",
                prior_event=prior_event,
                detail=(
                    "Future cash event was present in the "
                    "prior forecast but is absent now."
                ),
            ),
        )

    prior_future = _is_future_cash_event(
        prior_event
    )

    current_future = _is_future_cash_event(
        current_event
    )

    if prior_future and not current_future:
        return (
            _variance_item(
                event_id=event_id,
                category="MISSING_EVENT",
                prior_event=prior_event,
                current_event=current_event,
                detail=(
                    "Previously active future cash is no "
                    "longer part of the future forecast."
                ),
            ),
        )

    if not prior_future and current_future:
        return (
            _variance_item(
                event_id=event_id,
                category="NEW_EVENT",
                prior_event=prior_event,
                current_event=current_event,
                detail=(
                    "Cash event has become active future "
                    "cash in the current forecast."
                ),
            ),
        )

    if not prior_future and not current_future:
        return ()

    if (
        prior_event.source_type
        == "MANAGEMENT_ASSUMPTION"
        or current_event.source_type
        == "MANAGEMENT_ASSUMPTION"
    ):
        if (
            prior_event.model_dump(mode="json")
            != current_event.model_dump(mode="json")
        ):
            return (
                _variance_item(
                    event_id=event_id,
                    category="ASSUMPTION_CHANGE",
                    prior_event=prior_event,
                    current_event=current_event,
                    detail=(
                        "Explicit management-assumption "
                        "evidence changed."
                    ),
                ),
            )

        return ()

    items: list[
        ForecastVarianceItem
    ] = []

    amount_changed = (
        float(prior_event.amount)
        != float(current_event.amount)
    )

    timing_changed = (
        prior_event.effective_cash_date
        != current_event.effective_cash_date
    )

    if amount_changed:
        items.append(
            _variance_item(
                event_id=event_id,
                category="AMOUNT",
                prior_event=prior_event,
                current_event=current_event,
                detail=(
                    "Forecast cash amount changed while "
                    "retaining the same event identity."
                ),
            )
        )

    if timing_changed:
        items.append(
            _variance_item(
                event_id=event_id,
                category="TIMING",
                prior_event=prior_event,
                current_event=current_event,
                detail=(
                    "Effective cash timing changed without "
                    "treating the movement as business "
                    "deterioration by itself."
                ),
            )
        )

    metadata_changed = (
        prior_event.source_type
        != current_event.source_type
        or prior_event.direction
        != current_event.direction
        or prior_event.category
        != current_event.category
        or prior_event.status
        != current_event.status
        or prior_event.description
        != current_event.description
        or prior_event.source_reference
        != current_event.source_reference
    )

    contractual_dates_changed_without_cash_timing_change = (
        not timing_changed
        and (
            prior_event.date
            != current_event.date
            or prior_event.due_date
            != current_event.due_date
            or prior_event.expected_cash_date
            != current_event.expected_cash_date
        )
    )

    if (
        metadata_changed
        or contractual_dates_changed_without_cash_timing_change
    ):
        items.append(
            _variance_item(
                event_id=event_id,
                category="ASSUMPTION_CHANGE",
                prior_event=prior_event,
                current_event=current_event,
                detail=(
                    "Forecast evidence or non-cash-timing "
                    "basis changed."
                ),
            )
        )

    return tuple(items)


def compare_forecast_snapshots(
    prior: DirectCashForecastSnapshot,
    current: DirectCashForecastSnapshot,
) -> ForecastSnapshotComparison:
    """
    Compare a prior forecast with a newer forecast.

    The function explains changes in the forecast basis and
    headline liquidity position. It does not infer MODEL_ERROR;
    that classification requires actual evidence.
    """
    prior_events = {
        event.event_id: event
        for event in (
            prior.forecast_input.events
        )
    }

    current_events = {
        event.event_id: event
        for event in (
            current.forecast_input.events
        )
    }

    variances: list[
        ForecastVarianceItem
    ] = []

    for event_id in sorted(
        set(prior_events)
        | set(current_events)
    ):
        variances.extend(
            _event_variances(
                prior_events.get(event_id),
                current_events.get(event_id),
            )
        )

    category_order = {
        "NEW_EVENT": 0,
        "MISSING_EVENT": 1,
        "TIMING": 2,
        "AMOUNT": 3,
        "ASSUMPTION_CHANGE": 4,
        "MODEL_ERROR": 5,
    }

    ordered_variances = tuple(
        sorted(
            variances,
            key=lambda item: (
                item.event_id,
                category_order[
                    item.category
                ],
            ),
        )
    )

    prior_reserve = (
        prior.decision_metrics
        .management_reserve
    )

    current_reserve = (
        current.decision_metrics
        .management_reserve
    )

    return ForecastSnapshotComparison(
        prior_snapshot_id=(
            prior.snapshot_id
        ),
        current_snapshot_id=(
            current.snapshot_id
        ),
        same_forecast_basis=(
            prior.forecast_basis_fingerprint
            == current.forecast_basis_fingerprint
        ),
        prior_start_date=(
            prior.forecast_input
            .start_date
            .isoformat()
        ),
        current_start_date=(
            current.forecast_input
            .start_date
            .isoformat()
        ),
        prior_management_reserve=float(
            prior_reserve
        ),
        current_management_reserve=float(
            current_reserve
        ),
        management_reserve_changed=(
            prior_reserve
            != current_reserve
        ),
        opening_cash_change=float(
            current.forecast.opening_cash
            - prior.forecast.opening_cash
        ),
        closing_cash_change=float(
            current.forecast.closing_cash
            - prior.forecast.closing_cash
        ),
        minimum_cash_change=float(
            current.forecast
            .minimum_closing_cash
            - prior.forecast
            .minimum_closing_cash
        ),
        minimum_headroom_change=float(
            current.decision_metrics
            .minimum_headroom
            - prior.decision_metrics
            .minimum_headroom
        ),
        prior_first_reserve_breach_week=(
            prior.decision_metrics
            .first_reserve_breach_week
        ),
        current_first_reserve_breach_week=(
            current.decision_metrics
            .first_reserve_breach_week
        ),
        variances=ordered_variances,
    )


class ActualCashObservation(BaseModel):
    """
    Realised cash evidence used for forecast monitoring.

    forecast_event_id is optional:
    - populated: explicitly links the actual to forecast evidence;
    - None: the actual is treated as previously unforecast cash.

    Matching is never inferred from amount, category or date.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    actual_id: str
    date: date

    amount: float

    direction: Literal[
        "INFLOW",
        "OUTFLOW",
    ]

    source_reference: str

    forecast_event_id: str | None = None

    @field_validator(
        "actual_id",
        "source_reference",
    )
    @classmethod
    def _require_actual_string(
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
        "forecast_event_id",
    )
    @classmethod
    def _clean_optional_event_id(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                "forecast_event_id must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "forecast_event_id must not be blank."
            )

        return cleaned

    @field_validator(
        "amount",
        mode="before",
    )
    @classmethod
    def _validate_actual_amount(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Actual amount must be numeric, "
                "not boolean."
            )

        numeric = float(value)

        if (
            numeric < 0.0
            or numeric != numeric
            or numeric in (
                float("inf"),
                float("-inf"),
            )
        ):
            raise ValueError(
                "Actual amount must be finite "
                "and nonnegative."
            )

        return value


class ForecastActualVarianceItem(BaseModel):
    """
    One forecast-versus-actual monitoring variance.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    forecast_event_id: str | None
    actual_ids: tuple[str, ...]

    category: ForecastVarianceCategory

    forecast_amount: float | None = None
    actual_amount: float | None = None

    forecast_effective_cash_date: str | None = None
    actual_dates: tuple[str, ...] = ()

    detail: str


class ForecastActualComparison(BaseModel):
    """
    Forecast-versus-actual monitoring through a stated date.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    snapshot_id: str
    through_date: date

    actual_inflows: float
    actual_outflows: float
    actual_net_cash: float

    variances: tuple[
        ForecastActualVarianceItem,
        ...,
    ] = ()


class WeeklyForecastRollForwardResult(BaseModel):
    """
    One completed weekly monitoring and reforecast cycle.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    prior_snapshot_id: str
    current_snapshot_id: str

    actual_comparison: ForecastActualComparison
    forecast_comparison: ForecastSnapshotComparison

    current_snapshot: DirectCashForecastSnapshot


def _forecast_contributions_by_event(
    snapshot: DirectCashForecastSnapshot,
):
    contributions = {}

    for week in snapshot.forecast.weeks:
        for contribution in week.contributions:
            contributions[
                contribution.event_id
            ] = contribution

    return contributions


def compare_forecast_to_actual(
    snapshot: DirectCashForecastSnapshot,
    actuals: tuple[
        ActualCashObservation,
        ...,
    ],
    *,
    through_date: date,
) -> ForecastActualComparison:
    """
    Compare one saved forecast with realised cash evidence.

    Rules:
    - links are explicit, never inferred;
    - timing differences remain TIMING;
    - amount differences on MODELLED cash are MODEL_ERROR;
    - amount differences on other evidence are AMOUNT;
    - unlinked actual cash is NEW_EVENT;
    - forecast cash due by through_date with no linked actual
      is MISSING_EVENT.
    """
    if through_date < snapshot.forecast_input.start_date:
        raise ValueError(
            "through_date cannot be before the "
            "forecast start date."
        )

    event_by_id = {
        event.event_id: event
        for event in (
            snapshot.forecast_input.events
        )
    }

    contribution_by_id = (
        _forecast_contributions_by_event(
            snapshot
        )
    )

    seen_actual_ids: set[str] = set()

    linked_actuals: dict[
        str,
        list[ActualCashObservation],
    ] = {}

    unlinked_actuals: list[
        ActualCashObservation
    ] = []

    for actual in actuals:
        if actual.actual_id in seen_actual_ids:
            raise ValueError(
                "Duplicate actual cash observation ID: "
                f"{actual.actual_id}"
            )

        seen_actual_ids.add(
            actual.actual_id
        )

        if (
            actual.date
            < snapshot.forecast_input.start_date
            or actual.date > through_date
        ):
            raise ValueError(
                "Actual cash observation falls outside "
                "the monitoring period."
            )

        if actual.forecast_event_id is None:
            unlinked_actuals.append(actual)
            continue

        forecast_event = event_by_id.get(
            actual.forecast_event_id
        )

        if forecast_event is None:
            raise ValueError(
                "Actual cash observation references "
                "unknown forecast event ID: "
                f"{actual.forecast_event_id}"
            )

        contribution = contribution_by_id.get(
            actual.forecast_event_id
        )

        if contribution is None:
            raise ValueError(
                "Linked forecast event has no included "
                "cash contribution in this snapshot: "
                f"{actual.forecast_event_id}"
            )

        if (
            actual.direction
            != forecast_event.direction
        ):
            raise ValueError(
                "Actual cash direction does not match "
                "the linked forecast event."
            )

        linked_actuals.setdefault(
            actual.forecast_event_id,
            [],
        ).append(actual)

    variances: list[
        ForecastActualVarianceItem
    ] = []

    for actual in sorted(
        unlinked_actuals,
        key=lambda item: (
            item.date,
            item.actual_id,
        ),
    ):
        variances.append(
            ForecastActualVarianceItem(
                forecast_event_id=None,
                actual_ids=(
                    actual.actual_id,
                ),
                category="NEW_EVENT",
                actual_amount=float(
                    actual.amount
                ),
                actual_dates=(
                    actual.date.isoformat(),
                ),
                detail=(
                    "Realised cash was observed without "
                    "an explicit forecast-event link."
                ),
            )
        )

    for event_id in sorted(
        contribution_by_id
    ):
        contribution = (
            contribution_by_id[event_id]
        )

        forecast_event = event_by_id[
            event_id
        ]

        linked = linked_actuals.get(
            event_id,
            [],
        )

        if not linked:
            if (
                contribution.effective_cash_date
                <= through_date
            ):
                variances.append(
                    ForecastActualVarianceItem(
                        forecast_event_id=event_id,
                        actual_ids=(),
                        category="MISSING_EVENT",
                        forecast_amount=float(
                            contribution
                            .included_amount
                        ),
                        forecast_effective_cash_date=(
                            contribution
                            .effective_cash_date
                            .isoformat()
                        ),
                        detail=(
                            "Forecast cash was expected by "
                            "the monitoring date but no "
                            "linked actual was supplied."
                        ),
                    )
                )

            continue

        linked = sorted(
            linked,
            key=lambda item: (
                item.date,
                item.actual_id,
            ),
        )

        actual_total = sum(
            float(actual.amount)
            for actual in linked
        )

        actual_dates = tuple(
            actual.date.isoformat()
            for actual in linked
        )

        forecast_amount = float(
            contribution.included_amount
        )

        timing_changed = any(
            actual.date
            != contribution.effective_cash_date
            for actual in linked
        )

        amount_changed = (
            abs(
                actual_total
                - forecast_amount
            )
            > 1e-9
        )

        if timing_changed:
            variances.append(
                ForecastActualVarianceItem(
                    forecast_event_id=event_id,
                    actual_ids=tuple(
                        actual.actual_id
                        for actual in linked
                    ),
                    category="TIMING",
                    forecast_amount=(
                        forecast_amount
                    ),
                    actual_amount=(
                        actual_total
                    ),
                    forecast_effective_cash_date=(
                        contribution
                        .effective_cash_date
                        .isoformat()
                    ),
                    actual_dates=actual_dates,
                    detail=(
                        "Realised cash timing differs "
                        "from forecast timing."
                    ),
                )
            )

        if amount_changed:
            category: ForecastVarianceCategory = (
                "MODEL_ERROR"
                if (
                    forecast_event.source_type
                    == "MODELLED"
                )
                else "AMOUNT"
            )

            variances.append(
                ForecastActualVarianceItem(
                    forecast_event_id=event_id,
                    actual_ids=tuple(
                        actual.actual_id
                        for actual in linked
                    ),
                    category=category,
                    forecast_amount=(
                        forecast_amount
                    ),
                    actual_amount=(
                        actual_total
                    ),
                    forecast_effective_cash_date=(
                        contribution
                        .effective_cash_date
                        .isoformat()
                    ),
                    actual_dates=actual_dates,
                    detail=(
                        "Realised cash amount differs "
                        "from the included forecast amount."
                    ),
                )
            )

    category_order = {
        "NEW_EVENT": 0,
        "MISSING_EVENT": 1,
        "TIMING": 2,
        "AMOUNT": 3,
        "ASSUMPTION_CHANGE": 4,
        "MODEL_ERROR": 5,
    }

    variances = sorted(
        variances,
        key=lambda item: (
            item.forecast_event_id or "",
            category_order[
                item.category
            ],
            item.actual_ids,
        ),
    )

    actual_inflows = sum(
        float(actual.amount)
        for actual in actuals
        if actual.direction == "INFLOW"
    )

    actual_outflows = sum(
        float(actual.amount)
        for actual in actuals
        if actual.direction == "OUTFLOW"
    )

    return ForecastActualComparison(
        snapshot_id=snapshot.snapshot_id,
        through_date=through_date,
        actual_inflows=float(
            actual_inflows
        ),
        actual_outflows=float(
            actual_outflows
        ),
        actual_net_cash=float(
            actual_inflows
            - actual_outflows
        ),
        variances=tuple(
            variances
        ),
    )


def roll_forward_forecast(
    prior: DirectCashForecastSnapshot,
    *,
    new_start_date: date,
    actual_opening_cash: float,
    actual_observations: tuple[
        ActualCashObservation,
        ...,
    ],
    future_events: tuple[
        CashEvent,
        ...,
    ],
    coverage_allocations: tuple[
        CashCoverageAllocation,
        ...,
    ] = (),
    snapshot_id: str,
    created_at: datetime,
    management_reserve: float | None = None,
) -> WeeklyForecastRollForwardResult:
    """
    Close one forecast week and create the next 13-week forecast.

    The function does NOT infer how unresolved events should move.
    The caller must provide the updated future-event evidence
    explicitly.

    actual_opening_cash becomes the new known opening cash.
    """
    expected_new_start = (
        prior.forecast_input.start_date
        + timedelta(days=7)
    )

    if new_start_date != expected_new_start:
        raise ValueError(
            "Weekly roll-forward must advance "
            "start_date by exactly 7 days."
        )

    through_date = (
        new_start_date
        - timedelta(days=1)
    )

    actual_comparison = (
        compare_forecast_to_actual(
            prior,
            actual_observations,
            through_date=through_date,
        )
    )

    reserve = (
        prior.decision_metrics
        .management_reserve
        if management_reserve is None
        else management_reserve
    )

    current_input = (
        DirectCashForecastInput(
            start_date=new_start_date,
            opening_cash=actual_opening_cash,
            events=future_events,
            coverage_allocations=(
                coverage_allocations
            ),
        )
    )

    current_snapshot = (
        create_forecast_snapshot(
            current_input,
            snapshot_id=snapshot_id,
            created_at=created_at,
            management_reserve=reserve,
        )
    )

    forecast_comparison = (
        compare_forecast_snapshots(
            prior,
            current_snapshot,
        )
    )

    return WeeklyForecastRollForwardResult(
        prior_snapshot_id=(
            prior.snapshot_id
        ),
        current_snapshot_id=(
            current_snapshot.snapshot_id
        ),
        actual_comparison=(
            actual_comparison
        ),
        forecast_comparison=(
            forecast_comparison
        ),
        current_snapshot=(
            current_snapshot
        ),
    )
