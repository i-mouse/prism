"""
query_live_db.py — one-off diagnostic queries against the live Azure
Postgres Flexible Server, using Entra ID (passwordless) auth.

Drop this into Prism.PythonService/scripts/ in the repo.

Requires you to be logged in via `az login` (or any source
DefaultAzureCredential recognizes) before running. Targets the LIVE
server only — it never touches the local Aspire-managed Postgres.

Usage:
    python scripts/query_live_db.py -q "SELECT * FROM paper_claims LIMIT 5;"
    python scripts/query_live_db.py -f queries/check_evidence.sql
    python scripts/query_live_db.py -q "DELETE FROM ..." --allow-write

Dependencies: psycopg, azure-identity. Check they're in
pyproject.toml/requirements before assuming they're installed — if
`azure-identity` is missing: pip install azure-identity
"""
import argparse
import re
import sys

import psycopg
from azure.identity import DefaultAzureCredential

# --- Fixed for this project. Update if the server/db name ever changes. ---
DB_HOST = "postgres-udnvqoy3me2bs.postgres.database.azure.com"
DB_NAME = "prism-db"
DB_USER = "nitin8764_live.com#EXT#@nitin8764live.onmicrosoft.com"
TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def get_token() -> str:
    """Fetch a fresh Entra token. Short-lived (~1hr) - fine since this
    script is short-lived too; no need to cache across runs."""
    credential = DefaultAzureCredential()
    return credential.get_token(TOKEN_SCOPE).token


def run_query(sql: str, allow_write: bool) -> None:
    match = WRITE_KEYWORDS.search(sql)
    if match and not allow_write:
        print(
            f"Refusing to run a query that looks like a write "
            f"(matched: {match.group()}).\n"
            "Pass --allow-write if this is intentional.",
            file=sys.stderr,
        )
        sys.exit(1)

    token = get_token()
    with psycopg.connect(
        host=DB_HOST,
        port=5432,
        dbname=DB_NAME,
        user=DB_USER,
        password=token,
        sslmode="require",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                print(f"OK - {cur.rowcount} rows affected.")
                return
            cols = [desc.name for desc in cur.description]
            header = " | ".join(cols)
            print(header)
            print("-" * len(header))
            for row in cur.fetchall():
                print(" | ".join(str(v) for v in row))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-q", "--query", help="SQL query text")
    group.add_argument("-f", "--file", help="Path to a .sql file")
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Allow INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/GRANT/REVOKE statements",
    )
    args = parser.parse_args()

    if args.query:
        sql = args.query
    else:
        with open(args.file, encoding="utf-8") as f:
            sql = f.read()

    run_query(sql, args.allow_write)


if __name__ == "__main__":
    main()
