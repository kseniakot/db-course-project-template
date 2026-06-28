"""FastAPI dependency providers.

Services are created once in the app lifespan and stored on app.state; these
helpers expose them to route handlers via Depends.
"""

from fastapi import Request

from src.services.cart_service import CartService
from src.services.recommendation_service import RecommendationService
from src.services.search_service import SearchService


def get_search_service(request: Request) -> SearchService:
    """Return the shared SearchService from app state."""
    return request.app.state.search_service


def get_cart_service(request: Request) -> CartService:
    """Return the shared CartService from app state."""
    return request.app.state.cart_service


def get_recommendation_service(request: Request) -> RecommendationService:
    """Return the shared RecommendationService from app state."""
    return request.app.state.recommendation_service
