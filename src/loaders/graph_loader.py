"""Load nodes and relationships into Neo4j."""

from typing import Any

import pandas as pd

from src.db.neo4j_client import neo4j_client
from src.logging_config import get_logger, setup_logging
from src.utils.data_parser import DataParser

logger = get_logger(__name__)

SAME_SELLER_WEIGHT = 0.6
SAME_CATEGORY_WEIGHT = 0.4


class GraphLoader:
    """Load the product graph (nodes + structural relationships) into Neo4j."""

    def __init__(self) -> None:
        """Initialize graph loader with parsed source data."""
        self.client = neo4j_client
        self.parser: DataParser = DataParser()
        self.products: pd.DataFrame = self.parser.parse_products()
        self.users: pd.DataFrame = self.parser.parse_users()
        self.sellers: pd.DataFrame = self.parser.parse_sellers()
        self.categories: pd.DataFrame = self.parser.parse_categories()
        self.category_map: dict[str, str] = dict(zip(self.categories["name"], self.categories["id"], strict=False))

    def load_nodes(self) -> None:
        """Batch-create Category, Seller, User and Product nodes."""
        self.client.create_category_nodes(self.categories[["id", "name"]].to_dict("records"))
        self.client.create_seller_nodes(self.sellers[["id", "name"]].to_dict("records"))

        users = self.users[["id", "name", "join_date"]].copy()
        users["join_date"] = users["join_date"].apply(lambda d: d.isoformat())
        self.client.create_user_nodes(users.to_dict("records"))

        products = self.products[["id", "name", "category", "seller_id"]].copy()
        products["category_id"] = products["category"].map(self.category_map)
        self.client.create_product_nodes(products.to_dict("records"))

        logger.info(
            f"Loaded nodes: {len(self.categories)} categories, {len(self.sellers)} sellers, "
            f"{len(self.users)} users, {len(self.products)} products"
        )

    def load_belongs_to(self) -> None:
        """Batch-create BELONGS_TO relationships from products to their category."""
        pairs: list[dict[str, str]] = pd.DataFrame(
            {
                "product_id": self.products["id"],
                "category_id": self.products["category"].map(self.category_map),
            }
        ).to_dict("records")
        self.client.add_belongs_to_relationships(pairs)
        logger.info(f"Loaded {len(pairs)} BELONGS_TO relationships")

    def load_created(self) -> None:
        """Batch-create CREATED relationships from sellers to their products."""
        pairs: list[dict[str, str]] = (
            self.products[["seller_id", "id"]].rename(columns={"id": "product_id"}).to_dict("records")
        )
        self.client.add_created_relationships(pairs)
        logger.info(f"Loaded {len(pairs)} CREATED relationships")

    def load_similar_to(self) -> None:
        """Batch-create SIMILAR_TO relationships for product pairs sharing seller or category.

        Score uses the same formula as the recommendation MMR diversity penalty:
        same_seller * 0.6 + same_category * 0.4. Edges are created in a single
        direction per pair; queries should traverse SIMILAR_TO undirected.
        """
        records: list[dict] = self.products.to_dict("records")
        pairs: list[dict[str, Any]] = []

        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                first, second = records[i], records[j]
                same_seller: float = 1.0 if first["seller_id"] == second["seller_id"] else 0.0
                same_category: float = 1.0 if first["category"] == second["category"] else 0.0
                score: float = same_seller * SAME_SELLER_WEIGHT + same_category * SAME_CATEGORY_WEIGHT

                if score > 0:
                    pairs.append({"product1_id": first["id"], "product2_id": second["id"], "score": score})

        self.client.add_similar_to_relationships(pairs)
        logger.info(f"Loaded {len(pairs)} SIMILAR_TO relationships")

    def load_all(self) -> None:
        """Create constraints, nodes and structural relationships."""
        logger.info("Creating constraints...")
        self.client.create_constraints()

        logger.info("Loading nodes...")
        self.load_nodes()

        logger.info("Loading BELONGS_TO...")
        self.load_belongs_to()

        logger.info("Loading CREATED...")
        self.load_created()

        logger.info("Loading SIMILAR_TO...")
        self.load_similar_to()

        logger.info("Graph data loading complete!")


if __name__ == "__main__":
    setup_logging()
    loader = GraphLoader()
    loader.load_all()
    loader.client.close()
