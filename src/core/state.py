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

    # ------------------------------------------------------------------ #
    # Input (set by the caller / orchestrator before the first agent)
    # ------------------------------------------------------------------ #

    # Absolute local path to the cloned repository root.
    repo_path: str

    # Primary programming language detected (e.g. "python", "javascript").
    language: str

    # Original GitHub URL supplied by the user.
    github_url: str

    # Branch / tag that was checked out.
    branch: Optional[str]

    # ------------------------------------------------------------------ #
    # Agent 1 — CodeAnalyzerAgent
    # ------------------------------------------------------------------ #

    # Raw structural data extracted by AST analysis.
    code_structure: Dict[str, Any]

    # Output of CodeAnalyzerAgent: overview + API docs prose.
    analysis_output: Dict[str, Any]

    # ------------------------------------------------------------------ #
    # Future agents will add their own keys here
    # ------------------------------------------------------------------ #

    # Accumulated errors from any agent (non-fatal; agents append to it).
    errors: List[str]
