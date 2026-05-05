"""
src/agents/base_agent.py

Abstract base class for all documentation-pipeline agents.

Every concrete agent must:
  1. Subclass BaseAgent.
  2. Call super().__init__(llm, name) in its __init__.
  3. Implement the async ``invoke(state: DocState) -> Dict[str, Any]`` method.

Design notes
------------
* ``llm`` is typed as ``Any`` so the class stays decoupled from a specific
  LangChain version or provider.  Callers pass a ChatModel instance that
  exposes ``.ainvoke(prompt: str)``.
* ``format_output`` produces a standard envelope that every agent returns,
  making it trivial to log, diff, or replay individual stages.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from src.core.state import DocState


class BaseAgent(ABC):
    """Abstract base for all documentation agents in the pipeline."""

    def __init__(self, llm: Any, name: str) -> None:
        """Initialize the agent with an LLM and identifier."""
        self.llm = llm
        self.name = name

    # ------------------------------------------------------------------
    # Abstract interface — every subclass must implement this.
    # ------------------------------------------------------------------

    @abstractmethod
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Run the agent against state and return the output envelope."""



    def format_output(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Wrap content and metadata in the standard output envelope."""
        return {
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "agent": self.name,
        }
