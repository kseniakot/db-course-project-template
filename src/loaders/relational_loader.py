"""Load data into PostgreSQL database."""

import pandas as pd

from src.db.postgres_client import PostgresConnection
from src.logging_config import get_logger, setup_logging
from src.utils.data_parser import DataParser

logger = get_logger(__name__)


class RelationalLoader:
    def __init__(self) -> None:
        """Initialize relational loader."""
        self.db: PostgresConnection = PostgresConnection()
        self.parser: DataParser = DataParser()

    def load_categories(self) -> None:
        """Load categories into PostgreSQL."""
        categories: pd.DataFrame = self.parser.parse_categories()

        with self.db.get_cursor() as cursor:
            for _, row in categories.iterrows():
                query: str = """
                        INSERT INTO categories (id, name, description)
                        VALUES (%(id)s, %(name)s, %(description)s) ON CONFLICT (id) DO NOTHING;
                        """
                cursor.execute(query, row.to_dict())

        logger.info(f"Loaded {len(categories)} categories")

    def load_sellers(self) -> None:
        """Load sellers into PostgreSQL."""
        sellers: pd.DataFrame = self.parser.parse_sellers()

        with self.db.get_cursor() as cursor:
            for _, row in sellers.iterrows():
                query: str = """
                        INSERT INTO sellers (id, name, rating, specialty, joined)
                        VALUES (%(id)s, %(name)s, %(rating)s, %(specialty)s, %(joined)s)
                        ON CONFLICT (id) DO NOTHING;
                        """
                cursor.execute(query, row.to_dict())

        logger.info(f"Loaded {len(sellers)} sellers")

    def load_users(self) -> None:
        """Load users into PostgreSQL."""
        users: pd.DataFrame = self.parser.parse_users()

        with self.db.get_cursor() as cursor:
            for _, row in users.iterrows():
                query: str = """
                        INSERT INTO users (id, name, email, join_date, location, interests)
                        VALUES (%(id)s, %(name)s, %(email)s, %(join_date)s, %(location)s, %(interests)s)
                        ON CONFLICT (id) DO NOTHING;
                        """
                cursor.execute(query, row.to_dict())

        logger.info(f"Loaded {len(users)} users")

    def load_products(self) -> None:
        """Load products into PostgreSQL, mapping category name to category id."""
        categories: pd.DataFrame = self.parser.parse_categories()
        category_map: dict[str, str] = {
            row["name"]: row["id"] for _, row in categories.iterrows()
        }

        products: pd.DataFrame = self.parser.parse_products()

        with self.db.get_cursor() as cursor:
            for _, row in products.iterrows():
                params: dict = row.to_dict()
                params["category_id"] = category_map[params["category"]]
                query: str = """
                        INSERT INTO products
                            (id, name, description, price, category_id, seller_id, tags, stock)
                        VALUES
                            (%(id)s, %(name)s, %(description)s, %(price)s, %(category_id)s,
                             %(seller_id)s, %(tags)s, %(stock)s)
                        ON CONFLICT (id) DO NOTHING;
                        """
                cursor.execute(query, params)

        logger.info(f"Loaded {len(products)} products")

    def load_all(self) -> None:
        """Load all data into PostgreSQL respecting foreign key order."""
        logger.info("Creating tables...")
        self.db.create_tables()

        logger.info("Loading categories...")
        self.load_categories()

        logger.info("Loading sellers...")
        self.load_sellers()

        logger.info("Loading users...")
        self.load_users()

        logger.info("Loading products...")
        self.load_products()

        logger.info("Relational data loading complete!")


if __name__ == "__main__":
    setup_logging()
    loader = RelationalLoader()
    loader.load_all()
