from pathlib import Path

from src.core.direct_cash import (
    DirectCashForecastInput,
    build_direct_cash_forecast,
)
from src.ingestion.customer_cash import (
    build_customer_cash_events,
    parse_customer_cash_csv,
)


EXPECTED_LIQUIDITY = (
    26_749_000.0,
    21_120_000.0,
    17_393_000.0,
    9_315_000.0,
    53_229_000.0,
    56_960_000.0,
    104_966_000.0,
    106_507_000.0,
    92_176_000.0,
    87_969_000.0,
    92_041_000.0,
    119_004_000.0,
    122_706_000.0,
)


def test_public_sec_csv_reconciles_exact_liquidity_path():
    path = Path(
        "data/public/"
        "cenveo_2018_sec_liquidity_movements.csv"
    )

    raw = parse_customer_cash_csv(
        path.read_bytes()
    )

    events = build_customer_cash_events(
        raw,
        upload_reference=(
            "Cenveo 2018 SEC Exhibit 99.4"
        ),
    )

    forecast_input = (
        DirectCashForecastInput(
            start_date="2017-12-30",
            opening_cash=26_749_000.0,
            events=events,
        )
    )

    result = build_direct_cash_forecast(
        forecast_input
    )

    actual = tuple(
        float(
            week.closing_cash
        )
        for week in result.weeks
    )

    assert actual == EXPECTED_LIQUIDITY


def test_public_sec_liquidity_trough_is_week_four():
    path = Path(
        "data/public/"
        "cenveo_2018_sec_liquidity_movements.csv"
    )

    raw = parse_customer_cash_csv(
        path.read_bytes()
    )

    events = build_customer_cash_events(
        raw,
        upload_reference=(
            "Cenveo 2018 SEC Exhibit 99.4"
        ),
    )

    result = build_direct_cash_forecast(
        DirectCashForecastInput(
            start_date="2017-12-30",
            opening_cash=26_749_000.0,
            events=events,
        )
    )

    assert (
        result.minimum_closing_cash
        == 9_315_000.0
    )

    assert (
        result.minimum_closing_cash_week
        == 4
    )
