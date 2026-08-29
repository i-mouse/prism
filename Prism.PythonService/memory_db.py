from psycopg_pool import AsyncConnectionPool
from config import settings

def create_db_connection_pool() -> AsyncConnectionPool:
    conninfo = (
        f"host={settings.prism_db_host} port={settings.prism_db_port} "
        f"dbname={settings.prism_db_databasename} user={settings.prism_db_username} "
        f"password={settings.prism_db_password}"
    )
    print(f"[OK] Connecting to: {settings.prism_db_host}:{settings.prism_db_port}/{settings.prism_db_databasename}", flush=True)

    return AsyncConnectionPool(conninfo=conninfo, min_size=1, max_size=10, open=False)
