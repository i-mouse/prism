from psycopg_pool import AsyncConnectionPool
from config import settings


def _local_conninfo() -> str:
    """Local (RunAsContainer) Postgres uses a real username/password."""
    return (
        f"host={settings.prism_db_host} port={settings.prism_db_port} "
        f"dbname={settings.prism_db_databasename} user={settings.prism_db_username} "
        f"password={settings.prism_db_password}"
    )


def create_db_connection_pool() -> AsyncConnectionPool:
    print(f"[OK] Connecting to: {settings.prism_db_host}:{settings.prism_db_port}/{settings.prism_db_databasename}", flush=True)

    if settings.prism_db_password is not None:
        return AsyncConnectionPool(conninfo=_local_conninfo(), min_size=1, max_size=10, open=False)

    # Deployed Azure Postgres Flexible Server is Entra-only (no password exists) -
    # prism_db_password is unset there. AsyncEntraConnection fetches a fresh Managed
    # Identity access token per connection (not once at pool creation), so tokens stay
    # valid across psycopg_pool's default hourly connection recycling (max_lifetime).
    from azure.identity.aio import DefaultAzureCredential
    from azure_postgresql_auth.psycopg3 import AsyncEntraConnection

    conninfo = (
        f"host={settings.prism_db_host} port={settings.prism_db_port} "
        f"dbname={settings.prism_db_databasename} user={settings.prism_db_username} "
        f"sslmode=require"
    )
    return AsyncConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=10,
        open=False,
        connection_class=AsyncEntraConnection,
        kwargs={"credential": DefaultAzureCredential()},
    )
