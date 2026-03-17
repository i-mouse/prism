import os
from psycopg_pool import AsyncConnectionPool

def create_db_connection_pool() -> AsyncConnectionPool:
    host     = os.environ["TENDER_DB_HOST"]
    port     = os.environ.get("TENDER_DB_PORT", "5432")
    dbname   = os.environ["TENDER_DB_DATABASENAME"]
    user     = os.environ["TENDER_DB_USERNAME"]
    password = os.environ["TENDER_DB_PASSWORD"]

    conninfo = f"host={host} port={port} dbname={dbname} user={user} password={password}"
    print(f"✅ Connecting to: {host}:{port}/{dbname}", flush=True)

    return AsyncConnectionPool(conninfo=conninfo, min_size=1, max_size=10, open=False)