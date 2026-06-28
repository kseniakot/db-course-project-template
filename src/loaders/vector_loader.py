"""Load vector embeddings into pgvector."""

import numpy as np
from sentence_transformers import SentenceTransformer

from src.db.postgres_client import db
from src.logging_config import get_logger, setup_logging
from src.utils.data_parser import DataParser

logger = get_logger(__name__)


class VectorLoader:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize vector loader with embedding model.

        Args:
            model_name: HuggingFace model identifier (default: all-MiniLM-L6-v2)
        """
        self.model: SentenceTransformer = SentenceTransformer(model_name)
        self.parser: DataParser = DataParser()

    def generate_embeddings(self) -> tuple[int, int]:
        """Generate embeddings for all product descriptions.

        Returns:
            Tuple of (success_count, error_count)
        """
        products = self.parser.parse_products()
        logger.info("Generating embeddings for %d products", len(products))

        for _, product in products.iterrows():
            # Combine relevant text fields
            text: str = f"{product['name']} {product['description']} {' '.join(product['tags'])}"

            # Generate embedding
            embedding: np.ndarray = self.model.encode(text)

            # Store in database
            self._store_embedding(product["id"], embedding)

        logger.info("Stored %d product embeddings in pgvector", len(products))
        return len(products), 0

    def _store_embedding(self, product_id: str, embedding: np.ndarray) -> None:
        """Store embedding in pgvector.

        Args:
            product_id: Product identifier
            embedding: Embedding vector (numpy array)
        """
        with db.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO product_embeddings (product_id, embedding)
                VALUES (%s, %s)
                ON CONFLICT (product_id) DO UPDATE
                SET embedding = EXCLUDED.embedding;
                """,
                (product_id, embedding.tolist()),
            )


if __name__ == "__main__":
    setup_logging()
    loader = VectorLoader()
    loader.generate_embeddings()
