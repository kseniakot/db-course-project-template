"""Routes backed by Redis (cart sessions and cache metrics)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_cart_service
from src.api.models import CartItem, QuantityUpdate
from src.db.redis_client import redis_client
from src.services.cart_service import CartService

router = APIRouter(tags=["redis"])


@router.get("/cart/{user_id}")
def get_cart(user_id: str, svc: CartService = Depends(get_cart_service)) -> dict[str, Any]:
    """Get a user's cart with item count and total."""
    return {
        "items": svc.get_cart(user_id),
        "item_count": svc.get_cart_item_count(user_id),
        "total": svc.get_cart_total(user_id),
    }


@router.post("/cart/{user_id}/items")
def add_cart_item(user_id: str, item: CartItem, svc: CartService = Depends(get_cart_service)) -> dict[str, int]:
    """Add an item to the cart."""
    return {"quantity": svc.add_item(user_id, item.product_id, item.quantity)}


@router.put("/cart/{user_id}/items/{product_id}")
def update_cart_item(
    user_id: str, product_id: str, update: QuantityUpdate, svc: CartService = Depends(get_cart_service)
) -> dict[str, int]:
    """Set the quantity for a cart item."""
    return {"result": svc.update_item_quantity(user_id, product_id, update.quantity)}


@router.delete("/cart/{user_id}/items/{product_id}")
def remove_cart_item(user_id: str, product_id: str, svc: CartService = Depends(get_cart_service)) -> dict[str, int]:
    """Remove an item from the cart."""
    return {"removed": svc.remove_item(user_id, product_id)}


@router.delete("/cart/{user_id}")
def clear_cart(user_id: str, svc: CartService = Depends(get_cart_service)) -> dict[str, int]:
    """Clear the cart."""
    return {"cleared": svc.clear_cart(user_id)}


@router.post("/cart/{user_id}/checkout")
def checkout(user_id: str, svc: CartService = Depends(get_cart_service)) -> dict[str, Any]:
    """Convert the cart into an order."""
    order = svc.convert_cart_to_order(user_id)
    if order is None:
        raise HTTPException(status_code=400, detail="Cart is empty")
    return order


@router.get("/metrics/cache")
def cache_metrics() -> dict[str, int]:
    """Cache hit/miss counters."""
    return redis_client.get_cache_metrics()
