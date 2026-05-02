"""
config.py — Application-wide configuration.

All tunable knobs live here so that nothing is hard-coded inside the
service layer.
"""

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
MAX_FILE_SIZE_BYTES: int = 5 * 1024 * 1024  # 5 MB
