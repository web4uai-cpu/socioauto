"""CLI entry point: run a single campaign cycle for a demo brand."""

from __future__ import annotations

from src.orchestrator.graph import run_campaign
from src.orchestrator.state import CampaignState


def main() -> None:
    state = CampaignState(
        brand_name="Demo Brand",
        voice_guidelines={"tone": "friendly, expert"},
        platforms=["x", "linkedin"],
        trends=[{"topic": "AI in marketing", "score": 0.9, "source": "demo"}],
    )
    state = run_campaign(state)
    for line in state.log:
        print(line)


if __name__ == "__main__":
    main()
