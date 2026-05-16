"""
src/agents/api_documenter_agent.py

Agent 3 — API Documenter
=========================
Responsibilities
----------------
1. Scan the parsed code structure for REST/GraphQL endpoint definitions,
   request/response schemas, error codes, and auth patterns.
2. Feed those signals to the LLM to produce an API Reference section.
3. Generate a minimal OpenAPI-compatible spec dict from the discovered endpoints.
4. Store results in DocState under ``api_documentation_output``.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional

from src.agents.base_agent import BaseAgent
from src.core.state import DocState


# ---------------------------------------------------------------------------
# Heuristic keyword sets
# ---------------------------------------------------------------------------

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}

_ROUTE_DECORATORS = {
    # FastAPI / Flask / Starlette / Sanic / Litestar
    "router.get", "router.post", "router.put", "router.patch", "router.delete",
    "app.get", "app.post", "app.put", "app.patch", "app.delete",
    "app.route", "router.route",
    # Django REST Framework
    "api_view", "action",
    # Express (JS)
    "app.get", "app.post", "router.get", "router.post",
    # GraphQL resolver names
    "query", "mutation", "subscription",
}

_AUTH_PATTERNS = {
    "oauth", "jwt", "bearer", "api_key", "apikey", "auth", "token",
    "depends", "security", "permission", "authenticate", "authorize",
    "credentials", "basic_auth",
}

_ERROR_PATTERNS = {
    "httperror", "httpexception", "raise", "error", "status_code",
    "exception", "abort", "badrequest", "notfound", "unauthorized",
    "forbidden", "unprocessable",
}

_SCHEMA_PATTERNS = {
    "basemodel", "schema", "request", "response", "body", "payload",
    "serializer", "typeddict", "dataclass", "model",
}


class APIDocumenterAgent(BaseAgent):
    """Extract API surface area and generate API Reference + OpenAPI spec."""

    def __init__(self, llm: Any) -> None:
        super().__init__(llm, "api_documenter")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def invoke(self, state: DocState) -> Dict[str, Any]:
        t_start = time.monotonic()

        structure: Dict[str, Any] = state.get("code_structure", {})
        repo_path: str = state.get("repo_path", "")

        api_signals = self._extract_api_signals(structure)
        openapi_spec = self._build_openapi_spec(api_signals, repo_path)

        try:
            content = await self._generate_api_docs(api_signals, openapi_spec)
        except Exception:
            content = self._fallback_summary(api_signals)

        elapsed = time.monotonic() - t_start
        output = self.format_output(
            content=content,
            metadata={
                "repo_path": repo_path,
                "endpoints_found": len(api_signals.get("endpoints", [])),
                "schemas_found": len(api_signals.get("schemas", [])),
                "auth_patterns_found": len(api_signals.get("auth_patterns", [])),
                "error_codes_found": len(api_signals.get("error_patterns", [])),
                "analysis_duration_seconds": round(elapsed, 3),
                "openapi_spec": openapi_spec,
            },
        )
        state["api_documentation_output"] = output
        return output

    # ------------------------------------------------------------------
    # Signal extraction
    # ------------------------------------------------------------------

    def _extract_api_signals(self, structure: Dict[str, Any]) -> Dict[str, Any]:
        functions: List[Dict[str, Any]] = structure.get("functions", [])
        classes: List[Dict[str, Any]] = structure.get("classes", [])
        imports: List[str] = structure.get("imports", [])
        modules: List[str] = structure.get("modules", [])

        endpoints = self._detect_endpoints(functions)
        schemas = self._detect_schemas(classes)
        auth_patterns = self._detect_auth(imports, functions, classes)
        error_patterns = self._detect_error_patterns(functions, classes)
        api_type = self._infer_api_type(imports, modules, functions)

        return {
            "endpoints": endpoints,
            "schemas": schemas,
            "auth_patterns": auth_patterns,
            "error_patterns": error_patterns,
            "api_type": api_type,
        }

    def _detect_endpoints(
        self, functions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        endpoints: List[Dict[str, Any]] = []
        for fn in functions:
            name: str = fn.get("name", "").lower()
            file: str = fn.get("file", "")

            # Heuristic: function name starts with an HTTP method verb
            method_hint: Optional[str] = None
            for method in _HTTP_METHODS:
                if name.startswith(method + "_") or name == method:
                    method_hint = method.upper()
                    break

            # File lives under routes/views/controllers/handlers
            is_route_file = any(
                kw in file.lower()
                for kw in ("route", "view", "controller", "handler", "api", "endpoint")
            )

            if method_hint or is_route_file:
                # Try to infer a path from the function name
                path_guess = self._name_to_path(fn.get("name", ""))
                endpoints.append(
                    {
                        "name": fn.get("name"),
                        "file": file,
                        "line": fn.get("line_start"),
                        "method": method_hint or "GET",
                        "path": path_guess,
                    }
                )
        return endpoints

    @staticmethod
    def _name_to_path(name: str) -> str:
        """Heuristically convert a function name to a URL path."""
        for method in _HTTP_METHODS:
            name = re.sub(rf"^{method}_?", "", name, flags=re.IGNORECASE)
        parts = re.sub(r"([A-Z])", r"_\1", name).lower().strip("_").split("_")
        return "/" + "/".join(p for p in parts if p) if parts else "/"

    def _detect_schemas(
        self, classes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        schemas = []
        for cls in classes:
            name_lower = cls.get("name", "").lower()
            if any(kw in name_lower for kw in _SCHEMA_PATTERNS):
                schemas.append(
                    {
                        "name": cls.get("name"),
                        "file": cls.get("file"),
                        "methods": cls.get("methods", []),
                    }
                )
        return schemas

    @staticmethod
    def _detect_auth(
        imports: List[str],
        functions: List[Dict[str, Any]],
        classes: List[Dict[str, Any]],
    ) -> List[str]:
        found: set[str] = set()
        haystack = (
            " ".join(imports).lower()
            + " ".join(f.get("name", "") for f in functions).lower()
            + " ".join(c.get("name", "") for c in classes).lower()
        )
        for pattern in _AUTH_PATTERNS:
            if pattern in haystack:
                found.add(pattern)
        return sorted(found)

    @staticmethod
    def _detect_error_patterns(
        functions: List[Dict[str, Any]],
        classes: List[Dict[str, Any]],
    ) -> List[str]:
        found: set[str] = set()
        haystack = (
            " ".join(f.get("name", "") for f in functions).lower()
            + " ".join(c.get("name", "") for c in classes).lower()
        )
        for pattern in _ERROR_PATTERNS:
            if pattern in haystack:
                found.add(pattern)
        return sorted(found)

    @staticmethod
    def _infer_api_type(
        imports: List[str],
        modules: List[str],
        functions: List[Dict[str, Any]],
    ) -> str:
        haystack = (
            " ".join(imports).lower()
            + " ".join(modules).lower()
            + " ".join(f.get("name", "") for f in functions).lower()
        )
        if "graphql" in haystack or "ariadne" in haystack or "strawberry" in haystack:
            return "GraphQL"
        if "grpc" in haystack:
            return "gRPC"
        if any(kw in haystack for kw in ("fastapi", "flask", "django", "express", "starlette")):
            return "REST"
        return "REST"

    # ------------------------------------------------------------------
    # OpenAPI spec builder
    # ------------------------------------------------------------------

    def _build_openapi_spec(
        self, signals: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        paths: Dict[str, Any] = {}
        for ep in signals.get("endpoints", [])[:30]:
            path = ep.get("path", "/")
            method = ep.get("method", "GET").lower()
            if path not in paths:
                paths[path] = {}
            paths[path][method] = {
                "summary": ep.get("name", ""),
                "operationId": ep.get("name", ""),
                "responses": {"200": {"description": "Successful response"}},
                "tags": [ep.get("file", "").split("/")[0] or "default"],
            }

        schemas: Dict[str, Any] = {}
        for schema in signals.get("schemas", [])[:20]:
            name = schema.get("name", "")
            if name:
                schemas[name] = {
                    "type": "object",
                    "properties": {
                        m: {"type": "string"}
                        for m in (schema.get("methods") or [])[:10]
                    },
                }

        security_schemes: Dict[str, Any] = {}
        for auth in signals.get("auth_patterns", []):
            if "jwt" in auth or "bearer" in auth or "token" in auth:
                security_schemes["BearerAuth"] = {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            elif "api_key" in auth or "apikey" in auth:
                security_schemes["ApiKeyAuth"] = {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                }
            elif "oauth" in auth:
                security_schemes["OAuth2"] = {
                    "type": "oauth2",
                    "flows": {"authorizationCode": {"scopes": {}}},
                }

        project_name = repo_path.split("/")[-1].split("\\")[-1] if repo_path else "API"
        return {
            "openapi": "3.1.0",
            "info": {
                "title": f"{project_name} API",
                "version": "1.0.0",
                "description": f"Auto-generated OpenAPI spec for {project_name}",
            },
            "paths": paths,
            "components": {
                "schemas": schemas,
                "securitySchemes": security_schemes,
            },
        }

    # ------------------------------------------------------------------
    # LLM synthesis
    # ------------------------------------------------------------------

    async def _generate_api_docs(
        self,
        signals: Dict[str, Any],
        openapi_spec: Dict[str, Any],
    ) -> str:
        truncated_signals = {
            "api_type": signals.get("api_type"),
            "endpoints": signals.get("endpoints", [])[:20],
            "schemas": signals.get("schemas", [])[:15],
            "auth_patterns": signals.get("auth_patterns", []),
            "error_patterns": signals.get("error_patterns", []),
        }

        prompt = f"""You are a technical writer creating an API Reference section for developer documentation.

API signals extracted from the codebase:
{json.dumps(truncated_signals, indent=2)}

Generate a comprehensive **API Reference** section covering:

1. **API Overview** — Type (REST/GraphQL/gRPC), base URL conventions, and overall design style.
2. **Authentication** — Describe the authentication mechanism(s) detected (JWT, API key, OAuth, etc.).
3. **Endpoints / Operations** — For each discovered endpoint, document:
   - HTTP method and path (or GraphQL operation name)
   - Brief description of what it does
   - Expected request body or query parameters (inferred from function/schema names)
   - Response format
4. **Request & Response Schemas** — Describe the key data models (schemas/models/serializers) found.
5. **Error Handling** — Common error codes and patterns used in the codebase.
6. **OpenAPI Specification** — Note that a machine-readable OpenAPI 3.1 spec is available alongside this documentation.

Write in clear, developer-friendly language. Use markdown tables and code snippets where helpful.
"""
        response = await self.llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_summary(signals: Dict[str, Any]) -> str:
        endpoints = signals.get("endpoints", [])
        schemas = signals.get("schemas", [])
        auth = signals.get("auth_patterns", [])
        ep_lines = "\n".join(
            f"  - `{e['method']} {e['path']}` — `{e['name']}` ({e['file']})"
            for e in endpoints[:10]
        ) or "  - None detected"
        return (
            "## API Reference (Auto-generated)\n\n"
            f"**API Type:** {signals.get('api_type', 'REST')}\n\n"
            f"**Endpoints detected:** {len(endpoints)}\n{ep_lines}\n\n"
            f"**Schemas detected:** {len(schemas)}\n"
            f"**Auth patterns:** {', '.join(auth) or 'None detected'}\n\n"
            "*(LLM was unavailable — this is a structural summary only.)*"
        )
