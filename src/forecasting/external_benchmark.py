"""Offline, advisory-only external benchmark. Never writes production configuration."""
from __future__ import annotations
import hashlib
import json
import warnings
from pathlib import Path
import numpy as np
import pandas as pd
from src.forecasting.validation import _CANDIDATE_MODEL_FUNCTIONS

DATA_ROOT = Path(__file__).resolve().parents[2] / 'data' / 'external_benchmark'
MODEL_LABELS = {'naive': 'Naive', 'drift': 'Drift', 'ses': 'SES', 'holt': 'Holt', 'damped_holt': 'Damped Holt'}
PRODUCTION_MODEL = 'holt'  # governance reference, not a selector for company forecasts

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def code_fingerprint() -> str:
    root = Path(__file__).resolve().parent
    return hashlib.sha256(b''.join((root / name).read_bytes() for name in
                                  ('external_benchmark.py', 'models.py', 'validation.py'))).hexdigest()

def validate_observations(frame: pd.DataFrame) -> pd.DataFrame:
    if set(frame.columns) != {'series_id', 'date', 'value'} or frame.empty:
        raise ValueError('Benchmark requires series_id, date, value and nonempty observations.')
    data = frame.copy()
    if data.isna().any().any():
        raise ValueError('Missing benchmark observations are not silently imputed.')
    data['date'] = pd.to_datetime(data['date'], errors='raise')
    data['value'] = pd.to_numeric(data['value'], errors='raise').astype(float)
    if not np.isfinite(data['value']).all() or data.duplicated(['series_id', 'date']).any():
        raise ValueError('Non-finite or duplicate benchmark observations.')
    data = data.sort_values(['series_id', 'date']).reset_index(drop=True)
    for _, group in data.groupby('series_id'):
        expected = pd.date_range(group.date.iloc[0], periods=len(group), freq='MS')
        if not np.array_equal(expected.values, group.date.values):
            raise ValueError('Benchmark dates must be consecutive month starts.')
    return data

def load_external_benchmark(root: Path = DATA_ROOT) -> tuple[pd.DataFrame, dict]:
    root = Path(root)
    metadata = json.loads((root / 'metadata.json').read_text())
    if metadata.get('schema_version') != 1 or sha256(root / 'observations.csv') != metadata['csv_sha256']:
        raise ValueError('Benchmark manifest or frozen data checksum mismatch.')
    frame = validate_observations(pd.read_csv(root / 'observations.csv'))
    if set(frame.series_id) != {s['series_id'] for s in metadata['series']}:
        raise ValueError('Benchmark series differ from manifest.')
    for item in metadata['series']:
        group = frame[frame.series_id == item['series_id']]
        if len(group) != item['observations'] or len(group) < 120 or group.date.iloc[0].strftime('%Y-%m-%d') != item['start'] or group.date.iloc[-1].strftime('%Y-%m-%d') != item['end']:
            raise ValueError('Benchmark coverage differs from manifest or is too short.')
        if sha256(root / item['raw_file']) != item['raw_sha256']:
            raise ValueError('Official raw file checksum mismatch.')
    return frame, metadata

def rolling_origin(series: pd.Series, *, min_train: int = 60, horizon: int = 3,
                   step: int = 3, models=None) -> list[dict]:
    """Each fit sees only the prefix before its holdout. Failed fits retain rows."""
    if min_train < 4 or horizon < 1 or step < horizon or len(series) < min_train + horizon:
        raise ValueError('Invalid rolling design; holdout windows must not overlap.')
    values = pd.to_numeric(series, errors='raise').astype(float).reset_index(drop=True)
    if not np.isfinite(values).all():
        raise ValueError('Finite observations required.')
    pool = _CANDIDATE_MODEL_FUNCTIONS if models is None else models
    rows = []
    for split in range(min_train, len(values) - horizon + 1, step):
        train = values.iloc[:split].copy()
        actual = values.iloc[split:split + horizon].to_numpy()
        # m=1 nonseasonal naive scaling, calculated from training prefix only.
        scale = float(np.mean(np.abs(np.diff(train.to_numpy()))))
        for name, fn in pool.items():
            row = {'model': name, 'origin': split, 'horizon': horizon, 'train_count': split,
                   'mase_scale': scale if scale > 0 else None, 'warnings': [], 'failed': False}
            try:
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    predicted = np.asarray(fn(train.copy(), horizon), dtype=float)
                row['warnings'] = sorted({f'{w.category.__name__}: {w.message}' for w in caught})
                if predicted.shape != actual.shape or not np.isfinite(predicted).all():
                    raise ValueError('Invalid forecast shape or non-finite values')
                error = actual - predicted
                row.update(mae=float(np.mean(np.abs(error))), mse=float(np.mean(error ** 2)),
                           mase=float(np.mean(np.abs(error)) / scale) if scale > 0 else None,
                           actual=actual.tolist(), predicted=predicted.tolist())
            except Exception as exc:
                row.update(failed=True, mae=None, mse=None, mase=None, actual=actual.tolist(), predicted=None)
                row['warnings'].append(f'{type(exc).__name__}: {exc}')
            rows.append(row)
    return rows

def summarize(rows: list[dict]) -> list[dict]:
    """Equal weights for series; metrics suppressed on incomplete model coverage."""
    frame = pd.DataFrame(rows)
    results = []
    for (horizon, model), group in frame.groupby(['horizon', 'model'], sort=True):
        valid = group[~group.failed]
        complete = len(valid) == len(group)
        by_series = valid.groupby('series_id')[['mae', 'mse', 'mase']].mean()
        holt = frame[(frame.horizon == horizon) & (frame.model == PRODUCTION_MODEL)][['series_id', 'origin', 'mae', 'failed']]
        paired = group.merge(holt, on=['series_id', 'origin'], suffixes=('', '_holt'))
        wins = (~paired.failed & ~paired.failed_holt & (paired.mae < paired.mae_holt - 1e-10))
        series_wins = []
        for series_id, sg in group.groupby('series_id'):
            hg = holt[holt.series_id == series_id]
            if not sg.failed.any() and not hg.failed.any() and sg.mae.mean() < hg.mae.mean() - 1e-10:
                series_wins.append(series_id)
        eras = []
        for era, eg in group.groupby('era'):
            eh = frame[(frame.horizon == horizon) & (frame.model == PRODUCTION_MODEL) & (frame.era == era)]
            if not eg.failed.any() and not eh.failed.any() and eg.groupby('series_id').mae.mean().mean() < eh.groupby('series_id').mae.mean().mean() - 1e-10:
                eras.append(era)
        results.append({'model': model, 'horizon': int(horizon), 'mae': float(by_series.mae.mean()) if complete else None,
                        'rmse': float(np.sqrt(by_series.mse.mean())) if complete else None,
                        'mase': float(by_series.mase.mean()) if complete and valid.mase.notna().all() else None,
                        'windows': len(group), 'successful_windows': len(valid),
                        'failed_windows': len(group)-len(valid), 'warning_windows': int(group.warnings.map(bool).sum()),
                        'win_rate_vs_holt': float(wins.sum() / len(group)), 'series_wins_vs_holt': series_wins,
                        'era_wins_vs_holt': eras, 'series_count': group.series_id.nunique(), 'era_count': group.era.nunique()})
    for result in results:
        naive = next(r for r in results if r['model'] == 'naive' and r['horizon'] == result['horizon'])
        holt = next(r for r in results if r['model'] == PRODUCTION_MODEL and r['horizon'] == result['horizon'])
        for name, reference in [('naive', naive), ('holt', holt)]:
            result[f'mae_improvement_vs_{name}'] = (1-result['mae']/reference['mae']) if result['mae'] is not None and reference['mae'] and reference['mae'] > 0 else None
    return results

def build_benchmark(frame: pd.DataFrame, metadata: dict, *, min_train=60, step=3) -> dict:
    data = validate_observations(frame)
    rows = []
    for series_id, group in data.groupby('series_id'):
        group = group.reset_index(drop=True)
        for horizon in (1, 3):
            for row in rolling_origin(group.value, min_train=min_train, horizon=horizon, step=step):
                split = row['origin']
                year = int(group.date.iloc[split].year)
                row.update(series_id=series_id, train_end=group.date.iloc[split-1].strftime('%Y-%m-%d'),
                           test_start=group.date.iloc[split].strftime('%Y-%m-%d'),
                           test_end=group.date.iloc[split+horizon-1].strftime('%Y-%m-%d'),
                           year=year, era='Pre-2020' if year < 2020 else '2020–2021' if year < 2022 else '2022 onwards')
                rows.append(row)
    return {'schema_version': 1, 'data_sha256': metadata['csv_sha256'], 'code_sha256': code_fingerprint(),
            'production_reference': PRODUCTION_MODEL, 'scope': 'external_benchmark_only',
            'design': {'min_train': min_train, 'horizons': [1,3], 'step': step, 'primary_horizon': 3,
                       'method': 'Expanding rolling origin; nonoverlapping holdouts per horizon; same origins across models',
                       'mase': 'Training-prefix mean absolute first difference, m=1; undefined for constant prefixes',
                       'aggregation': 'Equal-weight industry mean MAE/MASE; square root of industry mean MSE'},
            'source': metadata, 'aggregate': summarize(rows), 'windows': rows,
            'gates': {'regression_tests': 'NOT_ASSESSED', 'downstream_financial_consistency': 'NOT_APPROVED'},
            'limitations': [metadata['vintage_limitation'], 'Industry indexes are not company revenue or cash evidence.',
                            'Shared macro shocks; series are economically diverse, not statistically independent.',
                            'Only three selected industries and transparent nonseasonal models; no universal best-model claim.',
                            'Win rates are descriptive; no significance test or selection-bias correction.',
                            'One/three-month validation cannot authorize a 13-week liquidity model change.']}

def load_benchmark_report(root: Path = DATA_ROOT) -> dict:
    _, metadata = load_external_benchmark(root)
    result_path = Path(root) / 'results.json'
    if sha256(result_path) != (Path(root) / 'results.sha256').read_text().strip():
        raise ValueError('Benchmark report checksum mismatch.')
    report = json.loads(result_path.read_text())
    if report.get('schema_version') != 1 or report.get('data_sha256') != metadata['csv_sha256'] or report.get('code_sha256') != code_fingerprint():
        raise ValueError('Benchmark results are stale; regenerate offline.')
    return report
