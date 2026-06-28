"""Generate random purchase history using semantic interest matching."""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

import pandas as pd
from sentence_transformers import SentenceTransformer

from src.db.neo4j_client import neo4j_client
from src.db.postgres_client import db
from src.logging_config import get_logger, setup_logging
from src.utils.data_parser import DataParser

logger = get_logger(__name__)

RANDOM_SEED = 42
BASE_DATE = datetime(2026, 1, 1)
AFFINITY_WEIGHT = 2.0
ORDER_STATUSES = ["delivered", "shipped", "pending", "cancelled"]


class PurchaseGenerator:
    """Generate realistic purchases, biased toward products that semantically match user interests."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize generator with source data and embedding model.

        Args:
            model_name: HuggingFace model identifier (default: all-MiniLM-L6-v2)
        """
        random.seed(RANDOM_SEED)
        self.parser: DataParser = DataParser()
        self.users: pd.DataFrame = self.parser.parse_users()
        self.products: pd.DataFrame = self.parser.parse_products()
        self.model: SentenceTransformer = SentenceTransformer(model_name)
        self.product_ids: List[str] = self.products["id"].tolist()
        self.price_map: Dict[str, float] = dict(
            zip(self.products["id"], self.products["price"])
        )

    def _affinity_pool(self, interests: List[str]) -> List[Tuple[str, float]]:
        """Rank all products by semantic similarity to a user's interests.

        Args:
            interests: User interest phrases

        Returns:
            List of (product_id, weight) where weight = 1 + AFFINITY_WEIGHT * similarity
        """
        embedding = self.model.encode(", ".join(interests))
        ranked: List[Dict[str, Any]] = db.semantic_search(
            embedding.tolist(), limit=len(self.product_ids)
        )
        return [
            (row["id"], 1.0 + AFFINITY_WEIGHT * max(0.0, float(row["similarity"])))
            for row in ranked
        ]

    def _weighted_sample(self, pool: List[Tuple[str, float]], k: int) -> List[str]:
        """Sample k distinct product ids from a weighted pool without replacement."""
        items: List[str] = [pid for pid, _ in pool]
        weights: List[float] = [w for _, w in pool]
        chosen: List[str] = []

        for _ in range(min(k, len(items))):
            idx: int = random.choices(range(len(items)), weights=weights, k=1)[0]
            chosen.append(items[idx])
            items.pop(idx)
            weights.pop(idx)

        return chosen

    def _order_date(self, join_date: pd.Timestamp) -> datetime:
        """Return a random order date between the user's join date and BASE_DATE."""
        join: datetime = join_date.to_pydatetime()
        span_days: int = (BASE_DATE - join).days
        if span_days <= 0:
            return join
        return join + timedelta(days=random.randint(0, span_days))

    def generate_purchases(self, target_line_items: int = 100) -> pd.DataFrame:
        """Generate purchases until reaching the target number of line items.

        Each order belongs to one user and contains 1-3 distinct products,
        selected with probability proportional to semantic interest affinity.

        Args:
            target_line_items: Approximate number of order-item rows to generate

        Returns:
            DataFrame of purchase line items with per-order total price
        """
        pools: Dict[str, List[Tuple[str, float]]] = {
            user["id"]: self._affinity_pool(user["interests"])
            for _, user in self.users.iterrows()
        }
        user_records: List[Dict[str, Any]] = self.users.to_dict("records")

        purchases: List[Dict[str, Any]] = []
        order_num: int = 0

        while len(purchases) < target_line_items:
            order_num += 1
            user: Dict[str, Any] = random.choice(user_records)
            order_id: str = f"O{order_num:04d}"
            order_date: datetime = self._order_date(user["join_date"])
            status: str = random.choice(ORDER_STATUSES)

            for product_id in self._weighted_sample(pools[user["id"]], random.randint(1, 3)):
                purchases.append({
                    "order_id": order_id,
                    "user_id": user["id"],
                    "product_id": product_id,
                    "quantity": random.randint(1, 3),
                    "price_at_purchase": self.price_map[product_id],
                    "order_date": order_date,
                    "status": status,
                })

        purchases_df: pd.DataFrame = pd.DataFrame(purchases)

        order_totals: pd.Series = purchases_df.groupby("order_id").apply(
            lambda rows: (rows["price_at_purchase"] * rows["quantity"]).sum()
        )
        order_totals.name = "total_price"
        return purchases_df.merge(order_totals, on="order_id")

    def _build_viewed(self, purchases_df: pd.DataFrame) -> List[Tuple[str, str]]:
        """Derive VIEWED pairs: every purchased product plus a few extra browsed ones."""
        viewed: List[Tuple[str, str]] = []

        for user_id, group in purchases_df.groupby("user_id"):
            bought: set = set(group["product_id"])
            not_bought: List[str] = [pid for pid in self.product_ids if pid not in bought]
            extras: List[str] = random.sample(
                not_bought, k=min(random.randint(2, 5), len(not_bought))
            )
            for product_id in bought.union(extras):
                viewed.append((str(user_id), product_id))

        return viewed

    def load_into_postgres(self, purchases_df: pd.DataFrame) -> None:
        """Load orders and order items into PostgreSQL in a single transaction."""
        orders: pd.DataFrame = purchases_df[
            ["order_id", "user_id", "order_date", "status", "total_price"]
        ].drop_duplicates(subset="order_id")

        with db.get_cursor() as cursor:
            for _, order in orders.iterrows():
                cursor.execute(
                    """
                    INSERT INTO orders (id, user_id, order_date, status, total_price)
                    VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING;
                    """,
                    (order["order_id"], order["user_id"], order["order_date"],
                     order["status"], order["total_price"]),
                )

            for _, item in purchases_df.iterrows():
                cursor.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
                    VALUES (%s, %s, %s, %s) ON CONFLICT (order_id, product_id) DO NOTHING;
                    """,
                    (item["order_id"], item["product_id"], item["quantity"],
                     item["price_at_purchase"]),
                )

        logger.info(f"Loaded {len(orders)} orders and {len(purchases_df)} order items into PostgreSQL")

    def load_into_neo4j(self, purchases_df: pd.DataFrame) -> None:
        """Load PURCHASED and VIEWED relationships into Neo4j."""
        for _, item in purchases_df.iterrows():
            neo4j_client.add_purchase_relationship(
                user_id=str(item["user_id"]),
                product_id=str(item["product_id"]),
                quantity=int(item["quantity"]),
                date=item["order_date"].isoformat(),
            )

        viewed: List[Tuple[str, str]] = self._build_viewed(purchases_df)
        for user_id, product_id in viewed:
            neo4j_client.add_view_relationship(user_id, product_id)

        logger.info(f"Loaded {len(purchases_df)} PURCHASED and {len(viewed)} VIEWED relationships into Neo4j")


if __name__ == "__main__":
    setup_logging()
    generator = PurchaseGenerator()
    logger.info("Generating purchase data...")
    purchases = generator.generate_purchases()
    logger.info(f"Generated {len(purchases)} purchase line items")

    logger.info("Loading into databases...")
    generator.load_into_postgres(purchases)
    generator.load_into_neo4j(purchases)
    neo4j_client.close()
    logger.info("Purchase generation and loading complete!")
