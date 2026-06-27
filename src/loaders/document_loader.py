"""Load synthetic document data into MongoDB."""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd

from src.db.mongodb_client import mongo_client
from src.utils.data_parser import DataParser

RANDOM_SEED = 42
BASE_DATE = datetime(2026, 1, 1)

REVIEW_TITLES: Dict[int, List[str]] = {
    5: ["Absolutely love it!", "Exceeded expectations", "Best purchase this year"],
    4: ["Really good", "Happy with it", "Solid quality"],
    3: ["It's okay", "Decent but not great", "Average"],
    2: ["Disappointed", "Not what I expected", "Could be better"],
    1: ["Would not recommend", "Poor quality", "Waste of money"],
}

REVIEW_CONTENT: Dict[int, List[str]] = {
    5: ["The craftsmanship is stunning and it arrived well packaged.",
        "Exactly as described, beautiful work. Will buy again."],
    4: ["Great product overall, minor imperfections but worth it.",
        "Very pleased, would order from this seller again."],
    3: ["Does the job but the finish wasn't as smooth as I hoped.",
        "Fine for the price, nothing special though."],
    2: ["Quality didn't match the photos, a bit let down.",
        "Arrived later than expected and felt flimsy."],
    1: ["Broke within a week, very disappointed.",
        "Not as pictured at all, returning it."],
}

COMMENT_TEXTS: List[str] = [
    "Totally agree!", "Thanks for the honest review.",
    "I had the same experience.", "Good to know before buying.",
]

MATERIALS_BY_CATEGORY: Dict[str, List[str]] = {
    "Home & Kitchen": ["Acacia wood", "Bamboo", "Ceramic", "Stainless steel"],
    "Fashion": ["Organic cotton", "Merino wool", "Linen", "Vegetable-tanned leather"],
    "Jewelry": ["Sterling silver", "14k gold", "Brass", "Natural gemstone"],
    "Home Decor": ["Hand-blown glass", "Reclaimed wood", "Stoneware", "Woven fabric"],
    "Stationery": ["Recycled paper", "Cotton paper", "Leather", "Cardstock"],
    "Beauty": ["Shea butter", "Cold-pressed oils", "Beeswax", "Botanical extract"],
}

CARE_INSTRUCTIONS: List[str] = [
    "Hand wash only", "Keep away from direct sunlight", "Wipe with a dry cloth",
    "Oil regularly", "Store in a cool dry place", "Do not machine wash",
]


class DocumentLoader:
    """Generate and load synthetic documents into MongoDB collections."""

    def __init__(self) -> None:
        """Initialize document loader with parsed source data."""
        random.seed(RANDOM_SEED)
        self.parser: DataParser = DataParser()
        self.products: pd.DataFrame = self.parser.parse_products()
        self.users: pd.DataFrame = self.parser.parse_users()
        self.sellers: pd.DataFrame = self.parser.parse_sellers()
        self.categories: pd.DataFrame = self.parser.parse_categories()
        self.user_ids: List[str] = self.users["id"].tolist()

    def _random_date(self, max_days_ago: int = 365) -> datetime:
        """Return a random datetime within the last `max_days_ago` days."""
        return BASE_DATE - timedelta(days=random.randint(0, max_days_ago))

    def load_reviews(self) -> None:
        """Generate 1-4 reviews per product."""
        collection = mongo_client.get_collection("reviews")
        collection.delete_many({})

        documents: List[Dict[str, Any]] = []
        for _, product in self.products.iterrows():
            for _ in range(random.randint(1, 4)):
                rating: int = random.choices([5, 4, 3, 2, 1], weights=[40, 30, 15, 10, 5])[0]
                comments: List[Dict[str, Any]] = [
                    {
                        "user_id": random.choice(self.user_ids),
                        "content": random.choice(COMMENT_TEXTS),
                        "created_at": self._random_date(),
                    }
                    for _ in range(random.randint(0, 2))
                ]
                documents.append({
                    "product_id": product["id"],
                    "user_id": random.choice(self.user_ids),
                    "rating": rating,
                    "title": random.choice(REVIEW_TITLES[rating]),
                    "content": random.choice(REVIEW_CONTENT[rating]),
                    "helpful_votes": random.randint(0, 50),
                    "verified_purchase": random.random() < 0.7,
                    "created_at": self._random_date(),
                    "comments": comments,
                })

        collection.insert_many(documents)
        print(f"Loaded {len(documents)} reviews")

    def load_product_specs(self) -> None:
        """Generate one spec document per product."""
        collection = mongo_client.get_collection("product_specs")
        collection.delete_many({})

        documents: List[Dict[str, Any]] = []
        for _, product in self.products.iterrows():
            category: str = product["category"]
            materials: List[str] = MATERIALS_BY_CATEGORY.get(category, ["Mixed materials"])
            documents.append({
                "product_id": product["id"],
                "category": category,
                "specs": {
                    "material": random.choice(materials),
                    "dimensions": {
                        "length": random.randint(5, 40),
                        "width": random.randint(5, 40),
                        "height": random.randint(2, 20),
                        "unit": "cm",
                    },
                    "care_instructions": random.sample(CARE_INSTRUCTIONS, k=random.randint(1, 3)),
                    "weight": f"{random.randint(100, 2000)}g",
                },
            })

        collection.insert_many(documents)
        print(f"Loaded {len(documents)} product specs")

    def load_seller_profiles(self) -> None:
        """Generate a rich profile per seller, including a portfolio from their products."""
        collection = mongo_client.get_collection("seller_profiles")
        collection.delete_many({})

        documents: List[Dict[str, Any]] = []
        for _, seller in self.sellers.iterrows():
            seller_products: List[str] = self.products[
                self.products["seller_id"] == seller["id"]
            ]["name"].tolist()
            portfolio: List[Dict[str, str]] = [
                {"title": name, "description": f"Handcrafted {name.lower()}."}
                for name in seller_products[:3]
            ]
            documents.append({
                "seller_id": seller["id"],
                "name": seller["name"],
                "specialty": seller["specialty"],
                "rating": float(seller["rating"]),
                "joined": seller["joined"].to_pydatetime(),
                "bio": f"{seller['name']} specializes in {seller['specialty'].lower()}, "
                       f"crafting each piece by hand.",
                "portfolio": portfolio,
                "total_sales": random.randint(50, 5000),
            })

        collection.insert_many(documents)
        print(f"Loaded {len(documents)} seller profiles")

    def load_user_preferences(self) -> None:
        """Generate a preference document per user, seeded from their interests."""
        collection = mongo_client.get_collection("user_preferences")
        collection.delete_many({})

        category_names: List[str] = self.categories["name"].tolist()

        documents: List[Dict[str, Any]] = []
        for _, user in self.users.iterrows():
            min_price: int = random.randint(10, 30)
            documents.append({
                "user_id": user["id"],
                "interests": user["interests"],
                "preferred_categories": random.sample(
                    category_names, k=random.randint(1, 3)
                ),
                "price_range": {"min": min_price, "max": min_price + random.randint(50, 200)},
                "last_active": self._random_date(max_days_ago=90),
            })

        collection.insert_many(documents)
        print(f"Loaded {len(documents)} user preferences")

    def load_all(self) -> None:
        """Load all document collections and create indexes."""
        print("Creating indexes...")
        mongo_client.create_indexes()

        print("Loading reviews...")
        self.load_reviews()

        print("Loading product specs...")
        self.load_product_specs()

        print("Loading seller profiles...")
        self.load_seller_profiles()

        print("Loading user preferences...")
        self.load_user_preferences()

        print("Document data loading complete!")


if __name__ == "__main__":
    loader = DocumentLoader()
    loader.load_all()
