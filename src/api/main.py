"""FastAPI application entry point for ArtisanMarket."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import routers
from src.db.neo4j_client import neo4j_client
from src.logging_config import get_logger, setup_logging
from src.services.cart_service import CartService
from src.services.recommendation_service import RecommendationService
from src.services.search_service import SearchService

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared services on startup and release resources on shutdown."""
    logger.info("Startup: initializing services")
    app.state.search_service = SearchService()
    app.state.cart_service = CartService()
    app.state.recommendation_service = RecommendationService()
    yield
    logger.info("Shutdown: closing Neo4j driver")
    neo4j_client.close()


app = FastAPI(title="ArtisanMarket API", version="1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}


for router in routers:
    app.include_router(router)
