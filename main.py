import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.generate_docs import router as generate_docs_router

app = FastAPI(
    title="AI-Powered Code-to-Document Generator",
    description=(
        "Generates a full academic-style PDF project report from any GitHub repository.\n\n"
        "**Single endpoint pipeline**\n\n"
        "`POST /api/v1/generate_docs` — Accepts `github_url` and optional `branch`, "
        "clones the repository, runs the multi-agent analysis pipeline "
        "(Code Analyzer → Architecture Detective → API Documenter → "
        "Documentation Generator), and returns a downloadable PDF report.\n\n"
        "**Report sections generated**\n"
        "1. Abstract\n"
        "2. Introduction\n"
        "3. Objectives\n"
        "4. Overview of the System\n"
        "5. System Analysis (5.1 Existing System · 5.2 Proposed System)\n"
        "6. Literature Survey\n"
        "8. System Requirements (8.1 Hardware · 8.2 Software)\n"
        "9. System Implementation (9.1 Technology · 9.2 Modules)\n"
        "10. SDLC Methodology\n"
        "11. System Design\n"
        "12. Coding\n"
        "13. Testing\n"
        "14. Output Screens\n"
        "15. Conclusion\n"
        "16. References\n\n"
        "Each section is produced by a dedicated LLM call for maximum quality."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_docs_router, prefix="/api/v1")


@app.get("/health", tags=["Health"], summary="Health check")
async def health_check() -> dict:
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": app.version}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
