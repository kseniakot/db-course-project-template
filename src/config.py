"""Configuration management for ArtisanMarket."""

import os
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "raw_data"


class PostgresConfig(TypedDict):
    host: str
    port: int
    database: str
    user: str
    password: str


class MongoConfig(TypedDict):
    uri: str
    database: str


class RedisConfig(TypedDict):
    host: str
    port: int
    db: int
    decode_responses: bool


class Neo4jConfig(TypedDict):
    uri: str
    user: str
    password: str


# Database configurations
POSTGRES_CONFIG: PostgresConfig = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", 5432)),
    "database": os.getenv("POSTGRES_DB", "artisan_market"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "password"),
}

MONGO_CONFIG: MongoConfig = {
    "uri": os.getenv("MONGO_URI", "mongodb://localhost:27017/"),
    "database": os.getenv("MONGO_DB", "artisan_market"),
}

REDIS_CONFIG: RedisConfig = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", 6379)),
    "db": int(os.getenv("REDIS_DB", 0)),
    "decode_responses": True,
}

NEO4J_CONFIG: Neo4jConfig = {
    "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "user": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "password"),
}

# Cache settings
CACHE_TTL: int = 3600  # 1 hour
CART_TTL: int = 86400  # 24 hours
CACHE_METRICS_TTL = 86400
RECOMMENDATIONS_TTL: int = 300 # 5 minutes
HOT_PRODUCTS_TTL =  7 * 60 * 60 * 24 # 7 days


# Rate limiting
RATE_LIMIT_REQUESTS: int = 100
RATE_LIMIT_WINDOW: int = 60  # seconds

