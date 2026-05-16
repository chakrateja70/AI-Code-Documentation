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
from src.agents.api_documenter_agent import APIDocumenterAgent
from src.agents.examples_synthesizer_agent import ExamplesSynthesizerAgent
from src.agents.consistency_validator_agent import ConsistencyValidatorAgent
from src.agents.documentation_generator_agent import DocumentationGeneratorAgent

__all__ = [
    "BaseAgent",
    "CodeAnalyzerAgent",
    "ArchitectureDetectiveAgent",
    "APIDocumenterAgent",
    "ExamplesSynthesizerAgent",
    "ConsistencyValidatorAgent",
    "DocumentationGeneratorAgent",
]
