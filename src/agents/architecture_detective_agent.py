"""
src/agents/architecture_detective_agent.py

Agent 2 — Architecture Detective
================================
Infers system architecture signals from the repository structure and imports,
then asks the LLM to write an Architecture section.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from src.agents.base_agent import BaseAgent
from src.core.state import DocState


class ArchitectureDetectiveAgent(BaseAgent):
    """Infer architecture signals and generate an architecture summary."""

    def __init__(self, llm: Any) -> None:
        super().__init__(llm, "architecture_detective")

    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Run architecture analysis for the current state."""
        t_start = time.monotonic()

        structure = state.get("code_structure", {})
        repo_path = state.get("repo_path", "")

        facts = self._build_architecture_facts(structure)

        try:
            content = await self._generate_architecture_doc(facts, repo_path)
        except Exception:
            content = self._fallback_summary(facts)

        elapsed = time.monotonic() - t_start
        output = self.format_output(
            content=content,
            metadata={
                "repo_path": repo_path,
                "top_level_dirs": len(facts.get("top_level_dirs", [])),
                "layers_detected": len(facts.get("layers", [])),
                "analysis_duration_seconds": round(elapsed, 3),
            },
        )
        state["architecture_output"] = output
        return output

    # ------------------------------------------------------------------
    # Architecture inference
    # ------------------------------------------------------------------

    def _build_architecture_facts(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        modules: List[str] = structure.get("modules", [])
        classes: List[Dict[str, Any]] = structure.get("classes", [])
        functions: List[Dict[str, Any]] = structure.get("functions", [])
        imports: List[str] = structure.get("imports", [])

        top_level_dirs, second_level_dirs = self._summarize_directories(modules)
        layers = self._detect_layers(modules)
        patterns = self._detect_patterns(modules, classes, functions)
        import_summary = self._summarize_imports(imports)

        return {
            "top_level_dirs": top_level_dirs,
            "second_level_dirs": second_level_dirs,
            "layers": layers,
            "patterns": patterns,
            "import_summary": import_summary,
            "module_count": len(modules),
            "class_count": len(classes),
            "function_count": len(functions),
        }

    @staticmethod
    def _summarize_directories(modules: Iterable[str]) -> Tuple[List[str], List[str]]:
        top_counter: Counter[str] = Counter()
        second_counter: Counter[str] = Counter()

        for module in modules:
            parts = Path(module).parts
            if not parts:
                continue
            top_counter[parts[0]] += 1
            if len(parts) > 1:
                second_counter["/".join(parts[:2])] += 1

        top_level = [name for name, _ in top_counter.most_common(10)]
        second_level = [name for name, _ in second_counter.most_common(10)]
        return top_level, second_level

    @staticmethod
    def _detect_layers(modules: Iterable[str]) -> List[str]:
        joined = "\n".join(modules).lower()
        layers = []

        def add_if(keyword: str, label: str) -> None:
            if keyword in joined and label not in layers:
                layers.append(label)

        add_if("api/", "API layer")
        add_if("routes/", "Routing layer")
        add_if("controllers/", "Controller layer")
        add_if("services/", "Service layer")
        add_if("core/", "Core/domain layer")
        add_if("models/", "Model layer")
        add_if("utils/", "Utility layer")
        add_if("db/", "Data access layer")
        add_if("repository/", "Repository layer")
        add_if("frontend/", "Frontend layer")
        add_if("client/", "Client layer")
        add_if("ui/", "UI layer")
        add_if("components/", "Component layer")

        return layers

    @staticmethod
    def _detect_patterns(
        modules: Iterable[str],
        classes: Iterable[Dict[str, Any]],
        functions: Iterable[Dict[str, Any]],
    ) -> List[str]:
        haystack = "\n".join(modules).lower()
        haystack += "\n" + "\n".join(c.get("name", "").lower() for c in classes)
        haystack += "\n" + "\n".join(f.get("name", "").lower() for f in functions)

        patterns = []
        checks = {
            "factory": "Factory",
            "builder": "Builder",
            "singleton": "Singleton",
            "repository": "Repository",
            "adapter": "Adapter",
            "strategy": "Strategy",
            "observer": "Observer",
            "decorator": "Decorator",
            "pipeline": "Pipeline",
            "service": "Service Layer",
        }

        for token, label in checks.items():
            if token in haystack and label not in patterns:
                patterns.append(label)

        return patterns

    @staticmethod
    def _summarize_imports(imports: Iterable[str]) -> Dict[str, Any]:
        external: Counter[str] = Counter()
        internal: Counter[str] = Counter()

        for imp in imports:
            line = imp.strip()
            if not line:
                continue

            module = ""
            if line.startswith("from "):
                module = line.split(" ", 2)[1]
            elif line.startswith("import "):
                module = line.split(" ", 1)[1].split(",")[0]
            module = module.split(" as ")[0].strip()

            if not module:
                continue

            if module.startswith("."):
                internal[module] += 1
            else:
                # Heuristic: treat stdlib/local package names later in summary.
                external[module] += 1

        return {
            "external_top": [name for name, _ in external.most_common(10)],
            "internal_top": [name for name, _ in internal.most_common(10)],
            "external_count": sum(external.values()),
            "internal_count": sum(internal.values()),
        }

    # ------------------------------------------------------------------
    # LLM synthesis
    # ------------------------------------------------------------------

    async def _generate_architecture_doc(
        self, facts: Dict[str, Any], repo_path: str
    ) -> str:
        truncated = {
            "top_level_dirs": facts.get("top_level_dirs", []),
            "second_level_dirs": facts.get("second_level_dirs", []),
            "layers": facts.get("layers", []),
            "patterns": facts.get("patterns", []),
            "import_summary": facts.get("import_summary", {}),
            "module_count": facts.get("module_count", 0),
            "class_count": facts.get("class_count", 0),
            "function_count": facts.get("function_count", 0),
        }

        prompt = f"""You are a senior software architect writing the Architecture section for a codebase.

Architecture signals extracted from the repository:
{json.dumps(truncated, indent=2)}

Write a clear Architecture section that covers:
1. System overview and major components.
2. Component relationships and data flow between layers.
3. Design patterns inferred from names and structure.
4. Layering (frontend/backend/services/data) and boundaries.
5. Scalability or extensibility cues (modularity, plugin points, async/batching, etc.).

Focus on what the structure implies. If uncertain, phrase as "appears to" or "likely".
"""

        response = await self.llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    @staticmethod
    def _fallback_summary(facts: Dict[str, Any]) -> str:
        return (
            "## Architecture Summary (Auto-generated)\n\n"
            f"- **Top-level directories**: {', '.join(facts.get('top_level_dirs', [])) or 'N/A'}\n"
            f"- **Detected layers**: {', '.join(facts.get('layers', [])) or 'N/A'}\n"
            f"- **Detected patterns**: {', '.join(facts.get('patterns', [])) or 'N/A'}\n"
            f"- **Module count**: {facts.get('module_count', 0)}\n"
            f"- **Class count**: {facts.get('class_count', 0)}\n"
            f"- **Function count**: {facts.get('function_count', 0)}\n"
            "\n*(LLM was unavailable — this is a structural summary only.)*"
        )
