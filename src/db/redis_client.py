"""Redis connection and utilities."""

import json
from typing import Any, Dict, List, Optional, Tuple

import redis

from src.config import (
    CACHE_TTL,
    CART_TTL,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    RECOMMENDATIONS_TTL,
    REDIS_CONFIG,
    HOT_PRODUCTS_TTL, 
    CACHE_METRICS_TTL
)

CART_PREFIX = "cart"
RATE_LIMIT_PREFIX = "rate_limit"
PRODUCT_PREFIX = "product"
RECOMMENDATIONS_PREFIX = "recommendations"
VIEWED_PREFIX = "viewed"


class RedisClient:
    def __init__(self) -> None:
        pool: redis.ConnectionPool = redis.ConnectionPool(max_connections=50, **REDIS_CONFIG)
        self.client: redis.Redis[str] = redis.Redis(connection_pool=pool)

    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON data from Redis.

        Args:
            key: Redis key to retrieve

        Returns:
            Parsed JSON data or None if key doesn't exist
        """
        data: Optional[bytes] = self.client.get(key)
        return json.loads(data) if data else None

    def set_json(self, key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
        """Set JSON data in Redis with TTL.

        Args:
            key: Redis key to set
            value: Data to store (will be JSON encoded)
            ttl: Time to live in seconds (default: 1 hour)

        Returns:
            True if successful
        """
        result: bool = self.client.setex(key, ttl, json.dumps(value))
        return result

    def get_cart_key(self, user_id: str) -> str:
        """Generate the Redis key for a user's cart.

        Args:
            user_id: User identifier

        Returns:
            Formatted cart key
        """
        return f"{CART_PREFIX}:{user_id}"

    def add_to_cart(self, user_id: str, product_id: str, quantity: int) -> int:
        """Add item to user's cart (increments quantity if exists).

        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: Quantity to add

        Returns:
            New quantity value for the product
        """
        cart_key: str = self.get_cart_key(user_id)
        result: int = self.client.hincrby(cart_key, product_id, quantity)
        self.client.expire(cart_key, CART_TTL)
        return result

    def add_to_hot_products(self, product_id: str, date_key: str) -> float:
        """Increment product score in hot products list.

        Args:
            product_id: Product identifier
            date_key: Date key for organizing hot products

        Returns:
            New score value
        """
        key = f"hot_products:{date_key}"
        result = self.client.zincrby(key, 1, product_id)
        self.client.expire(key, HOT_PRODUCTS_TTL)
        return result

    def get_hot_products(self, date_key: str, limit: int = 10,) -> List[Tuple[str, float]]:
        """Get top products by purchase count.

        Args:
            date_key: Date key for organizing hot products
            limit: Number of products to return

        Returns:
            List of tuples (product_id, score)
        """
        key = f"hot_products:{date_key}"
        results = self.client.zrange(key, 0, -1, desc=True,  withscores=True)
       
        return results[-limit:]

    def update_cart_item_quantity(self, user_id: str, product_id: str, quantity: int) -> int:
        """Set a specific quantity for a product in the cart.

        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: New quantity value

        Returns:
            1 if new field was added, 0 if existing field was updated
        """
        cart_key: str = self.get_cart_key(user_id)
        result: int = self.client.hset(cart_key, product_id, str(quantity))
        self.client.expire(cart_key, CART_TTL)
        return result

    def remove_from_cart(self, user_id: str, product_id: str, quantity: int = None) -> int:
        """Remove a product from the user's cart.

        Args:
            user_id: User identifier
            product_id: Product identifier
            quantity: Unused parameter (kept for API compatibility)

        Returns:
            1 if field was deleted, 0 if field didn't exist
        """
        cart_key: str = self.get_cart_key(user_id)
        result: int = self.client.hdel(cart_key, product_id)
        self.client.expire(cart_key, CART_TTL)
        return result

    def get_cart(self, user_id: str) -> Dict[str, int]:
        """Retrieve user's shopping cart.

        Args:
            user_id: User identifier

        Returns:
            Dictionary mapping product_id to quantity
        """
        cart_key: str = self.get_cart_key(user_id)
        cart_data: Dict[str, bytes] = self.client.hgetall(cart_key)
        return {product.decode(): int(qty) for product, qty in cart_data.items()}

    def clear_cart(self, user_id: str) -> int:
        """Clear all items from a user's cart.

        Args:
            user_id: User identifier

        Returns:
            1 if key was deleted, 0 if key didn't exist
        """
        cart_key: str = self.get_cart_key(user_id)
        result: int = self.client.delete(cart_key)
        return result

    def rate_limit_check(self, user_id: str, endpoint: str) -> bool:
        """Check if user has exceeded rate limit.

        Args:
            user_id: User identifier
            endpoint: API endpoint name

        Returns:
            True if under limit, False if exceeded
        """
        rate_limit_id: str = f"{RATE_LIMIT_PREFIX}:{user_id}:{endpoint}"
        count: int = self.client.incr(rate_limit_id)

        if count == 1:
            self.client.expire(rate_limit_id, RATE_LIMIT_WINDOW)

        return count <= RATE_LIMIT_REQUESTS

    def increment_cache_metric(self, metric_name: str, ttl: int = CACHE_METRICS_TTL) -> int:
        """Increment a cache metric counter.

        Args:
            metric_name: Name of the metric (e.g., 'search_hits')

        Returns:
            New metric value
        """
        key = f"cache_metrics:{metric_name}"
        result: int = self.client.incr(key)
        self.client.expire(key, ttl, nx=True)
        return result

    def get_cache_metrics(self) -> Dict[str, int]:
        """Get all cache metrics like hits and misses by scanning keys.

        Returns:
            Dictionary mapping metric names to their values
        """
        metrics: Dict[str, int] = {}
        for key in self.client.scan_iter("cache_metrics:*"):
            metric_name: str = key.split(":", 1)[1]
            value: Optional[bytes] = self.client.get(key)
            metrics[metric_name] = int(value) if value else 0
        return metrics


redis_client: RedisClient = RedisClient()
        



# Singleton instance
redis_client = RedisClient()
