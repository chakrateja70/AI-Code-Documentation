"""
main.py — FastAPI application entry-point.

Run locally with:
    uvicorn main:app --reload

Swagger UI:  http://127.0.0.1:8000/docs
ReDoc:       http://127.0.0.1:8000/redoc
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI-Powered Code-to-Document Generator",
    description=(
        "An intelligent pipeline that takes a GitHub repository URL and "
        "produces rich, structured documentation by parsing source code, "
        "building call/dependency graphs, and leveraging LLMs."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow all origins during development — tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Register routers
# ---------------------------------------------------------------------------

from src.api.routes.ingest import router as ingest_router  # noqa: E402

app.include_router(ingest_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Health-check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"], summary="Health check")
async def health_check() -> dict:
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": app.version}


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
