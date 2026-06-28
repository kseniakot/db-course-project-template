"""Routes backed by PostgreSQL relational/full-text queries."""

from typing import Any

from fastapi import APIRouter

from src.api.deps import search_service

router = APIRouter(tags=["postgres"])


@router.get("/search/name")
def search_by_name(name: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search products by name."""
    return search_service.search_by_name(name, limit)


@router.get("/search/tags")
def search_by_tags(tags: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search products by comma-separated tags."""
    return search_service.search_by_tags([t.strip() for t in tags.split(",")], limit)


@router.get("/filter/category")
def filter_by_category(category_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Filter products by category."""
    return search_service.filter_by_category(category_id, limit)


@router.get("/filter/price")
def filter_by_price(min_price: float = 0, max_price: float = 1e9, limit: int = 20) -> list[dict[str, Any]]:
    """Filter products by price range."""
    return search_service.filter_by_price(min_price, max_price, limit)
