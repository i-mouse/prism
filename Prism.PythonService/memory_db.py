from psycopg_pool import AsyncConnectionPool
from config import settings

# Azure Postgres Flexible Server AAD token scope (docs: "Connect with Managed
# Identity in Azure Database for PostgreSQL flexible server").
_AAD_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


def _resolve_password() -> str:
    """Local (RunAsContainer) Postgres uses a real password. The deployed Azure
    Postgres Flexible Server is Entra-only (no password exists) - prism_db_password
    is unset there, so fall back to a Managed Identity access token used as the
    password, same mechanism the C# side gets for free via Npgsql/DefaultAzureCredential.

    Known limitation: the token is fetched once per pool creation, not refreshed on a
    schedule - fine for this container's lifetime today, but a connection opened after
    the token's ~1hr expiry (e.g. the pool growing under load, or a connection recycling
    long after startup) would fail. Acceptable for the current single-replica, low-churn
    deployment; a real fix needs a per-connection token provider.
    """
    if settings.prism_db_password is not None:
        return settings.prism_db_password

    from azure.identity import DefaultAzureCredential
    return DefaultAzureCredential().get_token(_AAD_TOKEN_SCOPE).token


def create_db_connection_pool() -> AsyncConnectionPool:
    password = _resolve_password()
    sslmode = " sslmode=require" if settings.prism_db_password is None else ""
    conninfo = (
        f"host={settings.prism_db_host} port={settings.prism_db_port} "
        f"dbname={settings.prism_db_databasename} user={settings.prism_db_username} "
        f"password={password}{sslmode}"
    )
    print(f"[OK] Connecting to: {settings.prism_db_host}:{settings.prism_db_port}/{settings.prism_db_databasename}", flush=True)

    return AsyncConnectionPool(conninfo=conninfo, min_size=1, max_size=10, open=False)
