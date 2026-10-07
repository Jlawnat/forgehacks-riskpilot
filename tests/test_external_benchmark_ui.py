from pathlib import Path
import ast
from streamlit.testing.v1 import AppTest


def test_forecast_workspace_displays_separate_external_and_business_evidence(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    at=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py',default_timeout=60).run()
    at.session_state['riskpilot_product_area']='Advanced Analytics'
    at.run()
    assert not at.exception
    texts='\n'.join(e.value for e in at.markdown)
    assert 'External Real-Data Benchmark' in texts
    assert 'Current Business Forecast' in texts
    assert 'REVIEW CHALLENGER' in texts
    assert 'not the current business revenue history' in texts
    for table in at.dataframe:
        if 'Improvement vs Naive' in table.value.columns:
            values = table.value['Improvement vs Naive'].dropna()
            assert all(value == 0 or abs(value) >= .05 for value in values)
    assert any(e.label=='Official observations' and e.value=='567' for e in at.metric)
    at.radio(key='external_benchmark_horizon').set_value(1).run()
    assert not at.exception
    assert at.radio(key='external_benchmark_horizon').value==1


def test_unavailable_external_evidence_does_not_break_business_forecast(monkeypatch):
    def unavailable(): raise ValueError('stale')
    monkeypatch.setattr('src.ui.external_benchmark.load_benchmark_report',unavailable)
    at=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py',default_timeout=60).run()
    at.session_state['riskpilot_product_area']='Advanced Analytics'; at.run()
    assert not at.exception
    assert any('unavailable or stale' in w.value for w in at.warning)
    assert any(e.label=='Production model' for e in at.metric)


def test_percent_display_normalizes_negative_zero():
    tree=ast.parse(Path('app.py').read_text())
    function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='percent')
    namespace={}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'percent','exec'),namespace)
    assert namespace['percent'](-.000001)=='0.0%'
    assert namespace['percent'](-.01)=='-1.0%'
    assert namespace['percent'](None)=='N/A'
