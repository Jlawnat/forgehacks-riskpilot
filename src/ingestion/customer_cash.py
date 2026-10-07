from __future__ import annotations

from io import BytesIO
from datetime import date, timedelta
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from src.core.cash_events import CashEvent
from src.core.direct_cash import DirectCashForecastInput
from src.core.weekly_uncertainty import (
    ModelledCashErrorSample,
    WeeklyUncertaintyProfile,
)
from src.demo.v2_scenarios import V2DemoScenario


REQUIRED_COLUMNS = {
    "date",
    "amount",
    "direction",
    "category",
    "source_type",
}

OPTIONAL_COLUMNS = {
    "event_id",
    "status",
    "description",
    "source_reference",
    "due_date",
    "expected_cash_date",
}

ALLOWED_DIRECTIONS = {
    "INFLOW",
    "OUTFLOW",
}

ALLOWED_SOURCE_TYPES = {
    "COMMITTED",
    "MODELLED",
    "MANAGEMENT_ASSUMPTION",
}

ALLOWED_STATUSES = {
    "ACTIVE",
    "SETTLED",
    "CANCELLED",
}


class CustomerCashImportReport(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    rows_loaded: int = Field(ge=0)
    active_events: int = Field(ge=0)

    committed_events: int = Field(ge=0)
    modelled_events: int = Field(ge=0)
    management_assumption_events: int = Field(ge=0)

    inflow_events: int = Field(ge=0)
    outflow_events: int = Field(ge=0)

    forecast_horizon_events: int = Field(ge=0)
    outside_horizon_events: int = Field(ge=0)

    warnings: tuple[str, ...] = ()


def _clean_column_name(value: object) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )


def parse_customer_cash_csv(
    data: bytes,
) -> pd.DataFrame:
    if not data:
        raise ValueError(
            "Uploaded CSV is empty."
        )

    try:
        df = pd.read_csv(
            BytesIO(data)
        )
    except Exception as exc:
        raise ValueError(
            "The uploaded file could not be read as CSV."
        ) from exc

    if df.empty:
        raise ValueError(
            "Uploaded CSV contains no rows."
        )

    df = df.copy()

    df.columns = [
        _clean_column_name(column)
        for column in df.columns
    ]

    missing = (
        REQUIRED_COLUMNS
        - set(df.columns)
    )

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(
                sorted(missing)
            )
        )

    unexpected = (
        set(df.columns)
        - REQUIRED_COLUMNS
        - OPTIONAL_COLUMNS
    )

    if unexpected:
        raise ValueError(
            "Unsupported columns: "
            + ", ".join(
                sorted(unexpected)
            )
        )

    return df


def _optional_date(
    value: object,
    *,
    field_name: str,
    row_number: int,
) -> date | None:
    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    parsed = pd.to_datetime(
        text,
        errors="coerce",
    )

    if pd.isna(parsed):
        raise ValueError(
            f"Row {row_number}: "
            f"{field_name} could not be parsed."
        )

    return parsed.date()


def _required_date(
    value: object,
    *,
    row_number: int,
) -> date:
    result = _optional_date(
        value,
        field_name="date",
        row_number=row_number,
    )

    if result is None:
        raise ValueError(
            f"Row {row_number}: date is required."
        )

    return result


def _required_amount(
    value: object,
    *,
    row_number: int,
) -> float:
    try:
        amount = float(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"Row {row_number}: "
            "amount must be numeric."
        ) from exc

    if (
        not pd.notna(amount)
        or amount < 0.0
    ):
        raise ValueError(
            f"Row {row_number}: "
            "amount must be non-negative."
        )

    return amount


def _required_text(
    value: object,
    *,
    field_name: str,
    row_number: int,
) -> str:
    if pd.isna(value):
        raise ValueError(
            f"Row {row_number}: "
            f"{field_name} is required."
        )

    text = str(value).strip()

    if not text:
        raise ValueError(
            f"Row {row_number}: "
            f"{field_name} is required."
        )

    return text


def build_customer_cash_events(
    df: pd.DataFrame,
    *,
    upload_reference: str,
) -> tuple[CashEvent, ...]:
    events: list[CashEvent] = []

    event_ids: set[str] = set()

    for index, row in df.iterrows():
        row_number = index + 2

        event_id_value = row.get(
            "event_id"
        )

        if (
            event_id_value is None
            or pd.isna(event_id_value)
            or not str(
                event_id_value
            ).strip()
        ):
            event_id = (
                f"customer-upload-"
                f"{index + 1:04d}"
            )
        else:
            event_id = str(
                event_id_value
            ).strip()

        if event_id in event_ids:
            raise ValueError(
                f"Row {row_number}: "
                f"duplicate event_id "
                f"'{event_id}'."
            )

        event_ids.add(event_id)

        direction = _required_text(
            row["direction"],
            field_name="direction",
            row_number=row_number,
        ).upper()

        if (
            direction
            not in ALLOWED_DIRECTIONS
        ):
            raise ValueError(
                f"Row {row_number}: direction "
                "must be INFLOW or OUTFLOW."
            )

        source_type = _required_text(
            row["source_type"],
            field_name="source_type",
            row_number=row_number,
        ).upper()

        if (
            source_type
            not in ALLOWED_SOURCE_TYPES
        ):
            raise ValueError(
                f"Row {row_number}: source_type "
                "must be COMMITTED, MODELLED or "
                "MANAGEMENT_ASSUMPTION."
            )

        status_raw = row.get(
            "status",
            "ACTIVE",
        )

        if (
            pd.isna(status_raw)
            or not str(
                status_raw
            ).strip()
        ):
            status = "ACTIVE"
        else:
            status = str(
                status_raw
            ).strip().upper()

        if (
            status
            not in ALLOWED_STATUSES
        ):
            raise ValueError(
                f"Row {row_number}: status "
                "must be ACTIVE, SETTLED or CANCELLED."
            )

        description_raw = row.get(
            "description"
        )

        description = (
            None
            if (
                description_raw is None
                or pd.isna(
                    description_raw
                )
                or not str(
                    description_raw
                ).strip()
            )
            else str(
                description_raw
            ).strip()
        )

        source_reference_raw = row.get(
            "source_reference"
        )

        source_reference = (
            upload_reference
            if (
                source_reference_raw is None
                or pd.isna(
                    source_reference_raw
                )
                or not str(
                    source_reference_raw
                ).strip()
            )
            else str(
                source_reference_raw
            ).strip()
        )

        events.append(
            CashEvent(
                event_id=event_id,
                date=_required_date(
                    row["date"],
                    row_number=row_number,
                ),
                amount=_required_amount(
                    row["amount"],
                    row_number=row_number,
                ),
                direction=direction,
                category=_required_text(
                    row["category"],
                    field_name="category",
                    row_number=row_number,
                ),
                source_type=source_type,
                status=status,
                description=description,
                source_reference=(
                    source_reference
                ),
                due_date=_optional_date(
                    row.get("due_date"),
                    field_name="due_date",
                    row_number=row_number,
                ),
                expected_cash_date=(
                    _optional_date(
                        row.get(
                            "expected_cash_date"
                        ),
                        field_name=(
                            "expected_cash_date"
                        ),
                        row_number=(
                            row_number
                        ),
                    )
                ),
            )
        )

    return tuple(events)


def build_customer_import_report(
    events: tuple[CashEvent, ...],
    *,
    forecast_start: date,
) -> CustomerCashImportReport:
    horizon_end = (
        forecast_start
        + timedelta(days=13 * 7)
    )

    warnings: list[str] = []

    active = tuple(
        event
        for event in events
        if event.status == "ACTIVE"
    )

    before_start = tuple(
        event
        for event in active
        if (
            event.effective_cash_date
            < forecast_start
        )
    )

    if before_start:
        raise ValueError(
            f"{len(before_start)} active cash "
            "event(s) fall before the forecast "
            "start date. Update their expected "
            "cash dates or remove them."
        )

    in_horizon = tuple(
        event
        for event in active
        if (
            forecast_start
            <= event.effective_cash_date
            < horizon_end
        )
    )

    outside = tuple(
        event
        for event in active
        if (
            event.effective_cash_date
            >= horizon_end
        )
    )

    if outside:
        warnings.append(
            f"{len(outside)} active event(s) fall "
            "outside the 13-week horizon and will "
            "not affect this forecast."
        )

    if not in_horizon:
        warnings.append(
            "No active cash events fall inside "
            "the 13-week forecast horizon."
        )

    if not any(
        event.source_type == "COMMITTED"
        for event in in_horizon
    ):
        warnings.append(
            "No committed evidence is present "
            "inside the forecast horizon."
        )

    if not any(
        event.direction == "INFLOW"
        for event in in_horizon
    ):
        warnings.append(
            "No active inflows are present "
            "inside the forecast horizon."
        )

    if not any(
        event.direction == "OUTFLOW"
        for event in in_horizon
    ):
        warnings.append(
            "No active outflows are present "
            "inside the forecast horizon."
        )

    return CustomerCashImportReport(
        rows_loaded=len(events),
        active_events=len(active),
        committed_events=sum(
            event.source_type
            == "COMMITTED"
            for event in active
        ),
        modelled_events=sum(
            event.source_type
            == "MODELLED"
            for event in active
        ),
        management_assumption_events=sum(
            event.source_type
            == "MANAGEMENT_ASSUMPTION"
            for event in active
        ),
        inflow_events=sum(
            event.direction == "INFLOW"
            for event in active
        ),
        outflow_events=sum(
            event.direction == "OUTFLOW"
            for event in active
        ),
        forecast_horizon_events=len(
            in_horizon
        ),
        outside_horizon_events=len(
            outside
        ),
        warnings=tuple(warnings),
    )


UncertaintyProfileName = Literal[
    "Low",
    "Standard",
    "High",
]


def customer_uncertainty_profile(
    profile: UncertaintyProfileName,
) -> WeeklyUncertaintyProfile:
    profiles: dict[
        str,
        tuple[
            tuple[float, float],
            ...,
        ],
    ] = {
        "Low": (
            (-0.06, 0.05),
            (-0.04, 0.03),
            (-0.03, 0.02),
            (-0.02, 0.02),
            (-0.01, 0.01),
            (0.00, 0.00),
            (0.01, -0.01),
            (0.02, -0.02),
            (0.03, -0.02),
            (0.05, -0.03),
        ),
        "Standard": (
            (-0.15, 0.12),
            (-0.12, 0.10),
            (-0.10, 0.08),
            (-0.07, 0.06),
            (-0.04, 0.03),
            (0.00, 0.00),
            (0.03, -0.02),
            (0.06, -0.04),
            (0.09, -0.05),
            (0.12, -0.07),
        ),
        "High": (
            (-0.30, 0.25),
            (-0.25, 0.20),
            (-0.20, 0.16),
            (-0.15, 0.12),
            (-0.08, 0.08),
            (0.00, 0.00),
            (0.06, -0.05),
            (0.12, -0.08),
            (0.18, -0.10),
            (0.25, -0.15),
        ),
    }

    values = profiles[profile]

    return WeeklyUncertaintyProfile(
        modelled_flow_error_samples=tuple(
            ModelledCashErrorSample(
                inflow_error_pct=inflow,
                outflow_error_pct=outflow,
            )
            for inflow, outflow in values
        )
    )


def build_customer_scenario(
    *,
    company_name: str,
    forecast_start: date,
    opening_cash: float,
    management_reserve: float,
    max_breach_probability: float,
    uncertainty_profile_name: UncertaintyProfileName,
    events: tuple[CashEvent, ...],
) -> V2DemoScenario:
    clean_name = company_name.strip()

    if not clean_name:
        raise ValueError(
            "Company name is required."
        )

    if opening_cash < 0.0:
        raise ValueError(
            "Opening cash cannot be negative."
        )

    if management_reserve < 0.0:
        raise ValueError(
            "Management reserve cannot be negative."
        )

    if not (
        0.0
        < max_breach_probability
        < 0.5
    ):
        raise ValueError(
            "Risk appetite must be greater "
            "than 0% and below 50%."
        )

    scenario_id = (
        "customer-"
        + "".join(
            char.lower()
            if char.isalnum()
            else "-"
            for char in clean_name
        ).strip("-")[:48]
    )

    if scenario_id == "customer-":
        scenario_id = "customer-company"

    return V2DemoScenario(
        scenario_id=scenario_id,
        name=clean_name,
        description=(
            "Customer-supplied 13-week direct cash "
            "forecast evaluated using RiskPilot's "
            "verified liquidity decision engines."
        ),
        management_reserve=float(
            management_reserve
        ),
        max_reserve_breach_probability=float(
            max_breach_probability
        ),
        forecast_input=DirectCashForecastInput(
            start_date=forecast_start,
            opening_cash=float(
                opening_cash
            ),
            events=events,
        ),
        uncertainty_profile=(
            customer_uncertainty_profile(
                uncertainty_profile_name
            )
        ),
    )


def customer_cash_template(
    *,
    forecast_start: date,
) -> str:
    rows = [
        {
            "event_id": "invoice-001",
            "date": (
                forecast_start
                + timedelta(days=2)
            ).isoformat(),
            "amount": 25000,
            "direction": "INFLOW",
            "category": "customer receipts",
            "source_type": "COMMITTED",
            "status": "ACTIVE",
            "description": (
                "Approved customer invoice"
            ),
            "source_reference": (
                "AR-ledger-001"
            ),
            "due_date": "",
            "expected_cash_date": "",
        },
        {
            "event_id": "payroll-001",
            "date": (
                forecast_start
                + timedelta(days=4)
            ).isoformat(),
            "amount": 18000,
            "direction": "OUTFLOW",
            "category": "payroll",
            "source_type": "COMMITTED",
            "status": "ACTIVE",
            "description": (
                "Scheduled payroll"
            ),
            "source_reference": (
                "payroll-run-001"
            ),
            "due_date": "",
            "expected_cash_date": "",
        },
        {
            "event_id": "sales-model-001",
            "date": (
                forecast_start
                + timedelta(days=9)
            ).isoformat(),
            "amount": 12000,
            "direction": "INFLOW",
            "category": (
                "residual sales receipts"
            ),
            "source_type": "MODELLED",
            "status": "ACTIVE",
            "description": (
                "Forecast residual collections"
            ),
            "source_reference": (
                "sales-model"
            ),
            "due_date": "",
            "expected_cash_date": "",
        },
        {
            "event_id": "supplier-001",
            "date": (
                forecast_start
                + timedelta(days=11)
            ).isoformat(),
            "amount": 9000,
            "direction": "OUTFLOW",
            "category": "supplier payments",
            "source_type": "COMMITTED",
            "status": "ACTIVE",
            "description": (
                "Approved supplier payment"
            ),
            "source_reference": (
                "AP-ledger-001"
            ),
            "due_date": "",
            "expected_cash_date": "",
        },
    ]

    return pd.DataFrame(
        rows
    ).to_csv(
        index=False
    )
