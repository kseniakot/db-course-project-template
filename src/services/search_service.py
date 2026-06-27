"""Search service for products with multiple search strategies."""

from typing import Any, Dict, List

import numpy as np
from sentence_transformers import SentenceTransformer

from src.db.postgres_client import db as postgres_db
from src.db.redis_client import redis_client


class SemanticSearchService:
    """Search products using semantic embeddings and traditional methods."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize search service with embedding model.

        Args:
            model_name: HuggingFace model identifier (default: all-MiniLM-L6-v2)
        """
        self.model: SentenceTransformer = SentenceTransformer(model_name)
        print(f"SentenceTransformer model '{model_name}' loaded.")

    def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products using semantic similarity.

        Args:
            query: Natural language search query
            limit: Maximum number of results (default: 10)

        Returns:
            List of matching products with similarity scores
        """
        query_embedding: np.ndarray = self.model.encode(query)

        with postgres_db.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT p.*,
                       1 - (pe.embedding <=> %s::vector) as similarity
                FROM products p
                JOIN product_embeddings pe ON p.id = pe.product_id
                ORDER BY pe.embedding <=> %s::vector
                LIMIT %s;
                """,
                (query_embedding.tolist(), query_embedding.tolist(), limit),
            )
            return cursor.fetchall()

