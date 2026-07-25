"""Base interface every agent implements: pure function over CampaignState."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.orchestrator.state import CampaignState


class BaseAgent(ABC):
    name: str = "base-agent"

    @abstractmethod
    def run(self, state: CampaignState) -> CampaignState:
        """Process the campaign state and return the (possibly mutated) state."""
        raise NotImplementedError
