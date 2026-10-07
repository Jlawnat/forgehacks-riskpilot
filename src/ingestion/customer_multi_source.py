from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CustomerSourceProfile:
    source_id: str
    label: str
    default_direction: str | None
    default_category: str
    default_source_type: str
    description: str


SOURCE_PROFILES = (
    CustomerSourceProfile(
        source_id="ar",
        label="Accounts Receivable / Customer receipts",
        default_direction="INFLOW",
        default_category="customer receipts",
        default_source_type="COMMITTED",
        description=(
            "Invoices, expected customer collections "
            "and confirmed receivable cash dates."
        ),
    ),
    CustomerSourceProfile(
        source_id="ap",
        label="Accounts Payable / Supplier payments",
        default_direction="OUTFLOW",
        default_category="supplier payments",
        default_source_type="COMMITTED",
        description=(
            "Approved supplier invoices and expected "
            "payment dates."
        ),
    ),
    CustomerSourceProfile(
        source_id="payroll",
        label="Payroll",
        default_direction="OUTFLOW",
        default_category="payroll",
        default_source_type="COMMITTED",
        description=(
            "Scheduled wages, salaries and payroll "
            "cash requirements."
        ),
    ),
    CustomerSourceProfile(
        source_id="tax",
        label="Tax / BAS / Super",
        default_direction="OUTFLOW",
        default_category="tax and statutory payments",
        default_source_type="COMMITTED",
        description=(
            "Tax, BAS, PAYG, superannuation and other "
            "scheduled statutory cash payments."
        ),
    ),
    CustomerSourceProfile(
        source_id="other",
        label="Other cash items",
        default_direction=None,
        default_category="other cash movement",
        default_source_type="MANAGEMENT_ASSUMPTION",
        description=(
            "Other operating, financing or management "
            "cash assumptions."
        ),
    ),
)


def get_source_profile(
    source_id: str,
) -> CustomerSourceProfile:
    for profile in SOURCE_PROFILES:
        if profile.source_id == source_id:
            return profile

    raise ValueError(
        f"Unknown customer source profile: {source_id}"
    )


def merge_standardized_sources(
    sources: tuple[
        tuple[str, pd.DataFrame],
        ...,
    ],
) -> pd.DataFrame:
    if not sources:
        raise ValueError(
            "At least one mapped finance source is required."
        )

    frames: list[pd.DataFrame] = []

    seen_ids: set[str] = set()

    for source_name, frame in sources:
        if frame.empty:
            continue

        if "event_id" not in frame.columns:
            raise ValueError(
                f"{source_name}: mapped data has no event_id."
            )

        ids = {
            str(value)
            for value in frame["event_id"]
        }

        duplicates = (
            ids & seen_ids
        )

        if duplicates:
            raise ValueError(
                f"{source_name}: duplicate cash event IDs "
                "were created across source files."
            )

        seen_ids.update(ids)

        working = frame.copy()

        working[
            "_riskpilot_source_file"
        ] = source_name

        frames.append(
            working
        )

    if not frames:
        raise ValueError(
            "Uploaded finance sources contain no rows."
        )

    merged = pd.concat(
        frames,
        ignore_index=True,
    )

    return merged
