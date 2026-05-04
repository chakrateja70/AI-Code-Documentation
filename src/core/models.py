"""
src/core/models.py

Pydantic models used as the shared data contract across every layer of the
pipeline (Input → Repo Manager → File Loader → Parser → IR Builder …).

Only the models needed for Steps 1-3 are defined here.  Later steps will
extend this file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Step 1 — Input Layer
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    """Payload sent by the user to kick off the pipeline."""

    github_url: str = Field(
        ...,
        examples=["https://github.com/tiangolo/fastapi"],
        description="Public GitHub repository URL to document.",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Branch / tag to check out. Defaults to the repo's default branch.",
    )

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


# ---------------------------------------------------------------------------
# Step 2 — Repository Manager
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Step 3 — File Loader
# ---------------------------------------------------------------------------


class FileInfo(BaseModel):
    """Metadata + raw content for a single source file."""

    # Relative path from repo root (e.g.  "src/api/routes/ingest.py")
    relative_path: str
    # Absolute path on the local filesystem
    absolute_path: Path
    # File extension including leading dot (e.g. ".py")
    extension: str
    # Size in bytes
    size_bytes: int
    # Raw text content (None if file is binary or exceeds the size limit)
    content: Optional[str] = None
    # Encoding detected (or assumed "utf-8")
    encoding: str = "utf-8"

    model_config = {"arbitrary_types_allowed": True}


class FileLoaderResult(BaseModel):
    """Aggregated output of the File Loader step."""

    repo_info: RepoInfo
    files: list[FileInfo] = Field(default_factory=list)
    skipped_files: list[str] = Field(
        default_factory=list,
        description="Relative paths of files that were skipped (binary / too large).",
    )
    total_files_found: int = 0
    total_files_loaded: int = 0
    load_duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Step 4 — Code Parser (AST Analysis)
# ---------------------------------------------------------------------------


class SymbolInfo(BaseModel):
    """A symbol (function, class, method, etc.) extracted from source code."""

    kind: str = Field(..., description="Symbol kind: function, class, method, variable, etc.")
    name: str = Field(..., description="Symbol name")
    line_start: int = Field(..., description="Starting line number (1-indexed)")
    line_end: int = Field(..., description="Ending line number (1-indexed, inclusive)")
    parent: Optional[str] = Field(
        default=None,
        description="Parent symbol name (e.g., class name for a method), if any.",
    )


class ParsedFile(BaseModel):
    """Result of parsing a single source file."""

    relative_path: str = Field(..., description="Path relative to repository root")
    symbols: list[SymbolInfo] = Field(
        default_factory=list, description="List of symbols extracted from the file"
    )
    imports: list[str] = Field(
        default_factory=list, description="List of imported modules or files"
    )


class ParseResult(BaseModel):
    """Aggregated output of the Code Parser step."""

    repo_info: RepoInfo
    parsed_files: list[ParsedFile] = Field(default_factory=list)
    parse_duration_seconds: float = 0.0
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages encountered during parsing (per file).",
    )


# ---------------------------------------------------------------------------
# Step 5 — Agent 1: Code Analyzer
# ---------------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Request body for the POST /analyze endpoint."""

    github_url: str = Field(
        ...,
        examples=["https://github.com/tiangolo/fastapi"],
        description=(
            "Public GitHub repository URL. "
            "The repository must have been ingested first via POST /ingest."
        ),
    )
    language: str = Field(
        default="python",
        examples=["python", "javascript", "typescript", "java", "go"],
        description="Primary programming language of the repository.",
    )
    branch: Optional[str] = Field(
        default=None,
        description="Branch that was used during ingestion (used to resolve the local path).",
    )

    @field_validator("language")
    @classmethod
    def _normalise_language(cls, v: str) -> str:
        return v.strip().lower()


class AnalyzeResponse(BaseModel):
    """Response returned by the POST /analyze endpoint."""

    status: str = "success"
    message: str
    data: Optional[dict] = None


# ---------------------------------------------------------------------------
# Generic API response wrappers
# ---------------------------------------------------------------------------


class SuccessResponse(BaseModel):
    status: str = "success"
    message: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None
