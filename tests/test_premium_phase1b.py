"""API contract tests for restored customer mapping and multi-source import.

Financial computation is mocked at the boundary. Existing customer ingestion
modules perform all mapping and cash-evidence validation.
"""

import io
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.api import premium_web as api
from src.api import customer_import_mapping as mapping


@pytest.fixture(autouse=True)
def clear_customer_sessions():
    with api._CUSTOMER_LOCK:
        api._CUSTOMER_SESSIONS.clear()
    yield
    with api._CUSTOMER_LOCK:
        api._CUSTOMER_SESSIONS.clear()


def settings():
    return {
        "company_name": "Test Company",
        "forecast_start": "2026-10-05",
        "opening_cash": "250000",
        "management_reserve": "75000",
        "max_breach_probability": "0.10",
        "uncertainty_profile": "Standard",
    }


def csv_bytes(*, amount="12500", direction="INFLOW"):
    return (
        "Posting Date,Cash Amount,Flow,Category,Evidence\n"
        f"2026-10-07,{amount},{direction},customer receipts,COMMITTED\n"
    ).encode()


def source_spec(direction=None, category="other cash movement", evidence="MANAGEMENT_ASSUMPTION"):
    return {
        "date_column": "posting_date",
        "amount_column": "cash_amount",
        "direction_column": "flow" if direction is None else None,
        "category_column": "category" if direction is None else None,
        "source_type_column": "evidence" if direction is None else None,
        "default_direction": direction,
        "default_category": category,
        "default_source_type": evidence,
    }


def test_mapping_preview_normalizes_columns_and_returns_existing_suggestions():
    client = TestClient(api.app)
    response = client.post(
        "/api/customer/mapping/preview",
        files={"file": ("ledger.csv", csv_bytes(), "text/csv")},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["row_count"] == 1
    assert "posting_date" in result["columns"]
    assert result["preview_rows"][0]["cash_amount"] == 12500
    assert "source_profiles" in result


def test_mapping_rejects_missing_required_columns():
    frame = mapping.load_customer_table(csv_bytes(), filename="ledger.csv")
    with pytest.raises(HTTPException) as error:
        mapping.map_table(frame, mapping.parse_spec({
            "date_column": "not_a_column", "amount_column": "cash_amount",
            "default_direction": "INFLOW",
        }), prefix="test")
    assert error.value.status_code == 422


def test_mapping_defaults_to_assumption_not_committed():
    spec = mapping.parse_spec({
        "date_column": "posting_date", "amount_column": "cash_amount",
        "default_direction": "INFLOW",
    })
    assert spec.default_source_type == "MANAGEMENT_ASSUMPTION"
    frame = mapping.load_customer_table(csv_bytes(), filename="ledger.csv")
    standardized = mapping.map_table(frame, spec, prefix="test")
    assert standardized["source_type"].iloc[0] == "MANAGEMENT_ASSUMPTION"


def test_explicit_mapping_preserves_existing_evidence_classification():
    frame = mapping.load_customer_table(csv_bytes(), filename="ledger.csv")
    standardized = mapping.map_table(frame, mapping.parse_spec(source_spec()), prefix="test")
    assert standardized["source_type"].iloc[0] == "COMMITTED"
    assert standardized["direction"].iloc[0] == "INFLOW"
    assert standardized["amount"].iloc[0] == 12500


def test_two_finance_sources_merge_without_colliding_event_ids():
    first = mapping.load_customer_table(csv_bytes(), filename="ar.csv")
    second = mapping.load_customer_table(csv_bytes(amount="9000", direction="OUTFLOW"), filename="ap.csv")
    ar = mapping.map_table(first, mapping.parse_spec(source_spec("INFLOW", "customer receipts", "COMMITTED")), prefix="source-1")
    ap = mapping.map_table(second, mapping.parse_spec(source_spec("OUTFLOW", "supplier payments", "COMMITTED")), prefix="source-2")
    merged = mapping.merge_tables((("ar.csv", ar), ("ap.csv", ap)))
    assert len(merged) == 2
    assert merged["event_id"].is_unique
    assert set(merged["_riskpilot_source_file"]) == {"ar.csv", "ap.csv"}


def test_unknown_source_profile_rejected():
    with pytest.raises(HTTPException) as error:
        mapping.parse_source_specs(json.dumps([{
            "source_id": "unknown", "mapping": source_spec(),
        }]), 1)
    assert error.value.status_code == 422


def test_mapped_import_uses_original_cash_evidence_engine(monkeypatch):
    captured = {}
    def fake_engine(scenario, **kwargs):
        captured["scenario"] = scenario
        return object()
    monkeypatch.setattr(api, "build_command_center", fake_engine)
    monkeypatch.setattr(api, "_summary", lambda scenario, result: {"scenario": {"name": scenario.name}})
    client = TestClient(api.app)
    response = client.post(
        "/api/customer/mapping/import",
        files={"file": ("ledger.csv", csv_bytes(), "text/csv")},
        data={**settings(), "mapping_json": json.dumps(source_spec())},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["report"]["rows_loaded"] == 1
    assert captured["scenario"].forecast_input.events[0].source_type == "COMMITTED"
    assert api._load_customer_session(result["customer_session_id"])["scenario"] is captured["scenario"]


def test_multi_import_reuses_evidence_engine_not_separate_math(monkeypatch):
    captured = {}
    monkeypatch.setattr(api, "build_command_center", lambda scenario, **kw: captured.setdefault("scenario", scenario))
    monkeypatch.setattr(api, "_summary", lambda scenario, result: {"scenario": {"name": scenario.name}})
    source_files = [
        ("files", ("ar.csv", csv_bytes(), "text/csv")),
        ("files", ("ap.csv", csv_bytes(amount="9000", direction="OUTFLOW"), "text/csv")),
    ]
    specs = [
        {"source_id": "ar", "mapping": source_spec("INFLOW", "customer receipts", "COMMITTED")},
        {"source_id": "ap", "mapping": source_spec("OUTFLOW", "supplier payments", "COMMITTED")},
    ]
    response = TestClient(api.app).post(
        "/api/customer/multi/import", files=source_files,
        data={**settings(), "sources_json": json.dumps(specs)},
    )
    assert response.status_code == 200, response.text
    assert response.json()["report"]["rows_loaded"] == 2
    assert len(captured["scenario"].forecast_input.events) == 2


def test_rejects_unsupported_file_extension_and_unknown_evidence_type():
    response = TestClient(api.app).post(
        "/api/customer/mapping/preview",
        files={"file": ("unsafe.exe", b"not a csv", "application/octet-stream")},
    )
    assert response.status_code == 422
    with pytest.raises(HTTPException):
        mapping.parse_spec({
            "date_column": "date", "amount_column": "amount",
            "default_source_type": "PUBLIC_SOURCE",
        })
