"""
PGP Excel ingestion script

Reads all sheets from the PGP export file and loads them into PostgreSQL.
Tables are created automatically in the raw schema.

Each ingestion adds a snapshot_date so historical data is preserved.
If the script runs multiple times the same day, duplicates are avoided.
"""

import pandas as pd
import psycopg2
from psycopg2 import sql
from datetime import date
import re

# =========================
# Configuration
# =========================

FILE_PATH = "data/PGP x D4G- Exported Vaccine Data.xlsx"

DB_CONFIG = {
    "host": "localhost",
    "port": "5432",   # Change docker postgres port
    "dbname": "eu_fact_force",
    "user": "eu_fact_force",
    "password": "eu_fact_force"
}

RAW_SCHEMA = "raw"


# =========================
# Helper functions
# =========================

def clean_name(name):
    """
    Clean sheet and column names so they are valid SQL identifiers.
    """
    name = name.lower()
    name = name.replace("%", "percent")
    name = re.sub(r"[^\w]+", "_", name)
    return name.strip("_")


def create_schema(cursor):
    """
    Ensure schemas exist.
    """
    cursor.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    cursor.execute("CREATE SCHEMA IF NOT EXISTS analytics;")


def create_table_if_not_exists(cursor, table_name, columns):
    """
    Create table dynamically from dataframe columns.
    """

    column_defs = []

    for col in columns:
        column_defs.append(sql.SQL("{} TEXT").format(sql.Identifier(col)))

    column_defs.append(sql.SQL("snapshot_date DATE"))

    query = sql.SQL("""
        CREATE TABLE IF NOT EXISTS {}.{} (
            id SERIAL PRIMARY KEY,
            {}
        )
    """).format(
        sql.Identifier(RAW_SCHEMA),
        sql.Identifier(table_name),
        sql.SQL(", ").join(column_defs)
    )

    cursor.execute(query)


def insert_dataframe(cursor, table_name, df):
    """
    Insert dataframe rows into PostgreSQL.
    """

    cols = list(df.columns)
    cols.append("snapshot_date")

    insert_query = sql.SQL("""
        INSERT INTO {}.{} ({})
        VALUES ({})
    """).format(
        sql.Identifier(RAW_SCHEMA),
        sql.Identifier(table_name),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        sql.SQL(", ").join(sql.Placeholder() * len(cols))
    )

    snapshot = date.today()

    for _, row in df.iterrows():
        values = [str(v) if pd.notna(v) else None for v in row.tolist()]
        values.append(snapshot)
        cursor.execute(insert_query, values)


# =========================
# Main ingestion process
# =========================

def ingest_excel():

    print("Reading Excel file...")

    xls = pd.ExcelFile(FILE_PATH)
    sheets = xls.sheet_names

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    create_schema(cursor)

    for sheet in sheets:

        print(f"Ingesting sheet: {sheet}")

        df = pd.read_excel(FILE_PATH, sheet_name=sheet)

        # clean column names
        df.columns = [clean_name(c) for c in df.columns]

        table_name = clean_name(sheet)

        create_table_if_not_exists(cursor, table_name, df.columns)

        insert_dataframe(cursor, table_name, df)

        conn.commit()

    cursor.close()
    conn.close()

    print("Ingestion complete.")


# =========================

if __name__ == "__main__":
    ingest_excel()