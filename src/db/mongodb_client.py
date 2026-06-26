"""MongoDB connection and utilities."""

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database

from src.config import MONGO_CONFIG


class MongoDBClient:
    def __init__(self):
        self.client = MongoClient(MONGO_CONFIG["uri"])
        self.db: Database = self.client[MONGO_CONFIG["database"]]

    def get_collection(self, name: str):
        """Get a MongoDB collection."""
        return self.db[name]

    def create_indexes(self):
        """Create necessary indexes."""

        reviews = self.get_collection("reviews")
        reviews.create_index([("product_id", ASCENDING)])
        reviews.create_index([("user_id", ASCENDING)])
        reviews.create_index([("helpful_votes", DESCENDING)])
        reviews.create_index([("product_id", ASCENDING), ("rating", DESCENDING)])

        product_specs = self.get_collection("product_specs")
        product_specs.create_index([("product_id", ASCENDING)], unique=True)
        product_specs.create_index([("category", ASCENDING)])
        product_specs.create_index([("specs.material", ASCENDING)])

        seller_profiles = self.get_collection("seller_profiles")
        seller_profiles.create_index([("seller_id", ASCENDING)], unique=True)
        seller_profiles.create_index([("rating", ASCENDING)])

        user_preferences = self.get_collection("user_preferences")
        user_preferences.create_index([("user_id", ASCENDING)], unique=True)


     

# Singleton instance
mongo_client = MongoDBClient()
