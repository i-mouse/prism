import os
from psycopg_pool import AsyncConnectionPool

def create_db_connection_pool() -> AsyncConnectionPool:
    host     = os.environ["PRISM_DB_HOST"]
    port     = os.environ.get("PRISM_DB_PORT", "5432")
    dbname   = os.environ["PRISM_DB_DATABASENAME"]
    user     = os.environ["PRISM_DB_USERNAME"]
    password = os.environ["PRISM_DB_PASSWORD"]

    conninfo = f"host={host} port={port} dbname={dbname} user={user} password={password}"
    print(f"✅ Connecting to: {host}:{port}/{dbname}", flush=True)

    return AsyncConnectionPool(conninfo=conninfo, min_size=1, max_size=10, open=False)