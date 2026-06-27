def semantic_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search products using semantic similarity."""
    # Generate embedding for search query
    query_embedding = self.model.encode(query)

    # Find similar products using pgvector
    with db.get_cursor() as cursor:
        cursor.execute(
            """
            SELECT p.*,
                   1 - (pe.embedding <=> %s::vector) as similarity
            FROM products p
            JOIN product_embeddings pe ON p.id = pe.product_id
            ORDER BY pe.embedding <=> %s::vector
            LIMIT %s;
            """,
            (query_embedding.tolist(), query_embedding.tolist(), limit),
        )
        return cursor.fetchall()
