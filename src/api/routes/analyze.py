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

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

import config
from src.agents import CodeAnalyzerAgent
from src.core.models import AnalyzeRequest, AnalyzeResponse
from src.core.state import DocState

router = APIRouter(prefix="/analyze", tags=["Analyze"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_repo_path(github_url: str) -> Path:
    """
    Derive the local clone directory from a GitHub URL.

    Mirrors the naming convention used by ``repo_manager.clone_or_update_repo``:
        REPOS_DIR / <owner>_<repo>

    Raises
    ------
    ValueError
        If the URL cannot be parsed into owner/repo components.
    """
    # Accept both  https://github.com/owner/repo  and  github.com/owner/repo
    match = re.search(r"github\.com[/:]([^/]+)/([^/.\s]+?)(?:\.git)?$", github_url)
    if not match:
        raise ValueError(f"Cannot parse owner/repo from URL: {github_url!r}")

    owner, repo = match.group(1), match.group(2)
    # NOTE: repo_manager uses double-underscore separator: "<owner>__<repo>"
    return config.REPOS_DIR / f"{owner}__{repo}"


def _looks_like_json(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and stripped[0] in "{["


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a repository with Agent 1 — Code Analyzer",
    description=(
        "Runs the CodeAnalyzerAgent on a previously ingested repository. "
        "The agent extracts the code structure (modules, classes, functions, imports) "
        "using AST analysis and generates comprehensive documentation prose via an LLM. "
        "**The repository must be ingested first via POST /ingest.**"
    ),
)
async def analyze_repository(request: Request) -> AnalyzeResponse:
    """
    Agent 1 — Code Analyzer endpoint.

    Steps
    -----
    1. Parse + validate the request body (handles plain JSON and double-encoded strings).
    2. Resolve the local clone path.
    3. Initialise the LLM from environment configuration.
    4. Build ``DocState`` and call ``CodeAnalyzerAgent.invoke``.
    5. Return structured analysis output.
    """

    # ------------------------------------------------------------------
    # 1. Parse request body — robust to double-encoded JSON strings
    #    (happens when client sends Content-Type: text/plain or omits it)
    # ------------------------------------------------------------------
    try:
        raw = await request.body()
        payload = json.loads(raw)
        # If the payload itself is a JSON string (double-encoded), parse again
        # only when it looks like a JSON object/array.
        if isinstance(payload, str):
            if _looks_like_json(payload):
                payload = json.loads(payload)
            else:
                raise ValueError("Request body is a JSON string, not an object")
        body = AnalyzeRequest(**payload)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invalid request body: {exc}. "
                "Send a JSON object with 'github_url', 'language', and optionally 'branch'. "
                "Make sure Content-Type is application/json."
            ),
        ) from exc

    # ------------------------------------------------------------------
    # 2. Resolve local repo path
    # ------------------------------------------------------------------
    try:
        repo_path = _resolve_repo_path(body.github_url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if not repo_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Repository '{repo_path.name}' not found locally. "
                "Please call POST /api/v1/ingest first to clone the repository."
            ),
        )

    # ------------------------------------------------------------------
    # 3. Initialise LLM
    # ------------------------------------------------------------------
    try:
        llm = config.get_llm()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # ------------------------------------------------------------------
    # 4. Build DocState and run the agent
    # ------------------------------------------------------------------
    state: DocState = {
        "repo_path": str(repo_path),
        "language": body.language,
        "github_url": body.github_url,
        "branch": body.branch,
        "errors": [],
    }

    try:
        agent = CodeAnalyzerAgent(llm=llm)
        output = await agent.invoke(state)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code analysis failed: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 5. Build response
    # ------------------------------------------------------------------
    meta = output.get("metadata", {})
    owner_repo = repo_path.name  # e.g. "tiangolo_fastapi"

    return AnalyzeResponse(
        status="success",
        message=(
            f"Code analysis complete for '{owner_repo}'. "
            f"{meta.get('functions_found', 0)} function(s) and "
            f"{meta.get('classes_found', 0)} class(es) found across "
            f"{meta.get('modules_found', 0)} module(s)."
        ),
        data={
            "repo": {
                "github_url": body.github_url,
                "local_path": str(repo_path),
                "language": body.language,
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
