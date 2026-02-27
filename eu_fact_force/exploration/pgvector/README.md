# Exploration - postgreSQL - `pgvector` and `tsvector` 

## Local postgresSQL database using Docker
Run the following to start a local postgreSQL instance with pgvector.
```shell
docker run --name eu-fact-force-test -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=eu-fact-force-test -p 5432:5432 -d pgvector/pgvector:pg16
```

## Enable extensions
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## `pgvector`
https://github.com/pgvector/pgvector

## `tsvector`
https://www.postgresql.org/docs/current/datatype-textsearch.html