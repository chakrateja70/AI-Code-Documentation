import asyncio

from fastapi import APIRouter
from src.core.exceptions import (
    FileLoadFailedException,
    InvalidInputException,
    RepoCloneFailedException,
)
from src.core.models import FileLoaderResult, IngestRequest, SuccessResponse
from src.services.file_loader import load_files
from src.services.repo_manager import clone_or_update_repo

router = APIRouter(prefix="/ingest", tags=["Ingest"])

@router.post("/", response_model=SuccessResponse)
async def ingest_repository(body: IngestRequest) -> SuccessResponse:
    """Clone/update the repo, load files, and return an ingest summary."""
    try:
        repo_info = await asyncio.to_thread(
            clone_or_update_repo,
            body.github_url,
            body.branch,
        )
    except ValueError as exc:
        raise InvalidInputException(str(exc))
    except Exception as exc:
        raise RepoCloneFailedException(str(exc))

    # Step 3: File loader (blocking I/O -> thread-pool)
    try:
        loader_result: FileLoaderResult = await asyncio.to_thread(
            load_files,
            repo_info,
        )
    except Exception as e:
        raise FileLoadFailedException(str(e))

    # Build response summary
    file_summary = [
        {
            "path": f.relative_path,
            "extension": f.extension,
            "size_bytes": f.size_bytes,
        }
        for f in loader_result.files
    ]

    return SuccessResponse(
        message=(
            f"Repository '{repo_info.owner}/{repo_info.repo}' ingested successfully."
        ),
        data={
            "repo": {
                "clone_url": repo_info.clone_url,
                "already_existed": repo_info.already_existed,
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
