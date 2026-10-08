"""Read-only synthetic fixture library and per-browser ownership for a public judge sandbox.

The project financial engines are never changed. Public uploads are limited to
exact bytes distributed by this application: this is not a real-data service.
"""
from __future__ import annotations

import csv
from contextvars import ContextVar
from functools import lru_cache
from io import BytesIO, StringIO
from pathlib import Path
from datetime import date, timedelta
from hashlib import sha256
from threading import Lock
from time import monotonic
import hmac
import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

_CURRENT_VISITOR: ContextVar[str | None] = ContextVar("riskpilot_public_visitor", default=None)


def public_interactive_enabled() -> bool:
    return os.environ.get("RISKPILOT_PUBLIC_INTERACTIVE", "").strip().lower() in {"1", "true", "yes", "on"}


def set_public_visitor(visitor_id: str):
    return _CURRENT_VISITOR.set(visitor_id)


def reset_public_visitor(token):
    _CURRENT_VISITOR.reset(token)


def current_public_owner() -> str | None:
    """Return the current cookie-bound visitor, or None in private/local mode."""
    if not public_interactive_enabled():
        return None
    owner = _CURRENT_VISITOR.get()
    if not owner:
        raise HTTPException(status_code=403, detail="Interactive demo session missing. Reload the website.")
    return owner


def history_storage_key(history_key: str):
    """Different browser sessions cannot collide even with identical history_key."""
    owner = current_public_owner()
    return (owner, history_key) if owner else history_key


_ISSUED: dict[str, tuple[str, float]] = {}
_ISSUED_LOCK = Lock()
_ISSUED_TTL = 7200

_DEMO_FILES = {
    "cash.csv", "cash.xlsx", "receipts.csv", "receipts.xlsx",
    "payments.csv", "payments.xlsx", "actuals.csv",
}


def _normalize_csv(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").rstrip(b"\n")


def _customer_csv(forecast_start: str | None = None) -> bytes:
    # Lazy imports avoid circular dependencies with the Premium API.
    from src.api.premium_web import synthetic_demo_csv
    raw = bytes(synthetic_demo_csv().body)
    if forecast_start is None:
        return raw
    from src.api.premium_demo import synthetic_management_demo
    target = date.fromisoformat(forecast_start)
    if not (date(2025, 1, 1) <= target <= date(2031, 12, 31)):
        raise ValueError("Demo forecast date must be between 2025 and 2031.")
    delta = target - synthetic_management_demo().forecast_input.start_date
    reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames or [], lineterminator="\n")
    writer.writeheader()
    for row in reader:
        for field in ("date", "due_date", "expected_cash_date"):
            if row.get(field):
                row[field] = (date.fromisoformat(row[field]) + delta).isoformat()
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def _csv_subset(kind: str, forecast_start: str | None = None) -> bytes:
    full = _customer_csv(forecast_start).decode("utf-8-sig")
    reader = csv.DictReader(StringIO(full))
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=reader.fieldnames or [], lineterminator="\n")
    writer.writeheader()
    rows = [row for row in reader if row.get("direction") == ("INFLOW" if kind == "receipts" else "OUTFLOW")]
    if not rows:
        raise RuntimeError(f"The built-in {kind} synthetic demo contains no eligible events.")
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _observed_csv() -> bytes:
    """Fictional observations derived from sample events, never actual company activity."""
    raw = _customer_csv().decode("utf-8-sig")
    reader = csv.DictReader(StringIO(raw))
    fieldnames = ["actual_id", "date", "amount", "direction", "source_reference", "forecast_event_id"]
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for i, row in enumerate(reader):
        if i >= 5:
            break
        writer.writerow({
            "actual_id": f"fictional-actual-{i+1}",
            "date": row.get("date", ""),
            "amount": row.get("amount", ""),
            "direction": row.get("direction", ""),
            "source_reference": row.get("source_reference") or f"fictional-sample-{i+1}",
            "forecast_event_id": row.get("event_id", ""),
        })
    return output.getvalue().encode("utf-8")


def _make_xlsx(raw: bytes) -> bytes:
    from openpyxl import Workbook
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Synthetic Cash Events"
    for cells in csv.reader(StringIO(raw.decode("utf-8-sig"))):
        sheet.append(cells)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


@lru_cache(maxsize=160)
def sample_bytes(name: str, forecast_start: str | None = None) -> bytes:
    if name not in _DEMO_FILES and name != "monthly.csv":
        raise ValueError("Sample not found")
    if name == "monthly.csv":
        return (Path(__file__).resolve().parents[2] / "web" / "public" /
                "RiskPilot_Harborview_Synthetic_Monthly.csv").read_bytes()
    kind, ext = name.rsplit(".", 1)
    if kind == "cash":
        csv_data = _customer_csv(forecast_start)
    elif kind in {"receipts", "payments"}:
        csv_data = _csv_subset(kind, forecast_start)
    elif kind == "actuals":
        csv_data = _observed_csv()
    else:
        raise ValueError("Sample not found")
    return csv_data if ext == "csv" else _make_xlsx(csv_data)


def _digest(raw: bytes, filename: str) -> str:
    canonical = _normalize_csv(raw) if filename.lower().endswith(".csv") else raw
    return sha256(canonical).hexdigest()


def _remember_sample(name: str, raw: bytes):
    now = monotonic()
    key = _digest(raw, name)
    with _ISSUED_LOCK:
        for k, (_, expires) in list(_ISSUED.items()):
            if expires < now:
                _ISSUED.pop(k, None)
        if len(_ISSUED) > 256:
            for k in list(_ISSUED)[:64]:
                _ISSUED.pop(k, None)
        _ISSUED[key] = (name, now + _ISSUED_TTL)


def require_demo_upload(raw: bytes, filename: str | None, *, purpose: str) -> None:
    """Only files issued by this service (or the official fixed monthly file)."""
    if not public_interactive_enabled():
        return
    suffix = Path(filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}:
        raise HTTPException(403, "Use an official synthetic CSV or XLSX demo download.")
    if purpose == "monthly":
        allowed_names = {"monthly.csv"}
    elif purpose == "customer":
        allowed_names = {"cash.csv"}
    elif purpose == "actuals":
        allowed_names = {"actuals.csv"}
    elif purpose == "mapping":
        allowed_names = _DEMO_FILES - {"actuals.csv"}
    else:
        raise HTTPException(403, "Unrecognised demo upload type.")
    # Also support the official static examples already shipped with RiskPilot.
    for canonical_name in allowed_names:
        if canonical_name.endswith(suffix):
            original = sample_bytes(canonical_name)
            if hmac.compare_digest(_digest(raw, filename or ""), _digest(original, canonical_name)):
                return
    with _ISSUED_LOCK:
        entry = _ISSUED.get(_digest(raw, filename or ""))
    if entry and entry[0] in allowed_names and entry[0].endswith(suffix) and entry[1] >= monotonic():
        return
    raise HTTPException(403, detail=(
        "Public judge sandbox accepts only RiskPilot synthetic sample downloads. "
        "Do not upload private or customer financial data. "
        "Download the current-date examples from Company Data or Advanced Monthly Analyst."
    ))


router = APIRouter(prefix="/api/demo", tags=["Public judge synthetic samples"])


@router.get("/samples/{sample_name}")
def download_synthetic_sample(sample_name: str, forecast_start: str | None = None):
    if sample_name not in _DEMO_FILES:
        raise HTTPException(404, "Synthetic sample not found.")
    try:
        content = sample_bytes(sample_name, forecast_start if sample_name != "actuals.csv" else None)
    except ValueError:
        raise HTTPException(422, "Invalid synthetic forecast start date.") from None
    _remember_sample(sample_name, content)
    media_type = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  if sample_name.endswith(".xlsx") else "text/csv")
    return Response(content=content, media_type=media_type,
                    headers={"Content-Disposition": f'attachment; filename="RiskPilot_Synthetic_{sample_name}"',
                             "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
