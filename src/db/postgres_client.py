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
            CREATE INDEX IF NOT EXISTS idx_embedding_product ON product_embeddings USING hnsw (embedding vector_l2_ops);
            """,
        ]

        with self.get_cursor() as cursor:
            for query in queries:
                cursor.execute(query)
        

# Singleton instance
db = PostgresConnection()
