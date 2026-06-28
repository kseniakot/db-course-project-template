"""Service for managing shopping carts."""

from typing import Any, Dict, List

from src.db.postgres_client import db as postgres_db
from src.db.redis_client import redis_client
from src.logging_config import get_logger

logger = get_logger(__name__)


class CartService:
    """Manage user shopping carts using Redis session storage."""

    CART_PREFIX = "cart"

    def _get_cart_key(self, user_id: str) -> str:
        """Generate cache key for user cart."""
        return redis_client.get_cart_key(user_id)

    def add_item(self, user_id: str, product_id: str, quantity: int = 1) -> int:
        """Add item to user's cart or increment quantity if exists.

        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: Quantity to add (default: 1)

        Returns:
            New quantity value for the product
        """
        logger.info("Cart add user=%s product=%s qty=%d", user_id, product_id, quantity)
        return redis_client.add_to_cart(user_id, product_id, quantity)

    def remove_item(self, user_id: str, product_id: str) -> int:
        """Remove product from user's cart.

        Args:
            user_id: User identifier
            product_id: Product identifier

        Returns:
            1 if item was deleted, 0 if it didn't exist
        """
        return redis_client.remove_from_cart(user_id, product_id)

    def update_item_quantity(self, user_id: str, product_id: str, quantity: int) -> int:
        """Update quantity for a product in cart.

        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: New quantity value

        Returns:
            1 if new item was added, 0 if existing item was updated
        """
        if quantity <= 0:
            return self.remove_item(user_id, product_id)
        return redis_client.update_cart_item_quantity(user_id, product_id, quantity)

    def get_cart(self, user_id: str) -> Dict[str, int]:
        """Retrieve user's shopping cart.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping product_id to quantity
        """
        return redis_client.get_cart(user_id)

    def clear_cart(self, user_id: str) -> int:
        """Clear all items from user's cart.

        Args:
            user_id: User identifier

        Returns:
            1 if cart was deleted, 0 if cart didn't exist
        """
        return redis_client.clear_cart(user_id)

    def get_cart_total(self, user_id: str) -> float:
        """Calculate total price for items in cart.

        Args:
            user_id: User identifier

        Returns:
            Total price of all items in cart
        """
        cart: Dict[str, int] = self.get_cart(user_id)
        if not cart:
            return 0.0

        total: float = 0.0

        for product_id, quantity in cart.items():
            product: Dict[str, Any] | None = postgres_db.get_product_by_id(product_id)
            if product:
                total += product.get("price", 0) * quantity

        return total

    def convert_cart_to_order(self, user_id: str) -> Dict[str, Any] | None:
        """Convert cart to order and clear cart.

        Args:
            user_id: User identifier

        Returns:
            Order data with items and total, or None if cart is empty
        """
        cart: Dict[str, int] = self.get_cart(user_id)
        if not cart:
            logger.info("Checkout attempted on empty cart user=%s", user_id)
            return None

        order_items: List[Dict[str, Any]] = []
        total_price: float = 0.0

        for product_id, quantity in cart.items():
            product_data: Dict[str, Any] | None = postgres_db.get_product_by_id(product_id)
            if product_data:
                price: float = product_data.get("price", 0)
                order_items.append({
                    "product_id": product_id,
                    "name": product_data.get("name", ""),
                    "price": price,
                    "quantity": quantity,
                    "subtotal": price * quantity,
                })
                total_price += price * quantity

        order: Dict[str, Any] = {
            "user_id": user_id,
            "items": order_items,
            "total_price": total_price,
            "item_count": len(order_items),
            "status": "pending",
        }

        self.clear_cart(user_id)
        logger.info(
            "Checkout user=%s: %d items, total=%.2f",
            user_id, len(order_items), total_price,
        )
        return order

    def get_cart_item_count(self, user_id: str) -> int:
        """Get total number of items in cart.

        Args:
            user_id: User identifier

        Returns:
            Total quantity of items in cart
        """
        cart: Dict[str, int] = self.get_cart(user_id)
        return sum(cart.values()) if cart else 0

    def has_product_in_cart(self, user_id: str, product_id: str) -> bool:
        """Check if product is in user's cart.

        Args:
            user_id: User identifier
            product_id: Product identifier

        Returns:
            True if product is in cart, False otherwise
        """
        cart: Dict[str, int] = self.get_cart(user_id)
        return product_id in cart
