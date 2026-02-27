import pandas as pd
import psycopg2
from sentence_transformers import SentenceTransformer

# Postgres connection and utils
local_db_credentials = {
    "database": "eu-fact-force-test",
    "user": "user",
    "password": "password",
    "host": "localhost",
    "port": 5432,
}
connection = psycopg2.connect(**local_db_credentials)


def execute(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()


def query(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        records = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
    connection.commit()
    return pd.DataFrame(records, columns=cols)


# Search functions
def dense_search(input_vector, distance="cosine", n=5):
    if distance == "euclidean":
        sql = f"""
        SELECT id, content, dense_vector <-> '{input_vector}' as distance, rank() over (order by dense_vector <-> '{input_vector}') FROM vector_store ORDER BY dense_vector <-> '{input_vector}' LIMIT {n};
        """
    elif distance == "cosine":
        sql = f"""
        SELECT id, content, dense_vector <=> '{input_vector}' as distance, rank() over (order by dense_vector <=> '{input_vector}')  FROM vector_store ORDER BY dense_vector <=> '{input_vector}' LIMIT {n};
        """
    else:
        raise NotImplemented(f"Unknown distance: {distance}")

    return query(sql)


def sparse_search(input, n=5):
    sql = f"""
        SELECT id, content, ts_rank_cd(sparse_vector, query) AS similarity, rank() over (ORDER BY ts_rank_cd(sparse_vector, query) DESC) FROM vector_store, to_tsquery('{input}') query
        WHERE query @@ sparse_vector
        ORDER BY similarity DESC
        LIMIT {n};"""
    return query(sql)


# Hybrid search - reciprocal rank fusion
def rrf_results(dense_df, sparse_df, alpha=60, n=5):
    dense_df["score_rrf"] = 1 / (alpha + dense_df["rank"])
    sparse_df["score_rrf"] = 1 / (alpha + sparse_df["rank"])

    combined = pd.concat(
        [
            dense_df.loc[:, ["id", "content", "score_rrf"]],
            sparse_df.loc[:, ["id", "content", "score_rrf"]],
        ],
        ignore_index=True,
    )

    # Sum RRF scores for chunks appearing in multiple sources
    rrf_agg = (
        combined.groupby("id", as_index=False)
        .agg({"score_rrf": "sum", "content": "first"})
        .sort_values("score_rrf", ascending=False)
        .rename(columns={"score_rrf": "score"})
        .head(n)
    )
    return rrf_agg
