"""
src/agents/consistency_validator_agent.py

Agent 5 — Consistency Validator
=================================
Responsibilities
----------------
1. Inspect all documentation sections produced by Agents 1–4 for:
   - **Completeness** — all required sections are present.
   - **Consistency** — uniform writing style, terminology, and formatting.
   - **Clarity** — readability and absence of vague language.
   - **Coverage** — all detected APIs, classes, and modules are documented.
2. Compute a quality score from 1 (very poor) to 5 (excellent).
3. Return improvement suggestions grouped by category.
4. Store results in DocState under ``validation_output``.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from src.agents.base_agent import BaseAgent
from src.core.state import DocState


# ---------------------------------------------------------------------------
# Section requirements
# ---------------------------------------------------------------------------

_REQUIRED_SECTIONS = [
    "project overview",
    "architecture",
    "api reference",
    "quick start",
    "examples",
]

_STYLE_RED_FLAGS = [
    r"\btodo\b",
    r"\bfixme\b",
    r"\bplaceholder\b",
    r"\bcoming soon\b",
    r"\btbd\b",
    r"\bn/a\b",
    r"\bnone detected\b",
    r"\bauto-generated\b",
    r"\bllm was unavailable\b",
]

_VAGUE_PHRASES = [
    "various", "some", "many", "several", "etc", "and so on",
    "as needed", "if applicable", "might be", "could be",
]


class ConsistencyValidatorAgent(BaseAgent):
    """Validate documentation quality and return a score + improvement plan."""

    def __init__(self, llm: Any) -> None:
        super().__init__(llm, "consistency_validator")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def invoke(self, state: DocState) -> Dict[str, Any]:
        t_start = time.monotonic()

        docs = self._collect_docs(state)
        structure: Dict[str, Any] = state.get("code_structure", {})
        api_meta = (
            state.get("api_documentation_output", {}).get("metadata", {})
        )

        completeness = self._check_completeness(docs)
        consistency = self._check_consistency(docs)
        clarity = self._check_clarity(docs)
        coverage = self._check_coverage(docs, structure, api_meta)

        heuristic_score = self._compute_heuristic_score(
            completeness, consistency, clarity, coverage
        )

        try:
            llm_result = await self._llm_validate(docs, heuristic_score)
            final_score = llm_result["score"]
            suggestions = llm_result["suggestions"]
            llm_summary = llm_result["summary"]
        except Exception:
            final_score = heuristic_score
            suggestions = self._build_fallback_suggestions(
                completeness, consistency, clarity, coverage
            )
            llm_summary = self._build_fallback_text(
                final_score, completeness, consistency, clarity, coverage
            )

        elapsed = time.monotonic() - t_start
        output = self.format_output(
            content=llm_summary,
            metadata={
                "quality_score": final_score,
                "heuristic_score": heuristic_score,
                "completeness": completeness,
                "consistency": consistency,
                "clarity": clarity,
                "coverage": coverage,
                "suggestions": suggestions,
                "analysis_duration_seconds": round(elapsed, 3),
            },
        )
        state["validation_output"] = output
        return output

    # ------------------------------------------------------------------
    # Document collection
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_docs(state: DocState) -> Dict[str, str]:
        def _text(key: str) -> str:
            val = state.get(key)  # type: ignore[call-overload]
            if isinstance(val, dict):
                return val.get("content", "") or ""
            return ""

        return {
            "analysis": _text("analysis_output"),
            "architecture": _text("architecture_output"),
            "api_reference": _text("api_documentation_output"),
            "examples": _text("examples_output"),
        }

    # ------------------------------------------------------------------
    # Heuristic checks
    # ------------------------------------------------------------------

    def _check_completeness(self, docs: Dict[str, str]) -> Dict[str, Any]:
        combined = "\n".join(docs.values()).lower()
        present = []
        missing = []
        for section in _REQUIRED_SECTIONS:
            if section in combined:
                present.append(section)
            else:
                missing.append(section)

        section_lengths = {k: len(v) for k, v in docs.items()}
        empty_sections = [k for k, v in docs.items() if not v.strip()]

        score = max(0.0, 1.0 - len(missing) / len(_REQUIRED_SECTIONS))
        return {
            "score": round(score, 2),
            "present_sections": present,
            "missing_sections": missing,
            "empty_agent_outputs": empty_sections,
            "section_lengths": section_lengths,
        }

    def _check_consistency(self, docs: Dict[str, str]) -> Dict[str, Any]:
        issues = []
        combined = "\n".join(docs.values())

        # Check for fallback/stub content
        for pattern in _STYLE_RED_FLAGS:
            if re.search(pattern, combined, re.IGNORECASE):
                issues.append(f"Contains stub/fallback text matching '{pattern}'")

        # Check heading style consistency (mix of # and ## at top level)
        h1_count = len(re.findall(r"^# ", combined, re.MULTILINE))
        h2_count = len(re.findall(r"^## ", combined, re.MULTILINE))
        if h1_count > 0 and h2_count > 0 and h1_count > 1:
            issues.append("Mixed heading levels — some sections use H1, others H2")

        # Check for inconsistent terminology (e.g. both "endpoint" and "route")
        has_endpoint = bool(re.search(r"\bendpoint\b", combined, re.IGNORECASE))
        has_route = bool(re.search(r"\broute\b", combined, re.IGNORECASE))
        if has_endpoint and has_route:
            issues.append(
                "Inconsistent terminology: 'endpoint' and 'route' used interchangeably"
            )

        score = max(0.0, 1.0 - min(len(issues), 5) / 5)
        return {"score": round(score, 2), "issues": issues}

    def _check_clarity(self, docs: Dict[str, str]) -> Dict[str, Any]:
        issues = []
        combined = " ".join(docs.values()).lower()

        for phrase in _VAGUE_PHRASES:
            count = combined.count(phrase)
            if count > 3:
                issues.append(
                    f"Vague phrase '{phrase}' used {count} times — consider specifics"
                )

        # Very short sections indicate thin content
        for name, text in docs.items():
            word_count = len(text.split())
            if text.strip() and word_count < 50:
                issues.append(
                    f"Section '{name}' is very short ({word_count} words) — may lack detail"
                )

        # Check for code examples in examples section
        has_code = "```" in docs.get("examples", "")
        if docs.get("examples") and not has_code:
            issues.append("Examples section has no code blocks")

        score = max(0.0, 1.0 - min(len(issues), 5) / 5)
        return {"score": round(score, 2), "issues": issues}

    @staticmethod
    def _check_coverage(
        docs: Dict[str, str],
        structure: Dict[str, Any],
        api_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        issues = []
        combined = "\n".join(docs.values()).lower()

        classes = structure.get("classes", [])
        documented_classes = sum(
            1 for c in classes if c.get("name", "").lower() in combined
        )
        class_coverage = (
            documented_classes / len(classes) if classes else 1.0
        )
        if class_coverage < 0.5 and classes:
            issues.append(
                f"Only {documented_classes}/{len(classes)} classes mentioned in docs"
            )

        endpoints_found = api_meta.get("endpoints_found", 0)
        if endpoints_found > 0:
            # Check how many endpoint paths appear in docs
            openapi = api_meta.get("openapi_spec", {})
            paths = list((openapi.get("paths") or {}).keys())
            documented_paths = sum(1 for p in paths if p.lower() in combined)
            path_coverage = documented_paths / len(paths) if paths else 1.0
            if path_coverage < 0.5 and paths:
                issues.append(
                    f"Only {documented_paths}/{len(paths)} API paths appear in docs"
                )
        else:
            path_coverage = 1.0

        score = (class_coverage + path_coverage) / 2
        return {
            "score": round(score, 2),
            "class_coverage": round(class_coverage, 2),
            "api_path_coverage": round(path_coverage, 2),
            "issues": issues,
        }

    # ------------------------------------------------------------------
    # Score computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_heuristic_score(
        completeness: Dict[str, Any],
        consistency: Dict[str, Any],
        clarity: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> float:
        raw = (
            completeness["score"] * 0.35
            + consistency["score"] * 0.25
            + clarity["score"] * 0.20
            + coverage["score"] * 0.20
        )
        # Map [0, 1] → [1, 5]
        return round(1.0 + raw * 4.0, 1)

    # ------------------------------------------------------------------
    # LLM validation
    # ------------------------------------------------------------------

    async def _llm_validate(
        self,
        docs: Dict[str, str],
        heuristic_score: float,
    ) -> Dict[str, Any]:
        truncated = {
            k: (v[:800] + "…" if len(v) > 800 else v) for k, v in docs.items()
        }

        prompt = f"""You are a senior technical writer performing a documentation quality review.

Documentation sections to review (truncated for brevity):
{json.dumps(truncated, indent=2)}

Heuristic quality score (1-5): {heuristic_score}

Evaluate the documentation on four dimensions:

1. **Completeness** (1-5): Are all required sections present and sufficiently detailed?
2. **Consistency** (1-5): Is the writing style, terminology, and formatting uniform?
3. **Clarity** (1-5): Is the language clear, specific, and free of vague statements?
4. **Coverage** (1-5): Are all major APIs, classes, and features actually documented?

Then provide:
- **Overall quality score** (1-5, where 1=very poor, 3=acceptable, 5=excellent). Use the heuristic score as a starting point but adjust based on your review.
- **Top 5 improvement suggestions**, each with: category (Completeness/Consistency/Clarity/Coverage), priority (High/Medium/Low), and a concrete, actionable recommendation.
- **2-3 sentence executive summary** of the documentation quality.

Respond ONLY with valid JSON in this exact schema:
{{
  "score": <number 1-5>,
  "dimensions": {{
    "completeness": <1-5>,
    "consistency": <1-5>,
    "clarity": <1-5>,
    "coverage": <1-5>
  }},
  "suggestions": [
    {{"category": "...", "priority": "High|Medium|Low", "suggestion": "..."}}
  ],
  "summary": "..."
}}
"""
        response = await self.llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from the response (handle markdown code fences)
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            raise ValueError("LLM did not return valid JSON")

        parsed = json.loads(json_match.group())

        score = float(parsed.get("score", heuristic_score))
        score = max(1.0, min(5.0, score))

        suggestions = parsed.get("suggestions", [])
        summary = parsed.get("summary", "")

        # Build full prose report
        dims = parsed.get("dimensions", {})
        full_text = self._build_prose_report(score, dims, suggestions, summary)

        return {"score": score, "suggestions": suggestions, "summary": full_text}

    # ------------------------------------------------------------------
    # Prose report builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prose_report(
        score: float,
        dimensions: Dict[str, Any],
        suggestions: List[Dict[str, Any]],
        summary: str,
    ) -> str:
        star_map = {5: "★★★★★", 4: "★★★★☆", 3: "★★★☆☆", 2: "★★☆☆☆", 1: "★☆☆☆☆"}
        stars = star_map.get(round(score), "★★★☆☆")

        lines = [
            "## Documentation Quality Report",
            "",
            f"**Overall Score: {score}/5** {stars}",
            "",
            "### Dimension Scores",
            "",
        ]

        for dim in ("completeness", "consistency", "clarity", "coverage"):
            dim_score = dimensions.get(dim, "N/A")
            dim_stars = star_map.get(round(float(dim_score)) if dim_score != "N/A" else 0, "")
            lines.append(f"- **{dim.capitalize()}**: {dim_score}/5 {dim_stars}")

        lines += ["", "### Executive Summary", "", summary or "N/A", ""]

        if suggestions:
            lines += ["### Improvement Suggestions", ""]
            by_priority = {"High": [], "Medium": [], "Low": []}
            for s in suggestions:
                p = s.get("priority", "Medium")
                by_priority.get(p, by_priority["Medium"]).append(s)

            for priority in ("High", "Medium", "Low"):
                items = by_priority[priority]
                if items:
                    lines.append(f"#### {priority} Priority")
                    for item in items:
                        cat = item.get("category", "General")
                        sug = item.get("suggestion", "")
                        lines.append(f"- **[{cat}]** {sug}")
                    lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Fallbacks
    # ------------------------------------------------------------------

    @staticmethod
    def _build_fallback_suggestions(
        completeness: Dict[str, Any],
        consistency: Dict[str, Any],
        clarity: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        suggestions = []
        for section in completeness.get("missing_sections", []):
            suggestions.append(
                {
                    "category": "Completeness",
                    "priority": "High",
                    "suggestion": f"Add missing '{section}' section to documentation",
                }
            )
        for issue in consistency.get("issues", [])[:2]:
            suggestions.append(
                {"category": "Consistency", "priority": "Medium", "suggestion": issue}
            )
        for issue in clarity.get("issues", [])[:2]:
            suggestions.append(
                {"category": "Clarity", "priority": "Medium", "suggestion": issue}
            )
        for issue in coverage.get("issues", [])[:2]:
            suggestions.append(
                {"category": "Coverage", "priority": "High", "suggestion": issue}
            )
        return suggestions

    def _build_fallback_text(
        self,
        score: float,
        completeness: Dict[str, Any],
        consistency: Dict[str, Any],
        clarity: Dict[str, Any],
        coverage: Dict[str, Any],
    ) -> str:
        suggestions = self._build_fallback_suggestions(
            completeness, consistency, clarity, coverage
        )
        dims = {
            "completeness": round(1 + completeness["score"] * 4),
            "consistency": round(1 + consistency["score"] * 4),
            "clarity": round(1 + clarity["score"] * 4),
            "coverage": round(1 + coverage["score"] * 4),
        }
        return self._build_prose_report(
            score,
            dims,
            suggestions,
            "Quality score computed from heuristic analysis (LLM unavailable).",
        )
