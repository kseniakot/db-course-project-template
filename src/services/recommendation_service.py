"""Service for product recommendations."""

import math
import random
from typing import Any, Dict, List

from src.db.neo4j_client import neo4j_client
from src.db.postgres_client import db as postgres_db
from src.db.redis_client import redis_client


class RecommendationService:
    """Generate personalized product recommendations using multiple strategies."""

    COLLAB_FILTERING_PREFIX = "recommend:collab"
    ALSO_BOUGHT_PREFIX = "recommend:also_bought"
    FREQUENTLY_TOGETHER_PREFIX = "recommend:together"
    SIMILAR_PRODUCTS_PREFIX = "recommend:similar"
    SELLER_PRODUCTS_PREFIX = "recommend:seller"
    PERSONALIZED_PREFIX = "recommend:personalized"

    def _get_collab_filtering_key(self, user_id: str, limit: int) -> str:
        """Generate cache key for collaborative filtering."""
        return f"{self.COLLAB_FILTERING_PREFIX}:{user_id}:{limit}"

    def _get_also_bought_key(self, product_id: str, limit: int) -> str:
        """Generate cache key for also bought recommendations."""
        return f"{self.ALSO_BOUGHT_PREFIX}:{product_id}:{limit}"

    def _get_frequently_together_key(self, limit: int) -> str:
        """Generate cache key for frequently bought together."""
        return f"{self.FREQUENTLY_TOGETHER_PREFIX}:{limit}"

    def _get_similar_products_key(self, product_id: str, limit: int) -> str:
        """Generate cache key for similar products."""
        return f"{self.SIMILAR_PRODUCTS_PREFIX}:{product_id}:{limit}"

    def _get_seller_products_key(self, user_id: str, limit: int) -> str:
        """Generate cache key for seller products."""
        return f"{self.SELLER_PRODUCTS_PREFIX}:{user_id}:{limit}"

    def _get_personalized_key(self, user_id: str, limit: int) -> str:
        """Generate cache key for personalized recommendations."""
        return f"{self.PERSONALIZED_PREFIX}:{user_id}:{limit}"

    def get_collaborative_filtering(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recommendations using collaborative filtering (users who bought also bought).

        Args:
            user_id: User identifier
            limit: Maximum number of recommendations (default: 5)

        Returns:
            List of recommended products
        """
        cache_key: str = self._get_collab_filtering_key(user_id, limit)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.COLLAB_FILTERING_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.COLLAB_FILTERING_PREFIX}:miss")
        result: List[Dict[str, Any]] = neo4j_client.get_recommendations(user_id, limit)
        redis_client.set_json(cache_key, result)
        return result

    def get_also_bought(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get products frequently bought with a specific product.

        Args:
            product_id: Product identifier
            limit: Maximum number of recommendations (default: 5)

        Returns:
            List of frequently bought products
        """
        cache_key: str = self._get_also_bought_key(product_id, limit)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.ALSO_BOUGHT_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.ALSO_BOUGHT_PREFIX}:miss")
        result: List[Dict[str, Any]] = neo4j_client.get_also_bought_products(product_id, limit)
        redis_client.set_json(cache_key, result)
        return result

    def get_frequently_bought_together(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get product pairs frequently bought together.

        Args:
            limit: Maximum number of pairs (default: 10)

        Returns:
            List of frequently bought product pairs
        """
        cache_key: str = self._get_frequently_together_key(limit)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.FREQUENTLY_TOGETHER_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.FREQUENTLY_TOGETHER_PREFIX}:miss")
        result: List[Dict[str, Any]] = neo4j_client.get_products_frequently_bought_together(limit)
        redis_client.set_json(cache_key, result)
        return result

    def get_similar_products(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get products similar to a specific product using vector similarity.

        Args:
            product_id: Product identifier
            limit: Maximum number of recommendations (default: 5)

        Returns:
            List of similar products
        """
        cache_key: str = self._get_similar_products_key(product_id, limit)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.SIMILAR_PRODUCTS_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.SIMILAR_PRODUCTS_PREFIX}:miss")
        result: List[Dict[str, Any]] = postgres_db.find_similar_products(product_id, limit)
        redis_client.set_json(cache_key, result)
        return result

    def get_seller_products(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get other products from same seller as user's purchased products.

        Args:
            user_id: User identifier
            limit: Maximum number of recommendations (default: 5)

        Returns:
            List of products from same seller
        """
        cache_key: str = self._get_seller_products_key(user_id, limit)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.SELLER_PRODUCTS_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.SELLER_PRODUCTS_PREFIX}:miss")
        result: List[Dict[str, Any]] = neo4j_client.get_other_products_from_same_seller(user_id, limit)
        redis_client.set_json(cache_key, result)
        return result

    def _calculate_similarity(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> float:
        """Calculate similarity between two items using seller and category.

        Formula: similarity = same_seller * 0.6 + same_category * 0.4

        Args:
            item1: First product
            item2: Second product

        Returns:
            Similarity score (0-1)
        """
        same_seller: float = 1.0 if item1.get("seller_id") == item2.get("seller_id") else 0.0
        same_category: float = 1.0 if item1.get("category_id") == item2.get("category_id") else 0.0

        similarity: float = same_seller * 0.6 + same_category * 0.4
        return similarity

    def _compute_mmr_score(
        self,
        candidate: Dict[str, Any],
        selected: List[Dict[str, Any]],
        lambda_param: float = 0.6,
    ) -> float:
        """Compute MMR (Maximum Marginal Relevance) score for a candidate.

        Formula: S_i = λ * Rel(i) - (1 - λ) * max_similarity(i, j in selected)

        Args:
            candidate: Candidate item to score
            selected: Already selected items
            lambda_param: Balance between relevance (λ) and diversity (1-λ)

        Returns:
            MMR score
        """
        relevance: float = candidate.get("score", 0.5)

        if not selected:
            return relevance

        max_similarity: float = max(
            self._calculate_similarity(candidate, item) for item in selected
        )

        mmr_score: float = lambda_param * relevance - (1 - lambda_param) * max_similarity
        return mmr_score

    def _sampled_mmr_select_batch(
        self,
        candidates: List[Dict[str, Any]],
        selected: List[Dict[str, Any]],
        batch_size: int,
        lambda_param: float = 0.6,
        temperature: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Select a batch of items using Sampled MMR with softmax.

        MMR scores are computed once against the frozen `selected` set, then the
        whole batch is sampled without replacement using those scores. Items
        within the same batch are not compared with each other, which is what
        gives exponential batching its logarithmic complexity.

        Args:
            candidates: Pool of candidates
            selected: Already selected items (frozen for this batch)
            batch_size: Number of items to draw in this batch
            lambda_param: Balance between relevance and diversity
            temperature: Softmax temperature (lower = more deterministic)

        Returns:
            List of selected items (up to batch_size)
        """
        if not candidates:
            return []

        scores: List[float] = [
            self._compute_mmr_score(c, selected, lambda_param) for c in candidates
        ]
        max_score: float = max(scores)

        pool_items: List[Dict[str, Any]] = list(candidates)
        pool_weights: List[float] = [
            math.exp(min((score - max_score) / temperature, 100)) for score in scores
        ]

        draw_count: int = min(batch_size, len(pool_items))
        batch: List[Dict[str, Any]] = []

        for _ in range(draw_count):
            idx: int = random.choices(range(len(pool_items)), weights=pool_weights, k=1)[0]
            batch.append(pool_items.pop(idx))
            pool_weights.pop(idx)

        return batch

    def get_personalized_recommendations(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get personalized recommendations using Sampled MMR with exponential batching.

        Uses Maximum Marginal Relevance with probabilistic sampling to balance
        relevance and diversity, preventing popularity bias. Exponential batching
        (1, 2, 4, 8...) reduces complexity from O(N²) to O(N log N).

        Args:
            user_id: User identifier
            limit: Maximum number of recommendations (default: 10)

        Returns:
            List of personalized product recommendations
        """
        cache_key: str = self._get_personalized_key(user_id, limit)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.PERSONALIZED_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.PERSONALIZED_PREFIX}:miss")

        collab_recs: List[Dict[str, Any]] = self.get_collaborative_filtering(user_id, limit * 2)
        seller_recs: List[Dict[str, Any]] = self.get_seller_products(user_id, limit * 2)

        all_candidates: Dict[str, Dict[str, Any]] = {}
        for idx, rec in enumerate(collab_recs):
            rec_id: str = rec.get("product_id", "")
            all_candidates[rec_id] = {
                **rec,
                "score": 1.0 / (idx + 1),
                "product_name": rec.get("product_name", rec.get("name", "")),
            }

        for idx, rec in enumerate(seller_recs):
            rec_id: str = rec.get("product_id", "")
            if rec_id in all_candidates:
                all_candidates[rec_id]["score"] += 0.5 / (idx + 1)
            else:
                all_candidates[rec_id] = {
                    **rec,
                    "score": 0.5 / (idx + 1),
                    "product_name": rec.get("product_name", rec.get("name", "")),
                }

        candidates: List[Dict[str, Any]] = list(all_candidates.values())
        selected: List[Dict[str, Any]] = []
        batch_size: int = 1

        while len(selected) < limit and candidates:
            take: int = min(batch_size, limit - len(selected))
            batch: List[Dict[str, Any]] = self._sampled_mmr_select_batch(
                candidates,
                selected,
                take,
                lambda_param=0.6,
                temperature=1.0,
            )

            if not batch:
                break

            for item in batch:
                selected.append(item)
                candidates.remove(item)

            batch_size *= 2

        redis_client.set_json(cache_key, selected)
        return selected
