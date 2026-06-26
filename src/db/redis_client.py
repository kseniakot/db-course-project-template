"""Redis connection and utilities."""

import redis
import json
from typing import Optional, Any
from src.config import REDIS_CONFIG, CACHE_TTL, CART_TTL, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW, RECOMMENDATIONS_TTL

CART_PREFIX = "cart"
RATE_LIMIT_PREFIX = "rate_limit"
PRODUCT_PREFIX = "product"
RECOMMENDATIONS_PREFIX = "recommendations"
VIEWED_PREFIX = "viewed"


class RedisClient:
    def __init__(self):
        self.client = redis.Redis(**REDIS_CONFIG)

    def get_json(self, key: str) -> Optional[Any]:
        """Get JSON data from Redis."""
        data = self.client.get(key)
        return json.loads(data) if data else None

    def set_json(self, key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
        """Set JSON data in Redis with TTL."""
        return self.client.setex(key, ttl, json.dumps(value))
    
    def get_cart_key(self, user_id: str) -> str:
        """Generate the Redis key for a user's cart."""
        return f"{CART_PREFIX}:{user_id}"

    def add_to_cart(self, user_id: str, product_id: str, quantity: int):
        """Add item to user's cart."""
        cart_key = self.get_cart_key(user_id)
        self.client.hincrby(cart_key, product_id, quantity)
        self.client.expire(cart_key, CART_TTL)

    def update_cart_item_quantity(self, user_id: str, product_id: str, quantity: int):
        """Set a specific quantity for a product in the cart."""
        cart_key = self.get_cart_key(user_id)
        self.client.hset(cart_key, product_id, str(quantity))
        self.client.expire(cart_key, CART_TTL)

    def remove_from_cart(self, user_id: str, product_id: str, quantity: int):
        """Remove a product from the user's cart."""
        cart_key = self.get_cart_key(user_id)
        self.client.hdel(cart_key, product_id)
        self.client.expire(cart_key, CART_TTL)

    def get_cart(self, user_id: str) -> dict[str, int]:
      """Retrieve user's shopping cart."""
      cart_key = self.get_cart_key(user_id)
      cart_data = self.client.hgetall(cart_key)
      return {product: int(qty) for product, qty in cart_data.items()}
    
    def clear_cart(self, user_id: str):
        """Clear all items from a user's cart."""
        cart_key = self.get_cart_key(user_id)
        self.client.delete(cart_key)

    def rate_limit_check(self, user_id: str, endpoint: str) -> bool:
        """Check if user has exceeded rate limit."""
        rate_limit_id = f"{RATE_LIMIT_PREFIX}:{user_id}:{endpoint}"
        count = self.client.incr(rate_limit_id)

        if count == 1:
            self.client.expire(rate_limit_id, RATE_LIMIT_WINDOW)

        return count <= RATE_LIMIT_REQUESTS
    
    def cache_product_view(self, product_id: str, product_data: dict, ttl: int = CACHE_TTL):
        """Cache full product info with TTL."""
        key = f"{PRODUCT_PREFIX}:{product_id}"
        self.set_json(key, product_data, ttl)

    def get_cached_product(self, product_id: str):
        """Get cached product or None."""
        key = f"{PRODUCT_PREFIX}:{product_id}"
        return self.get_json(key)
    
    def cache_recommendations(self, user_id: str, recommendations: list, ttl: int = RECOMMENDATIONS_TTL):
        """Cache recommendations with full product details."""
        key = f"{RECOMMENDATIONS_PREFIX}:{user_id}"
        self.set_json(key, recommendations, ttl)

    def get_recommendations(self, user_id: str):
        """Get cached recommendations ready to show."""
        key = f"{RECOMMENDATIONS_PREFIX}:{user_id}"
        return self.get_json(key)
    
    def increment_cache_metric(self, metric_name: str):
        """Increment a cache metric"""
        self.client.incr(f"cache_metrics:{metric_name}")

    def get_cache_metrics(self) -> dict[str, int]:
        """Get all cache metrics like hits and misses by scanning keys."""
        metrics = {}
        for key in self.client.scan_iter("cache_metrics:*"):
            metric_name = key.split(":", 1)[1]
            value = self.client.get(key)
            metrics[metric_name] = int(value) if value else 0
        return metrics
        



# Singleton instance
redis_client = RedisClient()
