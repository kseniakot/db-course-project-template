"""PostgreSQL connection and utilities."""

from contextlib import contextmanager
from typing import Any, Dict, Generator, List

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.config import POSTGRES_CONFIG
from src.logging_config import get_logger

logger = get_logger(__name__)

POOL_MIN_CONN = 1
POOL_MAX_CONN = 10

# SQLAlchemy declarative base
try:
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()
except ImportError:
    from sqlalchemy.orm import declarative_base

    Base = declarative_base()


class PostgresConnection:
    def __init__(self) -> None:
        self.config: Dict[str, Any] = POSTGRES_CONFIG
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._pool: ThreadedConnectionPool | None = None

    @property
    def pool(self) -> ThreadedConnectionPool:
        """Get or create the psycopg2 connection pool."""
        if not self._pool:
            logger.info(
                "Creating PostgreSQL connection pool (min=%d, max=%d)",
                POOL_MIN_CONN, POOL_MAX_CONN,
            )
            self._pool = ThreadedConnectionPool(POOL_MIN_CONN, POOL_MAX_CONN, **self.config)
        return self._pool

    @property
    def engine(self) -> Engine:
        """Get or create SQLAlchemy engine."""
        if not self._engine:
            db_url: str = (
                f"postgresql://{self.config['user']}:{self.config['password']}@"
                f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
            )
            self._engine = create_engine(db_url)
        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get or create session factory."""
        if not self._session_factory:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    @contextmanager
    def get_cursor(self) -> Generator[RealDictCursor, None, None]:
        """Get a database cursor for raw SQL queries.

        Yields:
            RealDictCursor: Cursor that returns rows as dictionaries
        """
        conn: psycopg2.extensions.connection = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
                conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("PostgreSQL transaction failed, rolled back")
            raise
        finally:
            self.pool.putconn(conn)

    def create_tables(self) -> None:
        """Create all tables in the database."""
        queries: List[str] = [
            """
            CREATE EXTENSION IF NOT EXISTS vector;
            """,
            """
            CREATE TABLE IF NOT EXISTS categories (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                description TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS sellers (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                rating FLOAT,
                specialty VARCHAR(255),
                joined TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                join_date TIMESTAMP,
                location VARCHAR(255),
                interests TEXT[]
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS products (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                price DECIMAL(10, 2),
                category_id VARCHAR(255) REFERENCES categories(id),
                seller_id VARCHAR(255) REFERENCES sellers(id),
                tags TEXT[],
                stock INT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS orders (
                id VARCHAR(255) PRIMARY KEY,
                user_id VARCHAR(255) REFERENCES users(id),
                order_date TIMESTAMP,
                status VARCHAR(50),
                total_price DECIMAL(10, 2)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS order_items (
                order_id VARCHAR(255) REFERENCES orders(id),
                product_id VARCHAR(255) REFERENCES products(id),
                quantity INT,
                price_at_purchase DECIMAL(10, 2),
                PRIMARY KEY (order_id, product_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS product_embeddings (
                product_id VARCHAR(255) PRIMARY KEY REFERENCES products(id),
                embedding vector(384)
            );
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_product_category ON products(category_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_product_seller ON products(seller_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_product_seller_category ON products(seller_id, category_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_order_user ON orders(user_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_order_item_lookup ON order_items(product_id, order_id);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_embedding_product ON product_embeddings USING hnsw (embedding vector_cosine_ops);
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_product_fulltext ON products USING gin (to_tsvector('english', name || ' ' || description));
            """,
        ]

        logger.info("Creating %d tables/indexes if not present", len(queries))
        with self.get_cursor() as cursor:
            for query in queries:
                cursor.execute(query)
        logger.info("PostgreSQL schema ready")

    def get_product_by_id(self, product_id: str) -> Dict[str, Any] | None:
        """Fetch a single product by its exact id.

        Args:
            product_id: Product identifier

        Returns:
            Product row as a dict, or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, description, price, category_id, seller_id, tags, stock
                FROM products
                WHERE id = %s
                """,
                (product_id,),
            )
            return cursor.fetchone()

    def find_similar_products(self, product_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar products using vector similarity search.

        Args:
            product_id: Target product ID
            limit: Maximum number of results

        Returns:
            List of similar products with similarity scores
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.price,
                    1 - (pe.embedding <=> pe2.embedding) as similarity
                FROM product_embeddings pe
                JOIN products p ON pe.product_id = p.id
                JOIN product_embeddings pe2 ON pe2.product_id = %s
                WHERE p.id <> %s
                ORDER BY pe.embedding <=> pe2.embedding
                LIMIT %s
                """,
                (product_id, product_id, limit),
            )
            return cursor.fetchall()

    def full_text_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search across product names and descriptions.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching products
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.description,
                    p.price,
                    c.name as category,
                    s.name as seller
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN sellers s ON p.seller_id = s.id
                WHERE p.stock >= 1
                AND (
                    to_tsvector('english', p.name || ' ' || p.description)
                    @@ plainto_tsquery('english', %s)
                )
                LIMIT %s
                """,
                (query, limit)
            )
            return cursor.fetchall()
        
    def search_by_name(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products by name (case-insensitive).

        Args:
            name: Product name or partial name to search
            limit: Maximum number of results

        Returns:
            List of matching products with category and seller info
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id, p.name, p.description, p.price,
                    c.name as category, s.name as seller
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN sellers s ON p.seller_id = s.id
                WHERE p.stock >= 1 AND p.name ILIKE %s
                ORDER BY p.name ASC
                LIMIT %s
                """,
                (f"%{name}%", limit),
            )
            return cursor.fetchall()

    def search_by_tags(self, tags: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """Search products that have ANY of the specified tags.

        Args:
            tags: List of tags to search for
            limit: Maximum number of results

        Returns:
            List of products with matching tags
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id, p.name, p.description, p.price,
                    c.name as category, s.name as seller
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN sellers s ON p.seller_id = s.id
                WHERE p.stock >= 1 AND p.tags && %s
                ORDER BY p.name ASC
                LIMIT %s
                """,
                (tags, limit),
            )
            return cursor.fetchall()

    def filter_by_category(self, category_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Filter products by category.

        Args:
            category_id: Category identifier
            limit: Maximum number of results

        Returns:
            List of products in the category sorted by price
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id, p.name, p.description, p.price,
                    c.name as category, s.name as seller
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN sellers s ON p.seller_id = s.id
                WHERE p.stock >= 1 AND p.category_id = %s
                ORDER BY p.price ASC
                LIMIT %s
                """,
                (category_id, limit),
            )
            return cursor.fetchall()

    def filter_by_price(
        self, min_price: float = 0, max_price: float = float("inf"), limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Filter products by price range.

        Args:
            min_price: Minimum price (inclusive)
            max_price: Maximum price (inclusive)
            limit: Maximum number of results

        Returns:
            List of products in price range sorted by price
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    p.id, p.name, p.description, p.price,
                    c.name as category, s.name as seller
                FROM products p
                JOIN categories c ON p.category_id = c.id
                JOIN sellers s ON p.seller_id = s.id
                WHERE p.stock >= 1
                AND p.price >= %s
                AND p.price <= %s
                ORDER BY p.price ASC
                LIMIT %s
                """,
                (min_price, max_price, limit),
            )
            return cursor.fetchall()
        

    def semantic_search(self, embedding: list, limit: int = 10) -> List[Dict[str, Any]]:
        """Search products using semantic similarity."""
        logger.debug("Semantic search (limit=%d)", limit)
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT p.id, p.name, p.description, p.price, p.category_id,
                       p.seller_id, p.tags, p.stock,
                       1 - (pe.embedding <=> %s::vector) as similarity
                FROM products p
                JOIN product_embeddings pe ON p.id = pe.product_id
                ORDER BY pe.embedding <=> %s::vector
                LIMIT %s;
                """,
                (embedding, embedding, limit),
            )
            results = cursor.fetchall()
        logger.debug("Semantic search returned %d rows", len(results))
        return results


# Singleton instance
db = PostgresConnection()
