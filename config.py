"""
config.py — Application-wide configuration.

All tunable knobs live here so that nothing is hard-coded inside the
service layer.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Root of the project (the directory that contains this file).
BASE_DIR: Path = Path(__file__).resolve().parent

# Where cloned repositories are stored on disk.
REPOS_DIR: Path = BASE_DIR / "repos"
REPOS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# File Loader settings
# ---------------------------------------------------------------------------

# Source-code extensions that the FileLoader will collect.
SUPPORTED_EXTENSIONS: set[str] = {
    ".py",   # Python
    ".js",   # JavaScript
    ".ts",   # TypeScript
    ".jsx",  # React JSX
    ".tsx",  # React TSX
    ".java", # Java
    ".go",   # Go
    ".rb",   # Ruby
    ".rs",   # Rust
    ".cpp",  # C++
    ".c",    # C
    ".cs",   # C#
    ".php",  # PHP
    ".kt",   # Kotlin
    ".swift",# Swift
    ".scala",# Scala
    ".sh",   # Shell scripts
    ".yaml", # YAML (configs / k8s)
    ".yml",
    ".json", # JSON (package manifests, etc.)
    ".toml", # TOML (pyproject.toml, Cargo.toml, etc.)
    ".md",   # Markdown (README, docs)
}

# Directory names to skip during traversal (dependencies, build artefacts…).
EXCLUDED_DIRS: set[str] = {
    ".git",
    ".github",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    "dist",
    "build",
    "out",
    ".next",
    ".nuxt",
    "target",       # Rust / Maven
    "vendor",       # Go / PHP
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "coverage",
    ".coverage",
    "htmlcov",
    "eggs",
    ".eggs",
    "*.egg-info",
}

# ---------------------------------------------------------------------------
# Repository Manager settings
# ---------------------------------------------------------------------------

# Maximum size (bytes) we allow a single file to be loaded into memory.
MAX_FILE_SIZE_BYTES: int = int(
    os.getenv("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024))
)  # 5 MB default

# ---------------------------------------------------------------------------
# LLM settings  (Agent layer — Groq / Llama)
# ---------------------------------------------------------------------------

from typing import Any
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv(BASE_DIR / ".env")

# Groq API key — set GROQ_API_KEY in your environment or .env file.
# Get a free key at https://console.groq.com/keys
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# Llama model served by Groq (overridable via env var).
# Options: llama-3.3-70b-versatile | llama3-8b-8192 | llama3-70b-8192
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Temperature — lower = more factual documentation prose.
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))


def get_llm() -> Any:
    """
    Return a ready-to-use async-compatible LLM instance backed by Groq.

    The model used is Llama 3.3 70B (configurable via GROQ_MODEL env var).
    GROQ_API_KEY must be set; raises ``RuntimeError`` with a clear message
    if it is missing or ``langchain-groq`` is not installed.

    The returned object exposes ``.ainvoke(prompt)`` and returns a LangChain
    ``AIMessage`` with a ``.content`` attribute.
    """
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Create a free key at https://console.groq.com/keys and set it as "
            "an environment variable:  $env:GROQ_API_KEY = 'your-key-here'"
        )

    try:
        from langchain_groq import ChatGroq  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "'langchain-groq' is not installed. "
            "Run: uv pip install langchain-groq"
        ) from exc

    return ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        temperature=LLM_TEMPERATURE,
    )
