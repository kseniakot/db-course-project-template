"""Load nodes and relationships into Neo4j."""

from typing import Dict, List

import pandas as pd

from src.db.neo4j_client import neo4j_client
from src.utils.data_parser import DataParser

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
        self.category_map: Dict[str, str] = {
            row["name"]: row["id"] for _, row in self.categories.iterrows()
        }

    def load_nodes(self) -> None:
        """Create Category, Seller, User and Product nodes."""
        for _, category in self.categories.iterrows():
            self.client.create_category_node(category["id"], category["name"])

        for _, seller in self.sellers.iterrows():
            self.client.create_seller_node(seller["id"], seller["name"])

        for _, user in self.users.iterrows():
            self.client.create_user_node(
                user["id"], user["name"], user["join_date"].isoformat()
            )

        for _, product in self.products.iterrows():
            category_id: str = self.category_map[product["category"]]
            self.client.create_product_node(
                product["id"],
                product["name"],
                product["category"],
                category_id,
                product["seller_id"],
            )

        print(
            f"Loaded nodes: {len(self.categories)} categories, {len(self.sellers)} sellers, "
            f"{len(self.users)} users, {len(self.products)} products"
        )

    def load_belongs_to(self) -> None:
        """Create BELONGS_TO relationships from products to their category."""
        for _, product in self.products.iterrows():
            category_id: str = self.category_map[product["category"]]
            self.client.add_belongs_to_category_relationship(category_id, product["id"])

        print(f"Loaded {len(self.products)} BELONGS_TO relationships")

    def load_created(self) -> None:
        """Create CREATED relationships from sellers to their products."""
        for _, product in self.products.iterrows():
            self.client.add_product_creation_relationship(product["seller_id"], product["id"])

        print(f"Loaded {len(self.products)} CREATED relationships")

    def load_similar_to(self) -> None:
        """Create SIMILAR_TO relationships for product pairs sharing seller or category.

        Score uses the same formula as the recommendation MMR diversity penalty:
        same_seller * 0.6 + same_category * 0.4. Edges are created in a single
        direction per pair; queries should traverse SIMILAR_TO undirected.
        """
        records: List[Dict] = self.products.to_dict("records")
        count: int = 0

        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                first, second = records[i], records[j]
                same_seller: float = 1.0 if first["seller_id"] == second["seller_id"] else 0.0
                same_category: float = 1.0 if first["category"] == second["category"] else 0.0
                score: float = same_seller * SAME_SELLER_WEIGHT + same_category * SAME_CATEGORY_WEIGHT

                if score > 0:
                    self.client.add_similar_to_relationship(first["id"], second["id"], score)
                    count += 1

        print(f"Loaded {count} SIMILAR_TO relationships")

    def load_all(self) -> None:
        """Create constraints, nodes and structural relationships."""
        print("Creating constraints...")
        self.client.create_constraints()

        print("Loading nodes...")
        self.load_nodes()

        print("Loading BELONGS_TO...")
        self.load_belongs_to()

        print("Loading CREATED...")
        self.load_created()

        print("Loading SIMILAR_TO...")
        self.load_similar_to()

        print("Graph data loading complete!")


if __name__ == "__main__":
    loader = GraphLoader()
    loader.load_all()
    loader.client.close()
