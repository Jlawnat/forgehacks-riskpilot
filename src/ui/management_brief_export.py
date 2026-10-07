from __future__ import annotations

import json
import re

import streamlit as st

from src.core.command_center import (
    CommandCenterResult,
)
from src.reporting.management_brief_pdf import (
    build_management_brief_pdf,
)


def _filename_slug(
    value: str,
) -> str:
    cleaned = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        value.strip(),
    )

    cleaned = cleaned.strip(
        "-"
    ).lower()

    return (
        cleaned
        or "workspace"
    )


def render_management_brief_export(
    result: CommandCenterResult,
) -> None:
    st.markdown(
        """
        <style>
        .rp-export-shell {
            margin-top: 0.75rem;
            padding: 0.85rem 0.95rem;
            border: 1px solid #dbe4f0;
            border-radius: 10px;
            background:
                linear-gradient(
                    90deg,
                    #f8fbff 0%,
                    #ffffff 100%
                );
        }

        .rp-export-kicker {
            color: #2563eb;
            font-size: 0.58rem;
            font-weight: 800;
            letter-spacing: 0.10em;
            text-transform: uppercase;
        }

        .rp-export-title {
            margin-top: 0.15rem;
            color: #0b1739;
            font-size: 0.84rem;
            font-weight: 750;
        }

        .rp-export-copy {
            margin-top: 0.10rem;
            color: #718198;
            font-size: 0.66rem;
            line-height: 1.42;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        (
            '<div class="rp-export-shell">'
            '<div class="rp-export-kicker">'
            'MANAGEMENT PACK'
            '</div>'
            '<div class="rp-export-title">'
            'Export a verified liquidity brief'
            '</div>'
            '<div class="rp-export-copy">'
            'Share the same forecast, uncertainty, recovery, '
            'monitoring and evidence values shown in the '
            'Command Center.'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    slug = _filename_slug(
        result.scenario_name
    )

    pdf_bytes = (
        build_management_brief_pdf(
            result
        )
    )

    audit_json = json.dumps(
        result.model_dump(
            mode="json"
        ),
        indent=2,
    )

    pdf_col, json_col = (
        st.columns(2)
    )

    with pdf_col:
        st.download_button(
            "Download Management Brief PDF",
            data=pdf_bytes,
            file_name=(
                f"riskpilot-{slug}-"
                "management-brief.pdf"
            ),
            mime="application/pdf",
            use_container_width=True,
            key=(
                "riskpilot_download_"
                "management_pdf"
            ),
        )

    with json_col:
        st.download_button(
            "Download Verified Audit JSON",
            data=audit_json,
            file_name=(
                f"riskpilot-{slug}-"
                "verified-audit.json"
            ),
            mime="application/json",
            use_container_width=True,
            key=(
                "riskpilot_download_"
                "management_json"
            ),
        )

    st.caption(
        "The PDF export presents existing engine outputs only. "
        "It does not ask the AI layer to calculate replacement "
        "financial values."
    )
