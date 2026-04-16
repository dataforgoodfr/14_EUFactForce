"""Cosine-similarity search for the Dash app (standalone, no Django ORM)."""

import os
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

QUERY_PREFIX = "query: "
MODEL_ID = "intfloat/multilingual-e5-base"
_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(MODEL_ID)
    return _MODEL


def embed_query(query: str) -> list[float]:
    model = _get_model()
    vector = model.encode(
        [f"{QUERY_PREFIX}{query.strip()}"],
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    out = vector[0]
    return out.tolist() if hasattr(out, "tolist") else list(out)


def _connect():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL is not set")
    p = urlparse(db_url)
    return psycopg2.connect(
        dbname=p.path.lstrip("/"),
        user=p.username,
        password=p.password,
        host=p.hostname,
        port=p.port or 5432,
    )


def search_chunks(query: str, k: int = 10) -> list[dict]:
    """Return top-k chunks ranked by cosine similarity to *query*."""
    vector = embed_query(query)
    vector_literal = f"[{','.join(str(x) for x in vector)}]"
    sql = """
        SELECT
            c.id,
            c.content,
            c."order",
            d.id,
            d.title,
            d.doi,
            1 - (c.embedding <=> %(vec)s::vector) AS similarity
        FROM ingestion_documentchunk c
        JOIN ingestion_document d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> %(vec)s::vector
        LIMIT %(k)s
    """
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, {"vec": vector_literal, "k": k})
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "rank": i + 1,
            "chunk_id": row[0],
            "content": row[1],
            "order": row[2],
            "doc_id": row[3],
            "doc_title": row[4],
            "doi": row[5] or "",
            "similarity": round(float(row[6]), 4),
        }
        for i, row in enumerate(rows)
    ]
