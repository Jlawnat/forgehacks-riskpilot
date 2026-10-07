"""Reproduce every fit and metric offline from the frozen official ABS data."""
import importlib.metadata
import json
import platform
from src.forecasting.external_benchmark import DATA_ROOT, build_benchmark, load_external_benchmark, sha256

if __name__ == '__main__':
    frame, metadata = load_external_benchmark()
    report = build_benchmark(frame, metadata)
    report['runtime'] = {'python': platform.python_version(), **{name: importlib.metadata.version(name) for name in ('numpy', 'pandas', 'statsmodels')}}
    (DATA_ROOT / 'results.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (DATA_ROOT / 'results.sha256').write_text(sha256(DATA_ROOT / 'results.json') + '\n')
    for row in report['aggregate']:
        print(row)
