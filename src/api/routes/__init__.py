"""Aggregate all database-scoped routers."""

from src.api.routes import mongodb, neo4j, pgvector, postgres, redis

routers = [
    postgres.router,
    pgvector.router,
    redis.router,
    neo4j.router,
    mongodb.router,
]
