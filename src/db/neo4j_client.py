"""Neo4j connection and utilities."""

from datetime import datetime
from typing import Any

from neo4j import Driver, GraphDatabase

from src.config import NEO4J_CONFIG
from src.logging_config import get_logger

logger = get_logger(__name__)


class Neo4jClient:
    def __init__(self) -> None:
        logger.info("Initializing Neo4j driver (max_connection_pool_size=50)")
        self.driver: Driver = GraphDatabase.driver(
            NEO4J_CONFIG["uri"],
            auth=(NEO4J_CONFIG["user"], NEO4J_CONFIG["password"]),
            max_connection_pool_size=50,
        )

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        self.driver.close()

    def create_constraints(self) -> None:
        """Create uniqueness constraints."""
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
            session.run("CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE")
            session.run("CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE")
            logger.info("Neo4j uniqueness constraints created")

    def create_category_nodes(self, categories: list[dict[str, Any]]) -> None:
        """Batch-create/update Category nodes.

        Args:
            categories: List of dicts with keys: id, name
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Category {id: row.id})
                SET c.name = row.name
                """,
                rows=categories,
            )

    def create_seller_nodes(self, sellers: list[dict[str, Any]]) -> None:
        """Batch-create/update Seller nodes.

        Args:
            sellers: List of dicts with keys: id, name
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (s:Seller {id: row.id})
                SET s.name = row.name
                """,
                rows=sellers,
            )

    def create_user_nodes(self, users: list[dict[str, Any]]) -> None:
        """Batch-create/update User nodes.

        Args:
            users: List of dicts with keys: id, name, join_date
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (u:User {id: row.id})
                SET u.name = row.name, u.join_date = row.join_date
                """,
                rows=users,
            )

    def create_product_nodes(self, products: list[dict[str, Any]]) -> None:
        """Batch-create/update Product nodes.

        Stores only the minimal fields needed for graph traversal and result return.

        Args:
            products: List of dicts with keys: id, name, category, category_id, seller_id
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:Product {id: row.id})
                SET p.name = row.name,
                    p.category = row.category,
                    p.category_id = row.category_id,
                    p.seller_id = row.seller_id
                """,
                rows=products,
            )

    def add_view_relationship(self, user_id: str, product_id: str) -> None:
        """Add a VIEWED relationship between user and product.

        Args:
            user_id: User node identifier
            product_id: Product node identifier
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (u:User {id: $user_id})
                MATCH (p:Product {id: $product_id})
                CREATE (u)-[:VIEWED {timestamp: $timestamp}]->(p)
                """,
                user_id=user_id,
                product_id=product_id,
                timestamp=datetime.now().isoformat(),
            )

    def add_created_relationships(self, pairs: list[dict[str, Any]]) -> None:
        """Batch-create CREATED relationships.

        Args:
            pairs: List of dicts with keys: seller_id, product_id
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (s:Seller {id: row.seller_id})
                MATCH (p:Product {id: row.product_id})
                MERGE (s)-[r:CREATED]->(p)
                SET r.timestamp = $timestamp
                """,
                rows=pairs,
                timestamp=datetime.now().isoformat(),
            )

    def add_belongs_to_relationships(self, pairs: list[dict[str, Any]]) -> None:
        """Batch-create BELONGS_TO relationships.

        Args:
            pairs: List of dicts with keys: product_id, category_id
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (c:Category {id: row.category_id})
                MATCH (p:Product {id: row.product_id})
                MERGE (p)-[:BELONGS_TO]->(c)
                """,
                rows=pairs,
            )

    def add_similar_to_relationships(self, pairs: list[dict[str, Any]]) -> None:
        """Batch-create SIMILAR_TO relationships between products.

        Args:
            pairs: List of dicts with keys: product1_id, product2_id, score
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p1:Product {id: row.product1_id})
                MATCH (p2:Product {id: row.product2_id})
                MERGE (p1)-[r:SIMILAR_TO]->(p2)
                SET r.score = row.score
                """,
                rows=pairs,
            )

    def add_purchase_relationship(self, user_id: str, product_id: str, quantity: int, date: str) -> None:
        """Add a PURCHASED relationship between user and product.

        Args:
            user_id: User node identifier
            product_id: Product node identifier
            quantity: Number of items purchased
            date: Date of purchase (ISO format string)
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (u:User {id: $user_id})
                MATCH (p:Product {id: $product_id})
                CREATE (u)-[:PURCHASED {quantity: $quantity, date: $date}]->(p)
                """,
                user_id=user_id,
                product_id=product_id,
                quantity=quantity,
                date=date,
            )

    def add_purchase_relationships(self, pairs: list[dict[str, Any]]) -> None:
        """Batch-create PURCHASED relationships.

        Args:
            pairs: List of dicts with keys: user_id, product_id, quantity, date
        """
        with self.driver.session() as session:
            session.run(
                """
                UNWIND $rows AS row
                MATCH (u:User {id: row.user_id})
                MATCH (p:Product {id: row.product_id})
                CREATE (u)-[:PURCHASED {quantity: row.quantity, date: row.date}]->(p)
                """,
                rows=pairs,
            )

    def get_recommendations(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get product recommendations for a user based on collaborative filtering.

        Args:
            user_id: User identifier
            limit: Maximum number of recommendations

        Returns:
            List of recommended products
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (target:User {id: $user_id})-[:PURCHASED]->(p:Product)<-[:PURCHASED]-(other:User)
                MATCH (other)-[:PURCHASED]->(rec:Product)
                WHERE NOT (target)-[:PURCHASED]->(rec)
                WITH rec, count(*) as frequency
                ORDER BY frequency DESC
                LIMIT $limit
                RETURN rec.id as product_id, rec.name as product_name,
                       rec.seller_id as seller_id, rec.category_id as category_id
                """,
                user_id=user_id,
                limit=limit,
            )
            return [record.data() for record in result]

    def get_also_bought_products(self, product_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get products frequently bought by users who purchased a specific product.

        Args:
            product_id: Product identifier
            limit: Maximum number of results

        Returns:
            List of frequently bought products
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (:Product {id: $product_id})<-[:PURCHASED]-(u:User)-
                [:PURCHASED]->(rec:Product)
                WHERE rec.id <> $product_id
                WITH rec, count(*) as frequency
                ORDER BY frequency DESC
                LIMIT $limit
                RETURN rec.id as product_id, rec.name as product_name
                """,
                product_id=product_id,
                limit=limit,
            )
            return [record.data() for record in result]

    def get_products_frequently_bought_together(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get product pairs that are frequently bought together.

        Args:
            limit: Maximum number of pairs

        Returns:
            List of product pair combinations
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p1:Product)<-[:PURCHASED]-(u:User)-[:PURCHASED]->(p2:Product)
                WHERE p1.id <> p2.id
                WITH p1, p2, count(u) AS purchase_count
                ORDER by purchase_count DESC
                LIMIT $limit
                RETURN p1 as product1, p2 as product2
                """,
                limit=limit,
            )
            return [record.data() for record in result]

    def get_other_products_from_same_seller(self, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Get other products from the same seller as a user's purchased product.

        Args:
            user_id: User identifier
            limit: Maximum number of results

        Returns:
            List of products from same seller
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (u:User {id: $user_id})-[:PURCHASED]->(p:Product)<-[:CREATED]-(s:Seller)-
                [:CREATED]->(other:Product)
                WHERE other.id <> p.id
                AND NOT (u)-[:PURCHASED]->(other)
                WITH other, COUNT { (other)<-[:PURCHASED]-(:User) } as purchase_count
                ORDER BY purchase_count DESC
                LIMIT $limit
                RETURN other.id as product_id, other.name as product_name,
                       other.seller_id as seller_id, other.category_id as category_id
                """,
                user_id=user_id,
                limit=limit,
            )
            return [record.data() for record in result]


neo4j_client: Neo4jClient = Neo4jClient()
