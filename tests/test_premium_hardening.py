"""Regression contracts for synthetic demo and premium UI hardening.

The existing financial engines remain the calculation authority. Real AI SDK
calls are deliberately excluded; agent adapter invariants use a stub response.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import premium_web as api
from src.api.premium_demo import DEMO_ID, resolve_premium_scenario
from src.core.command_center import build_command_center
from src.core.recovery_optimizer import RecoverySearchConfig, optimize_recovery


@pytest.fixture
def client():
    return TestClient(api.app)


def test_synthetic_scenario_is_distinct_and_clearly_named(client):
    cases = client.get('/api/scenarios').json()
    assert cases[0]['id'] == DEMO_ID
    assert 'Synthetic Demo' in cases[0]['name']
    assert any(case['id'] == 'public_sec_cenveo' for case in cases)
    synthetic = resolve_premium_scenario(DEMO_ID)
    public = resolve_premium_scenario('public_sec_cenveo')
    assert synthetic.scenario_id != public.scenario_id
    assert synthetic.forecast_input.events != public.forecast_input.events


def test_synthetic_baseline_uses_real_engines_not_fixed_metrics(client):
    result = client.get(f'/api/command-center/{DEMO_ID}')
    assert result.status_code == 200
    data = result.json()
    assert len(data['weeks']) == 13
    assert data['scenario']['is_synthetic'] is True
    assert data['scenario']['is_public'] is False
    assert 0 < data['risk']['probability'] < 1
    assert 0 < data['position']['evidence_coverage'] < 1
    assert data['scenario']['what_if_capabilities']['modelled_revenue_events'] == 13
    assert data['scenario']['what_if_capabilities']['modelled_cost_events'] == 13
    assert data['risk']['simulations'] == 2000


def test_stress_updates_only_modelled_categories(client):
    base = client.get(f'/api/command-center/{DEMO_ID}').json()
    response = client.post('/api/what-if', json={
        'scenario_id': DEMO_ID, 'revenue_change_pct': -20,
        'cost_change_pct': 10,
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['effect']['revenue_events_adjusted'] == 13
    assert data['effect']['cost_events_adjusted'] == 13
    assert data['effect']['neutral_recalculation'] is False
    assert data['result']['position']['minimum_cash'] != base['position']['minimum_cash']
    committed_before = {
        row['event_id']: row['amount'] for row in base['events']
        if row['source_type'] == 'COMMITTED'
    }
    committed_after = {
        row['event_id']: row['amount'] for row in data['result']['events']
        if row['source_type'] == 'COMMITTED'
    }
    assert committed_before == committed_after


def test_no_op_is_explicit_baseline_recalculation(client):
    result = client.post('/api/what-if', json={
        'scenario_id': DEMO_ID, 'revenue_change_pct': 0,
        'cost_change_pct': 0,
    })
    assert result.status_code == 200
    assert result.json()['effect']['neutral_recalculation'] is True


def test_public_sec_unsupported_shock_does_not_claim_verification(client):
    response = client.post('/api/what-if', json={
        'scenario_id': 'public_sec_cenveo',
        'revenue_change_pct': -20, 'cost_change_pct': 10,
    })
    assert response.status_code == 422
    assert 'no eligible' in response.json()['detail'].lower()
    valid_reserve_only = client.post('/api/what-if', json={
        'scenario_id': 'public_sec_cenveo',
        'revenue_change_pct': 0, 'cost_change_pct': 0,
        'management_reserve': 21000000,
    })
    assert valid_reserve_only.status_code == 200
    assert valid_reserve_only.json()['effect']['reserve_policy_adjusted'] is True


def test_optimizer_returns_unique_plans_with_objective_aliases(client):
    response = client.post('/api/recovery/optimise', json={'scenario_id': DEMO_ID})
    assert response.status_code == 200, response.text
    data = response.json()
    shortlist = data['shortlist']
    identities = [json.dumps(entry['candidate']['plan'], sort_keys=True) for entry in shortlist]
    assert len(set(identities)) == len(identities)
    assert data['unique_plan_count'] == len(shortlist)
    assert len(shortlist) >= 2
    assert data['duplicate_objectives'] + len(shortlist) <= 4
    assert all('within_risk_appetite' in entry['validation'] for entry in shortlist)
    assert any(entry['candidate']['plan']['revenue_improvement_pct'] > 0 for entry in shortlist)


def test_original_stressed_demo_remains_frozen(client):
    data = client.get('/api/command-center/stressed_recoverable').json()
    assert data['scenario']['reserve'] == 40000
    assert data['scenario']['is_synthetic'] is False
    assert data['scenario']['what_if_capabilities']['modelled_revenue_events'] == 13


def test_downloadable_synthetic_csv_matches_event_evidence(client):
    response = client.get('/api/demo/harborview-cash.csv')
    assert response.status_code == 200
    assert 'attachment' in response.headers['content-disposition']
    reader = list(csv.DictReader(io.StringIO(response.text)))
    assert len(reader) == 52
    assert len([r for r in reader if r['source_type'] == 'COMMITTED']) == 26
    assert len([r for r in reader if r['source_type'] == 'MODELLED']) == 26
    assert all(r['event_id'].startswith('harborview-') for r in reader)


def test_customer_import_and_scenario_share_same_data(client):
    csv_data = client.get('/api/demo/harborview-cash.csv').content
    response = client.post('/api/customer/import',
        files={'file': ('harborview.csv', csv_data, 'text/csv')},
        data={'company_name': 'Harborview Customer Demo',
              'forecast_start': '2026-10-05', 'opening_cash': '72000',
              'management_reserve': '42500',
              'max_breach_probability': '0.10', 'uncertainty_profile': 'Standard'})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['report']['active_events'] == 52
    assert body['capabilities']['modelled_revenue_events'] == 13
    session = body['customer_session_id']
    what_if = client.post('/api/what-if', json={
        'scenario_id': 'healthy', 'customer_session_id': session,
        'revenue_change_pct': -20, 'cost_change_pct': 10,
    })
    assert what_if.status_code == 200, what_if.text
    assert what_if.json()['baseline_scenario_id'].startswith('customer-')
    assert what_if.json()['effect']['revenue_events_adjusted'] == 13
    recovery = client.post('/api/recovery/optimise', json={
        'scenario_id': 'healthy', 'customer_session_id': session,
        'max_external_liquidity': 18000, 'max_revenue_improvement_pct': 30,
        'max_cost_reduction_pct': 25,
    })
    assert recovery.status_code == 200, recovery.text
    assert recovery.json()['scenario_name'] == 'Harborview Customer Demo'


def test_mapping_preview_uses_real_loader_and_isolation(client):
    raw = b'due_day,usd,cash_direction\n2026-10-07,25000,INFLOW\n2026-10-08,5000,OUTFLOW\n'
    preview = client.post('/api/customer/mapping/preview',
        files={'file': ('cash.csv', raw, 'text/csv')})
    assert preview.status_code == 200, preview.text
    assert preview.json()['row_count'] == 2
    assert preview.json()['columns'] == ['due_day', 'usd', 'cash_direction']
    mapping = {
        'date_column': 'due_day', 'amount_column': 'usd',
        'direction_column': 'cash_direction',
        'default_category': 'other cash movement',
        'default_source_type': 'MANAGEMENT_ASSUMPTION',
    }
    imported = client.post('/api/customer/mapping/import',
        files={'file': ('cash.csv', raw, 'text/csv')},
        data={'mapping_json': json.dumps(mapping), 'company_name': 'Mapped Customer',
              'forecast_start': '2026-10-05', 'opening_cash': '75000',
              'management_reserve': '30000', 'max_breach_probability': '.1',
              'uncertainty_profile': 'Standard'})
    assert imported.status_code == 200, imported.text
    report = imported.json()['report']
    assert report['management_assumption_events'] == 2
    assert report['committed_events'] == 0


def test_unchanged_source_reporting_pdf_audit_and_history(client):
    pdf = client.get(f'/api/reports/{DEMO_ID}/management.pdf')
    audit = client.get(f'/api/reports/{DEMO_ID}/audit.json')
    evidence = client.get(f'/api/evidence/weeks/{DEMO_ID}')
    assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF')
    assert audit.status_code == 200
    assert audit.json()['scenario']['scenario_id'] == DEMO_ID
    assert evidence.status_code == 200 and len(evidence.json()['weeks']) == 13
    key = 'hardening-unique-test-session-key'
    saved = client.post('/api/forecast/history/save', json={
        'history_key': key, 'scenario_id': DEMO_ID})
    assert saved.status_code == 200
    history = client.get('/api/forecast/history', params={'history_key': key})
    assert history.status_code == 200
    assert history.json()['history'][-1]['snapshot_id'] == saved.json()['saved']['snapshot_id']


def test_invalid_customer_token_never_falls_back_to_synthetic(client):
    response = client.get(f'/api/evidence/weeks/{DEMO_ID}',
        params={'customer_session_id': 'unrecognised-session-token'})
    assert response.status_code in (404, 410)


def test_excel_mapping_preview_uses_original_loader(client):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Cash Exports'
    ws.append(['Due Date', 'Cash Amount', 'Movement'])
    ws.append(['2026-10-07', 12000, 'INFLOW'])
    buffer = io.BytesIO()
    wb.save(buffer)
    response = client.post('/api/customer/mapping/preview',
        files={'file': ('accounts.xlsx', buffer.getvalue(),
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['sheets'] == ['Cash Exports']
    assert result['columns'] == ['due_date', 'cash_amount', 'movement']


def test_explicit_multi_source_merging_preserves_evidence_types(client):
    sources = [
        {
            'source_id': 'ar',
            'mapping': {
                'date_column': 'date', 'amount_column': 'amount',
                'default_direction': 'INFLOW', 'default_category': 'customer receipts',
                'default_source_type': 'COMMITTED',
            },
        },
        {
            'source_id': 'ap',
            'mapping': {
                'date_column': 'date', 'amount_column': 'amount',
                'default_direction': 'OUTFLOW', 'default_category': 'supplier payments',
                'default_source_type': 'MANAGEMENT_ASSUMPTION',
            },
        },
    ]
    r = client.post('/api/customer/multi/import',
        files=[
            ('files', ('receivables.csv', b'date,amount\n2026-10-07,18000\n', 'text/csv')),
            ('files', ('suppliers.csv', b'date,amount\n2026-10-08,6500\n', 'text/csv')),
        ],
        data={
            'sources_json': json.dumps(sources), 'company_name': 'Multi Source Test',
            'forecast_start': '2026-10-05', 'opening_cash': '80000',
            'management_reserve': '20000', 'max_breach_probability': '.1',
            'uncertainty_profile': 'Standard',
        })
    assert r.status_code == 200, r.text
    report = r.json()['report']
    assert report['rows_loaded'] == 2
    assert report['committed_events'] == 1
    assert report['management_assumption_events'] == 1


def test_hardening_react_navigation_and_diagnostic_contracts():
    root = Path(__file__).resolve().parents[1]
    app = (root / 'web/src/App.jsx').read_text()
    restored = (root / 'web/src/RestoredWorkspaces.jsx').read_text()
    assert 'harborview_synthetic' in app
    assert 'Advanced monthly analyst' in app
    assert 'Forecast monitoring & reports' in app
    assert '13-week verified forecast' in app
    assert '26-week forecast is not available' not in app
    assert '52-week forecast is not available' not in app
    assert 'unique_plan_count' in restored
    assert 'also_selected_for' in restored
    assert 'Advanced plan diagnostics' in restored
    assert 'Source provenance is a separate dimension' in app
