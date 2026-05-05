"""
src/agents/__init__.py

Public re-exports for the agents package.
Import agents from here to keep downstream code decoupled from internal
module layout.

Example
-------
    from src.agents import CodeAnalyzerAgent
"""

from src.agents.base_agent import BaseAgent
from src.agents.code_analyzer_agent import CodeAnalyzerAgent
from src.agents.architecture_detective_agent import ArchitectureDetectiveAgent

__all__ = [
    "BaseAgent",
    "CodeAnalyzerAgent",
    "ArchitectureDetectiveAgent",
]
