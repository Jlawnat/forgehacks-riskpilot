from datetime import datetime, timezone

from src.demo.v2_scenarios import (
    get_v2_demo_scenario,
)
from src.core.command_center import (
    build_command_center,
)
from src.reporting.management_brief_pdf import (
    build_management_brief_pdf,
)


def _result():
    scenario = get_v2_demo_scenario(
        "healthy"
    )

    return build_command_center(
        scenario,
        created_at=datetime(
            2026,
            10,
            7,
            8,
            0,
            tzinfo=timezone.utc,
        ),
        simulations=200,
        seed=42,
    )


def test_management_brief_pdf_is_valid_pdf_bytes():
    payload = (
        build_management_brief_pdf(
            _result()
        )
    )

    assert payload.startswith(
        b"%PDF"
    )

    assert len(payload) > 3000


def test_management_brief_pdf_is_deterministic_for_same_result():
    result = _result()

    first = (
        build_management_brief_pdf(
            result
        )
    )

    second = (
        build_management_brief_pdf(
            result
        )
    )

    assert first.startswith(
        b"%PDF"
    )

    assert second.startswith(
        b"%PDF"
    )

    assert len(first) > 3000
    assert len(second) > 3000
