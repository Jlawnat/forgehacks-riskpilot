from __future__ import annotations

from datetime import timedelta

import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from src.core.direct_cash import (
    DIRECT_CASH_HORIZON_WEEKS,
    DirectCashForecastInput,
    build_direct_cash_forecast,
)
from src.core.weekly_uncertainty import (
    WeeklyUncertaintyProfile,
    validate_weekly_uncertainty_profile,
)


class WeeklySimulationConfig(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    simulations: int = Field(
        default=5000,
        ge=100,
        le=50000,
    )

    seed: int = 42

    cash_floor: float = Field(
        default=0.0,
        allow_inf_nan=False,
    )

    confidence_level: float = Field(
        default=0.95,
        gt=0.5,
        lt=1.0,
    )

    @field_validator(
        "simulations",
        "seed",
        mode="before",
    )
    @classmethod
    def _reject_boolean_integer(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Integer simulation settings must "
                "not be boolean."
            )

        return value

    @field_validator(
        "cash_floor",
        "confidence_level",
        mode="before",
    )
    @classmethod
    def _reject_boolean_float(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, bool):
            raise ValueError(
                "Simulation settings must be "
                "numeric, not boolean."
            )

        return value



class WeeklyCashInjection(BaseModel):
    """
    Deterministic liquidity overlay applied to a simulation week.

    This is deliberately separate from the underlying CashEvent
    evidence set.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    week_number: int = Field(
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    amount: float = Field(
        ge=0.0,
        allow_inf_nan=False,
    )

    source_reference: str

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
                "Cash injection amount must be numeric, "
                "not boolean."
            )

        return value

    @field_validator(
        "source_reference",
    )
    @classmethod
    def _require_reference(
        cls,
        value: str,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "source_reference must be a string."
            )

        cleaned = value.strip()

        if not cleaned:
            raise ValueError(
                "source_reference must not be blank."
            )

        return cleaned


class WeeklyCashQuantilePoint(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    week_number: int = Field(
        ge=1,
        le=DIRECT_CASH_HORIZON_WEEKS,
    )

    p10_cash: float
    p50_cash: float
    p90_cash: float

    shortfall_probability: float = Field(
        ge=0.0,
        le=1.0,
    )


class WeeklyLiquiditySimulationResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    inputs: WeeklySimulationConfig

    simulations: int

    modelled_error_samples_available: int = Field(
        ge=0,
    )

    committed_timing_events_modelled: int = Field(
        ge=0,
    )

    shortfall_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    first_week_shortfall_probability: float = Field(
        ge=0.0,
        le=1.0,
    )

    median_end_cash: float
    p10_end_cash: float
    p90_end_cash: float

    median_min_cash: float
    p10_min_cash: float

    liquidity_buffer_at_confidence: float = Field(
        ge=0.0,
    )

    expected_tail_buffer: float = Field(
        ge=0.0,
    )

    cash_path_quantiles: tuple[
        WeeklyCashQuantilePoint,
        ...,
    ]

    limitations: tuple[str, ...] = ()


def _modelled_residual_amounts(
    forecast_input: DirectCashForecastInput,
) -> dict[str, float]:
    coverage_by_model: dict[str, float] = {}

    for allocation in (
        forecast_input.coverage_allocations
    ):
        model_id = allocation.modelled_event_id

        coverage_by_model[model_id] = (
            coverage_by_model.get(
                model_id,
                0.0,
            )
            + float(allocation.amount)
        )

    residuals: dict[str, float] = {}

    for event in forecast_input.events:
        if event.source_type != "MODELLED":
            continue

        residuals[event.event_id] = max(
            0.0,
            float(event.amount)
            - coverage_by_model.get(
                event.event_id,
                0.0,
            ),
        )

    return residuals


def _week_index(
    *,
    event_date,
    start_date,
) -> int | None:
    days_from_start = (
        event_date - start_date
    ).days

    if days_from_start < 0:
        return None

    if (
        days_from_start
        >= DIRECT_CASH_HORIZON_WEEKS * 7
    ):
        return None

    return days_from_start // 7


def _limitations(
    profile: WeeklyUncertaintyProfile,
) -> tuple[str, ...]:
    messages: list[str] = []

    modelled_count = len(
        profile.modelled_flow_error_samples
    )

    if 0 < modelled_count < 10:
        messages.append(
            "Only "
            f"{modelled_count} paired modelled cash-error "
            "samples are available; empirical bootstrap "
            "uncertainty is small-sample."
        )

    timing_counts = [
        len(
            item.timing_shift_days_samples
        )
        for item in (
            profile
            .committed_timing_uncertainty
        )
    ]

    if (
        timing_counts
        and min(timing_counts) < 10
    ):
        messages.append(
            "At least one committed-event timing "
            "distribution has fewer than 10 empirical "
            "observations; timing uncertainty is "
            "small-sample."
        )

    return tuple(messages)


def simulate_weekly_liquidity(
    forecast_input: DirectCashForecastInput,
    uncertainty_profile: WeeklyUncertaintyProfile,
    config: WeeklySimulationConfig | None = None,
    *,
    cash_injections: tuple[
        WeeklyCashInjection,
        ...,
    ] = (),
) -> WeeklyLiquiditySimulationResult:
    """
    Run Monte Carlo analysis on the 13-week direct cash model.

    MODELLED cash:
        paired relative inflow/outflow errors are resampled
        independently by forecast week.

    COMMITTED cash:
        only explicitly supplied event-level timing
        distributions are resampled.

    MANAGEMENT_ASSUMPTION cash:
        deterministic in this phase.

    ACTUAL, SETTLED and CANCELLED cash:
        excluded from future cash, consistent with the
        deterministic direct-cash engine.
    """
    simulation = (
        config
        if config is not None
        else WeeklySimulationConfig()
    )

    validate_weekly_uncertainty_profile(
        forecast_input,
        uncertainty_profile,
    )

    # Also enforce all deterministic direct-cash timing and
    # reconciliation rules before simulation.
    build_direct_cash_forecast(
        forecast_input
    )

    simulations = simulation.simulations

    weekly_inflows = np.zeros(
        (
            simulations,
            DIRECT_CASH_HORIZON_WEEKS,
        ),
        dtype=float,
    )

    weekly_outflows = np.zeros(
        (
            simulations,
            DIRECT_CASH_HORIZON_WEEKS,
        ),
        dtype=float,
    )

    residuals = _modelled_residual_amounts(
        forecast_input
    )

    modelled_inflows = np.zeros(
        DIRECT_CASH_HORIZON_WEEKS,
        dtype=float,
    )

    modelled_outflows = np.zeros(
        DIRECT_CASH_HORIZON_WEEKS,
        dtype=float,
    )

    timing_by_event = {
        item.event_id: item
        for item in (
            uncertainty_profile
            .committed_timing_uncertainty
        )
    }

    rng = np.random.default_rng(
        simulation.seed
    )

    for event in forecast_input.events:
        if event.source_type == "ACTUAL":
            continue

        if event.status != "ACTIVE":
            continue

        if event.source_type == "MODELLED":
            week_index = _week_index(
                event_date=(
                    event.effective_cash_date
                ),
                start_date=(
                    forecast_input.start_date
                ),
            )

            if week_index is None:
                continue

            amount = residuals[
                event.event_id
            ]

            if event.direction == "INFLOW":
                modelled_inflows[
                    week_index
                ] += amount
            else:
                modelled_outflows[
                    week_index
                ] += amount

            continue

        if event.source_type == "COMMITTED":
            timing = timing_by_event.get(
                event.event_id
            )

            if timing is None:
                week_index = _week_index(
                    event_date=(
                        event.effective_cash_date
                    ),
                    start_date=(
                        forecast_input.start_date
                    ),
                )

                if week_index is None:
                    continue

                target = (
                    weekly_inflows
                    if event.direction == "INFLOW"
                    else weekly_outflows
                )

                target[:, week_index] += float(
                    event.amount
                )

                continue

            samples = np.asarray(
                timing.timing_shift_days_samples,
                dtype=int,
            )

            selected = rng.integers(
                0,
                len(samples),
                size=simulations,
            )

            shifts = samples[selected]

            for path_index, shift in enumerate(
                shifts
            ):
                shifted_date = (
                    event.effective_cash_date
                    + timedelta(
                        days=int(shift)
                    )
                )

                # A future commitment cannot be simulated
                # as occurring before the known opening-cash
                # position. Clamp earlier draws to week 1.
                shifted_date = max(
                    shifted_date,
                    forecast_input.start_date,
                )

                week_index = _week_index(
                    event_date=shifted_date,
                    start_date=(
                        forecast_input.start_date
                    ),
                )

                if week_index is None:
                    continue

                target = (
                    weekly_inflows
                    if event.direction == "INFLOW"
                    else weekly_outflows
                )

                target[
                    path_index,
                    week_index,
                ] += float(
                    event.amount
                )

            continue

        if (
            event.source_type
            == "MANAGEMENT_ASSUMPTION"
        ):
            week_index = _week_index(
                event_date=(
                    event.effective_cash_date
                ),
                start_date=(
                    forecast_input.start_date
                ),
            )

            if week_index is None:
                continue

            target = (
                weekly_inflows
                if event.direction == "INFLOW"
                else weekly_outflows
            )

            target[:, week_index] += float(
                event.amount
            )

    error_samples = (
        uncertainty_profile
        .modelled_flow_error_samples
    )

    if error_samples:
        pairs = np.asarray(
            [
                (
                    sample.inflow_error_pct,
                    sample.outflow_error_pct,
                )
                for sample in error_samples
            ],
            dtype=float,
        )

        selected_indices = rng.integers(
            0,
            len(pairs),
            size=(
                simulations,
                DIRECT_CASH_HORIZON_WEEKS,
            ),
        )

        sampled_errors = pairs[
            selected_indices
        ]

        inflow_factors = np.maximum(
            0.0,
            1.0
            + sampled_errors[:, :, 0],
        )

        outflow_factors = np.maximum(
            0.0,
            1.0
            + sampled_errors[:, :, 1],
        )

        weekly_inflows += (
            modelled_inflows[None, :]
            * inflow_factors
        )

        weekly_outflows += (
            modelled_outflows[None, :]
            * outflow_factors
        )
    else:
        weekly_inflows += (
            modelled_inflows[None, :]
        )

        weekly_outflows += (
            modelled_outflows[None, :]
        )

    for injection in cash_injections:
        weekly_inflows[
            :,
            injection.week_number - 1,
        ] += float(
            injection.amount
        )

    weekly_net_cash = (
        weekly_inflows
        - weekly_outflows
    )

    cash_paths = (
        float(forecast_input.opening_cash)
        + np.cumsum(
            weekly_net_cash,
            axis=1,
        )
    )

    shortfall_matrix = (
        cash_paths
        < simulation.cash_floor
    )

    any_shortfall = np.any(
        shortfall_matrix,
        axis=1,
    )

    shortfall_probability = float(
        np.mean(any_shortfall)
    )

    first_week_shortfall_probability = float(
        np.mean(
            shortfall_matrix[:, 0]
        )
    )

    min_cash_by_path = np.min(
        cash_paths,
        axis=1,
    )

    end_cash = cash_paths[:, -1]

    required_buffer_by_path = np.maximum(
        0.0,
        simulation.cash_floor
        - min_cash_by_path,
    )

    buffer_at_confidence = float(
        np.quantile(
            required_buffer_by_path,
            simulation.confidence_level,
        )
    )

    tail_mask = (
        required_buffer_by_path
        >= buffer_at_confidence
    )

    expected_tail_buffer = (
        float(
            np.mean(
                required_buffer_by_path[
                    tail_mask
                ]
            )
        )
        if np.any(tail_mask)
        else 0.0
    )

    quantiles: list[
        WeeklyCashQuantilePoint
    ] = []

    for week_index in range(
        DIRECT_CASH_HORIZON_WEEKS
    ):
        period_cash = cash_paths[
            :,
            week_index,
        ]

        quantiles.append(
            WeeklyCashQuantilePoint(
                week_number=week_index + 1,
                p10_cash=float(
                    np.quantile(
                        period_cash,
                        0.10,
                    )
                ),
                p50_cash=float(
                    np.quantile(
                        period_cash,
                        0.50,
                    )
                ),
                p90_cash=float(
                    np.quantile(
                        period_cash,
                        0.90,
                    )
                ),
                shortfall_probability=float(
                    np.mean(
                        period_cash
                        < simulation.cash_floor
                    )
                ),
            )
        )

    return WeeklyLiquiditySimulationResult(
        inputs=simulation,
        simulations=simulations,
        modelled_error_samples_available=(
            len(error_samples)
        ),
        committed_timing_events_modelled=(
            len(timing_by_event)
        ),
        shortfall_probability=(
            shortfall_probability
        ),
        first_week_shortfall_probability=(
            first_week_shortfall_probability
        ),
        median_end_cash=float(
            np.quantile(
                end_cash,
                0.50,
            )
        ),
        p10_end_cash=float(
            np.quantile(
                end_cash,
                0.10,
            )
        ),
        p90_end_cash=float(
            np.quantile(
                end_cash,
                0.90,
            )
        ),
        median_min_cash=float(
            np.quantile(
                min_cash_by_path,
                0.50,
            )
        ),
        p10_min_cash=float(
            np.quantile(
                min_cash_by_path,
                0.10,
            )
        ),
        liquidity_buffer_at_confidence=(
            buffer_at_confidence
        ),
        expected_tail_buffer=(
            expected_tail_buffer
        ),
        cash_path_quantiles=tuple(
            quantiles
        ),
        limitations=_limitations(
            uncertainty_profile
        ),
    )
