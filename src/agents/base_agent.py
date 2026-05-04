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
* ``log_execution`` is a convenience wrapper; the underlying logger is
  named ``agent.<name>`` so log filtering is easy.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from src.core.state import DocState


class BaseAgent(ABC):
    """Abstract base for all documentation agents in the pipeline."""

    def __init__(self, llm: Any, name: str) -> None:
        """
        Parameters
        ----------
        llm:
            A LangChain-compatible chat model instance that exposes
            ``.ainvoke(prompt: str)`` returning an object with a
            ``.content`` attribute.
        name:
            Short snake_case identifier for this agent
            (e.g. ``"code_analyzer"``).  Used in logging and output
            envelopes.
        """
        self.llm = llm
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    # ------------------------------------------------------------------
    # Abstract interface — every subclass must implement this.
    # ------------------------------------------------------------------

    @abstractmethod
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """
        Execute the agent's logic against the current pipeline state.

        Agents are free to read *and* mutate ``state`` in place to make
        their results available to downstream agents.  They should also
        return the same data wrapped in ``format_output`` so the
        orchestrator can capture a snapshot.

        Parameters
        ----------
        state:
            Shared mutable pipeline state (see ``src.core.state.DocState``).

        Returns
        -------
        Dict[str, Any]
            Standardised output envelope produced by ``self.format_output``.
        """

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def log_execution(self, stage: str) -> None:
        """Emit an INFO log entry tagged with this agent's name."""
        self.logger.info("[%s] %s", self.name, stage)

    def log_warning(self, message: str) -> None:
        """Emit a WARNING log entry tagged with this agent's name."""
        self.logger.warning("[%s] %s", self.name, message)

    def log_error(self, message: str) -> None:
        """Emit an ERROR log entry tagged with this agent's name."""
        self.logger.error("[%s] %s", self.name, message)

    def format_output(
        self,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Wrap agent results in a standard envelope.

        Parameters
        ----------
        content:
            Primary textual output produced by this agent (e.g. LLM prose).
        metadata:
            Arbitrary key/value pairs that describe the run
            (counts, durations, detected language, …).

        Returns
        -------
        Dict[str, Any]
            ``{content, metadata, timestamp, agent}``
        """
        return {
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "agent": self.name,
        }
