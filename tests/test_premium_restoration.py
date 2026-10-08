"""Contract tests for premium adapters; use frozen engines, not guessed values."""
from __future__ import annotations

from datetime import date
from io import BytesIO

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import premium_web as api
from src.ingestion.customer_cash import customer_cash_template


@pytest.fixture
def client():
    return TestClient(api.app)


@pytest.fixture
def monthly_csv():
    periods = 24
    frame = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=periods, freq="MS").strftime("%Y-%m-%d"),
        "revenue": [100000 + 1000 * i for i in range(periods)],
        "operating_cost": [75000 + 350 * i for i in range(periods)],
        "cash_balance": [180000 + 1200 * i for i in range(periods)],
        "receivables": [26000 + 100 * i for i in range(periods)],
    })
    return frame.to_csv(index=False).encode()


def monthly_session(client, monthly_csv):
    resp = client.post("/api/legacy/monthly/import",
        files={"file": ("monthly.csv", monthly_csv, "text/csv")},
        data={"horizon": "3", "reserve": "50000", "appetite": "0.05"})
    assert resp.status_code == 200, resp.text
    return resp.json()["monthly_session_id"]


def test_monthly_import_is_explicitly_separate(client, monthly_csv):
    res = client.post("/api/legacy/monthly/import", files={"file": ("monthly.csv", monthly_csv, "text/csv")})
    assert res.status_code == 200
    assert res.json()["scope"] == "legacy_monthly_not_v2_weekly"
    assert res.json()["periods"] == 24


def test_weekly_cash_format_not_mislabeled_as_monthly(client):
    raw = customer_cash_template(forecast_start=date(2026, 10, 5)).encode()
    res = client.post("/api/legacy/monthly/import", files={"file": ("cash-events.csv", raw, "text/csv")})
    assert res.status_code == 422


def test_monthly_stress_uses_existing_decomposition(client, monthly_csv):
    token = monthly_session(client, monthly_csv)
    response = client.post("/api/legacy/monthly/stress", json={
        "monthly_session_id": token, "revenue_change_pct": -20,
        "cost_change_pct": 10, "receivable_delay_days": 15, "horizon_months": 3})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scope"] == "legacy_monthly"
    assert body["scenario"]["stressed_end_cash"] != body["scenario"]["baseline_end_cash"]
    assert body["decomposition"]["drivers"]


def test_monthly_reverse_stress_returns_engine_boundaries(client, monthly_csv):
    token = monthly_session(client, monthly_csv)
    response = client.post("/api/legacy/monthly/reverse-stress", json={
        "monthly_session_id": token, "target_min_cash": 50000,
        "horizon_months": 3, "max_receivable_delay_days": 45})
    assert response.status_code == 200, response.text
    assert "revenue_decline_breakpoint" in response.json()["reverse_stress"]


def test_monthly_ai_uses_original_runtime(monkeypatch, client, monthly_csv):
    from src.ai import analyst
    capture = []
    def fake(context, question):
        capture.append((context, question))
        return type("Answer", (), {"answer": "Verified monthly response", "tools_used": ("get_forecast_outlook",)})()
    monkeypatch.setattr(analyst, "run_risk_analyst", fake)
    token = monthly_session(client, monthly_csv)
    response = client.post("/api/legacy/monthly/agent", json={
        "monthly_session_id": token, "question": "Explain the risk"})
    assert response.status_code == 200, response.text
    assert capture[0][1] == "Explain the risk"
    assert response.json()["tools_used"] == ["get_forecast_outlook"]


def test_recovery_optimizer_uses_existing_constraints(client):
    response = client.post("/api/recovery/optimise", json={"scenario_id": "stressed_recoverable"})
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "v2_13_week"
    assert response.json()["search"]["candidates_evaluated"] >= 1
    assert response.json()["shortlist"]
    assert "validation" in response.json()["shortlist"][0]


def test_customer_recovery_is_from_uploaded_session(client):
    raw = customer_cash_template(forecast_start=date(2026, 10, 5)).encode()
    response = client.post("/api/customer/import", files={"file": ("upload.csv", raw, "text/csv")},
        data={"company_name": "Example Customer", "forecast_start": "2026-10-05",
              "opening_cash": "250000", "management_reserve": "75000",
              "max_breach_probability": "0.1", "uncertainty_profile": "Standard"})
    assert response.status_code == 200, response.text
    token = response.json()["customer_session_id"]
    search = client.post("/api/recovery/optimise", json={
        "scenario_id": "healthy", "customer_session_id": token,
        "apply_to_committed_receivables": True})
    assert search.status_code == 200, search.text
    assert search.json()["scenario_name"] == "Example Customer"
    assert "invoice-001" in search.json()["constraints"]["receivable_acceleration"]["eligible_event_ids"]


def test_forecast_snapshot_comparison_is_engine_derived(client):
    key = "test-restoration-session-key-1234567890"
    a = client.post("/api/forecast/history/save", json={"history_key": key, "scenario_id": "healthy"})
    b = client.post("/api/forecast/history/save", json={"history_key": key, "scenario_id": "stressed_recoverable"})
    assert a.status_code == b.status_code == 200
    compare = client.post("/api/forecast/history/compare", json={
        "history_key": key, "prior_snapshot_id": a.json()["saved"]["snapshot_id"],
        "current_snapshot_id": b.json()["saved"]["snapshot_id"]})
    assert compare.status_code == 200, compare.text
    assert compare.json()["comparison"]["same_forecast_basis"] is False


def test_forecast_history_is_isolated(client):
    response = client.get("/api/forecast/history", params={"history_key": "another-distinct-browser-session-key"})
    assert response.status_code == 200
    assert response.json()["history"] == []


def test_weekly_provenance_is_traceable(client):
    response = client.get("/api/evidence/weeks/healthy")
    assert response.status_code == 200, response.text
    assert len(response.json()["weeks"]) == 13
    first = response.json()["weeks"][0]["events"][0]
    assert first["event_id"] and first["source_type"]
    assert first["included_amount"] >= 0


def test_management_pdf_and_audit_reuse_engine_results(client):
    pdf = client.get("/api/reports/healthy/management.pdf")
    audit = client.get("/api/reports/healthy/audit.json")
    assert pdf.status_code == audit.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert audit.json()["scenario"]["scenario_id"] == "healthy"
    assert audit.json()["scope"] == "v2_13_week"


def test_unknown_customer_session_does_not_fall_back_to_demo(client):
    response = client.get("/api/evidence/weeks/healthy", params={"customer_session_id": "invalid"})
    assert response.status_code in (404, 410)


def test_actual_cash_monitoring_preserves_explicit_linking(client):
    key = "test-actual-comparison-session-1234567890"
    saved = client.post("/api/forecast/history/save", json={"history_key": key, "scenario_id": "healthy"})
    assert saved.status_code == 200, saved.text
    snapshot_id = saved.json()["saved"]["snapshot_id"]
    actuals = ("actual_id,date,amount,direction,source_reference,forecast_event_id\n"
               "realized-001,2026-10-07,24000,INFLOW,BANK-VERIFIED,healthy-w1-committed-in\n")
    response = client.post("/api/forecast/history/actuals", files={"file": ("observed.csv", actuals.encode(), "text/csv")},
        data={"history_key": key, "snapshot_id": snapshot_id, "through_date": "2026-10-08"})
    assert response.status_code == 200, response.text
    assert response.json()["comparison"]["actual_inflows"] == 24000
    assert response.json()["comparison"]["variances"]


def test_management_monitoring_is_from_brief(client):
    response = client.get("/api/monitoring/stressed_recoverable")
    assert response.status_code == 200, response.text
    assert response.json()["scope"] == "v2_13_week"
    assert "actions" in response.json()
    assert "monitoring" in response.json()
