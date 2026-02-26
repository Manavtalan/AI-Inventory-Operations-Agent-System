"""
AI Inventory & Operations Intelligence System — FastAPI Application Entry Point

This is the minimal scaffold created during Phase 0, Step 0.2 (Docker Environment Setup).
It provides the /health endpoint required for Docker health checks to pass.

Full application setup (structured logging, middleware, routers, startup validation)
happens in Phase 0, Step 0.3 — Core Application Setup.
"""

from fastapi import FastAPI

app = FastAPI(
    title="AI Inventory & Operations Intelligence System",
    description="Automated inventory reconciliation and reporting for D2C brands.",
    version="0.1.0",
)


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Health check endpoint — used by Docker, load balancers, and deployment platforms."""
    return {"status": "ok"}
