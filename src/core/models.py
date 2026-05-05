from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

class IngestRequest(BaseModel):
    """Payload sent by the user to kick off the pipeline."""

    github_url: str
    branch: Optional[str] = None

    @field_validator("github_url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        from src.utils.github_utils import is_valid_github_url

        v = v.strip()
        if not is_valid_github_url(v):
            raise ValueError(
                f"Invalid GitHub URL: {v!r}. "
                "Must be a valid https://github.com/owner/repo URL."
            )
        return v
class RepoInfo(BaseModel):
    """Metadata about a cloned / already-cached repository."""
    owner: str
    repo: str
    clone_url: str
    local_path: Path
    branch: Optional[str] = None
    cloned_at: datetime = Field(default_factory=datetime.utcnow)
    already_existed: bool = False  # True when repo was found in cache

    model_config = {"arbitrary_types_allowed": True}
    
class FileInfo(BaseModel):
    """Metadata + raw content for a single source file."""

    relative_path: str
    absolute_path: Path
    extension: str
    size_bytes: int
    content: Optional[str] = None
    encoding: str = "utf-8"

    model_config = {"arbitrary_types_allowed": True}


class FileLoaderResult(BaseModel):
    """Aggregated output of the File Loader step."""

    repo_info: RepoInfo
    files: list[FileInfo] = Field(default_factory=list)
    skipped_files: list[str] = Field(default_factory=list)
    total_files_found: int = 0
    total_files_loaded: int = 0
    load_duration_seconds: float = 0.0
class SymbolInfo(BaseModel):
    """A symbol (function, class, method, etc.) extracted from source code."""

    kind: str
    name: str
    line_start: int
    line_end: int
    parent: Optional[str] = None


class ParsedFile(BaseModel):
    """Result of parsing a single source file."""

    relative_path: str
    symbols: list[SymbolInfo] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)


class ParseResult(BaseModel):
    """Aggregated output of the Code Parser step."""

    repo_info: RepoInfo
    parsed_files: list[ParsedFile] = Field(default_factory=list)
    parse_duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 5 — Agent 1: Code Analyzer
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Request body for the POST /analyze endpoint."""

    github_url: str
    branch: Optional[str] = None


class SuccessResponse(BaseModel):
    statusCode: int = 200
    status: str = "success"
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    statusCode: int
    statusMessage: str
    errorMessage: str
