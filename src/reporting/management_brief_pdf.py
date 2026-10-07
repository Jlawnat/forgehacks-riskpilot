from __future__ import annotations

from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import (
    TA_CENTER,
    TA_LEFT,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.core.command_center import (
    CommandCenterResult,
)


NAVY = colors.HexColor("#0B1739")
BLUE = colors.HexColor("#2563EB")
SLATE = colors.HexColor("#64748B")
LIGHT = colors.HexColor("#F8FAFC")
BORDER = colors.HexColor("#E2E8F0")
GREEN = colors.HexColor("#047857")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")


def _money(
    value: float,
) -> str:
    return f"${value:,.0f}"


def _pct(
    value: float,
) -> str:
    return f"{value * 100:.1f}%"


def _status(
    result: CommandCenterResult,
) -> tuple[str, colors.Color]:
    position = (
        result.brief.position
    )

    uncertainty = (
        result.brief.uncertainty
    )

    if (
        position
        .first_reserve_breach_week
        is not None
    ):
        return (
            "ACTION REQUIRED",
            RED,
        )

    if (
        uncertainty is not None
        and not uncertainty
        .within_risk_appetite
    ):
        return (
            "RISK ABOVE APPETITE",
            AMBER,
        )

    return (
        "LIQUIDITY HEALTHY",
        GREEN,
    )


def _safe_text(
    value: object,
) -> str:
    if value is None:
        return "-"

    return str(value)


def _driver_rows(
    result: CommandCenterResult,
) -> list[list[str]]:
    rows: list[list[str]] = [
        [
            "Driver",
            "Week",
            "Evidence",
            "Direction",
            "Cash impact",
        ]
    ]

    for driver in (
        result.brief.cash_drivers
    ):
        impact = float(
            driver.signed_cash_effect
        )

        impact_text = (
            f"+{_money(impact)}"
            if impact >= 0
            else f"-{_money(abs(impact))}"
        )

        rows.append(
            [
                driver.category,
                f"W{driver.week_number}",
                driver.source_type,
                driver.direction,
                impact_text,
            ]
        )

    return rows


def _weekly_rows(
    result: CommandCenterResult,
) -> list[list[str]]:
    rows = [
        [
            "Week",
            "Closing cash",
            "Reserve",
            "Headroom",
        ]
    ]

    reserve = float(
        result.brief
        .position
        .management_reserve
    )

    for week in (
        result.snapshot
        .forecast
        .weeks
    ):
        closing = float(
            week.closing_cash
        )

        rows.append(
            [
                f"W{week.week_number}",
                _money(closing),
                _money(reserve),
                _money(
                    closing - reserve
                ),
            ]
        )

    return rows


def _build_styles():
    styles = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "RiskPilotTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=NAVY,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "RiskPilotSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=SLATE,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "RiskPilotSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "RiskPilotBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.7,
            leading=12,
            textColor=colors.HexColor(
                "#334155"
            ),
        ),
        "small": ParagraphStyle(
            "RiskPilotSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=10,
            textColor=SLATE,
        ),
        "status": ParagraphStyle(
            "RiskPilotStatus",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "RiskPilotMetricLabel",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=SLATE,
            alignment=TA_LEFT,
        ),
        "metric_value": ParagraphStyle(
            "RiskPilotMetricValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
        ),
    }


def _page_footer(
    canvas,
    doc,
) -> None:
    canvas.saveState()

    width, _ = A4

    canvas.setStrokeColor(
        BORDER
    )
    canvas.line(
        18 * mm,
        13 * mm,
        width - 18 * mm,
        13 * mm,
    )

    canvas.setFont(
        "Helvetica",
        7,
    )

    canvas.setFillColor(
        SLATE
    )

    canvas.drawString(
        18 * mm,
        8 * mm,
        "RiskPilot - AI Liquidity Decision Intelligence",
    )

    canvas.drawRightString(
        width - 18 * mm,
        8 * mm,
        f"Page {doc.page}",
    )

    canvas.restoreState()


def _metric_card(
    label: str,
    value: str,
    styles,
):
    return [
        Paragraph(
            label,
            styles["metric_label"],
        ),
        Paragraph(
            value,
            styles["metric_value"],
        ),
    ]


def _metric_table(
    result: CommandCenterResult,
    styles,
):
    position = (
        result.brief.position
    )

    uncertainty = (
        result.brief.uncertainty
    )

    evidence = (
        "-"
        if (
            position
            .evidence_coverage_ratio
            is None
        )
        else _pct(
            position
            .evidence_coverage_ratio
        )
    )

    breach_risk = (
        "-"
        if uncertainty is None
        else _pct(
            uncertainty
            .reserve_breach_probability
        )
    )

    cells = [
        _metric_card(
            "Current cash",
            _money(
                position.current_cash
            ),
            styles,
        ),
        _metric_card(
            "Minimum cash",
            (
                f"{_money(position.minimum_closing_cash)} "
                f"(W{position.minimum_closing_cash_week})"
            ),
            styles,
        ),
        _metric_card(
            "Management reserve",
            _money(
                position.management_reserve
            ),
            styles,
        ),
        _metric_card(
            "13-week closing cash",
            _money(
                position.closing_cash_13_week
            ),
            styles,
        ),
        _metric_card(
            "Reserve breach risk",
            breach_risk,
            styles,
        ),
        _metric_card(
            "Evidence coverage",
            evidence,
            styles,
        ),
    ]

    data = [
        cells[:3],
        cells[3:],
    ]

    table = Table(
        data,
        colWidths=[
            56 * mm,
            56 * mm,
            56 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    LIGHT,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    BORDER,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
            ]
        )
    )

    return table


def _standard_table(
    rows: Iterable[
        Iterable[object]
    ],
    *,
    widths,
):
    data = [
        [
            _safe_text(cell)
            for cell in row
        ]
        for row in rows
    ]

    table = Table(
        data,
        colWidths=widths,
        repeatRows=1,
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    NAVY,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (0, 1),
                    (-1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    7.2,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    BORDER,
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [
                        colors.white,
                        LIGHT,
                    ],
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4,
                ),
            ]
        )
    )

    return table


def build_management_brief_pdf(
    result: CommandCenterResult,
) -> bytes:
    """
    Build a management-facing PDF exclusively from already
    calculated RiskPilot Command Center outputs.

    This exporter does not recalculate forecast, risk,
    recovery or financial values.
    """
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=(
            "RiskPilot Management Brief"
        ),
        author="RiskPilot",
        subject=(
            "13-week liquidity decision brief"
        ),
    )

    styles = _build_styles()

    story = []

    status_text, status_color = (
        _status(result)
    )

    story.append(
        Paragraph(
            "RiskPilot",
            styles["title"],
        )
    )

    story.append(
        Paragraph(
            (
                "Management Liquidity Brief | "
                f"{result.scenario_name}"
            ),
            styles["subtitle"],
        )
    )

    status_table = Table(
        [
            [
                Paragraph(
                    status_text,
                    styles["status"],
                ),
                Paragraph(
                    (
                        "Forecast start: "
                        f"{result.brief.forecast_start_date.isoformat()}"
                    ),
                    styles["small"],
                ),
                Paragraph(
                    (
                        "Generated: "
                        f"{result.brief.created_at.strftime('%Y-%m-%d %H:%M UTC')}"
                    ),
                    styles["small"],
                ),
            ]
        ],
        colWidths=[
            45 * mm,
            58 * mm,
            65 * mm,
        ],
    )

    status_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, 0),
                    colors.Color(
                        status_color.red,
                        status_color.green,
                        status_color.blue,
                        alpha=0.08,
                    ),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (0, 0),
                    status_color,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    BORDER,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(
        status_table
    )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    story.append(
        Paragraph(
            "Executive liquidity position",
            styles["section"],
        )
    )

    story.append(
        _metric_table(
            result,
            styles,
        )
    )

    position = (
        result.brief.position
    )

    if (
        position
        .first_reserve_breach_week
        is not None
    ):
        decision_text = (
            "The deterministic forecast falls below the "
            "management reserve in Week "
            f"{position.first_reserve_breach_week}. "
            "Management action should be reviewed before "
            "the first forecast breach."
        )

    elif (
        result.brief.uncertainty
        is not None
        and not (
            result.brief
            .uncertainty
            .within_risk_appetite
        )
    ):
        decision_text = (
            "The deterministic cash position remains above "
            "reserve, but simulated reserve-breach risk "
            "exceeds the stated management appetite."
        )

    else:
        decision_text = (
            "The current 13-week liquidity position remains "
            "within the stated management reserve and risk "
            "appetite under the verified RiskPilot analysis."
        )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    story.append(
        Paragraph(
            decision_text,
            styles["body"],
        )
    )

    story.append(
        Paragraph(
            "13-week liquidity schedule",
            styles["section"],
        )
    )

    story.append(
        _standard_table(
            _weekly_rows(
                result
            ),
            widths=[
                22 * mm,
                48 * mm,
                48 * mm,
                48 * mm,
            ],
        )
    )

    if result.brief.cash_drivers:
        story.append(
            Paragraph(
                "Material cash drivers",
                styles["section"],
            )
        )

        story.append(
            _standard_table(
                _driver_rows(
                    result
                ),
                widths=[
                    58 * mm,
                    18 * mm,
                    34 * mm,
                    28 * mm,
                    32 * mm,
                ],
            )
        )

    uncertainty = (
        result.brief.uncertainty
    )

    if uncertainty is not None:
        story.append(
            Paragraph(
                "Liquidity uncertainty",
                styles["section"],
            )
        )

        uncertainty_rows = [
            [
                "Measure",
                "Value",
            ],
            [
                "Reserve breach probability",
                _pct(
                    uncertainty
                    .reserve_breach_probability
                ),
            ],
            [
                "Maximum acceptable breach probability",
                _pct(
                    uncertainty
                    .maximum_acceptable_breach_probability
                ),
            ],
            [
                "Within risk appetite",
                (
                    "Yes"
                    if uncertainty
                    .within_risk_appetite
                    else "No"
                ),
            ],
            [
                "Median minimum cash",
                _money(
                    uncertainty
                    .median_min_cash
                ),
            ],
            [
                "P10 minimum cash",
                _money(
                    uncertainty
                    .p10_min_cash
                ),
            ],
            [
                "Liquidity buffer at confidence",
                _money(
                    uncertainty
                    .liquidity_buffer_at_confidence
                ),
            ],
            [
                "Simulation runs",
                str(
                    uncertainty
                    .simulations
                ),
            ],
        ]

        story.append(
            _standard_table(
                uncertainty_rows,
                widths=[
                    92 * mm,
                    76 * mm,
                ],
            )
        )

    recovery = (
        result.brief.recovery
    )

    if recovery is not None:
        story.append(
            Paragraph(
                "Management recovery plan",
                styles["section"],
            )
        )

        recovery_rows = [
            [
                "Recovery measure",
                "Value",
            ],
            [
                "Revenue improvement",
                (
                    f"{recovery.revenue_improvement_pct:.1f}%"
                ),
            ],
            [
                "Cost reduction",
                (
                    f"{recovery.cost_reduction_pct:.1f}%"
                ),
            ],
            [
                "Receivable acceleration",
                (
                    f"{recovery.receivable_acceleration_days} days"
                ),
            ],
            [
                "External liquidity",
                _money(
                    recovery.external_liquidity
                ),
            ],
            [
                "Resulting minimum cash",
                (
                    f"{_money(recovery.resulting_min_cash)} "
                    f"(W{recovery.resulting_min_cash_week})"
                ),
            ],
            [
                "Deterministically feasible",
                (
                    "Yes"
                    if recovery
                    .deterministic_feasible
                    else "No"
                ),
            ],
        ]

        if (
            recovery
            .reserve_breach_probability
            is not None
        ):
            recovery_rows.append(
                [
                    "Recovery reserve-breach risk",
                    _pct(
                        recovery
                        .reserve_breach_probability
                    ),
                ]
            )

        story.append(
            _standard_table(
                recovery_rows,
                widths=[
                    92 * mm,
                    76 * mm,
                ],
            )
        )

    monitoring = (
        result.brief.monitoring
    )

    if monitoring is not None:
        story.append(
            Paragraph(
                "Monitoring",
                styles["section"],
            )
        )

        monitoring_summary = [
            [
                "Active triggers",
                str(
                    monitoring
                    .active_trigger_count
                ),
            ],
            [
                "Critical triggers",
                str(
                    monitoring
                    .critical_trigger_count
                ),
            ],
            [
                "Warning triggers",
                str(
                    monitoring
                    .warning_trigger_count
                ),
            ],
        ]

        story.append(
            _standard_table(
                [
                    [
                        "Monitoring measure",
                        "Value",
                    ],
                    *monitoring_summary,
                ],
                widths=[
                    92 * mm,
                    76 * mm,
                ],
            )
        )

        if monitoring.triggers:
            trigger_rows = [
                [
                    "Severity",
                    "Trigger",
                    "Reason",
                ]
            ]

            for trigger in (
                monitoring.triggers
            ):
                trigger_rows.append(
                    [
                        trigger.severity,
                        trigger.trigger_type,
                        trigger.message,
                    ]
                )

            story.append(
                Spacer(
                    1,
                    3 * mm,
                )
            )

            story.append(
                _standard_table(
                    trigger_rows,
                    widths=[
                        27 * mm,
                        55 * mm,
                        86 * mm,
                    ],
                )
            )

    story.append(
        PageBreak()
    )

    story.append(
        Paragraph(
            "Evidence and governance",
            styles["section"],
        )
    )

    evidence_rows = [
        [
            "Evidence category",
            "Amount",
        ],
        [
            "Committed evidence",
            _money(
                position
                .committed_evidence_amount
            ),
        ],
        [
            "Modelled residual",
            _money(
                position
                .modelled_residual_amount
            ),
        ],
        [
            "Management assumptions",
            _money(
                position
                .management_assumption_amount
            ),
        ],
    ]

    story.append(
        _standard_table(
            evidence_rows,
            widths=[
                92 * mm,
                76 * mm,
            ],
        )
    )

    limitations = list(
        result.brief.limitations
    )

    if uncertainty is not None:
        limitations.extend(
            uncertainty.limitations
        )

    if limitations:
        story.append(
            Paragraph(
                "Model limitations",
                styles["section"],
            )
        )

        for item in dict.fromkeys(
            limitations
        ):
            story.append(
                Paragraph(
                    f"- {item}",
                    styles["body"],
                )
            )

            story.append(
                Spacer(
                    1,
                    1.5 * mm,
                )
            )

    story.append(
        Paragraph(
            "Governance statement",
            styles["section"],
        )
    )

    story.append(
        Paragraph(
            (
                "This document is generated from verified "
                "RiskPilot engine outputs. The export layer "
                "does not recalculate or replace forecast, "
                "liquidity, probability, recovery or evidence "
                "values. Modelled and management-assumption "
                "cash flows should be reviewed alongside their "
                "underlying evidence before management action."
            ),
            styles["body"],
        )
    )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    story.append(
        Paragraph(
            (
                f"Snapshot ID: {result.snapshot.snapshot_id}<br/>"
                f"Forecast fingerprint: "
                f"{result.snapshot.forecast_basis_fingerprint}"
            ),
            styles["small"],
        )
    )

    doc.build(
        story,
        onFirstPage=_page_footer,
        onLaterPages=_page_footer,
    )

    return buffer.getvalue()
