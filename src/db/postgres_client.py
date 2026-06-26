"""PostgreSQL connection and utilities."""

from contextlib import contextmanager
import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from src.config import POSTGRES_CONFIG

Base = declarative_base()


class PostgresConnection:
    def __init__(self):
        self.config = POSTGRES_CONFIG
        self._engine = None
        self._session_factory = None

    @property
    def engine(self):
        if not self._engine:
            db_url = (
                f"postgresql://{self.config['user']}:{self.config['password']}@"
                f"{self.config['host']}:{self.config['port']}/{self.config['database']}"
            )
            self._engine = create_engine(db_url)
        return self._engine

    @property
    def session_factory(self):
        if not self._session_factory:
            self._session_factory = sessionmaker(bind=self.engine)
        return self._session_factory

    @contextmanager
    def get_cursor(self):
        """Get a database cursor for raw SQL queries."""
        conn = psycopg2.connect(**self.config)
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                yield cursor
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def create_tables(self):
        """Create all tables in the database."""
        queries = [
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

        with self.get_cursor() as cursor:
            for query in queries:
                cursor.execute(query)

    def find_similar_products(self, product_id: str, limit: int = 5):
        """Find similar products using vector similarity search."""
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
                (product_id, product_id, limit)
            )
            return cursor.fetchall()
        
    def full_text_search(self, query: str, limit: int = 10):
        """Full-text search across product names and descriptions."""
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
        
    def search_by_name(self, name: str, limit: int = 10):
        """Search products by name (case-insensitive)."""
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
                (f'%{name}%', limit)
            )
            return cursor.fetchall()

    def search_by_tags(self, tags: list, limit: int = 10):
        """Search products that have ANY of the specified tags."""
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
                (tags, limit)
            )
            return cursor.fetchall()

    def filter_by_category(self, category_id: str, limit: int = 20):
        """Filter products by category."""
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
                (category_id, limit)
            )
            return cursor.fetchall()

    def filter_by_price(self, min_price: float = 0, max_price: float = float('inf'), limit: int = 20):
        """Filter products by price range."""
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
                (min_price, max_price, limit)
            )
            return cursor.fetchall()


# Singleton instance
db = PostgresConnection()
