"""
src/api/routes/ingest.py

/ingest — Ingest Route (Steps 1 → 3)
======================================
Accepts a GitHub URL, runs the Repository Manager and File Loader pipeline
steps, and returns a structured JSON summary.

The heavy I/O work (git clone + filesystem traversal) is offloaded to a
thread-pool via ``asyncio.to_thread`` so the async event-loop is never
blocked.
"""

import asyncio

from fastapi import APIRouter, HTTPException, status

from src.core.models import (
    FileLoaderResult,
    IngestRequest,
    SuccessResponse,
)
from src.services.file_loader import load_files
from src.services.repo_manager import clone_or_update_repo

router = APIRouter(prefix="/ingest", tags=["Ingest"])


# ---------------------------------------------------------------------------
# POST /ingest
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=SuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a GitHub repository",
    description=(
        "Provide a public GitHub repository URL. "
        "The service will clone it locally, traverse all source files, "
        "and return a structured summary ready for the next pipeline stages."
    ),
)
async def ingest_repository(body: IngestRequest) -> SuccessResponse:
    """
    Pipeline entry-point.

    Steps executed:
      1. **Input Layer** — URL is validated by the Pydantic model.
      2. **Repository Manager** — clone or update the repo.
      3. **File Loader** — collect all relevant source files.
    """
    # ------------------------------------------------------------------
    # Step 2 — Repository Manager  (blocking I/O → thread-pool)
    # ------------------------------------------------------------------
    try:
        repo_info = await asyncio.to_thread(
            clone_or_update_repo,
            body.github_url,
            body.branch,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone repository: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # Step 3 — File Loader  (blocking I/O → thread-pool)
    # ------------------------------------------------------------------
    try:
        loader_result: FileLoaderResult = await asyncio.to_thread(
            load_files,
            repo_info,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File loading failed: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # Build response summary
    # ------------------------------------------------------------------
    file_summary = [
        {
            "path": f.relative_path,
            "extension": f.extension,
            "size_bytes": f.size_bytes,
        }
        for f in loader_result.files
    ]

    return SuccessResponse(
        status="success",
        message=(
            f"Repository '{repo_info.owner}/{repo_info.repo}' ingested successfully. "
            f"{loader_result.total_files_loaded} files loaded, "
            f"{len(loader_result.skipped_files)} skipped."
        ),
        data={
            "repo": {
                "owner": repo_info.owner,
                "name": repo_info.repo,
                "clone_url": repo_info.clone_url,
                "branch": repo_info.branch,
                "local_path": str(repo_info.local_path),
                "already_existed": repo_info.already_existed,
                "cloned_at": repo_info.cloned_at.isoformat(),
            },
            "file_loader": {
                "total_files_found": loader_result.total_files_found,
                "total_files_loaded": loader_result.total_files_loaded,
                "skipped_files": loader_result.skipped_files,
                "load_duration_seconds": loader_result.load_duration_seconds,
                "files": file_summary,
            },
        },
    )
