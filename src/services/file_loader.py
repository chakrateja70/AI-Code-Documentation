"""
src/services/file_loader.py

File Loader (Step 3)
====================
Responsible for:
  1. Recursively traversing the cloned repository.
  2. Filtering files by allowed extensions (``config.SUPPORTED_EXTENSIONS``).
  3. Skipping excluded directories (``config.EXCLUDED_DIRS``).
  4. Reading each file's raw text content (UTF-8 with fallback to latin-1).
  5. Skipping files that are binary or exceed the configured size limit.
  6. Returning a :class:`FileLoaderResult` with all collected :class:`FileInfo`
     objects **and** a list of skipped paths.

Design notes
------------
* File traversal is purely synchronous (``os.walk`` / ``pathlib``).
* The FastAPI route calls this inside ``asyncio.to_thread`` to avoid blocking.
* Content is stored as a plain string — the Parser layer will receive this
  directly.
"""

import os
import time
from pathlib import Path

from config import Settings
from src.core.models import FileInfo, FileLoaderResult, RepoInfo

# Load settings once at module level to avoid repeated environment variable access
settings = Settings()

def load_files(repo_info: RepoInfo) -> FileLoaderResult:
    """Collect source files from a repo and return the loader result."""
    root: Path = repo_info.local_path
    files: list[FileInfo] = []
    skipped: list[str] = []

    t_start = time.perf_counter()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            d for d in dirnames
            if d not in settings.EXCLUDED_DIRS and not d.endswith(".egg-info")
        ]

        for filename in filenames:
            abs_path = Path(dirpath) / filename
            ext = abs_path.suffix.lower()

            # Skip unsupported extensions
            if ext not in settings.SUPPORTED_EXTENSIONS:
                continue

            rel_path = abs_path.relative_to(root).as_posix()

            # Skip files that are too large
            try:
                size = abs_path.stat().st_size
            except OSError:
                skipped.append(rel_path)
                continue

            if size > settings.MAX_FILE_SIZE_BYTES:
                skipped.append(rel_path)
                continue

            # Attempt to read the file as text
            content, encoding = _read_text(abs_path)
            if content is None:
                skipped.append(rel_path)
                continue

            file_info = FileInfo(
                relative_path=rel_path,
                absolute_path=abs_path,
                extension=ext,
                size_bytes=size,
                content=content,
                encoding=encoding,
            )
            files.append(file_info)

    duration = time.perf_counter() - t_start

    result = FileLoaderResult(
        repo_info=repo_info,
        files=files,
        skipped_files=skipped,
        total_files_found=len(files) + len(skipped),
        total_files_loaded=len(files),
        load_duration_seconds=round(duration, 3),
    )

    return result

def _read_text(path: Path) -> tuple[str | None, str]:
    """Read text with utf-8/latin-1 fallback and return (content, encoding)."""
    for encoding in ("utf-8", "latin-1"):
        try:
            text = path.read_text(encoding=encoding, errors="strict")
            # Heuristic: if the text contains lots of null bytes → binary
            if "\x00" in text:
                return None, ""
            return text, encoding
        except (UnicodeDecodeError, PermissionError):
            continue
    return None, ""
