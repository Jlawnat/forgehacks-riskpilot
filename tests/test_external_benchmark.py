from copy import deepcopy
import json
import warnings
import numpy as np
import pandas as pd
import pytest
from src.forecasting.external_benchmark import (
    DATA_ROOT, build_benchmark, load_benchmark_report, load_external_benchmark,
    rolling_origin, summarize, validate_observations,
)
from src.forecasting.models import naive_forecast
from src.ai.model_governance import (
    GovernanceInterpretation, build_governance_evidence, deterministic_recommendation,
    run_governance_supervisor, statistical_eligibility, validate_interpretation,
)


def test_official_loader_metadata_and_counts():
    frame, manifest = load_external_benchmark()
    assert len(frame) == 567
    assert frame.groupby('series_id').size().tolist() == [189]*3
    assert frame.date.min() == pd.Timestamp('2010-01-01')
    assert frame.date.max() == pd.Timestamp('2025-09-01')
    assert 'not demo-company revenue' in manifest['purpose']
    for item in manifest['series']:
        assert item['source_url'].startswith('https://www.abs.gov.au/')
        assert item['series_type'] == 'Seasonally Adjusted'
        assert item['exact_series_name'].startswith('Business Turnover Index')
        assert item['raw_sha256']


def test_loader_rejects_tampered_csv(tmp_path):
    import shutil
    shutil.copytree(DATA_ROOT, tmp_path / 'data')
    with (tmp_path / 'data' / 'observations.csv').open('a') as f:
        f.write('tampered\n')
    with pytest.raises(ValueError, match='checksum'):
        load_external_benchmark(tmp_path / 'data')


def test_loader_rejects_tampered_raw_file(tmp_path):
    import shutil
    shutil.copytree(DATA_ROOT, tmp_path / 'data')
    (tmp_path / 'data' / 'raw' / 'retail.xlsx').write_bytes(b'bad')
    with pytest.raises(ValueError, match='checksum'):
        load_external_benchmark(tmp_path / 'data')


def test_chronological_order_is_restored():
    frame, _ = load_external_benchmark()
    ordered = validate_observations(frame.sample(frac=1, random_state=42))
    pd.testing.assert_frame_equal(ordered, frame)


@pytest.mark.parametrize('defect', ['duplicate','missing','nan','infinite','midmonth'])
def test_invalid_observations_rejected(defect):
    frame, _ = load_external_benchmark()
    if defect == 'duplicate': frame = pd.concat([frame,frame.iloc[:1]])
    if defect == 'missing': frame = frame.drop(index=2)
    if defect == 'nan': frame.loc[0,'value'] = np.nan
    if defect == 'infinite': frame.loc[0,'value'] = np.inf
    if defect == 'midmonth': frame.loc[0,'date'] = pd.Timestamp('2010-01-02')
    with pytest.raises(ValueError): validate_observations(frame)


def test_rolling_origin_no_future_leakage_and_manual_metrics():
    values = pd.Series(np.arange(12, dtype=float))
    seen = []
    def spy(train, horizon):
        seen.append(train.tolist())
        return np.repeat(train.iloc[-1],horizon)
    rows = rolling_origin(values,min_train=6,horizon=3,step=3,models={'spy':spy})
    assert seen == [list(range(6)),list(range(9))]
    assert [r['origin'] for r in rows] == [6,9]
    assert rows[0]['mae'] == 2
    assert rows[0]['mse'] == pytest.approx(14/3)
    assert rows[0]['mase'] == 2
    changed = values.copy(); changed.iloc[9:] = 9999
    new = rolling_origin(changed,min_train=6,horizon=3,step=3,models={'spy':spy})
    assert rows[0] == new[0]
    assert rows[1]['predicted'] == new[1]['predicted']


def test_constant_training_mase_is_undefined():
    rows = rolling_origin(pd.Series([10.]*6+[11.,12.,13.]), min_train=6,horizon=3,models={'naive':naive_forecast})
    assert rows[0]['mase'] is None
    assert rows[0]['mae'] == 2


@pytest.mark.parametrize('kwargs',[{'min_train':3},{'horizon':0},{'step':1}])
def test_bad_rolling_design_rejected(kwargs):
    with pytest.raises(ValueError): rolling_origin(pd.Series(range(100)),**kwargs)


def test_failures_and_warnings_retained():
    def bad(train,horizon): raise RuntimeError('fit failed')
    def warned(train,horizon):
        warnings.warn('unstable',RuntimeWarning)
        return naive_forecast(train,horizon)
    rows = rolling_origin(pd.Series(range(9)),min_train=6,models={'bad':bad,'warned':warned})
    assert rows[0]['failed'] and rows[0]['mae'] is None
    assert 'fit failed' in rows[0]['warnings'][0]
    assert not rows[1]['failed'] and rows[1]['warnings']


def test_invalid_predictions_retained_as_failures():
    rows = rolling_origin(pd.Series(range(9)),min_train=6,models={'bad':lambda t,h:np.repeat(np.nan,h)})
    assert rows[0]['failed']


def test_frozen_report_metrics_can_be_independently_recomputed():
    report = load_benchmark_report()
    recalculated = summarize(report['windows'])
    assert recalculated == report['aggregate']
    assert len(report['windows']) == 1290
    for row in report['aggregate']:
        assert row['windows'] == 129
        assert row['failed_windows'] == 0
        assert row['warning_windows'] == 0
    for row in report['windows']:
        assert row['train_end'] < row['test_start'] <= row['test_end']
        errors = np.array(row['actual'])-np.array(row['predicted'])
        assert row['mae'] == pytest.approx(np.abs(errors).mean())
        assert row['mse'] == pytest.approx((errors**2).mean())
        assert row['mase'] == pytest.approx(row['mae']/row['mase_scale'])


def test_cross_series_aggregation_weights_industries_equally():
    report = load_benchmark_report()
    aggregate = summarize(report['windows'])
    frame = pd.DataFrame(report['windows'])
    for row in aggregate:
        subset = frame[(frame.horizon==row['horizon']) & (frame.model==row['model'])]
        assert row['mae'] == pytest.approx(subset.groupby('series_id').mae.mean().mean())
        assert row['rmse'] == pytest.approx(np.sqrt(subset.groupby('series_id').mse.mean().mean()))
    assert aggregate == report['aggregate']


def test_partial_failures_do_not_gain_comparable_score():
    report = load_benchmark_report()
    rows = deepcopy(report['windows'])
    row = next(r for r in rows if r['model']=='drift' and r['horizon']==3)
    row.update(failed=True,mae=None,mse=None,mase=None)
    score = next(r for r in summarize(rows) if r['model']=='drift' and r['horizon']==3)
    assert score['mae'] is None and score['failed_windows']==1


def test_partial_undefined_mase_is_not_silently_averaged():
    rows = deepcopy(load_benchmark_report()['windows'])
    rows[0]['mase'] = None
    score = next(r for r in summarize(rows) if r['model']==rows[0]['model'] and r['horizon']==rows[0]['horizon'])
    assert score['mase'] is None


def test_frozen_governance_keeps_holt_and_rejects_damped_promotion():
    report = load_benchmark_report()
    evidence = build_governance_evidence(report)
    assert evidence['production_model']=='holt'
    assert evidence['candidate_model']=='drift'
    assert evidence['outcome']=='REVIEW CHALLENGER'
    assert not evidence['production_change_authorized']
    assert not evidence['candidate_statistically_eligible']
    assert not statistical_eligibility(report,'damped_holt')


def eligible_report():
    report = deepcopy(load_benchmark_report())
    for row in report['aggregate']:
        if row['model']=='drift':
            row.update(mae=.1,rmse=.2,mase=.1,mae_improvement_vs_holt=.2,win_rate_vs_holt=.7,
                       series_wins_vs_holt=['a','b','c'],era_wins_vs_holt=['a','b','c'])
    return report


def test_lower_error_never_promotes_without_approval_gates():
    report = eligible_report()
    assert statistical_eligibility(report,'drift')
    assert build_governance_evidence(report)['outcome']=='REVIEW CHALLENGER'
    report['gates']['regression_tests']='PASS'
    assert build_governance_evidence(report)['outcome']=='REVIEW CHALLENGER'
    report['gates']['downstream_financial_consistency']='APPROVED'
    evidence = build_governance_evidence(report)
    assert evidence['outcome']=='PROMOTION CANDIDATE'
    assert not evidence['production_change_authorized']


@pytest.mark.parametrize('field,value',[('warning_windows',1),('win_rate_vs_holt',.54),('mae_improvement_vs_holt',.04),('failed_windows',1)])
def test_stability_gates_block_weak_candidate(field,value):
    report = eligible_report()
    row = next(r for r in report['aggregate'] if r['model']=='drift' and r['horizon']==1)
    row[field]=value
    assert not statistical_eligibility(report,'drift')


def test_insufficient_evidence_status():
    report = deepcopy(load_benchmark_report())
    report['aggregate'] = []
    assert build_governance_evidence(report)['outcome']=='INSUFFICIENT EVIDENCE'


def test_ai_evidence_contract_and_deterministic_fallback(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    monkeypatch.setattr('dotenv.load_dotenv',lambda:None)
    evidence = build_governance_evidence(load_benchmark_report())
    before = deepcopy(evidence)
    response = run_governance_supervisor(evidence)
    assert response == deterministic_recommendation(evidence)
    assert evidence == before
    assert 'Deterministic' in response.mode
    assert 'not the current business revenue' in response.summary
    assert 'no production selector is changed' in response.summary


def test_ai_cannot_change_policy_or_skip_evidence_tool():
    evidence = build_governance_evidence(load_benchmark_report())
    output=GovernanceInterpretation(outcome=evidence['outcome'],evidence_ids=['performance','stability'])
    with pytest.raises(ValueError): validate_interpretation(evidence,output,tool_used=False)
    wrong=output.model_copy(update={'outcome':'PROMOTION CANDIDATE'})
    with pytest.raises(ValueError): validate_interpretation(evidence,wrong,tool_used=True)
    response=validate_interpretation(evidence,output,tool_used=True)
    assert set(['scope','approval','vintage']).issubset(response.evidence_ids)
    assert 'AI-supervised' in response.mode


def test_ai_service_failure_falls_back(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key-do-not-use')
    monkeypatch.setattr('dotenv.load_dotenv',lambda:None)
    from agents import Runner
    def unavailable(*a,**kw): raise RuntimeError('service unavailable')
    monkeypatch.setattr(Runner,'run_sync',unavailable)
    evidence=build_governance_evidence(load_benchmark_report())
    assert run_governance_supervisor(evidence)==deterministic_recommendation(evidence)


def test_ai_output_cannot_contain_invented_claim_ids():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GovernanceInterpretation(outcome='KEEP PRODUCTION',evidence_ids=['invented_forecast','switch_model'])


def test_production_forecaster_and_v2_engine_unchanged():
    import subprocess
    for path in ['src/forecasting/forecast.py','src/core/direct_cash_engine.py','src/core/context.py']:
        result=subprocess.run(['git','diff','v2l-model-governance-verified','--',path],capture_output=True,text=True,check=True)
        assert not result.stdout


def test_report_checksum_rejects_tampering(tmp_path):
    import shutil
    shutil.copytree(DATA_ROOT, tmp_path/'data')
    (tmp_path/'data'/'results.json').write_text('{}')
    with pytest.raises(ValueError, match='checksum'):
        load_benchmark_report(tmp_path/'data')


def test_report_rejects_stale_code_fingerprint(tmp_path):
    import shutil
    from src.forecasting.external_benchmark import sha256
    shutil.copytree(DATA_ROOT, tmp_path/'data')
    result=tmp_path/'data'/'results.json'
    report=json.loads(result.read_text()); report['code_sha256']='stale'
    result.write_text(json.dumps(report))
    (tmp_path/'data'/'results.sha256').write_text(sha256(result))
    with pytest.raises(ValueError, match='stale'):
        load_benchmark_report(tmp_path/'data')


def test_generative_supervisor_uses_existing_agent_and_verified_tool(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from agents import Runner, RunContextWrapper
    monkeypatch.setenv('OPENAI_API_KEY','test-key-do-not-use')
    monkeypatch.setattr('dotenv.load_dotenv',lambda:None)
    evidence=build_governance_evidence(load_benchmark_report())
    def verified_run(agent, question, *, context, max_turns):
        assert agent.name=='RiskPilot AI Model Governance Supervisor'
        assert agent.output_type is GovernanceInterpretation
        assert agent.tools[0].name=='get_external_model_governance'
        from agents.tool_context import ToolContext
        tool_context=ToolContext.from_agent_context(RunContextWrapper(context=context), tool_call_id='test-call', agent=agent, tool_name=agent.tools[0].name, tool_arguments='{}')
        payload=asyncio.run(agent.tools[0].on_invoke_tool(tool_context,'{}'))
        assert json.loads(payload)==evidence
        return SimpleNamespace(final_output=GovernanceInterpretation(outcome=evidence['outcome'], evidence_ids=['stability','performance']))
    monkeypatch.setattr(Runner,'run_sync',verified_run)
    response=run_governance_supervisor(evidence)
    assert response.mode=='AI-supervised evidence explanation'
    assert response.evidence_ids[:2]==('stability','performance')
