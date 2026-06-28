"""Routes backed by pgvector semantic similarity."""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import get_recommendation_service, get_search_service
from src.services.recommendation_service import RecommendationService
from src.services.search_service import SearchService

router = APIRouter(tags=["pgvector"])


@router.get("/search/semantic")
def semantic_search(q: str, limit: int = 10, svc: SearchService = Depends(get_search_service)) -> list[dict[str, Any]]:
    """Semantic vector search."""
    return svc.semantic_search(q, limit)


@router.get("/search/hybrid")
def hybrid_search(q: str, limit: int = 10, svc: SearchService = Depends(get_search_service)) -> list[dict[str, Any]]:
    """Hybrid search combining semantic vectors and full-text (RRF)."""
    return svc.hybrid_search(q, limit)


@router.get("/recommendations/similar/{product_id}")
def similar(
    product_id: str, limit: int = 5, svc: RecommendationService = Depends(get_recommendation_service)
) -> list[dict[str, Any]]:
    """Similar products via vector similarity."""
    return svc.get_similar_products(product_id, limit)
