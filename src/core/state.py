"""
src/core/state.py

DocState — the shared pipeline state that is passed between every agent.

It is intentionally a plain TypedDict (not a Pydantic model) so that agent
code can mutate it in-place cheaply without going through validation on every
write.  Pydantic models are used *at the boundaries* (input / output of the
FastAPI layer) and for structured sub-documents stored inside DocState.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class DocState(TypedDict, total=False):
    """
    Mutable state bag threaded through the entire documentation pipeline.

    Fields are populated incrementally by each agent; a field is absent
    (KeyError) until the agent responsible for it has run.

    total=False means every key is optional at the TypedDict level — agents
    must guard with .get() or handle KeyError defensively.
    """

    repo_path: str
    language: str
    github_url: str
    branch: Optional[str]

    # ------------------------------------------------------------------ #
    # Agent 1 — CodeAnalyzerAgent
    # ------------------------------------------------------------------ #
    code_structure: Dict[str, Any]
    analysis_output: Dict[str, Any]

    # ------------------------------------------------------------------ #
    # Future agents will add their own keys here
    # ------------------------------------------------------------------ #

    # Accumulated errors from any agent (non-fatal; agents append to it).
    errors: List[str]
