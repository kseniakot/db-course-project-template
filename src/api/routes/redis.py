"""Routes backed by Redis (cart sessions and cache metrics)."""

from typing import Any

from fastapi import APIRouter, HTTPException

from src.api.deps import cart_service
from src.api.models import CartItem, QuantityUpdate
from src.db.redis_client import redis_client

router = APIRouter(tags=["redis"])


@router.get("/cart/{user_id}")
def get_cart(user_id: str) -> dict[str, Any]:
    """Get a user's cart with item count and total."""
    return {
        "items": cart_service.get_cart(user_id),
        "item_count": cart_service.get_cart_item_count(user_id),
        "total": cart_service.get_cart_total(user_id),
    }


@router.post("/cart/{user_id}/items")
def add_cart_item(user_id: str, item: CartItem) -> dict[str, int]:
    """Add an item to the cart."""
    return {"quantity": cart_service.add_item(user_id, item.product_id, item.quantity)}


@router.put("/cart/{user_id}/items/{product_id}")
def update_cart_item(user_id: str, product_id: str, update: QuantityUpdate) -> dict[str, int]:
    """Set the quantity for a cart item."""
    return {"result": cart_service.update_item_quantity(user_id, product_id, update.quantity)}


@router.delete("/cart/{user_id}/items/{product_id}")
def remove_cart_item(user_id: str, product_id: str) -> dict[str, int]:
    """Remove an item from the cart."""
    return {"removed": cart_service.remove_item(user_id, product_id)}


@router.delete("/cart/{user_id}")
def clear_cart(user_id: str) -> dict[str, int]:
    """Clear the cart."""
    return {"cleared": cart_service.clear_cart(user_id)}


@router.post("/cart/{user_id}/checkout")
def checkout(user_id: str) -> dict[str, Any]:
    """Convert the cart into an order."""
    order = cart_service.convert_cart_to_order(user_id)
    if order is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    return order


@router.get("/metrics/cache")
def cache_metrics() -> dict[str, int]:
    """Cache hit/miss counters."""
    return redis_client.get_cache_metrics()
