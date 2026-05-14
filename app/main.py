"""
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes.webhook import router as webhook_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# ---------- App ----------

app = FastAPI(
    title="Nistula Guest Message Handler",
    description=(
        "Backend system that receives guest messages from multiple channels, "
        "normalises them, drafts AI replies via Claude, and returns responses "
        "with confidence scores."
    ),
    version="1.0.0",
)

# Include routers
app.include_router(webhook_router)


# ---------- Health Check ----------

@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "nistula-message-handler"}


# ---------- Global Exception Handlers ----------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled exceptions."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
        },
    )
