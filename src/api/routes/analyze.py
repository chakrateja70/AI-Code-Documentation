"""
src/api/routes/analyze.py

POST /analyze  —  Agent 1: Code Analyzer
=========================================
Runs the CodeAnalyzerAgent against a repository that has already been cloned
by POST /ingest.

Flow
----
  1. Validate the request body (AnalyzeRequest).
  2. Resolve the local path of the cloned repository from ``config.REPOS_DIR``.
  3. Build DocState and invoke CodeAnalyzerAgent.
  4. Return an AnalyzeResponse with the generated documentation + metadata.

Error handling
--------------
  * 404 — repository has not been ingested yet (local path does not exist).
  * 503 — LLM is not configured (no API key set).
  * 500 — unexpected error during analysis.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter

import config
from src.agents import CodeAnalyzerAgent
from src.services import llm_service
from src.core.exceptions import (
    CodeAnalysisFailedException,
    InvalidRepoUrlException,
    InvalidRequestBodyException,
    LlmNotConfiguredException,
    RepoNotFoundException,
)
from src.core.models import AnalyzeRequest, SuccessResponse
from src.core.state import DocState

router = APIRouter(prefix="/analyze", tags=["Analyze"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_repo_path(github_url: str) -> Path:
    """Resolve the local clone directory for a GitHub URL."""
    # Accept both  https://github.com/owner/repo  and  github.com/owner/repo
    match = re.search(r"github\.com[/:]([^/]+)/([^/.\s]+?)(?:\.git)?$", github_url)
    if not match:
        raise ValueError(f"Cannot parse owner/repo from URL: {github_url!r}")

    owner, repo = match.group(1), match.group(2)
    # NOTE: repo_manager uses double-underscore separator: "<owner>__<repo>"
    return config.REPOS_DIR / f"{owner}__{repo}"


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=SuccessResponse,
)
async def analyze_repository(body: AnalyzeRequest | str) -> SuccessResponse:

    # Support clients that accidentally send a JSON object as a string.
    if isinstance(body, str):
        try:
            body = AnalyzeRequest.model_validate_json(body)
        except Exception as exc:
            raise InvalidRequestBodyException(
                "Expected a JSON object with github_url and optional branch"
            )

    # Step 2: Resolve local repo path
    try:
        repo_path = _resolve_repo_path(body.github_url)
    except ValueError as exc:
        raise InvalidRepoUrlException(body.github_url)

    if not repo_path.exists():
        raise RepoNotFoundException(repo_path.name)

    # Step 3: Initialize LLM
    try:
        llm = llm_service.get_llm()
    except RuntimeError as exc:
        raise LlmNotConfiguredException(str(exc))

    # Step 4: Build DocState and run agent
    state: DocState = {
        "repo_path": str(repo_path),
        "github_url": body.github_url,
        "branch": body.branch,
        "errors": [],
    }

    try:
        agent = CodeAnalyzerAgent(llm=llm)
        output = await agent.invoke(state)
    except Exception as exc:
        raise CodeAnalysisFailedException(str(exc))

    # Step 5: Build response
    meta = output.get("metadata", {})
    owner_repo = repo_path.name  # e.g. "tiangolo_fastapi"

    return SuccessResponse(
        message=f"Code analysis complete for '{owner_repo}'.",
        data={
            "repo": {
                "github_url": body.github_url,
                "local_path": str(repo_path),
                "branch": body.branch,
            },
            "analysis": {
                "overview_documentation": output.get("content", ""),
                "timestamp": output.get("timestamp"),
                "agent": output.get("agent"),
                "duration_seconds": meta.get("analysis_duration_seconds"),
                "stats": {
                    "modules_found": meta.get("modules_found", 0),
                    "functions_found": meta.get("functions_found", 0),
                    "classes_found": meta.get("classes_found", 0),
                    "imports_found": meta.get("imports_found", 0),
                },
            },
            "code_structure": state.get("code_structure", {}),
            "errors": state.get("errors", []),
        },
    )
