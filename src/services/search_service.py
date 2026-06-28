"""Search service for products with multiple search strategies."""

from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer

from src.db.postgres_client import db as postgres_db
from src.db.redis_client import redis_client
from src.logging_config import get_logger

logger = get_logger(__name__)


class SearchService:
    """Search products using semantic embeddings and traditional methods."""

    # cache key prefixes
    SEMANTIC_SEARCH_PREFIX = "semantic_search"
    HYBRID_SEARCH_PREFIX = "hybrid_search"
    SEARCH_NAME_PREFIX = "search:name"
    SEARCH_TAGS_PREFIX = "search:tags"
    FILTER_CATEGORY_PREFIX = "filter:category"
    FILTER_PRICE_PREFIX = "filter:price"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize search service with embedding model.

        Args:
            model_name: HuggingFace model identifier (default: all-MiniLM-L6-v2)
        """
        logger.info("Loading SentenceTransformer model '%s'", model_name)
        self.model: SentenceTransformer = SentenceTransformer(model_name)
        logger.info("SentenceTransformer model '%s' loaded", model_name)

    def _get_semantic_search_key(self, query: str) -> str:
        """Generate cache key for semantic search."""
        return f"{self.SEMANTIC_SEARCH_PREFIX}:query:{query}"

    def _get_hybrid_search_key(self, query: str) -> str:
        """Generate cache key for hybrid search."""
        return f"{self.HYBRID_SEARCH_PREFIX}:query:{query}"

    def _get_search_name_key(self, name: str, limit: int) -> str:
        """Generate cache key for name search."""
        return f"{self.SEARCH_NAME_PREFIX}:{name}:{limit}"

    def _get_search_tags_key(self, tags: List[str], limit: int) -> str:
        """Generate cache key for tag search."""
        tags_key: str = ",".join(sorted(tags))
        return f"{self.SEARCH_TAGS_PREFIX}:{tags_key}:{limit}"

    def _get_filter_category_key(self, category_id: str, limit: int) -> str:
        """Generate cache key for category filter."""
        return f"{self.FILTER_CATEGORY_PREFIX}:{category_id}:{limit}"

    def _get_filter_price_key(self, min_price: float, max_price: float, limit: int) -> str:
        """Generate cache key for price filter."""
        return f"{self.FILTER_PRICE_PREFIX}:{min_price}:{max_price}:{limit}"

    def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products using semantic similarity.

        Args:
            query: Natural language search query
            limit: Maximum number of results (default: 10)

        Returns:
            List of matching products with similarity scores
        """
        cache_key: str = self._get_semantic_search_key(query)
        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.SEMANTIC_SEARCH_PREFIX}:hit")
            logger.debug("Cache HIT semantic_search query=%r", query)
            return cached_result

        redis_client.increment_cache_metric(f"{self.SEMANTIC_SEARCH_PREFIX}:miss")
        logger.debug("Cache MISS semantic_search query=%r (limit=%d)", query, limit)
        query_embedding: np.ndarray = self.model.encode(query)
        result: List[Dict[str, Any]] = postgres_db.semantic_search(query_embedding.tolist(), limit)
        redis_client.set_json(cache_key, result)
        logger.info("semantic_search query=%r returned %d results", query, len(result))
        return result
    

    def hybrid_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Hybrid search combining semantic and full-text with RRF ranking.

        Uses Reciprocal Rank Fusion to merge results from multiple sources.

        Args:
            query: Natural language search query
            limit: Maximum number of results (default: 10)

        Returns:
            List of ranked products combining semantic and full-text scores
        """
        cache_key: str = self._get_hybrid_search_key(query)

        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.HYBRID_SEARCH_PREFIX}:hit")
            logger.debug("Cache HIT hybrid_search query=%r", query)
            return cached_result

        redis_client.increment_cache_metric(f"{self.HYBRID_SEARCH_PREFIX}:miss")
        logger.debug("Cache MISS hybrid_search query=%r (limit=%d)", query, limit)

        query_embedding: np.ndarray = self.model.encode(query)
        semantic_results: List[Dict[str, Any]] = postgres_db.semantic_search(query_embedding.tolist(), limit)
        keyword_results: List[Dict[str, Any]] = postgres_db.full_text_search(query, limit)

        # RRF
        rrf_scores: Dict[str, float] = {}
        k: int = 60

        for rank, doc in enumerate(semantic_results, 1):
            doc_id: str = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        for rank, doc in enumerate(keyword_results, 1):
            doc_id: str = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        all_results: Dict[str, Dict[str, Any]] = {doc["id"]: doc for doc in semantic_results + keyword_results}

        ranked_results: List[Dict[str, Any]] = sorted(
            [all_results[doc_id] for doc_id in rrf_scores.keys()],
            key=lambda x: rrf_scores[x["id"]],
            reverse=True
        )[:limit]

        redis_client.set_json(cache_key, ranked_results)
        logger.info(
            "hybrid_search query=%r fused %d semantic + %d keyword -> %d results",
            query, len(semantic_results), len(keyword_results), len(ranked_results),
        )
        return ranked_results

    def search_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products by name (case-insensitive).

        Args:
            name: Product name or partial name to search
            limit: Maximum number of results (default: 10)

        Returns:
            List of matching products
        """
        cache_key: str = self._get_search_name_key(name, limit)

        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.SEARCH_NAME_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.SEARCH_NAME_PREFIX}:miss")
        result: List[Dict[str, Any]] = postgres_db.search_by_name(name, limit)
        redis_client.set_json(cache_key, result)
        return result

    def search_by_tags(self, tags: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Search products by tags.

        Args:
            tags: List of tags to search for
            limit: Maximum number of results (default: 10)

        Returns:
            List of products with matching tags
        """
        cache_key: str = self._get_search_tags_key(tags, limit)

        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.SEARCH_TAGS_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.SEARCH_TAGS_PREFIX}:miss")
        result: List[Dict[str, Any]] = postgres_db.search_by_tags(tags, limit)
        redis_client.set_json(cache_key, result)
        return result

    def filter_by_category(self, category_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Filter products by category.

        Args:
            category_id: Category identifier
            limit: Maximum number of results (default: 20)

        Returns:
            List of products in the category
        """
        cache_key: str = self._get_filter_category_key(category_id, limit)

        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.FILTER_CATEGORY_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.FILTER_CATEGORY_PREFIX}:miss")
        result: List[Dict[str, Any]] = postgres_db.filter_by_category(category_id, limit)
        redis_client.set_json(cache_key, result)
        return result

    def filter_by_price(
        self, min_price: float = 0, max_price: float = float("inf"), limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Filter products by price range.

        Args:
            min_price: Minimum price (inclusive, default: 0)
            max_price: Maximum price (inclusive, default: inf)
            limit: Maximum number of results (default: 20)

        Returns:
            List of products in price range
        """
        cache_key: str = self._get_filter_price_key(min_price, max_price, limit)

        cached_result: List[Dict[str, Any]] | None = redis_client.get_json(cache_key)
        if cached_result:
            redis_client.increment_cache_metric(f"{self.FILTER_PRICE_PREFIX}:hit")
            return cached_result

        redis_client.increment_cache_metric(f"{self.FILTER_PRICE_PREFIX}:miss")
        result: List[Dict[str, Any]] = postgres_db.filter_by_price(min_price, max_price, limit)
        redis_client.set_json(cache_key, result)
        return result






        

