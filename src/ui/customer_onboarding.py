from __future__ import annotations

from datetime import date

import streamlit as st

from src.demo.v2_scenarios import (
    V2DemoScenario,
)
from src.ui.customer_history import (
    clear_customer_history,
)
from src.ingestion.customer_cash import (
    build_customer_cash_events,
    build_customer_import_report,
    build_customer_scenario,
    customer_cash_template,
    parse_customer_cash_csv,
)
from src.ingestion.customer_mapping import (
    build_standard_cash_dataframe,
    list_excel_sheets,
    load_customer_table,
    suggest_mapping,
)
from src.ingestion.customer_multi_source import (
    SOURCE_PROFILES,
    merge_standardized_sources,
)


CUSTOMER_SCENARIO_STATE_KEY = (
    "riskpilot_customer_scenario"
)

CUSTOMER_REPORT_STATE_KEY = (
    "riskpilot_customer_report"
)


def _inject_customer_styles() -> None:
    st.markdown(
        """
        <style>

        /* Customer onboarding is a dedicated 13-week workspace.
           Hide the separate monthly analytics sidebar here to
           avoid conflicting reserve / risk policy controls. */
        [data-testid="stSidebar"] {
            display: none !important;
        }

        [data-testid="collapsedControl"] {
            display: none !important;
        }

        .rp-customer-hero {
            margin: 0.55rem 0 0.85rem;
            padding: 1rem 1.1rem;
            border: 1px solid #d9e5f4;
            border-radius: 12px;
            background:
                linear-gradient(
                    115deg,
                    #f5f9ff 0%,
                    #ffffff 68%
                );
            box-shadow:
                0 6px 20px
                rgba(15, 42, 93, 0.035);
        }

        .rp-customer-kicker {
            color: #2563eb;
            font-size: 0.61rem;
            font-weight: 820;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }

        .rp-customer-title {
            color: #0b1739;
            font-size: 1.18rem;
            font-weight: 780;
            letter-spacing: -0.025em;
            margin-bottom: 0.25rem;
        }

        .rp-customer-copy {
            max-width: 900px;
            color: #65758e;
            font-size: 0.78rem;
            line-height: 1.5;
        }

        .rp-data-ready {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.72rem 0.85rem;
            margin: 0.45rem 0 0.7rem;
            border: 1px solid #bee8d7;
            border-radius: 9px;
            background: #f1fbf7;
        }

        .rp-data-ready-title {
            color: #087451;
            font-size: 0.76rem;
            font-weight: 760;
        }

        .rp-data-ready-copy {
            color: #5f716b;
            font-size: 0.66rem;
            margin-top: 0.14rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _stored_scenario(
) -> V2DemoScenario | None:
    payload = st.session_state.get(
        CUSTOMER_SCENARIO_STATE_KEY
    )

    if payload is None:
        return None

    try:
        return V2DemoScenario.model_validate(
            payload
        )
    except Exception:
        st.session_state.pop(
            CUSTOMER_SCENARIO_STATE_KEY,
            None,
        )
        st.session_state.pop(
            CUSTOMER_REPORT_STATE_KEY,
            None,
        )
        return None


def clear_customer_scenario() -> None:
    st.session_state.pop(
        CUSTOMER_SCENARIO_STATE_KEY,
        None,
    )

    st.session_state.pop(
        CUSTOMER_REPORT_STATE_KEY,
        None,
    )

    # A customer baseline timestamp is intentionally stable while
    # the same imported scenario is active so Copilot state survives
    # Streamlit reruns. When customer data is replaced, remove those
    # timestamps so the next imported dataset receives a fresh
    # baseline identity.
    for key in list(
        st.session_state.keys()
    ):
        if key.startswith(
            "riskpilot_customer_baseline_created_at_"
        ):
            st.session_state.pop(
                key,
                None,
            )

    clear_customer_history()


def render_customer_onboarding(
) -> V2DemoScenario | None:
    _inject_customer_styles()

    stored = _stored_scenario()

    if stored is not None:
        left, right = st.columns(
            [5, 1],
            vertical_alignment="center",
        )

        with left:
            st.markdown(
                (
                    '<div class="rp-data-ready">'
                    '<div>'
                    '<div class="rp-data-ready-title">'
                    '✓ COMPANY DATA VALIDATED'
                    '</div>'
                    '<div class="rp-data-ready-copy">'
                    f'{stored.name} · '
                    '13-week direct cash workspace · '
                    'RiskPilot engine ready'
                    '</div>'
                    '</div>'
                    '</div>'
                ),
                unsafe_allow_html=True,
            )

        with right:
            if st.button(
                "Replace data",
                key=(
                    "riskpilot_replace_"
                    "customer_data"
                ),
                use_container_width=True,
            ):
                clear_customer_scenario()
                st.rerun()

        return stored

    st.markdown(
        (
            '<div class="rp-customer-hero">'
            '<div class="rp-customer-kicker">'
            'CUSTOMER DATA ONBOARDING'
            '</div>'
            '<div class="rp-customer-title">'
            'Build a 13-week liquidity view '
            'from your own cash evidence'
            '</div>'
            '<div class="rp-customer-copy">'
            'Import dated customer receipts, '
            'supplier payments, payroll, taxes and '
            'modelled cash movements. RiskPilot '
            'validates the evidence before running '
            'the same liquidity, uncertainty and '
            'decision engines used by the Command '
            'Center.'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        "##### 1 · Configure policy"
    )

    c1, c2, c3 = st.columns(
        [1.4, 1, 1]
    )

    with c1:
        company_name = st.text_input(
            "Company / workspace name",
            value="My Company",
            key="riskpilot_customer_name",
        )

        forecast_start = st.date_input(
            "Forecast start date",
            value=date.today(),
            key=(
                "riskpilot_customer_"
                "forecast_start"
            ),
        )

        opening_cash_basis = st.selectbox(
            "Opening cash basis",
            [
                "Consolidated available cash",
                "Primary operating bank balance",
                "Operating cash excluding restricted funds",
            ],
            index=0,
            key=(
                "riskpilot_customer_"
                "opening_cash_basis"
            ),
            help=(
                "Defines what is included in opening cash. "
                "This does not change the engine calculation; "
                "it records the basis used for management review."
            ),
        )

    with c2:
        opening_cash = st.number_input(
            "Opening cash",
            min_value=0.0,
            value=250000.0,
            step=10000.0,
            format="%.2f",
            key=(
                "riskpilot_customer_"
                "opening_cash"
            ),
        )

        management_reserve = (
            st.number_input(
                "Minimum cash reserve",
                min_value=0.0,
                value=75000.0,
                step=5000.0,
                format="%.2f",
                key=(
                    "riskpilot_customer_"
                    "reserve"
                ),
            )
        )

    with c3:
        risk_appetite_pct = (
            st.number_input(
                "Maximum breach risk (%)",
                min_value=1.0,
                max_value=49.0,
                value=10.0,
                step=1.0,
                format="%.1f",
                key=(
                    "riskpilot_customer_"
                    "risk_appetite"
                ),
            )
        )

        uncertainty_display = (
            st.selectbox(
                "Uncertainty basis",
                [
                    "Conservative operating profile",
                    "Standard operating profile",
                    "High-volatility operating profile",
                ],
                index=1,
                key=(
                    "riskpilot_customer_"
                    "uncertainty_display"
                ),
                help=(
                    "Applied only to MODELLED cash flows. "
                    "Committed evidence remains fixed."
                ),
            )
        )

        uncertainty_profile = {
            "Conservative operating profile": "Low",
            "Standard operating profile": "Standard",
            "High-volatility operating profile": "High",
        }[
            uncertainty_display
        ]

    st.caption(
        "RiskPilot applies the uncertainty basis only to "
        "MODELLED cash flows. COMMITTED cash evidence remains "
        "fixed unless explicitly changed. Opening cash is "
        f"recorded on a '{opening_cash_basis}' basis."
    )

    st.markdown(
        "##### 2 · Import cash evidence"
    )

    import_method = st.radio(
        "Import method",
        [
            "RiskPilot template",
            "Map existing CSV / Excel",
            "Multiple finance sources",
        ],
        horizontal=True,
        key="riskpilot_import_method",
    )

    if (
        import_method
        == "RiskPilot template"
    ):
        download_col, note_col = (
            st.columns(
                [1, 3],
                vertical_alignment="center",
            )
        )

        with download_col:
            st.download_button(
                "Download CSV template",
                data=customer_cash_template(
                    forecast_start=(
                        forecast_start
                    )
                ),
                file_name=(
                    "riskpilot_13_week_"
                    "cash_template.csv"
                ),
                mime="text/csv",
                use_container_width=True,
            )

        with note_col:
            st.caption(
                "Fastest path when your team can "
                "export directly into RiskPilot's "
                "cash-event schema."
            )

        uploaded = st.file_uploader(
            "Upload RiskPilot cash-event CSV",
            type=["csv"],
            key=(
                "riskpilot_customer_"
                "cash_upload"
            ),
        )

        if uploaded is None:
            st.info(
                "Upload a RiskPilot cash-event CSV "
                "to continue to validation."
            )
            return None

        try:
            raw_df = (
                parse_customer_cash_csv(
                    uploaded.getvalue()
                )
            )

        except ValueError as exc:
            st.error(
                f"Data validation failed: "
                f"{exc}"
            )
            return None

    elif (
        import_method
        == "Map existing CSV / Excel"
    ):
        st.caption(
            "Upload an existing CSV or Excel file. "
            "RiskPilot will suggest a mapping, then "
            "you confirm how each source column "
            "should be interpreted."
        )

        uploaded = st.file_uploader(
            "Upload company CSV or Excel",
            type=[
                "csv",
                "xlsx",
                "xlsm",
            ],
            key=(
                "riskpilot_customer_"
                "mapped_upload"
            ),
        )

        if uploaded is None:
            st.info(
                "Upload a CSV or XLSX file "
                "to begin column mapping."
            )
            return None

        file_bytes = (
            uploaded.getvalue()
        )

        selected_sheet = 0

        if uploaded.name.lower().endswith(
            (
                ".xlsx",
                ".xlsm",
            )
        ):
            try:
                sheets = (
                    list_excel_sheets(
                        file_bytes
                    )
                )

            except Exception as exc:
                st.error(
                    "Excel workbook could not "
                    f"be read: {exc}"
                )
                return None

            selected_sheet = st.selectbox(
                "Excel worksheet",
                list(sheets),
                key=(
                    "riskpilot_excel_"
                    "sheet"
                ),
            )

        try:
            source_df = (
                load_customer_table(
                    file_bytes,
                    filename=(
                        uploaded.name
                    ),
                    sheet_name=(
                        selected_sheet
                    ),
                )
            )

        except ValueError as exc:
            st.error(
                f"Import failed: {exc}"
            )
            return None

        suggestion = (
            suggest_mapping(
                source_df
            )
        )

        st.markdown(
            "###### Confirm column mapping"
        )

        columns = list(
            source_df.columns
        )

        optional_columns = [
            "— Not mapped —",
            *columns,
        ]

        def _index_for(
            value,
            options,
        ):
            if (
                value is not None
                and value in options
            ):
                return options.index(
                    value
                )
            return 0

        required_left, required_right = (
            st.columns(2)
        )

        with required_left:
            date_column = st.selectbox(
                "Cash date column *",
                columns,
                index=_index_for(
                    suggestion.date_column,
                    columns,
                ),
                key=(
                    "riskpilot_map_date"
                ),
            )

            amount_column = st.selectbox(
                "Amount column *",
                columns,
                index=_index_for(
                    suggestion.amount_column,
                    columns,
                ),
                key=(
                    "riskpilot_map_amount"
                ),
            )

            direction_column_ui = (
                st.selectbox(
                    "Direction column",
                    optional_columns,
                    index=_index_for(
                        (
                            suggestion
                            .direction_column
                        ),
                        optional_columns,
                    ),
                    key=(
                        "riskpilot_map_"
                        "direction"
                    ),
                )
            )

            category_column_ui = (
                st.selectbox(
                    "Category column",
                    optional_columns,
                    index=_index_for(
                        (
                            suggestion
                            .category_column
                        ),
                        optional_columns,
                    ),
                    key=(
                        "riskpilot_map_"
                        "category"
                    ),
                )
            )

        with required_right:
            source_type_column_ui = (
                st.selectbox(
                    "Evidence / source-type column",
                    optional_columns,
                    index=_index_for(
                        (
                            suggestion
                            .source_type_column
                        ),
                        optional_columns,
                    ),
                    key=(
                        "riskpilot_map_"
                        "source_type"
                    ),
                )
            )

            source_reference_column_ui = (
                st.selectbox(
                    "Source reference column",
                    optional_columns,
                    index=_index_for(
                        (
                            suggestion
                            .source_reference_column
                        ),
                        optional_columns,
                    ),
                    key=(
                        "riskpilot_map_"
                        "reference"
                    ),
                )
            )

            due_date_column_ui = (
                st.selectbox(
                    "Due date column",
                    optional_columns,
                    index=_index_for(
                        (
                            suggestion
                            .due_date_column
                        ),
                        optional_columns,
                    ),
                    key=(
                        "riskpilot_map_"
                        "due_date"
                    ),
                )
            )

            expected_column_ui = (
                st.selectbox(
                    "Expected cash date column",
                    optional_columns,
                    index=_index_for(
                        (
                            suggestion
                            .expected_cash_date_column
                        ),
                        optional_columns,
                    ),
                    key=(
                        "riskpilot_map_"
                        "expected_date"
                    ),
                )
            )

        direction_column = (
            None
            if (
                direction_column_ui
                == "— Not mapped —"
            )
            else direction_column_ui
        )

        category_column = (
            None
            if (
                category_column_ui
                == "— Not mapped —"
            )
            else category_column_ui
        )

        source_type_column = (
            None
            if (
                source_type_column_ui
                == "— Not mapped —"
            )
            else source_type_column_ui
        )

        source_reference_column = (
            None
            if (
                source_reference_column_ui
                == "— Not mapped —"
            )
            else source_reference_column_ui
        )

        due_date_column = (
            None
            if (
                due_date_column_ui
                == "— Not mapped —"
            )
            else due_date_column_ui
        )

        expected_cash_date_column = (
            None
            if (
                expected_column_ui
                == "— Not mapped —"
            )
            else expected_column_ui
        )

        defaults_col1, defaults_col2 = (
            st.columns(2)
        )

        with defaults_col1:
            default_direction = None

            if direction_column is None:
                default_direction = (
                    st.selectbox(
                        "Default cash direction",
                        [
                            "INFLOW",
                            "OUTFLOW",
                        ],
                        key=(
                            "riskpilot_default_"
                            "direction"
                        ),
                    )
                )

            default_category = (
                st.text_input(
                    "Default category",
                    value=(
                        "cash movement"
                    ),
                    disabled=(
                        category_column
                        is not None
                    ),
                    key=(
                        "riskpilot_default_"
                        "category"
                    ),
                )
            )

        with defaults_col2:
            default_source_type = (
                st.selectbox(
                    "Default evidence type",
                    [
                        "COMMITTED",
                        "MODELLED",
                        "MANAGEMENT_ASSUMPTION",
                    ],
                    index=0,
                    disabled=(
                        source_type_column
                        is not None
                    ),
                    key=(
                        "riskpilot_default_"
                        "source_type"
                    ),
                )
            )

        with st.expander(
            "Preview source file",
            expanded=False,
        ):
            st.dataframe(
                source_df.head(30),
                use_container_width=True,
                hide_index=True,
            )

        try:
            raw_df = (
                build_standard_cash_dataframe(
                    source_df,
                    date_column=(
                        date_column
                    ),
                    amount_column=(
                        amount_column
                    ),
                    direction_column=(
                        direction_column
                    ),
                    category_column=(
                        category_column
                    ),
                    source_type_column=(
                        source_type_column
                    ),
                    status_column=None,
                    description_column=None,
                    source_reference_column=(
                        source_reference_column
                    ),
                    due_date_column=(
                        due_date_column
                    ),
                    expected_cash_date_column=(
                        expected_cash_date_column
                    ),
                    default_direction=(
                        default_direction
                    ),
                    default_category=(
                        default_category
                    ),
                    default_source_type=(
                        default_source_type
                    ),
                )
            )

        except ValueError as exc:
            st.error(
                f"Mapping failed: {exc}"
            )
            return None

    else:
        st.caption(
            "Upload separate finance exports. RiskPilot "
            "maps each source independently, preserves "
            "its provenance, then combines everything "
            "into one 13-week evidence set."
        )

        mapped_sources = []

        for source_index, profile in enumerate(
            SOURCE_PROFILES
        ):
            with st.expander(
                profile.label,
                expanded=(
                    profile.source_id
                    in {"ar", "ap"}
                ),
            ):
                st.caption(
                    profile.description
                )

                source_files = st.file_uploader(
                    f"Upload {profile.label}",
                    type=[
                        "csv",
                        "xlsx",
                        "xlsm",
                    ],
                    accept_multiple_files=True,
                    key=(
                        "riskpilot_multi_"
                        f"{profile.source_id}"
                    ),
                )

                if not source_files:
                    continue

                for file_index, source_file in enumerate(
                    source_files
                ):
                    st.markdown(
                        f"**{source_file.name}**"
                    )

                    file_bytes = (
                        source_file.getvalue()
                    )

                    sheet_name = 0

                    if (
                        source_file.name.lower()
                        .endswith(
                            (
                                ".xlsx",
                                ".xlsm",
                            )
                        )
                    ):
                        try:
                            sheet_names = (
                                list_excel_sheets(
                                    file_bytes
                                )
                            )
                        except Exception as exc:
                            st.error(
                                f"{source_file.name}: "
                                f"could not read workbook: "
                                f"{exc}"
                            )
                            continue

                        sheet_name = st.selectbox(
                            "Worksheet",
                            list(
                                sheet_names
                            ),
                            key=(
                                "riskpilot_multi_sheet_"
                                f"{profile.source_id}_"
                                f"{file_index}"
                            ),
                        )

                    try:
                        source_df = (
                            load_customer_table(
                                file_bytes,
                                filename=(
                                    source_file.name
                                ),
                                sheet_name=(
                                    sheet_name
                                ),
                            )
                        )
                    except ValueError as exc:
                        st.error(
                            f"{source_file.name}: "
                            f"{exc}"
                        )
                        continue

                    suggestion = (
                        suggest_mapping(
                            source_df
                        )
                    )

                    columns = list(
                        source_df.columns
                    )

                    optional_columns = [
                        "— Not mapped —",
                        *columns,
                    ]

                    def _mapping_index(
                        value,
                        options,
                    ):
                        if (
                            value is not None
                            and value in options
                        ):
                            return options.index(
                                value
                            )

                        return 0

                    map1, map2 = (
                        st.columns(2)
                    )

                    with map1:
                        date_column = (
                            st.selectbox(
                                "Cash date *",
                                columns,
                                index=(
                                    _mapping_index(
                                        suggestion
                                        .date_column,
                                        columns,
                                    )
                                ),
                                key=(
                                    "riskpilot_multi_date_"
                                    f"{profile.source_id}_"
                                    f"{file_index}"
                                ),
                            )
                        )

                        amount_column = (
                            st.selectbox(
                                "Amount *",
                                columns,
                                index=(
                                    _mapping_index(
                                        suggestion
                                        .amount_column,
                                        columns,
                                    )
                                ),
                                key=(
                                    "riskpilot_multi_amount_"
                                    f"{profile.source_id}_"
                                    f"{file_index}"
                                ),
                            )
                        )

                    with map2:
                        reference_ui = (
                            st.selectbox(
                                "Reference / document ID",
                                optional_columns,
                                index=(
                                    _mapping_index(
                                        suggestion
                                        .source_reference_column,
                                        optional_columns,
                                    )
                                ),
                                key=(
                                    "riskpilot_multi_ref_"
                                    f"{profile.source_id}_"
                                    f"{file_index}"
                                ),
                            )
                        )

                        expected_date_ui = (
                            st.selectbox(
                                "Expected cash date",
                                optional_columns,
                                index=(
                                    _mapping_index(
                                        suggestion
                                        .expected_cash_date_column,
                                        optional_columns,
                                    )
                                ),
                                key=(
                                    "riskpilot_multi_expected_"
                                    f"{profile.source_id}_"
                                    f"{file_index}"
                                ),
                            )
                        )

                    reference_column = (
                        None
                        if (
                            reference_ui
                            == "— Not mapped —"
                        )
                        else reference_ui
                    )

                    expected_column = (
                        None
                        if (
                            expected_date_ui
                            == "— Not mapped —"
                        )
                        else expected_date_ui
                    )

                    if (
                        profile.default_direction
                        is None
                    ):
                        source_direction = (
                            st.selectbox(
                                "Cash direction",
                                [
                                    "INFLOW",
                                    "OUTFLOW",
                                ],
                                key=(
                                    "riskpilot_multi_direction_"
                                    f"{profile.source_id}_"
                                    f"{file_index}"
                                ),
                            )
                        )
                    else:
                        source_direction = (
                            profile
                            .default_direction
                        )

                    category = st.text_input(
                        "Cash category",
                        value=(
                            profile
                            .default_category
                        ),
                        key=(
                            "riskpilot_multi_category_"
                            f"{profile.source_id}_"
                            f"{file_index}"
                        ),
                    )

                    evidence_type = (
                        st.selectbox(
                            "Evidence classification",
                            [
                                "COMMITTED",
                                "MODELLED",
                                "MANAGEMENT_ASSUMPTION",
                            ],
                            index=(
                                [
                                    "COMMITTED",
                                    "MODELLED",
                                    "MANAGEMENT_ASSUMPTION",
                                ].index(
                                    profile
                                    .default_source_type
                                )
                            ),
                            key=(
                                "riskpilot_multi_evidence_"
                                f"{profile.source_id}_"
                                f"{file_index}"
                            ),
                            help=(
                                "Only classify evidence as "
                                "COMMITTED when the source "
                                "supports a known dated cash "
                                "commitment."
                            ),
                        )
                    )

                    try:
                        standardized = (
                            build_standard_cash_dataframe(
                                source_df,
                                date_column=(
                                    date_column
                                ),
                                amount_column=(
                                    amount_column
                                ),
                                direction_column=None,
                                category_column=None,
                                source_type_column=None,
                                status_column=None,
                                description_column=None,
                                source_reference_column=(
                                    reference_column
                                ),
                                due_date_column=None,
                                expected_cash_date_column=(
                                    expected_column
                                ),
                                default_direction=(
                                    source_direction
                                ),
                                default_category=(
                                    category
                                ),
                                default_source_type=(
                                    evidence_type
                                ),
                                event_id_prefix=(
                                    f"{profile.source_id}-"
                                    f"{file_index + 1}"
                                ),
                            )
                        )
                    except ValueError as exc:
                        st.error(
                            f"{source_file.name}: "
                            f"{exc}"
                        )
                        continue

                    mapped_sources.append(
                        (
                            source_file.name,
                            standardized,
                        )
                    )

                    st.caption(
                        f"Mapped {len(standardized)} "
                        "cash event(s)."
                    )

        if not mapped_sources:
            st.info(
                "Upload at least one finance source "
                "to continue."
            )
            return None

        try:
            raw_df = (
                merge_standardized_sources(
                    tuple(
                        mapped_sources
                    )
                )
            )
        except ValueError as exc:
            st.error(
                f"Source merge failed: {exc}"
            )
            return None

        uploaded_names = ", ".join(
            source_name
            for source_name, _ in mapped_sources
        )

        upload_reference = (
            "customer-multi-source:"
            + uploaded_names
        )

    try:
        events = build_customer_cash_events(
            raw_df,
            upload_reference=(
                upload_reference
                if "upload_reference" in locals()
                else (
                    f"customer-upload:"
                    f"{uploaded.name}"
                )
            ),
        )

        report = build_customer_import_report(
            events,
            forecast_start=(
                forecast_start
            ),
        )

    except ValueError as exc:
        st.error(
            f"Data validation failed: {exc}"
        )
        return None

    st.markdown(
        "##### 3 · Validate evidence"
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Events loaded",
        report.rows_loaded,
    )

    m2.metric(
        "Committed",
        report.committed_events,
    )

    m3.metric(
        "Modelled",
        report.modelled_events,
    )

    m4.metric(
        "Inside 13 weeks",
        report.forecast_horizon_events,
    )

    if report.warnings:
        for warning in report.warnings:
            st.warning(warning)
    else:
        st.success(
            "No blocking data-quality issues detected."
        )

    with st.expander(
        "Review imported cash evidence",
        expanded=False,
    ):
        preview_columns = [
            column
            for column in (
                "event_id",
                "date",
                "amount",
                "direction",
                "category",
                "source_type",
                "status",
                "source_reference",
            )
            if column in raw_df.columns
        ]

        st.dataframe(
            raw_df[
                preview_columns
            ].head(50),
            use_container_width=True,
            hide_index=True,
        )

    blocking = (
        report.forecast_horizon_events
        == 0
    )

    if blocking:
        st.error(
            "At least one active event must fall "
            "inside the 13-week forecast horizon."
        )
        return None

    st.markdown(
        "##### 4 · Confirm workspace"
    )

    st.caption(
        "RiskPilot will not overwrite or reinterpret "
        "your uploaded source classifications. "
        "Committed, modelled and management-assumption "
        "evidence remain explicitly separated."
    )

    if st.button(
        "Open company Command Center",
        type="primary",
        use_container_width=True,
        key=(
            "riskpilot_confirm_"
            "customer_workspace"
        ),
    ):
        try:
            scenario = build_customer_scenario(
                company_name=company_name,
                forecast_start=forecast_start,
                opening_cash=float(
                    opening_cash
                ),
                management_reserve=float(
                    management_reserve
                ),
                max_breach_probability=(
                    float(
                        risk_appetite_pct
                    )
                    / 100.0
                ),
                uncertainty_profile_name=(
                    uncertainty_profile
                ),
                events=events,
            )
        except ValueError as exc:
            st.error(
                f"Workspace configuration failed: "
                f"{exc}"
            )
            return None

        st.session_state[
            CUSTOMER_SCENARIO_STATE_KEY
        ] = scenario.model_dump(
            mode="json"
        )

        st.session_state[
            CUSTOMER_REPORT_STATE_KEY
        ] = report.model_dump(
            mode="json"
        )

        st.rerun()

    return None
