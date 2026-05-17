"""
src/agents/examples_synthesizer_agent.py

Agent 4 — Examples Synthesizer
================================
Responsibilities
----------------
1. Mine the repository for existing examples, test fixtures, README snippets,
   and integration patterns.
2. Infer common use cases from the code structure and API surface.
3. Ask the LLM to synthesize a "Quick Start & Examples" documentation section
   with working code snippets and integration guidance.
4. Store results in DocState under ``examples_output``.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.core.state import DocState


# ---------------------------------------------------------------------------
# Heuristic patterns
# ---------------------------------------------------------------------------

_EXAMPLE_FILE_PATTERNS = {
    "example", "demo", "sample", "tutorial", "quickstart", "quick_start",
    "getting_started", "starter", "playground",
}

_TEST_FILE_PATTERNS = {"test_", "_test", "spec_", "_spec", "fixture", "mock"}

_README_EXTENSIONS = {".md", ".rst", ".txt"}

_INTEGRATION_KEYWORDS = {
    "client", "sdk", "connector", "plugin", "middleware", "adapter",
    "hook", "callback", "handler", "listener", "subscriber",
}

_FRONTEND_FRAMEWORK_KEYWORDS = {
    "react", "next", "nextjs", "vue", "nuxt", "angular", "svelte",
    "solid", "vite", "webpack", "rollup", "tailwind", "chakra",
    "mui", "material-ui", "shadcn", "remix", "astro", "gatsby",
    "frontend", "ui", "component", "components", "pages", "hooks",
}

_BACKEND_FRAMEWORK_KEYWORDS = {
    "fastapi", "flask", "django", "starlette", "sanic", "litestar",
    "express", "nestjs", "koa", "hapi", "spring", "springboot",
    "rails", "laravel", "asp.net", "dotnet", "gin", "echo", "fiber",
    "axum", "rocket", "phoenix", "backend", "api", "routes", "controllers",
    "services", "models", "repositories", "db", "database",
}

_STACK_KEYWORDS = _FRONTEND_FRAMEWORK_KEYWORDS | _BACKEND_FRAMEWORK_KEYWORDS | {
    "graphql", "grpc", "websocket", "socket", "mobile", "flutter",
    "react-native", "electron", "cli", "library", "package",
}

_LANGUAGE_BY_EXTENSION = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".java": "Java",
    ".go": "Go",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".php": "PHP",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".dart": "Dart",
    ".scala": "Scala",
    ".hs": "Haskell",
    ".lua": "Lua",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".vue": "Vue",
    ".svelte": "Svelte",
}

_USE_CASE_FUNCTION_PREFIXES = {
    "create", "get", "update", "delete", "list", "search", "upload",
    "download", "process", "generate", "parse", "validate", "send",
    "fetch", "load", "save", "run", "execute", "handle",
}


class ExamplesSynthesizerAgent(BaseAgent):
    """Mine repository patterns and synthesize practical usage examples."""

    def __init__(self, llm: Any) -> None:
        super().__init__(llm, "examples_synthesizer")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def invoke(self, state: DocState) -> Dict[str, Any]:
        t_start = time.monotonic()

        structure: Dict[str, Any] = state.get("code_structure", {})
        api_output: Dict[str, Any] = state.get("api_documentation_output", {})
        analysis_output: Dict[str, Any] = state.get("analysis_output", {})
        architecture_output: Dict[str, Any] = state.get("architecture_output", {})
        repo_path: str = state.get("repo_path", "")

        signals = self._extract_example_signals(
            structure,
            api_output,
            architecture_output,
        )
        context = self._build_synthesis_context(
            signals,
            analysis_output,
            api_output,
            architecture_output,
            repo_path,
        )

        try:
            content = await self._synthesize_examples(context)
        except Exception:
            content = self._fallback_summary(signals, repo_path)

        elapsed = time.monotonic() - t_start
        output = self.format_output(
            content=content,
            metadata={
                "repo_path": repo_path,
                "example_files_found": len(signals.get("example_files", [])),
                "test_files_found": len(signals.get("test_files", [])),
                "use_cases_detected": len(signals.get("use_cases", [])),
                "integration_patterns_found": len(signals.get("integration_patterns", [])),
                "analysis_duration_seconds": round(elapsed, 3),
            },
        )
        state["examples_output"] = output
        return output

    # ------------------------------------------------------------------
    # Signal extraction
    # ------------------------------------------------------------------

    def _extract_example_signals(
        self,
        structure: Dict[str, Any],
        api_output: Dict[str, Any],
        architecture_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        modules: List[str] = structure.get("modules", [])
        functions: List[Dict[str, Any]] = structure.get("functions", [])
        classes: List[Dict[str, Any]] = structure.get("classes", [])
        imports: List[str] = structure.get("imports", [])

        example_files = self._find_example_files(modules)
        test_files = self._find_test_files(modules)
        use_cases = self._infer_use_cases(functions, classes)
        integration_patterns = self._detect_integration_patterns(
            imports, classes, functions
        )
        stack_profile = self._detect_stack_profile(
            modules, imports, classes, functions, architecture_output
        )
        main_language = self._infer_language(modules)
        api_type = (
            api_output.get("metadata", {}).get("api_type")
            if api_output.get("metadata")
            else None
        )
        endpoints = (
            api_output.get("metadata", {}).get("openapi_spec", {}).get("paths", {})
            if api_output.get("metadata")
            else {}
        )

        return {
            "example_files": example_files,
            "test_files": test_files,
            "use_cases": use_cases,
            "integration_patterns": integration_patterns,
            "stack_profile": stack_profile,
            "main_language": main_language,
            "api_type": api_type or "REST",
            "sample_endpoints": list(endpoints.keys())[:5],
        }

    @staticmethod
    def _find_example_files(modules: List[str]) -> List[str]:
        found = []
        for mod in modules:
            lower = mod.lower()
            if any(pat in lower for pat in _EXAMPLE_FILE_PATTERNS):
                found.append(mod)
            elif Path(mod).suffix in _README_EXTENSIONS:
                found.append(mod)
        return found[:20]

    @staticmethod
    def _find_test_files(modules: List[str]) -> List[str]:
        found = []
        for mod in modules:
            lower = Path(mod).stem.lower()
            if any(pat in lower for pat in _TEST_FILE_PATTERNS):
                found.append(mod)
        return found[:20]

    @staticmethod
    def _infer_use_cases(
        functions: List[Dict[str, Any]],
        classes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        use_cases: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for fn in functions:
            name: str = fn.get("name", "")
            name_lower = name.lower()
            for prefix in _USE_CASE_FUNCTION_PREFIXES:
                if name_lower.startswith(prefix) and name not in seen:
                    # Strip the verb to get the resource name
                    resource = re.sub(rf"^{prefix}_?", "", name_lower, flags=re.IGNORECASE)
                    use_cases.append(
                        {
                            "verb": prefix,
                            "resource": resource or name,
                            "function": name,
                            "file": fn.get("file", ""),
                        }
                    )
                    seen.add(name)
                    break

        return use_cases[:25]

    @staticmethod
    def _detect_integration_patterns(
        imports: List[str],
        classes: List[Dict[str, Any]],
        functions: List[Dict[str, Any]],
    ) -> List[str]:
        found: set[str] = set()
        haystack = (
            " ".join(imports).lower()
            + " ".join(c.get("name", "").lower() for c in classes)
            + " ".join(f.get("name", "").lower() for f in functions)
        )
        for kw in _INTEGRATION_KEYWORDS:
            if kw in haystack:
                found.add(kw)
        return sorted(found)

    @staticmethod
    def _infer_language(modules: List[str]) -> str:
        ext_counter: Dict[str, int] = {}
        for mod in modules:
            ext = Path(mod).suffix.lower()
            ext_counter[ext] = ext_counter.get(ext, 0) + 1
        if not ext_counter:
            return "Python"
        dominant = max(ext_counter, key=lambda e: ext_counter[e])
        return _LANGUAGE_BY_EXTENSION.get(dominant, "Python")

    @staticmethod
    def _detect_stack_profile(
        modules: List[str],
        imports: List[str],
        classes: List[Dict[str, Any]],
        functions: List[Dict[str, Any]],
        architecture_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        language_counter: Counter[str] = Counter()
        for mod in modules:
            language = _LANGUAGE_BY_EXTENSION.get(Path(mod).suffix.lower())
            if language:
                language_counter[language] += 1

        primary_languages = [name for name, _ in language_counter.most_common(5)]
        if not primary_languages:
            primary_languages = ["Python"]

        haystack = "\n".join(modules).lower()
        haystack += "\n" + "\n".join(imports).lower()
        haystack += "\n" + "\n".join(c.get("name", "").lower() for c in classes)
        haystack += "\n" + "\n".join(f.get("name", "").lower() for f in functions)

        detected_frameworks = sorted(
            keyword for keyword in _STACK_KEYWORDS if keyword in haystack
        )
        frontend_frameworks = sorted(
            keyword for keyword in _FRONTEND_FRAMEWORK_KEYWORDS if keyword in haystack
        )
        backend_frameworks = sorted(
            keyword for keyword in _BACKEND_FRAMEWORK_KEYWORDS if keyword in haystack
        )

        if frontend_frameworks and backend_frameworks:
            project_type = "Full-stack"
        elif frontend_frameworks:
            project_type = "Frontend"
        elif backend_frameworks:
            project_type = "Backend"
        else:
            project_type = "Library / Tooling"

        architecture_layers: List[str] = []
        if architecture_output:
            architecture_layers = architecture_output.get("metadata", {}).get(
                "layers", []
            ) or []

        return {
            "primary_languages": primary_languages,
            "project_type": project_type,
            "frontend_frameworks": frontend_frameworks,
            "backend_frameworks": backend_frameworks,
            "detected_frameworks": detected_frameworks,
            "architecture_layers": architecture_layers,
        }

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_synthesis_context(
        signals: Dict[str, Any],
        analysis_output: Dict[str, Any],
        api_output: Dict[str, Any],
        architecture_output: Dict[str, Any],
        repo_path: str,
    ) -> Dict[str, Any]:
        project_name = (
            repo_path.split("/")[-1].split("\\")[-1] if repo_path else "Project"
        )
        overview = (
            analysis_output.get("content", "")[:500]
            if analysis_output
            else ""
        )
        api_summary = (
            api_output.get("content", "")[:500]
            if api_output
            else ""
        )
        return {
            "project_name": project_name,
            "main_language": signals.get("main_language", "Python"),
            "stack_profile": signals.get("stack_profile", {}),
            "api_type": signals.get("api_type", "REST"),
            "example_files": signals.get("example_files", []),
            "test_files": signals.get("test_files", [])[:10],
            "use_cases": signals.get("use_cases", [])[:15],
            "integration_patterns": signals.get("integration_patterns", []),
            "sample_endpoints": signals.get("sample_endpoints", []),
            "architecture_layers": (
                architecture_output.get("metadata", {}).get("layers", [])
                if architecture_output
                else []
            ),
            "project_overview": overview,
            "api_summary": api_summary,
        }

    # ------------------------------------------------------------------
    # LLM synthesis
    # ------------------------------------------------------------------

    async def _synthesize_examples(self, context: Dict[str, Any]) -> str:
        stack_profile = context.get("stack_profile", {})
        primary_languages = stack_profile.get("primary_languages", [])
        language_label = ", ".join(primary_languages[:3]) or context.get(
            "main_language", "Python"
        )
        project_type = stack_profile.get("project_type", "Library / Tooling")
        frontend_frameworks = stack_profile.get("frontend_frameworks", [])
        backend_frameworks = stack_profile.get("backend_frameworks", [])

        prompt = f"""You are a developer experience engineer writing the "Quick Start & Examples" section for a project's documentation.

Project context:
{json.dumps(context, indent=2)}

The repository may be frontend, backend, full-stack, or library/tooling oriented.
Do not assume FastAPI or Python. Adapt the examples to the detected stack profile.

Detected stack profile:
- Project type: {project_type}
- Primary languages: {language_label}
- Frontend frameworks: {', '.join(frontend_frameworks) or 'None detected'}
- Backend frameworks: {', '.join(backend_frameworks) or 'None detected'}

Generate a comprehensive **Quick Start & Examples** section that includes:

1. **Prerequisites** — What needs to be installed or configured before using this project.

2. **Quick Start (5 minutes)** — A step-by-step getting-started guide:
   - Installation command
   - Minimal configuration
    - First working code snippet in the most relevant detected language(s)

3. **Common Use Cases** — For each detected use case, provide:
   - A brief description of the scenario
    - A concise, working example that matches the detected stack and layers

4. **Frontend / Backend Integration** — If relevant, show how the pieces connect:
    - Frontend component/page usage for UI projects
    - Backend service/controller/API usage for server projects
    - Data fetching, state management, or request/response wiring where appropriate

5. **Integration Patterns** — Show how to integrate this project with other systems:
   - Client SDK usage (if applicable)
   - Middleware / plugin setup (if detected)
   - Webhook / event handler patterns (if detected)

6. **Best Practices** — 3-5 bullet points on recommended usage patterns inferred from the codebase.

7. **Full Example** — A more complete, end-to-end example that combines multiple features and reflects the real stack composition.

Make the examples realistic, copy-pasteable, and immediately useful.
Use markdown code blocks with proper language syntax highlighting.
"""
        response = await self.llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_summary(signals: Dict[str, Any], repo_path: str) -> str:
        project = repo_path.split("/")[-1].split("\\")[-1] if repo_path else "Project"
        use_cases = signals.get("use_cases", [])
        stack_profile = signals.get("stack_profile", {})
        uc_lines = "\n".join(
            f"  - `{uc['function']}` — {uc['verb']} {uc['resource']}"
            for uc in use_cases[:8]
        ) or "  - None detected"
        return (
            f"## Quick Start & Examples — {project}\n\n"
            f"**Language(s):** {', '.join(stack_profile.get('primary_languages', [])[:3]) or signals.get('main_language', 'Python')}\n"
            f"**Project type:** {stack_profile.get('project_type', 'Library / Tooling')}\n"
            f"**Frontend frameworks:** {', '.join(stack_profile.get('frontend_frameworks', [])) or 'None detected'}\n"
            f"**Backend frameworks:** {', '.join(stack_profile.get('backend_frameworks', [])) or 'None detected'}\n"
            f"**API Type:** {signals.get('api_type', 'REST')}\n\n"
            f"### Detected Use Cases\n{uc_lines}\n\n"
            f"**Example files found:** {len(signals.get('example_files', []))}\n"
            f"**Test files found:** {len(signals.get('test_files', []))}\n"
            f"**Integration patterns:** {', '.join(signals.get('integration_patterns', [])) or 'None'}\n\n"
            "*(LLM was unavailable — this is a structural summary only.)*"
        )
