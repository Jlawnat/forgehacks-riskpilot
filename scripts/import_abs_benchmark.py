"""Reimport frozen ABS files, or explicitly fetch the pinned official release."""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / 'data' / 'external_benchmark'
SOURCE = 'https://www.abs.gov.au/statistics/economy/business-indicators/monthly-business-turnover-indicator/sep-2025'
SERIES = [
    ('retail', 'Retail trade', 'A124873965J', '5681007_Retail_trade.xlsx'),
    ('accommodation', 'Accommodation and food services', 'A124873821W', '5681008_Accommodation_food_services.xlsx'),
    ('professional', 'Professional, scientific and technical services', 'A124873641L', '5681011_Professional_scientific_technical_services.xlsx'),
]

def import_data(fetch: bool = False) -> None:
    ROOT.joinpath('raw').mkdir(parents=True, exist_ok=True)
    previous = json.loads((ROOT / 'metadata.json').read_text()) if (ROOT / 'metadata.json').exists() else {}
    retrieved = datetime.now(timezone.utc).date().isoformat() if fetch or not previous else previous['retrieved_at']
    rows, metadata = [], []
    for key, name, series_id, filename in SERIES:
        path = ROOT / 'raw' / f'{key}.xlsx'
        url = f'{SOURCE}/{filename}'
        if fetch:
            with urlopen(url, timeout=45) as response:
                path.write_bytes(response.read())
        sheet = pd.read_excel(path, sheet_name='Data1', header=None)
        columns = [c for c in range(1, sheet.shape[1]) if sheet.iloc[9, c] == series_id]
        if len(columns) != 1:
            raise ValueError(f'ABS series ID not found uniquely: {series_id}')
        c = columns[0]
        exact_name = str(sheet.iloc[0, c])
        if sheet.iloc[2, c] != 'Seasonally Adjusted' or sheet.iloc[3, c] != 'INDEX' or f';  {name} ;' not in exact_name:
            raise ValueError('ABS schema, series name or adjustment changed')
        data = sheet.iloc[10:, [0, c]].dropna(how='all')
        dates = pd.to_datetime(data.iloc[:, 0], errors='raise')
        values = pd.to_numeric(data.iloc[:, 1], errors='raise')
        for date, value in zip(dates, values):
            rows.append({'series_id': series_id, 'date': date.strftime('%Y-%m-%d'), 'value': float(value)})
        metadata.append({'series_id': series_id, 'industry': name, 'exact_series_name': exact_name,
                         'series_type': 'Seasonally Adjusted', 'units': 'Index points; July 2019 = 100',
                         'source_url': url, 'raw_file': f'raw/{key}.xlsx',
                         'raw_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'observations': len(data), 'start': dates.min().strftime('%Y-%m-%d'),
                         'end': dates.max().strftime('%Y-%m-%d')})
    frame = pd.DataFrame(rows).sort_values(['series_id', 'date'])
    frame.to_csv(ROOT / 'observations.csv', index=False, float_format='%.1f', lineterminator='\n')
    manifest = {'schema_version': 1, 'source_name': 'Australian Bureau of Statistics — Monthly Business Turnover Indicator',
                'source_url': SOURCE, 'methodology_url': 'https://www.abs.gov.au/methodologies/monthly-business-turnover-indicator-methodology/sep-2025',
                'release_date': '2025-11-10', 'release_period': 'September 2025', 'publication_status': 'Ceased; historical external benchmark',
                'retrieved_at': retrieved, 'purpose': 'EXTERNAL MODEL BENCHMARK ONLY; not demo-company revenue',
                'transformations': 'Selected official seasonally adjusted current-price industry index columns by series ID; ISO dates; no imputation, smoothing, rescaling or outlier removal.',
                'vintage_limitation': 'Final revised September 2025 vintage, including concurrent seasonal adjustment; not an as-published real-time backtest.',
                'csv_sha256': hashlib.sha256((ROOT / 'observations.csv').read_bytes()).hexdigest(), 'series': metadata}
    (ROOT / 'metadata.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Imported {len(frame)} official observations across {len(metadata)} series.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Download pinned ABS release; default reimports frozen XLSX files offline.')
    import_data(parser.parse_args().fetch)
