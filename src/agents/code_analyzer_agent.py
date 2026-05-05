"""
src/agents/code_analyzer_agent.py

Agent 1 — Code Analyzer
========================
Responsibilities
----------------
1. Walk the cloned repository and extract structural information (modules,
   functions, classes, imports) using the existing ``code_parser`` service.
2. Feed that structure to the LLM to produce a human-readable overview and
   API documentation section.
3. Store the raw structure *and* the LLM prose back into ``DocState`` for
   downstream agents to use.

Integration with existing services
-----------------------------------
* ``src.services.code_parser.parse_file``  — tree-sitter-based AST analysis.
* ``src.services.file_loader``             — recursively loads source files.
* ``src.core.models``                      — ``FileInfo``, ``ParsedFile``, etc.
* ``src.core.state.DocState``              — shared pipeline state.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent
from src.core.models import FileInfo, ParsedFile
from src.core.state import DocState
from src.services.code_parser import parse_file
from config import settings


# Maximum file size we'll read into memory for AST analysis.


class CodeAnalyzerAgent(BaseAgent):
    """Analyze repo structure and generate documentation with an LLM."""

    def __init__(self, llm: Any, max_workers: int = 4) -> None:
        super().__init__(llm, "code_analyzer")
        self._max_workers = max(1, max_workers)
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers, thread_name_prefix="code-analyzer"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Run analysis for the current state and return the output envelope."""
        t_start = time.monotonic()

        repo_path: str = state["repo_path"]

        # ------------------------------------------------------------------ #
        # Step 1 — collect source files from disk
        # ------------------------------------------------------------------ #
        loop = asyncio.get_running_loop()
        file_infos: List[FileInfo] = await loop.run_in_executor(
            self._executor, self._collect_files, repo_path
        )

        # ------------------------------------------------------------------ #
        # Step 2 — parse each file with tree-sitter (via existing service)
        # ------------------------------------------------------------------ #
        parsed_files: List[ParsedFile] = await self._parse_files_in_parallel(
            file_infos
        )

        # ------------------------------------------------------------------ #
        # Step 3 — build the unified structure dict
        # ------------------------------------------------------------------ #
        structure = self._build_structure(parsed_files, repo_path)
        state["code_structure"] = structure

        # ------------------------------------------------------------------ #
        # Step 4 — ask the LLM to write the documentation prose
        # ------------------------------------------------------------------ #
        overview_docs = await self._generate_documentation(structure)

        # ------------------------------------------------------------------ #
        # Step 5 — pack results
        # ------------------------------------------------------------------ #
        elapsed = time.monotonic() - t_start

        output = self.format_output(
            content=overview_docs,
            metadata={
                "repo_path": repo_path,
                "modules_found": len(structure.get("modules", [])),
                "functions_found": len(structure.get("functions", [])),
                "classes_found": len(structure.get("classes", [])),
                "imports_found": len(structure.get("imports", [])),
                "analysis_duration_seconds": round(elapsed, 3),
            },
        )
        state["analysis_output"] = output
        return output

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_files(self, repo_path: str) -> List[FileInfo]:
        """Collect FileInfo records for source files in the repo."""
        root = Path(repo_path)
        target_extensions = settings.SUPPORTED_EXTENSIONS

        file_infos: List[FileInfo] = []

        for root_dir, dirs, files in os.walk(root, topdown=True):
            dirs[:] = [d for d in dirs if d not in settings.EXCLUDED_DIRS]

            for filename in files:
                path = Path(root_dir) / filename
                if path.suffix.lower() not in target_extensions:
                    continue

                try:
                    size = path.stat().st_size
                except OSError as exc:
                    continue

                content: str | None = None

                if size <= settings.MAX_FILE_SIZE_BYTES:
                    try:
                        raw = path.read_bytes()
                        if b"\x00" not in raw:
                            content = raw.decode("utf-8", errors="replace")
                    except Exception as exc:
                        pass

                file_infos.append(
                    FileInfo(
                        relative_path=str(path.relative_to(root)),
                        absolute_path=path,
                        extension=path.suffix.lower(),
                        size_bytes=size,
                        content=content,
                        encoding="utf-8",
                    )
                )

        return file_infos

    def _parse_all_files(self, file_infos: List[FileInfo]) -> List[ParsedFile]:
        """Parse each FileInfo and keep running on per-file errors."""
        parsed: List[ParsedFile] = []
        for fi in file_infos:
            try:
                parsed.append(parse_file(fi))
            except Exception as exc:
                # Append an empty ParsedFile so the module list stays intact.
                parsed.append(
                    ParsedFile(
                        relative_path=fi.relative_path,
                        symbols=[],
                        imports=[],
                    )
                )
        return parsed

    async def _parse_files_in_parallel(
        self, file_infos: List[FileInfo]
    ) -> List[ParsedFile]:
        if not file_infos:
            return []

        chunk_size = max(
            1, (len(file_infos) + self._max_workers - 1) // self._max_workers
        )
        chunks = [
            file_infos[i : i + chunk_size]
            for i in range(0, len(file_infos), chunk_size)
        ]

        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self._executor, self._parse_all_files, chunk)
            for chunk in chunks
        ]

        parsed_batches = await asyncio.gather(*tasks)
        parsed: List[ParsedFile] = []
        for batch in parsed_batches:
            parsed.extend(batch)
        return parsed

    def _build_structure(
        self,
        parsed_files: List[ParsedFile],
        repo_path: str,
    ) -> Dict[str, Any]:
        """
        Collapse the per-file ``ParsedFile`` list into a single flat
        structure dict that mirrors what the LLM prompt expects.

        Structure schema
        ----------------
        {
            "modules":   [str, ...],          # relative file paths
            "functions": [{"name", "file", "line_start", "line_end"}, ...],
            "classes":   [{"name", "file", "line_start", "line_end", "methods"}, ...],
            "imports":   [str, ...],          # deduplicated import strings
        }
        """
        modules: List[str] = []
        functions: List[Dict[str, Any]] = []
        classes: List[Dict[str, Any]] = []
        imports_set: set[str] = set()

        for pf in parsed_files:
            modules.append(pf.relative_path)

            for symbol in pf.symbols:
                if symbol.kind in ("function", "function_definition"):
                    functions.append(
                        {
                            "name": symbol.name,
                            "file": pf.relative_path,
                            "line_start": symbol.line_start,
                            "line_end": symbol.line_end,
                            "parent": symbol.parent,
                        }
                    )
                elif symbol.kind in ("class", "class_definition"):
                    # Gather methods that belong to this class.
                    methods = [
                        s.name
                        for s in pf.symbols
                        if s.parent == symbol.name
                        and s.kind in ("method", "method_definition", "function", "function_definition")
                    ]
                    classes.append(
                        {
                            "name": symbol.name,
                            "file": pf.relative_path,
                            "line_start": symbol.line_start,
                            "line_end": symbol.line_end,
                            "methods": methods,
                        }
                    )

            for imp in pf.imports:
                imports_set.add(imp.strip())

        return {
            "modules": modules,
            "functions": functions,
            "classes": classes,
            "imports": sorted(imports_set),
        }

    async def _generate_documentation(self, structure: Dict[str, Any]) -> str:
        """
        Send the code structure to the LLM and return the generated prose.

        If the LLM call fails for any reason, a fallback summary is
        returned so the pipeline can continue.
        """
        # Truncate the structure payload if it is enormous (to stay within
        # the LLM context window).
        truncated = self._truncate_structure(structure, max_items=50)

        prompt = f"""You are a senior software engineer writing documentation for a codebase.

Given the following code structure extracted from a repository, generate comprehensive documentation.

Code Structure:
{json.dumps(truncated, indent=2)}

Please produce:

1. **Project Overview** — A concise paragraph (3-5 sentences) explaining what this project does, its purpose, and its main capabilities.

2. **Key Classes** — For each class found, describe its role and main responsibilities in 1-2 sentences.

3. **Main Functions & Modules** — Highlight the most important functions and what they do.

4. **Dependencies & Imports** — Summarise the external libraries and internal module dependencies.

5. **Code Organisation** — Briefly describe how the codebase is structured (directories, separation of concerns, etc.).

Use clear, professional language suitable for a technical README or API reference.
"""

        try:
            response = await self.llm.ainvoke(prompt)
            # LangChain chat models return an AIMessage; plain callables return str.
            return response.content if hasattr(response, "content") else str(response)
        except Exception as exc:
            # Graceful fallback — return a minimal auto-generated summary.
            return self._fallback_summary(structure)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate_structure(
        structure: Dict[str, Any], max_items: int = 50
    ) -> Dict[str, Any]:
        """
        Limit list fields to *max_items* entries so we don't blow the LLM
        context window on very large repos.
        """
        return {
            "modules":   structure.get("modules", [])[:max_items],
            "functions": structure.get("functions", [])[:max_items],
            "classes":   structure.get("classes", [])[:max_items],
            "imports":   structure.get("imports", [])[:max_items],
        }

    @staticmethod
    def _fallback_summary(structure: Dict[str, Any]) -> str:
        """Return a minimal text summary when the LLM is unavailable."""
        n_modules   = len(structure.get("modules", []))
        n_functions = len(structure.get("functions", []))
        n_classes   = len(structure.get("classes", []))
        n_imports   = len(structure.get("imports", []))

        modules_list = ", ".join(structure.get("modules", [])[:10]) or "N/A"

        return (
            f"## Auto-generated Code Structure Summary\n\n"
            f"- **Modules analysed**: {n_modules} ({modules_list})\n"
            f"- **Functions found**: {n_functions}\n"
            f"- **Classes found**: {n_classes}\n"
            f"- **Unique imports**: {n_imports}\n\n"
            f"*(LLM was unavailable — this is a structural summary only.)*"
        )
