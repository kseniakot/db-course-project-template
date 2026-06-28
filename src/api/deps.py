"""Shared service singletons for the API.

Instantiated once so the heavy SearchService embedding model loads a single time
and is reused across all route modules.
"""

from src.services.cart_service import CartService
from src.services.recommendation_service import RecommendationService
from src.services.search_service import SearchService

search_service = SearchService()
cart_service = CartService()
recommendation_service = RecommendationService()
