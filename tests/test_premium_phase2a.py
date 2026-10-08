"""Contract tests for the Phase 2A read-only financial evidence workspace."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api import premium_web as api
from src.api import verified_agent_workspace as workspace


def _patch_snapshots(monkeypatch):
    """Replace the already-bound readers, not merely module-level symbols.

    _WORKSPACE_TOOLS stores callable references when the module is imported.
    Patching named functions after import does not replace those references.
    """
    calls = []

    def make_reader(tool_name):
        def reader(context):
            calls.append((tool_name, context))
            return {
                "available": True,
                "scope": tool_name,
                "grounding_notes": {"verified": True},
            }
        return reader

    mocked_tools = tuple(
        (section_id, title, tool_name, make_reader(tool_name))
        for section_id, title, tool_name, _reader
        in workspace._WORKSPACE_TOOLS
    )
    assert len(mocked_tools) == 4
    monkeypatch.setattr(workspace, "_WORKSPACE_TOOLS", mocked_tools)
    return calls


def test_workspace_returns_four_read_only_snapshots_without_ai_calls(monkeypatch):
    calls = _patch_snapshots(monkeypatch)
    context = SimpleNamespace(tool_calls=[])
    result = workspace.build_verified_agent_workspace(
        context, scenario_name="Case A", imported=False
    )
    assert result["kind"] == "read_only_verified_engine_evidence"
    assert len(result["sections"]) == 4
    assert all(item["available"] for item in result["sections"])
    assert len(calls) == 4
    assert context.tool_calls == []


def test_evidence_workspace_uses_requested_customer_context(monkeypatch):
    calls = _patch_snapshots(monkeypatch)
    captured = []
    brief = object()
    baseline = SimpleNamespace(name="Customer Example")
    def fake_context(scenario_id, customer_session_id):
        captured.append((scenario_id, customer_session_id))
        return baseline, SimpleNamespace(brief=brief)
    monkeypatch.setattr(api, "_analysis_context", fake_context)
    response = TestClient(api.app).get(
        "/api/agent/verified-workspace/healthy",
        params={"customer_session_id": "test-session"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scenario_name"] == "Customer Example"
    assert body["source"] == "customer_upload"
    assert len(body["sections"]) == 4
    assert captured == [("healthy", "test-session")]
    assert all(call[1].liquidity_brief is brief for call in calls)
    assert response.headers["cache-control"] == "no-store"


def test_missing_customer_session_is_not_silently_replaced_with_demo(monkeypatch):
    calls = _patch_snapshots(monkeypatch)
    with api._CUSTOMER_LOCK:
        api._CUSTOMER_SESSIONS.clear()
    response = TestClient(api.app).get(
        "/api/agent/verified-workspace/healthy",
        params={"customer_session_id": "nonexistent-customer-session"},
    )
    assert response.status_code == 404
    assert calls == []
