"""Pydantic request models for the API."""

from pydantic import BaseModel


class CartItem(BaseModel):
    """Request body for adding a cart item."""

    product_id: str
    quantity: int = 1


class QuantityUpdate(BaseModel):
    """Request body for updating a cart item quantity."""

    quantity: int
