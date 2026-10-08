"""Source-level contracts for the premium decision-workspace UI safety gates."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_monthly_assumption_changes_expire_previous_results():
    source = (ROOT / "web/src/RestoredWorkspaces.jsx").read_text()
    assert "const invalidateMonthlySession" in source
    assert "setSession(null); setStress(null); setReverse(null); setAnswer(null);" in source
    assert 'onChange={updateHorizon}' in source
    assert 'onChange={updateReserve}' in source
    assert 'updateMonthlyShock("revenue", v)' in source
    assert 'updateMonthlyShock("cost", v)' in source
    assert 'updateMonthlyShock("delay", v)' in source
    assert 'onChange={e => { setFile(e.target.files?.[0] || null); invalidateMonthlySession(); }}' in source


def test_custom_comparison_requires_two_verified_results():
    source = (ROOT / "web/src/RestoredWorkspaces.jsx").read_text()
    assert "manualResult && selectedOptimisedPlan" in source
    assert "buildRecoveryComparison(selectedOptimisedPlan, manualResult)" in source
    assert "Compare the two verified plan outputs" in source
    assert "selectedCompareIndex" in source
    assert "setManualResult(null)" in source


def test_customer_mapping_explicitly_discloses_default_classification():
    source = (ROOT / "web/src/CustomerAdvancedImport.jsx").read_text()
    assert "AR" not in source or "Accounts Receivable" in source
    assert "default to COMMITTED" in source
    assert "Source labels alone do not verify a transaction." in source
