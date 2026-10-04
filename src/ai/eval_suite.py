from __future__ import annotations

from dataclasses import dataclass

from src.ai.analyst import (
    run_risk_analyst,
)
from src.ai.context import (
    build_risk_analyst_context,
)
from src.core.risk_policy import RiskPolicy
from src.ingestion.loader import load_business_csv
from src.ingestion.validator import validate_business_data


@dataclass(frozen=True)
class EvalCase:
    name: str
    question: str
    required_tools: tuple[str, ...]
    acceptable_tools: tuple[str, ...]


CASES = (
    EvalCase(
        name="current_health",
        question=(
            "What is the current financial health of the "
            "business and what are the main risks?"
        ),
        required_tools=(
            "get_business_health",
        ),
        acceptable_tools=(
            "get_business_health",
            "get_forecast_outlook",
            "get_liquidity_risk",
        ),
    ),
    EvalCase(
        name="forecast",
        question=(
            "What does RiskPilot expect to happen to revenue "
            "and operating costs over the next three months?"
        ),
        required_tools=(
            "get_forecast_outlook",
        ),
        acceptable_tools=(
            "get_forecast_outlook",
        ),
    ),
    EvalCase(
        name="liquidity",
        question=(
            "What is the probability that cash breaches the "
            "management reserve over the next three months?"
        ),
        required_tools=(
            "get_liquidity_risk",
        ),
        acceptable_tools=(
            "get_liquidity_risk",
            "get_business_health",
        ),
    ),
    EvalCase(
        name="reserve_vs_insolvency",
        question=(
            "Explain the difference between this business's "
            "reserve-breach risk and probability of negative cash."
        ),
        required_tools=(
            "get_liquidity_risk",
        ),
        acceptable_tools=(
            "get_liquidity_risk",
        ),
    ),
    EvalCase(
        name="reverse_stress",
        question=(
            "How much further deterioration can the business "
            "withstand before breaching the management reserve?"
        ),
        required_tools=(
            "run_reverse_stress",
        ),
        acceptable_tools=(
            "run_reverse_stress",
            "get_business_health",
        ),
    ),
    EvalCase(
        name="stress",
        question=(
            "Stress revenue by -15%, costs by +10% and delay "
            "receivables by 30 days. What happens and what drives "
            "the liquidity impact?"
        ),
        required_tools=(
            "run_stress_test",
        ),
        acceptable_tools=(
            "run_stress_test",
        ),
    ),
    EvalCase(
        name="recovery",
        question=(
            "Under a -15% revenue shock, +10% cost shock and "
            "30-day receivable delay, what recovery options "
            "does management have?"
        ),
        required_tools=(
            "get_recovery_options",
        ),
        acceptable_tools=(
            "get_recovery_options",
            "validate_recovery_options",
            "run_stress_test",
        ),
    ),
    EvalCase(
        name="recovery_safety",
        question=(
            "Under a -15% revenue shock, +10% cost shock and "
            "30-day receivable delay, is the balanced recovery "
            "plan safe enough after forecast uncertainty?"
        ),
        required_tools=(
            "get_recovery_options",
            "validate_recovery_options",
        ),
        acceptable_tools=(
            "get_recovery_options",
            "validate_recovery_options",
            "run_stress_test",
        ),
    ),
)


def main() -> None:
    raw = load_business_csv(
        "data/demo/borderline_business.csv"
    )

    df, _ = validate_business_data(
        raw
    )

    passed = 0

    for index, case in enumerate(
        CASES,
        start=1,
    ):
        context = build_risk_analyst_context(
            df,
            RiskPolicy(
                minimum_cash_reserve=20000.0,
                max_shortfall_probability=0.05,
            ),
            horizon=3,
        )

        response = run_risk_analyst(
            context,
            case.question,
        )

        used = set(
            response.tools_used
        )

        required = set(
            case.required_tools
        )

        acceptable = set(
            case.acceptable_tools
        )

        missing = (
            required - used
        )

        unexpected = (
            used - acceptable
        )

        evidence_line = (
            "Evidence used:"
            in response.answer
        )

        case_passed = (
            not missing
            and not unexpected
            and evidence_line
        )

        if case_passed:
            passed += 1

        print()
        print(
            "=" * 72
        )
        print(
            f"{index}. {case.name}"
        )
        print(
            "=" * 72
        )

        print(
            "PASS:"
            if case_passed
            else "FAIL:",
            case_passed,
        )

        print(
            "Required:",
            ", ".join(
                case.required_tools
            ),
        )

        print(
            "Used:",
            ", ".join(
                response.tools_used
            ),
        )

        if missing:
            print(
                "Missing:",
                ", ".join(
                    sorted(missing)
                ),
            )

        if unexpected:
            print(
                "Unexpected:",
                ", ".join(
                    sorted(unexpected)
                ),
            )

        print(
            "Evidence line:",
            evidence_line,
        )

        print()
        print(
            response.answer
        )

    total = len(
        CASES
    )

    print()
    print(
        "=" * 72
    )
    print(
        "RISKPILOT AI EVALUATION"
    )
    print(
        "=" * 72
    )
    print(
        f"Passed: {passed}/{total}"
    )
    print(
        "Tool-selection accuracy:",
        f"{passed / total:.1%}",
    )

    if passed != total:
        raise SystemExit(
            1
        )


if __name__ == "__main__":
    main()
