from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.core.cash_events import CashEvent
from src.core.direct_cash import DirectCashForecastInput
from src.core.recovery_constraints import (
    CostReductionConstraint,
    ExternalLiquidityConstraint,
    ReceivableAccelerationConstraint,
    RecoveryConstraintSet,
    RevenueImprovementConstraint,
)
from src.core.recovery_engine import RecoveryPlan
from src.core.weekly_uncertainty import (
    ModelledCashErrorSample,
    WeeklyUncertaintyProfile,
)


class V2DemoScenario(BaseModel):
    """
    Self-contained synthetic business scenario for the
    RiskPilot V2 Command Center.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    scenario_id: str
    name: str
    description: str

    management_reserve: float = Field(
        ge=0.0,
    )

    max_reserve_breach_probability: float = Field(
        gt=0.0,
        lt=0.5,
    )

    forecast_input: DirectCashForecastInput
    uncertainty_profile: WeeklyUncertaintyProfile

    recovery_constraints: RecoveryConstraintSet | None = None
    recovery_plan: RecoveryPlan | None = None

    @model_validator(mode="after")
    def _validate_recovery_pair(self):
        if (
            self.recovery_constraints is None
        ) != (
            self.recovery_plan is None
        ):
            raise ValueError(
                "recovery_constraints and recovery_plan "
                "must be provided together."
            )

        return self


_START_DATE = date(2026, 10, 5)


def _weekly_events(
    prefix: str,
    weekly_values: tuple[
        tuple[
            float,
            float,
            float,
            float,
        ],
        ...,
    ],
) -> tuple[CashEvent, ...]:
    """
    Each weekly tuple is:

    (
        committed_inflow,
        modelled_inflow,
        committed_outflow,
        modelled_outflow,
    )
    """
    events: list[CashEvent] = []

    for index, values in enumerate(
        weekly_values
    ):
        week = index + 1

        (
            committed_inflow,
            modelled_inflow,
            committed_outflow,
            modelled_outflow,
        ) = values

        base_date = (
            _START_DATE
            + timedelta(days=index * 7)
        )

        if committed_inflow > 0.0:
            events.append(
                CashEvent(
                    event_id=(
                        f"{prefix}-w{week}-"
                        "committed-in"
                    ),
                    date=base_date + timedelta(days=1),
                    amount=committed_inflow,
                    direction="INFLOW",
                    category="customer receipts",
                    source_type="COMMITTED",
                    status="ACTIVE",
                    source_reference=(
                        f"{prefix}-invoice-ledger"
                    ),
                )
            )

        if modelled_inflow > 0.0:
            events.append(
                CashEvent(
                    event_id=(
                        f"{prefix}-w{week}-"
                        "modelled-in"
                    ),
                    date=base_date + timedelta(days=2),
                    amount=modelled_inflow,
                    direction="INFLOW",
                    category="residual sales receipts",
                    source_type="MODELLED",
                    status="ACTIVE",
                    source_reference=(
                        f"{prefix}-sales-model"
                    ),
                )
            )

        if committed_outflow > 0.0:
            events.append(
                CashEvent(
                    event_id=(
                        f"{prefix}-w{week}-"
                        "committed-out"
                    ),
                    date=base_date + timedelta(days=3),
                    amount=committed_outflow,
                    direction="OUTFLOW",
                    category="payroll and suppliers",
                    source_type="COMMITTED",
                    status="ACTIVE",
                    source_reference=(
                        f"{prefix}-payables-ledger"
                    ),
                )
            )

        if modelled_outflow > 0.0:
            events.append(
                CashEvent(
                    event_id=(
                        f"{prefix}-w{week}-"
                        "modelled-out"
                    ),
                    date=base_date + timedelta(days=4),
                    amount=modelled_outflow,
                    direction="OUTFLOW",
                    category="variable operating costs",
                    source_type="MODELLED",
                    status="ACTIVE",
                    source_reference=(
                        f"{prefix}-cost-model"
                    ),
                )
            )

    return tuple(events)


def _errors(
    values: tuple[
        tuple[float, float],
        ...,
    ],
) -> WeeklyUncertaintyProfile:
    return WeeklyUncertaintyProfile(
        modelled_flow_error_samples=tuple(
            ModelledCashErrorSample(
                inflow_error_pct=inflow,
                outflow_error_pct=outflow,
            )
            for inflow, outflow in values
        )
    )


def _public_liquidity_events(
    prefix: str,
    weekly_liquidity: tuple[float, ...],
) -> tuple[CashEvent, ...]:
    """
    Convert a disclosed weekly liquidity path into deterministic
    weekly liquidity-movement events.

    These events are intentionally classified as MODELLED because
    the public source is a management forecast / DIP budget, not
    RiskPilot-verified committed bank evidence.

    This preserves provenance honesty:
    - source liquidity path: public filing
    - RiskPilot reserve policy: illustrative
    - RiskPilot uncertainty overlay: illustrative
    """
    if not weekly_liquidity:
        return ()

    events: list[CashEvent] = []

    previous = weekly_liquidity[0]

    # W1 equals the disclosed starting liquidity used by the
    # forecast input, so no artificial W1 movement is created.
    for index, closing_liquidity in enumerate(
        weekly_liquidity[1:],
        start=1,
    ):
        delta = closing_liquidity - previous

        if delta != 0.0:
            events.append(
                CashEvent(
                    event_id=(
                        f"{prefix}-w{index + 1}-"
                        "public-liquidity-movement"
                    ),
                    date=(
                        _START_DATE
                        + timedelta(days=index * 7 + 3)
                    ),
                    amount=abs(delta),
                    direction=(
                        "INFLOW"
                        if delta > 0.0
                        else "OUTFLOW"
                    ),
                    category=(
                        "public SEC liquidity movement"
                    ),
                    source_type="MODELLED",
                    status="ACTIVE",
                    source_reference=(
                        "Cenveo-2018-SEC-Exhibit-99.4"
                    ),
                )
            )

        previous = closing_liquidity

    return tuple(events)


def _public_sec_restructuring() -> V2DemoScenario:
    """
    Public real-world demonstration case.

    Source:
    Cenveo, Inc. 2018 publicly filed 13-week DIP budget,
    SEC Exhibit 99.4, accession 0001193125-18-030024.

    The disclosed LIQUIDITY row is used as the deterministic
    weekly path, expressed in dollars rather than the filing's
    $000 presentation.

    IMPORTANT:
    - The public liquidity path is source data.
    - The $20m liquidity reference is sourced from the
      related restructuring materials.
    - The uncertainty profile is a RiskPilot demo overlay.
    - RiskPilot's breach probability and uncertainty overlay
      remain illustrative analysis layers and are not attributed
      to Cenveo management.
    """

    liquidity_thousands = (
        26749.0,
        21120.0,
        17393.0,
        9315.0,
        53229.0,
        56960.0,
        104966.0,
        106507.0,
        92176.0,
        87969.0,
        92041.0,
        119004.0,
        122706.0,
    )

    liquidity = tuple(
        value * 1000.0
        for value in liquidity_thousands
    )

    return V2DemoScenario(
        scenario_id="public_sec_cenveo",
        name="Public SEC Restructuring Case",
        description=(
            "Real 13-week public liquidity path from Cenveo's "
            "2018 SEC-filed DIP budget, evaluated against the "
            "$20m minimum-liquidity reference disclosed in the "
            "related restructuring materials."
        ),
        management_reserve=25000000.0,
        max_reserve_breach_probability=0.10,
        forecast_input=DirectCashForecastInput(
            start_date=_START_DATE,
            opening_cash=liquidity[0],
            events=_public_liquidity_events(
                "public-sec-cenveo",
                liquidity,
            ),
        ),
        uncertainty_profile=_errors(
            (
                (-0.15, 0.12),
                (-0.12, 0.10),
                (-0.10, 0.08),
                (-0.08, 0.06),
                (-0.05, 0.05),
                (-0.02, 0.02),
                (0.00, 0.00),
                (0.03, -0.02),
                (0.06, -0.04),
                (0.10, -0.06),
            )
        ),
    )


def _healthy() -> V2DemoScenario:
    weekly = tuple(
        (
            25000.0,
            5000.0,
            15000.0,
            5000.0,
        )
        for _ in range(13)
    )

    return V2DemoScenario(
        scenario_id="healthy",
        name="Healthy Business",
        description=(
            "Strong liquidity, predominantly committed cash "
            "evidence and substantial reserve headroom."
        ),
        management_reserve=40000.0,
        max_reserve_breach_probability=0.10,
        forecast_input=DirectCashForecastInput(
            start_date=_START_DATE,
            opening_cash=120000.0,
            events=_weekly_events(
                "healthy",
                weekly,
            ),
        ),
        uncertainty_profile=_errors(
            (
                (-0.05, 0.04),
                (-0.03, 0.02),
                (-0.02, 0.01),
                (-0.01, 0.02),
                (0.00, 0.00),
                (0.01, -0.01),
                (0.02, 0.01),
                (0.03, -0.02),
                (0.04, -0.02),
                (0.05, -0.03),
            )
        ),
    )


def _stressed_recoverable() -> V2DemoScenario:
    stressed_weeks = (
        (
            10000.0,
            5000.0,
            15000.0,
            10000.0,
        ),
    ) * 3

    recovery_weeks = (
        (
            20000.0,
            5000.0,
            15000.0,
            5000.0,
        ),
    ) * 10

    return V2DemoScenario(
        scenario_id="stressed_recoverable",
        name="Stressed Recoverable Business",
        description=(
            "Near-term cash pressure creates a reserve breach, "
            "but the gap is moderate and intended for recovery "
            "planning and management-action demonstration."
        ),
        management_reserve=40000.0,
        max_reserve_breach_probability=0.10,
        forecast_input=DirectCashForecastInput(
            start_date=_START_DATE,
            opening_cash=65000.0,
            events=_weekly_events(
                "stressed",
                stressed_weeks
                + recovery_weeks,
            ),
        ),
        uncertainty_profile=_errors(
            (
                (-0.12, 0.10),
                (-0.10, 0.08),
                (-0.08, 0.08),
                (-0.05, 0.05),
                (-0.03, 0.03),
                (0.00, 0.00),
                (0.02, 0.02),
                (0.03, -0.01),
                (0.05, -0.02),
                (0.06, -0.03),
            )
        ),
        recovery_constraints=RecoveryConstraintSet(
            revenue_improvement=RevenueImprovementConstraint(
                enabled=False,
                max_improvement_pct=0.0,
                available_from=_START_DATE,
            ),
            cost_reduction=CostReductionConstraint(
                enabled=False,
                max_reduction_pct=0.0,
                available_from=_START_DATE,
            ),
            receivable_acceleration=ReceivableAccelerationConstraint(
                enabled=False,
                max_acceleration_days=0,
                available_from=_START_DATE,
            ),
            external_liquidity=ExternalLiquidityConstraint(
                enabled=True,
                max_amount=15000.0,
                available_from=_START_DATE,
            ),
        ),
        recovery_plan=RecoveryPlan(
            external_liquidity=10000.0,
        ),
    )


def _severe_uncertain() -> V2DemoScenario:
    first_week = (
        (
            5000.0,
            15000.0,
            5000.0,
            17000.0,
        ),
    )

    later_weeks = (
        (
            5000.0,
            15000.0,
            5000.0,
            13000.0,
        ),
    ) * 12

    return V2DemoScenario(
        scenario_id="severe_uncertain",
        name="Severe Uncertain Business",
        description=(
            "The deterministic forecast narrowly preserves the "
            "cash reserve, but modelled cash uncertainty creates "
            "meaningful downside risk."
        ),
        management_reserve=40000.0,
        max_reserve_breach_probability=0.10,
        forecast_input=DirectCashForecastInput(
            start_date=_START_DATE,
            opening_cash=45000.0,
            events=_weekly_events(
                "severe",
                first_week
                + later_weeks,
            ),
        ),
        uncertainty_profile=_errors(
            (
                (-0.25, 0.20),
                (-0.20, 0.15),
                (-0.15, 0.10),
                (-0.10, 0.08),
                (-0.05, 0.05),
                (0.00, 0.00),
                (0.03, -0.02),
                (0.05, -0.03),
                (0.08, -0.05),
                (0.10, -0.05),
            )
        ),
        recovery_constraints=RecoveryConstraintSet(
            revenue_improvement=RevenueImprovementConstraint(
                enabled=False,
                max_improvement_pct=0.0,
                available_from=_START_DATE,
            ),
            cost_reduction=CostReductionConstraint(
                enabled=False,
                max_reduction_pct=0.0,
                available_from=_START_DATE,
            ),
            receivable_acceleration=ReceivableAccelerationConstraint(
                enabled=False,
                max_acceleration_days=0,
                available_from=_START_DATE,
            ),
            external_liquidity=ExternalLiquidityConstraint(
                enabled=False,
                max_amount=0.0,
                available_from=_START_DATE,
            ),
        ),
        recovery_plan=RecoveryPlan(),
    )


def get_v2_demo_scenarios(
) -> tuple[V2DemoScenario, ...]:
    return (
        _healthy(),
        _stressed_recoverable(),
        _severe_uncertain(),
        _public_sec_restructuring(),
    )


def get_v2_demo_scenario(
    scenario_id: str,
) -> V2DemoScenario:
    for scenario in get_v2_demo_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario

    raise ValueError(
        "Unknown V2 demo scenario: "
        f"{scenario_id}"
    )
