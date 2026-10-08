"""Contract tests for the premium customer-context API bridge.

No financial or AI engine is replaced; all calculation calls are mocked.
"""
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.api import premium_web as api


@pytest.fixture(autouse=True)
def clean_sessions():
    with api._CUSTOMER_LOCK:
        api._CUSTOMER_SESSIONS.clear()
    yield
    with api._CUSTOMER_LOCK:
        api._CUSTOMER_SESSIONS.clear()


def event(source, direction, category, amount=100):
    return SimpleNamespace(
        source_type=source, direction=direction, category=category, amount=amount
    )


def scenario(events=()):
    return SimpleNamespace(
        scenario_id="customer-test-company",
        forecast_input=SimpleNamespace(events=events),
        recovery_constraints=None,
        name="Test Company",
    )


def test_session_contains_verified_context_but_not_a_public_demo():
    customer = scenario((
        event("COMMITTED", "INFLOW", "customer receipts"),
        event("MODELLED", "INFLOW", "residual sales receipts"),
        event("MODELLED", "OUTFLOW", "variable operating costs"),
    ))
    baseline = SimpleNamespace(brief=object())
    token = api._save_customer_session(customer, baseline)
    assert len(token) >= 32
    loaded = api._load_customer_session(token)
    assert loaded["scenario"] is customer
    assert loaded["result"] is baseline
    assert loaded["capabilities"]["modelled_revenue_events"] == 1
    assert loaded["capabilities"]["modelled_cost_events"] == 1
    assert loaded["capabilities"]["receivable_timing_supported"] is False
    with pytest.raises(HTTPException) as info:
        api._load_customer_session("invalid-token")
    assert info.value.status_code == 404


def test_session_expires(monkeypatch):
    monkeypatch.setattr(api, "monotonic", lambda: 100.0)
    token = api._save_customer_session(scenario(), object())
    monkeypatch.setattr(api, "monotonic", lambda: 100 + api._CUSTOMER_TTL_SECONDS + 1)
    with pytest.raises(HTTPException) as info:
        api._load_customer_session(token)
    assert info.value.status_code == 410


def test_unsupported_shock_is_blocked_not_silently_ignored():
    token = api._save_customer_session(scenario((
        event("COMMITTED", "INFLOW", "customer receipts"),
    )), object())
    entry = api._load_customer_session(token)
    with pytest.raises(HTTPException) as error:
        api._validate_customer_what_if(api.WhatIfPayload(
            revenue_change_pct=-20, cost_change_pct=0
        ), entry)
    assert error.value.status_code == 422
    api._validate_customer_what_if(api.WhatIfPayload(
        revenue_change_pct=0, cost_change_pct=0, management_reserve=50000
    ), entry)


def test_what_if_passes_uploaded_scenario_to_existing_engine(monkeypatch):
    customer = scenario((event("MODELLED", "INFLOW", "residual sales receipts"),))
    token = api._save_customer_session(customer, object())
    captured = {}
    def engine(base, request, **kwargs):
        captured["baseline"] = base
        captured["request"] = request
        return SimpleNamespace(
            applied_changes=("Modelled revenue -20.0%",),
            baseline_scenario_id=base.scenario_id,
            scenario=base,
            command_center=object(),
        )
    monkeypatch.setattr(api, "run_v2_what_if", engine)
    monkeypatch.setattr(api, "_summary", lambda *_: {"verified": True})
    response = api.what_if(api.WhatIfPayload(
        scenario_id="healthy", customer_session_id=token,
        revenue_change_pct=-20, cost_change_pct=0,
    ))
    assert captured["baseline"] is customer
    assert response["result"] == {"verified": True}


def test_agent_uses_customer_baseline_not_demo(monkeypatch):
    customer = scenario()
    baseline = SimpleNamespace(brief=object())
    token = api._save_customer_session(customer, baseline)
    captured = {}
    def fake_context(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(what_if_result=None)
    monkeypatch.setattr(api, "V2CopilotContext", fake_context)
    monkeypatch.setattr(api, "run_v2_copilot", lambda context, question:
                        SimpleNamespace(answer="Evidence checked.", tools_used=("get_v2_liquidity_position",)))
    monkeypatch.setattr(api, "_summary", lambda *_: {"verified": True})
    response = api.agent(api.AgentPayload(
        scenario_id="healthy", customer_session_id=token,
        question="What is our cash position?"
    ))
    assert captured["baseline_scenario"] is customer
    assert captured["liquidity_brief"] is baseline.brief
    assert response["answer"] == "Evidence checked."


def test_customer_csv_import_returns_session_for_downstream_requests(monkeypatch):
    customer = scenario()
    monkeypatch.setattr(api, "parse_customer_cash_csv", lambda _: object())
    monkeypatch.setattr(api, "build_customer_cash_events", lambda *a, **kw: ())
    monkeypatch.setattr(api, "build_customer_import_report", lambda *a, **kw:
                        SimpleNamespace(model_dump=lambda **_: {"rows_loaded": 1}))
    monkeypatch.setattr(api, "build_customer_scenario", lambda **kw: customer)
    monkeypatch.setattr(api, "build_command_center", lambda *a, **kw: object())
    monkeypatch.setattr(api, "_summary", lambda *a: {"scenario": {"name": "Test Company"}})
    client = TestClient(api.app)
    response = client.post("/api/customer/import", files={
        "file": ("cash.csv", b"test", "text/csv")
    }, data={
        "company_name": "Test Company", "forecast_start": "2026-10-12",
        "opening_cash": "200000", "management_reserve": "50000",
        "max_breach_probability": "0.10", "uncertainty_profile": "Standard",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["scenario"]["name"] == "Test Company"
    assert api._load_customer_session(body["customer_session_id"])["scenario"] is customer
    assert body["session_expires_in_seconds"] == 3600
