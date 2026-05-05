import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.ingest import router as ingest_router  # noqa: E402
from src.api.routes.analyze import router as analyze_router  # noqa: E402

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest_router, prefix="/api/v1")
app.include_router(analyze_router, prefix="/api/v1")

@app.get("/health", tags=["Health"], summary="Health check")
async def health_check() -> dict:
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "version": app.version}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
