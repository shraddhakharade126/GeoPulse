"""Test Snowflake connectivity without creating or loading any project data."""

import os
from pathlib import Path

import snowflake.connector
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require_environment_variable(name: str) -> str:
    """Return a required setting or raise a beginner-friendly setup error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill in "
            "the placeholder values."
        )
    return value


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    authenticator = os.getenv("SNOWFLAKE_AUTHENTICATOR", "externalbrowser")
    connection_options: dict[str, str] = {
        "account": require_environment_variable("SNOWFLAKE_ACCOUNT"),
        "user": require_environment_variable("SNOWFLAKE_USER"),
        "authenticator": authenticator,
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "GEOPULSE_WH"),
        "database": os.getenv("SNOWFLAKE_DATABASE", "GEOPULSE_DB"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "RAW"),
    }

    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        connection_options["role"] = role

    if authenticator.lower() == "snowflake":
        connection_options["password"] = require_environment_variable(
            "SNOWFLAKE_PASSWORD"
        )

    connection = snowflake.connector.connect(**connection_options)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT CURRENT_ACCOUNT(),
                       CURRENT_USER(),
                       CURRENT_ROLE(),
                       CURRENT_WAREHOUSE(),
                       CURRENT_DATABASE(),
                       CURRENT_SCHEMA()
                """
            )
            session = cursor.fetchone()
            if session is None:
                raise RuntimeError("Snowflake returned no session details.")

            print("Snowflake connection successful.")
            print(
                "Account, user, role, warehouse, database, schema:"
                f" {session}"
            )
        finally:
            cursor.close()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
