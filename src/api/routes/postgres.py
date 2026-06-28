"""Routes backed by PostgreSQL relational/full-text queries."""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import get_search_service
from src.services.search_service import SearchService

router = APIRouter(tags=["postgres"])


@router.get("/search/name")
def search_by_name(
    name: str, limit: int = 10, svc: SearchService = Depends(get_search_service)
) -> list[dict[str, Any]]:
    """Search products by name."""
    return svc.search_by_name(name, limit)


@router.get("/search/tags")
def search_by_tags(
    tags: str, limit: int = 10, svc: SearchService = Depends(get_search_service)
) -> list[dict[str, Any]]:
    """Search products by comma-separated tags."""
    return svc.search_by_tags([t.strip() for t in tags.split(",")], limit)


@router.get("/filter/category")
def filter_by_category(
    category_id: str, limit: int = 20, svc: SearchService = Depends(get_search_service)
) -> list[dict[str, Any]]:
    """Filter products by category."""
    return svc.filter_by_category(category_id, limit)


@router.get("/filter/price")
def filter_by_price(
    min_price: float = 0,
    max_price: float = 1e9,
    limit: int = 20,
    svc: SearchService = Depends(get_search_service),
) -> list[dict[str, Any]]:
    """Filter products by price range."""
    return svc.filter_by_price(min_price, max_price, limit)
