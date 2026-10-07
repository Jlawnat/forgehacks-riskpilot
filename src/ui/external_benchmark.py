"""External model intelligence, intentionally isolated from business cash state."""
from __future__ import annotations
import hashlib
import json
import pandas as pd
import streamlit as st
from src.ai.model_governance import build_governance_evidence, deterministic_recommendation, run_governance_supervisor
from src.forecasting.external_benchmark import MODEL_LABELS, load_benchmark_report


def render_external_benchmark() -> None:
    st.markdown('### External Real-Data Benchmark')
    st.caption('Independent monthly model research · ABS industry turnover indexes · never used as demo-company revenue or 13-week cash evidence')
    try:
        report = load_benchmark_report()
        evidence = build_governance_evidence(report)
    except (ValueError, OSError, KeyError, TypeError):
        st.warning('External benchmark evidence is unavailable or stale. Current business forecasting remains available. Rebuild the frozen benchmark using the documented offline command.')
        return
    source = report['source']
    cols = st.columns(4)
    cols[0].metric('Official observations', sum(s['observations'] for s in source['series']))
    cols[1].metric('Industry series', len(source['series']))
    cols[2].metric('Governance reference', 'Holt · frozen')
    cols[3].metric('Leading challenger', MODEL_LABELS.get(evidence['candidate_model'], 'Unavailable'))
    st.markdown(f"[Australian Bureau of Statistics]({source['source_url']}) · January 2010–September 2025 · July 2019 = 100 · Seasonally adjusted")
    st.caption(f"Historical publication ended September 2025 · Retrieved {source['retrieved_at']} · Final revised vintage, not a real-time backtest")
    st.caption('Expanding rolling origin · 60-month initial training · origins every 3 months · 1- and 3-month holdouts · equal industry weighting · MASE uses training-only nonseasonal naive scale')
    with st.container(border=True):
        st.markdown('#### AI Model Governance Recommendation')
        st.markdown(f"**{evidence['outcome']}**")
        st.caption('Engines calculate → validation compares → governance checks → AI explains')
        signature = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        state_key = f'external_governance_{signature}'
        if st.button('Explain verified evidence with AI', key='explain_external_governance'):
            with st.spinner('Reviewing verified model evidence…'):
                st.session_state[state_key] = run_governance_supervisor(evidence)
        response = st.session_state.get(state_key, deterministic_recommendation(evidence))
        st.caption(response.mode)
        st.markdown(response.summary)
    horizon = st.radio('Benchmark forecast horizon', [3, 1], format_func=lambda h: f'{h}-month', horizontal=True, key='external_benchmark_horizon')
    results = [r for r in report['aggregate'] if r['horizon'] == horizon]
    display = pd.DataFrame([{
        'Model': MODEL_LABELS[r['model']], 'MAE (index points)': r['mae'], 'RMSE (index points)': r['rmse'],
        'MASE': r['mase'], 'MAE vs Naive (%)': 100*r['mae_improvement_vs_naive'] if r['mae_improvement_vs_naive'] is not None else None,
        'Wins vs Holt (%)': 100*r['win_rate_vs_holt'] if r['model'] != 'holt' else None,
        'Industry wins': f"{len(r['series_wins_vs_holt'])}/{r['series_count']}" if r['model'] != 'holt' else 'Reference',
        'Failed / warning fits': f"{r['failed_windows']} / {r['warning_windows']}"
    } for r in sorted(results, key=lambda x: x['mase'] if x['mase'] is not None else float('inf'))])
    st.dataframe(display, hide_index=True, width="stretch", column_config={
        name: st.column_config.NumberColumn(format='%.4f') for name in ('MAE (index points)', 'RMSE (index points)', 'MASE')
    } | {name: st.column_config.NumberColumn(format='%.1f%%') for name in ('MAE vs Naive (%)','Wins vs Holt (%)')})
    with st.expander('Industry results, time stability & source provenance'):
        meta = {s['series_id']: s for s in source['series']}
        windows = pd.DataFrame(report['windows'])
        selected = windows[(windows.horizon == horizon) & ~windows.failed]
        per_series = selected.groupby(['series_id','model']).agg(MAE=('mae','mean'), MSE=('mse','mean'), MASE=('mase','mean'), Windows=('origin','count')).reset_index()
        per_series['Industry'] = per_series.series_id.map(lambda sid: meta[sid]['industry'])
        per_series['Model'] = per_series.model.map(MODEL_LABELS)
        per_series['RMSE'] = per_series.MSE.pow(.5)
        st.dataframe(per_series[['Industry','Model','MAE','RMSE','MASE','Windows']], hide_index=True, width="stretch")
        era = selected.groupby(['era','model']).agg(MAE=('mae','mean'), MASE=('mase','mean')).reset_index()
        era['model'] = era.model.map(MODEL_LABELS)
        st.markdown('**Performance across time eras**')
        st.dataframe(era, hide_index=True, width="stretch")
        st.caption('Descriptive win rates; shared economic shocks and model selection limit statistical inference. Failed fits are retained in coverage counts, never silently removed from model eligibility.')
        for item in source['series']:
            st.markdown(f"[{item['industry']}]({item['source_url']}) · {item['series_id']} · {item['observations']} observations · {item['start']} → {item['end']}")
        st.markdown(f"[Official methodology]({source['methodology_url']})")
        for limitation in report['limitations']:
            st.caption(limitation)
        st.download_button('Download verified benchmark report', json.dumps(report, indent=2), 'riskpilot_external_benchmark.json', 'application/json', key='download_external_benchmark')
