from __future__ import annotations

import os
from typing import Any
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(override=True)

BASE_DIR: Path = Path(__file__).resolve().parent
REPOS_DIR: Path = BASE_DIR / "repos"; REPOS_DIR.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXTENSIONS: set[str] = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".rs", ".cpp", ".c", ".cs", ".php", ".kt", ".swift", ".scala", ".sh", ".yaml", ".yml", ".json", ".toml", ".md"}

EXCLUDED_DIRS: set[str] = {".git", ".github", "__pycache__", "node_modules", ".venv", "venv", "env", ".env", "dist", "build", "out", ".next", ".nuxt", "target", "vendor", ".mypy_cache", ".pytest_cache", ".ruff_cache", "coverage", ".coverage", "htmlcov", "eggs", ".eggs", "*.egg-info"}

MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024)))
GROQ_MODEL: str = "llama-3.3-70b-versatile"
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))

class Settings:
    """
    A centralized class to hold all application settings loaded from environment variables.
    """
    
    def __init__(self):
        # Required settings - validate immediately
        self.GROQ_API_KEY: str = self._get_required("GROQ_API_KEY")
        self.SUPPORTED_EXTENSIONS: set[str] = SUPPORTED_EXTENSIONS
        self.EXCLUDED_DIRS: set[str] = EXCLUDED_DIRS
        self.MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_BYTES
        self.GROQ_MODEL: str = GROQ_MODEL
        self.LLM_TEMPERATURE: float = LLM_TEMPERATURE
    
    @staticmethod
    def _get_required(key: str) -> str:
        """Get a required environment variable or raise ValueError."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"{key} not found in environment variables. Please check your .env file.")
        return value

# Create a single instance of the settings to be imported across the application
settings = Settings()
