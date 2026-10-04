from __future__ import annotations

import os

from dotenv import load_dotenv
from agents import Agent, Runner


def main() -> None:
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not configured in .env"
        )

    model = os.getenv(
        "RISKPILOT_AI_MODEL",
        "gpt-5.6-luna",
    )

    agent = Agent(
        name="RiskPilot Smoke Test",
        model=model,
        instructions=(
            "You are testing the RiskPilot AI connection. "
            "Reply with exactly: RISKPILOT_AI_OK"
        ),
    )

    result = Runner.run_sync(
        agent,
        "Confirm the AI connection.",
    )

    print("Model:", model)
    print("Output:", result.final_output)


if __name__ == "__main__":
    main()
