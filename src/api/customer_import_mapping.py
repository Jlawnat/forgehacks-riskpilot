"""Validated CSV/XLSX mapping and multi-source conversion for the Premium API.

This adapter reuses existing RiskPilot ingestion services; it does not alter
financial engines or fabricate evidence classification.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from src.ingestion.customer_mapping import (
    build_standard_cash_dataframe,
    list_excel_sheets,
    load_customer_table,
    suggest_mapping,
)
from src.ingestion.customer_multi_source import (
    SOURCE_PROFILES,
    get_source_profile,
    merge_standardized_sources,
)

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 15 * 1024 * 1024
MAX_SOURCE_FILES = 5
ACCEPTED_SUFFIXES = {".csv", ".xlsx", ".xlsm"}
EVIDENCE_TYPES = {"COMMITTED", "MODELLED", "MANAGEMENT_ASSUMPTION"}


class MappingSpec(BaseModel):
    """Client-confirmed mapping and explicit evidence assumptions."""

    model_config = ConfigDict(extra="forbid")

    date_column: str = Field(min_length=1)
    amount_column: str = Field(min_length=1)
    direction_column: str | None = None
    category_column: str | None = None
    source_type_column: str | None = None
    status_column: str | None = None
    description_column: str | None = None
    source_reference_column: str | None = None
    due_date_column: str | None = None
    expected_cash_date_column: str | None = None
    default_direction: str | None = None
    default_category: str = "other cash movement"
    default_source_type: str = "MANAGEMENT_ASSUMPTION"


def parse_spec(value: str | dict) -> MappingSpec:
    try:
        raw = json.loads(value) if isinstance(value, str) else value
        spec = MappingSpec.model_validate(raw)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid column mapping: {exc}") from exc
    if spec.default_direction not in ("INFLOW", "OUTFLOW", None):
        raise HTTPException(status_code=422, detail="Default direction must be INFLOW or OUTFLOW.")
    if spec.default_source_type not in EVIDENCE_TYPES:
        raise HTTPException(status_code=422, detail="Unknown default evidence classification.")
    return spec


async def read_table(file: UploadFile, sheet_name: str | None = None):
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in ACCEPTED_SUFFIXES:
        raise HTTPException(status_code=422, detail="Only CSV and Excel XLSX/XLSM files are supported.")
    raw = await file.read(MAX_FILE_BYTES + 1)
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Each source must contain data and be no larger than 5 MB.")
    from src.api.public_interactive import require_demo_upload
    require_demo_upload(raw, filename, purpose="mapping")
    try:
        sheets = list_excel_sheets(raw) if suffix != ".csv" else ()
        selected_sheet = sheet_name or (sheets[0] if sheets else None)
        if sheets and selected_sheet not in sheets:
            raise ValueError("Selected Excel sheet does not exist in this file.")
        frame = load_customer_table(raw, filename=filename, sheet_name=selected_sheet)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Unable to read finance file: {exc}") from exc
    return frame, sheets, selected_sheet, len(raw)


def table_preview(frame, sheets, selected_sheet):
    # pandas handles date cells, nulls and numeric values consistently here.
    return {
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "sheets": list(sheets),
        "selected_sheet": selected_sheet,
        "suggested_mapping": suggest_mapping(frame).model_dump(mode="json"),
        "preview_rows": json.loads(frame.head(8).to_json(orient="records", date_format="iso")),
        "source_profiles": [
            {
                "source_id": profile.source_id,
                "label": profile.label,
                "description": profile.description,
                "default_direction": profile.default_direction,
                "default_category": profile.default_category,
                "default_source_type": profile.default_source_type,
            }
            for profile in SOURCE_PROFILES
        ],
    }


def map_table(frame, spec: MappingSpec, prefix: str, source_filename: str | None = None):
    try:
        standardized = build_standard_cash_dataframe(
            frame, **spec.model_dump(), event_id_prefix=prefix,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Mapping could not be applied: {exc}") from exc
    if source_filename and not spec.source_reference_column:
        # Label upload provenance honestly, without implying a signed contract.
        standardized["source_reference"] = f"uploaded-file:{Path(source_filename).name}"
    return standardized


def merge_tables(sources):
    return merge_standardized_sources(tuple(sources))


def parse_source_specs(value: str, total: int):
    try:
        specs = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Source mappings must be valid JSON.") from exc
    if not isinstance(specs, list) or len(specs) != total:
        raise HTTPException(status_code=422, detail="Each uploaded finance file requires a matching source mapping.")
    for item in specs:
        if not isinstance(item, dict) or "mapping" not in item or "source_id" not in item:
            raise HTTPException(status_code=422, detail="Each finance source requires a profile and explicit mapping.")
        try:
            get_source_profile(item["source_id"])
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        parse_spec(item["mapping"])
    return specs
