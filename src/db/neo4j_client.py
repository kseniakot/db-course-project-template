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
        """Create uniqueness and existence constraints."""
        with self.driver.session() as session:
            # Uniqueness constraints (also create indexes)
            session.run("CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE")
            session.run("CREATE CONSTRAINT product_id IF NOT EXISTS FOR (p:Product) REQUIRE p.id IS UNIQUE")
            session.run("CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE")

            # Property existence constraints
            session.run("CREATE CONSTRAINT user_name IF NOT EXISTS FOR (u:User) REQUIRE u.name IS NOT NULL")
            session.run("CREATE CONSTRAINT product_name IF NOT EXISTS FOR (p:Product) REQUIRE p.name IS NOT NULL")
            session.run("CREATE CONSTRAINT category_name IF NOT EXISTS FOR (c:Category) REQUIRE c.name IS NOT NULL")
            logger.info("Neo4j constraints created")

    def create_category_node(self, category_id: str, name: str) -> None:
        """Create or update a Category node.

        Args:
            category_id: Category identifier
            name: Category name
        """
        with self.driver.session() as session:
            session.run(
                """
                MERGE (c:Category {id: $category_id})
                SET c.name = $name
                """,
                category_id=category_id,
                name=name,
            )

    def create_seller_node(self, seller_id: str, name: str) -> None:
        """Create or update a Seller node.

        Args:
            seller_id: Seller identifier
            name: Seller name
        """
        with self.driver.session() as session:
            session.run(
                """
                MERGE (s:Seller {id: $seller_id})
                SET s.name = $name
                """,
                seller_id=seller_id,
                name=name,
            )

    def create_user_node(self, user_id: str, name: str, join_date: str) -> None:
        """Create or update a User node.

        Args:
            user_id: User identifier
            name: User name
            join_date: Join date (ISO format string)
        """
        with self.driver.session() as session:
            session.run(
                """
                MERGE (u:User {id: $user_id})
                SET u.name = $name, u.join_date = $join_date
                """,
                user_id=user_id,
                name=name,
                join_date=join_date,
            )

    def create_product_node(
        self,
        product_id: str,
        name: str,
        category: str,
        category_id: str,
        seller_id: str,
    ) -> None:
        """Create or update a Product node.

        Stores only the minimal fields needed for graph traversal and result
        return.

        Args:
            product_id: Product identifier
            name: Product name
            category: Category name
            category_id: Category identifier (for similarity scoring)
            seller_id: Seller identifier (for similarity scoring)
        """
        with self.driver.session() as session:
            session.run(
                """
                MERGE (p:Product {id: $product_id})
                SET p.name = $name,
                    p.category = $category,
                    p.category_id = $category_id,
                    p.seller_id = $seller_id
                """,
                product_id=product_id,
                name=name,
                category=category,
                category_id=category_id,
                seller_id=seller_id,
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

    def add_product_creation_relationship(self, seller_id: str, product_id: str) -> None:
        """Add a CREATED relationship between seller and product.

        Args:
            seller_id: Seller node identifier
            product_id: Product node identifier
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (s:Seller {id: $seller_id})
                MATCH (p:Product {id: $product_id})
                MERGE (s)-[r:CREATED]->(p)
                SET r.timestamp = $timestamp
                """,
                seller_id=seller_id,
                product_id=product_id,
                timestamp=datetime.now().isoformat(),
            )

    def add_belongs_to_category_relationship(self, category_id: str, product_id: str) -> None:
        """Add a BELONGS_TO relationship between product and category.

        Args:
            category_id: Category node identifier
            product_id: Product node identifier
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (c:Category {id: $category_id})
                MATCH (p:Product {id: $product_id})
                MERGE (p)-[:BELONGS_TO]->(c)
                """,
                category_id=category_id,
                product_id=product_id,
            )

    def add_similar_to_relationship(self, product1_id: str, product2_id: str, score: float) -> None:
        """Add a SIMILAR_TO relationship between products.

        Args:
            product1_id: First product identifier
            product2_id: Second product identifier
            score: Similarity score between the two products
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (p1:Product {id: $product1_id})
                MATCH (p2:Product {id: $product2_id})
                MERGE (p1)-[r:SIMILAR_TO]->(p2)
                SET r.score = $score
                """,
                product1_id=product1_id,
                product2_id=product2_id,
                score=score,
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
                RETURN rec.id as product_id, rec.name as product_name
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
                WITH other, count((other)<-[:PURCHASED]-(:User)) as purchase_count
                ORDER BY purchase_count DESC
                LIMIT $limit
                RETURN other as product
                """,
                user_id=user_id,
                limit=limit,
            )
            return [record.data() for record in result]


neo4j_client: Neo4jClient = Neo4jClient()
