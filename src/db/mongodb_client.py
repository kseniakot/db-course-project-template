"""MongoDB connection and utilities."""

from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from src.config import MONGO_CONFIG


class MongoDBClient:
    def __init__(self) -> None:
        self.client: MongoClient[Any] = MongoClient(MONGO_CONFIG["uri"], maxPoolSize=50)
        self.db: Database[Any] = self.client[MONGO_CONFIG["database"]]

    def get_collection(self, name: str) -> Collection[Any]:
        """Get a MongoDB collection.

        Args:
            name: Collection name

        Returns:
            MongoDB collection object
        """
        return self.db[name]

    def create_indexes(self) -> None:
        """Create necessary indexes for collections."""
        reviews: Collection[Any] = self.get_collection("reviews")
        reviews.create_index([("product_id", ASCENDING)])
        reviews.create_index([("user_id", ASCENDING)])
        reviews.create_index([("helpful_votes", DESCENDING)])
        reviews.create_index([("product_id", ASCENDING), ("rating", DESCENDING)])

        product_specs: Collection[Any] = self.get_collection("product_specs")
        product_specs.create_index([("product_id", ASCENDING)], unique=True)
        product_specs.create_index([("category", ASCENDING)])
        product_specs.create_index([("specs.material", ASCENDING)])

        seller_profiles: Collection[Any] = self.get_collection("seller_profiles")
        seller_profiles.create_index([("seller_id", ASCENDING)], unique=True)
        seller_profiles.create_index([("rating", ASCENDING)])

        user_preferences: Collection[Any] = self.get_collection("user_preferences")
        user_preferences.create_index([("user_id", ASCENDING)], unique=True)


mongo_client: MongoDBClient = MongoDBClient()
