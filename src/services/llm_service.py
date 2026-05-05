"""
src/services/llm_service.py

LLM Service — Centralized LLM initialization.

Responsibilities:
  - Initialize Groq LLM client with credentials and settings from config.
  - Provide a single entry point for LLM access across the application.
"""

from __future__ import annotations

from typing import Any

from langchain_groq import ChatGroq

from config import Settings

settings = Settings()

def get_llm() -> Any:
    """Get a Groq LLM client configured from environment settings."""
    api_key = settings.GROQ_API_KEY
    model = settings.GROQ_MODEL
    temperature = settings.LLM_TEMPERATURE

    return ChatGroq(model=model, api_key=api_key, temperature=temperature)
