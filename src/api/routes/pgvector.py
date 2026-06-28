"""Routes backed by pgvector semantic similarity."""

from typing import Any

from fastapi import APIRouter

from src.api.deps import recommendation_service, search_service

router = APIRouter(tags=["pgvector"])


@router.get("/search/semantic")
def semantic_search(q: str, limit: int = 10) -> list[dict[str, Any]]:
    """Semantic vector search."""
    return search_service.semantic_search(q, limit)


@router.get("/search/hybrid")
def hybrid_search(q: str, limit: int = 10) -> list[dict[str, Any]]:
    """Hybrid search combining semantic vectors and full-text (RRF)."""
    return search_service.hybrid_search(q, limit)


@router.get("/recommendations/similar/{product_id}")
def similar(product_id: str, limit: int = 5) -> list[dict[str, Any]]:
    """Similar products via vector similarity."""
    return recommendation_service.get_similar_products(product_id, limit)
