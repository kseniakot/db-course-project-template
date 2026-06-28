"""Routes backed by Neo4j graph recommendations."""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import get_recommendation_service
from src.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["neo4j"])


@router.get("/collaborative/{user_id}")
def collaborative(
    user_id: str, limit: int = 5, svc: RecommendationService = Depends(get_recommendation_service)
) -> list[dict[str, Any]]:
    """Collaborative-filtering recommendations."""
    return svc.get_collaborative_filtering(user_id, limit)


@router.get("/also-bought/{product_id}")
def also_bought(
    product_id: str, limit: int = 5, svc: RecommendationService = Depends(get_recommendation_service)
) -> list[dict[str, Any]]:
    """'Customers also bought' recommendations."""
    return svc.get_also_bought(product_id, limit)


@router.get("/frequently-together")
def frequently_together(
    limit: int = 10, svc: RecommendationService = Depends(get_recommendation_service)
) -> list[dict[str, Any]]:
    """Products frequently bought together."""
    return svc.get_frequently_bought_together(limit)


@router.get("/seller/{user_id}")
def seller_products(
    user_id: str, limit: int = 5, svc: RecommendationService = Depends(get_recommendation_service)
) -> list[dict[str, Any]]:
    """Other products from sellers the user has purchased from."""
    return svc.get_seller_products(user_id, limit)


@router.get("/personalized/{user_id}")
def personalized(
    user_id: str, limit: int = 10, svc: RecommendationService = Depends(get_recommendation_service)
) -> list[dict[str, Any]]:
    """Personalized recommendations via Sampled MMR."""
    return svc.get_personalized_recommendations(user_id, limit)
