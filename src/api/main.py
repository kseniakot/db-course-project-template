"""FastAPI application entry point for ArtisanMarket."""

from typing import Dict

from fastapi import FastAPI

from src.api.routes import routers

app = FastAPI(title="ArtisanMarket API", version="1.0")


@app.get("/health")
def health() -> Dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


for router in routers:
    app.include_router(router)
