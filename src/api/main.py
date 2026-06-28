"""FastAPI application entry point for ArtisanMarket."""


from fastapi import FastAPI

from src.api.routes import routers
from src.logging_config import setup_logging

setup_logging()

app = FastAPI(title="ArtisanMarket API", version="1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


for router in routers:
    app.include_router(router)
