import pytest
from pydantic import ValidationError

from src.core.cash_events import CashEvent
from src.core.direct_cash import (
    DirectCashForecastInput,
)
from src.core.weekly_uncertainty import (
    CommittedTimingUncertainty,
    ModelledCashErrorSample,
    WeeklyUncertaintyProfile,
    validate_weekly_uncertainty_profile,
)


def _event(
    event_id,
    *,
    source_type,
    direction="INFLOW",
    status="ACTIVE",
):
    return CashEvent(
        event_id=event_id,
        date="2026-10-12",
        amount=10000.0,
        direction=direction,
        category="cash",
        source_type=source_type,
        status=status,
        source_reference=f"source-{event_id}",
    )


def _samples():
    return (
        ModelledCashErrorSample(
            inflow_error_pct=-0.10,
            outflow_error_pct=0.05,
        ),
        ModelledCashErrorSample(
            inflow_error_pct=0.00,
            outflow_error_pct=0.00,
        ),
        ModelledCashErrorSample(
            inflow_error_pct=0.08,
            outflow_error_pct=-0.04,
        ),
    )


def test_valid_weekly_uncertainty_profile():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "model-001",
                source_type="MODELLED",
            ),
            _event(
                "invoice-001",
                source_type="COMMITTED",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=(
            _samples()
        ),
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    0,
                    3,
                    7,
                ),
                source_reference=(
                    "historical-payment-timing"
                ),
            ),
        ),
    )

    validate_weekly_uncertainty_profile(
        forecast_input,
        profile,
    )


def test_modelled_cash_requires_at_least_three_error_pairs():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "model-001",
                source_type="MODELLED",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=(
            _samples()[:2]
        )
    )

    with pytest.raises(
        ValueError,
        match="At least 3 paired",
    ):
        validate_weekly_uncertainty_profile(
            forecast_input,
            profile,
        )


def test_no_modelled_cash_does_not_require_error_pairs():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "invoice-001",
                source_type="COMMITTED",
            ),
        ),
    )

    validate_weekly_uncertainty_profile(
        forecast_input,
        WeeklyUncertaintyProfile(),
    )


def test_timing_uncertainty_requires_three_samples():
    with pytest.raises(ValidationError):
        CommittedTimingUncertainty(
            event_id="invoice-001",
            timing_shift_days_samples=(0, 7),
            source_reference="timing-history",
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        float("nan"),
        float("inf"),
        float("-inf"),
        -1.01,
    ],
)
def test_invalid_modelled_error_is_rejected(
    value,
):
    with pytest.raises(ValidationError):
        ModelledCashErrorSample(
            inflow_error_pct=value,
            outflow_error_pct=0.0,
        )


def test_timing_uncertainty_unknown_event_is_rejected():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
    )

    profile = WeeklyUncertaintyProfile(
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="missing",
                timing_shift_days_samples=(
                    0,
                    3,
                    7,
                ),
                source_reference="timing-history",
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="unknown event ID",
    ):
        validate_weekly_uncertainty_profile(
            forecast_input,
            profile,
        )


def test_timing_uncertainty_requires_committed_event():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "model-001",
                source_type="MODELLED",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=(
            _samples()
        ),
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="model-001",
                timing_shift_days_samples=(
                    0,
                    3,
                    7,
                ),
                source_reference="timing-history",
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="COMMITTED",
    ):
        validate_weekly_uncertainty_profile(
            forecast_input,
            profile,
        )


def test_timing_uncertainty_requires_active_event():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "invoice-001",
                source_type="COMMITTED",
                status="CANCELLED",
            ),
        ),
    )

    profile = WeeklyUncertaintyProfile(
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    0,
                    3,
                    7,
                ),
                source_reference="timing-history",
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="ACTIVE",
    ):
        validate_weekly_uncertainty_profile(
            forecast_input,
            profile,
        )


def test_duplicate_timing_uncertainty_is_rejected():
    forecast_input = DirectCashForecastInput(
        start_date="2026-10-05",
        opening_cash=50000.0,
        events=(
            _event(
                "invoice-001",
                source_type="COMMITTED",
            ),
        ),
    )

    first = CommittedTimingUncertainty(
        event_id="invoice-001",
        timing_shift_days_samples=(0, 3, 7),
        source_reference="history-a",
    )

    second = CommittedTimingUncertainty(
        event_id="invoice-001",
        timing_shift_days_samples=(1, 2, 4),
        source_reference="history-b",
    )

    profile = WeeklyUncertaintyProfile(
        committed_timing_uncertainty=(
            first,
            second,
        )
    )

    with pytest.raises(
        ValueError,
        match="Duplicate committed timing",
    ):
        validate_weekly_uncertainty_profile(
            forecast_input,
            profile,
        )


def test_boolean_timing_shift_is_rejected():
    with pytest.raises(ValidationError):
        CommittedTimingUncertainty(
            event_id="invoice-001",
            timing_shift_days_samples=(
                0,
                True,
                7,
            ),
            source_reference="timing-history",
        )


def test_uncertainty_profile_is_immutable():
    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=(
            _samples()
        )
    )

    with pytest.raises(ValidationError):
        profile.modelled_flow_error_samples = ()


def test_uncertainty_profile_round_trips():
    profile = WeeklyUncertaintyProfile(
        modelled_flow_error_samples=(
            _samples()
        ),
        committed_timing_uncertainty=(
            CommittedTimingUncertainty(
                event_id="invoice-001",
                timing_shift_days_samples=(
                    -2,
                    0,
                    5,
                ),
                source_reference="timing-history",
            ),
        ),
    )

    payload = profile.model_dump(
        mode="json"
    )

    restored = (
        WeeklyUncertaintyProfile
        .model_validate(payload)
    )

    assert restored == profile
