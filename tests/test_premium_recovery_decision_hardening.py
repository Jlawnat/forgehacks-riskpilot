"""Regression tests for risk-aware premium Recovery Decision Center."""
from __future__ import annotations

from fastapi.testclient import TestClient
from src.api import premium_web as api
from src.api.premium_demo import DEMO_ID

client = TestClient(api.app)


def test_manual_harborview_plan_returns_authoritative_evaluation():
    answer = client.post('/api/recovery/validate-plan', json={
        'scenario_id': DEMO_ID,
        'revenue_improvement_pct': 30,
        'cost_reduction_pct': 25,
        'receivable_acceleration_days': 7,
        'external_liquidity': 0,
    })
    assert answer.status_code == 200, answer.text
    result = answer.json()
    assert result['scope'] == 'v2_13_week'
    assert result['plan']['revenue_improvement_pct'] == 30
    assert result['plan']['cost_reduction_pct'] == 25
    assert result['plan']['receivable_acceleration_days'] == 7
    assert result['evaluation']['feasible'] is True
    assert result['validation']['simulations'] == 1000
    assert result['validation']['within_risk_appetite'] is True


def test_manual_plan_respects_hard_demo_constraints():
    excessive = client.post('/api/recovery/validate-plan', json={
        'scenario_id': DEMO_ID, 'revenue_improvement_pct': 31,
    })
    assert excessive.status_code == 422, excessive.text
    unsupported = client.post('/api/recovery/validate-plan', json={
        'scenario_id': 'stressed_recoverable', 'cost_reduction_pct': 15,
    })
    assert unsupported.status_code == 422, unsupported.text


def test_manual_plan_does_not_mutate_baseline_evidence():
    before = client.get(f'/api/command-center/{DEMO_ID}').json()
    ans = client.post('/api/recovery/validate-plan', json={
        'scenario_id': DEMO_ID,
        'revenue_improvement_pct': 5,
        'cost_reduction_pct': 10,
    })
    assert ans.status_code == 200, ans.text
    after = client.get(f'/api/command-center/{DEMO_ID}').json()
    assert before['events'] == after['events']
    assert before['position']['minimum_cash'] == after['position']['minimum_cash']


def test_manual_missing_constraints_cannot_fallback():
    response = client.post('/api/recovery/validate-plan', json={
        'scenario_id': 'healthy', 'revenue_improvement_pct': 3,
    })
    assert response.status_code == 422


def test_manual_customer_context_does_not_use_demo():
    invalid = client.post('/api/recovery/validate-plan', json={
        'scenario_id': DEMO_ID,
        'customer_session_id': 'expired-or-unknown',
        'external_liquidity': 500,
    })
    assert invalid.status_code in (404,410)
