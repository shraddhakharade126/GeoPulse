"""Verify a Snowflake connection using environment-based settings."""

import os

import snowflake.connector


def required_environment_variable(name: str) -> str:
    """Return a required environment variable or explain how to set it."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Follow the setup instructions in snowflake/README.md."
        )
    return value


def main() -> None:
    """Connect to Snowflake and print the active session context."""
    authenticator = os.getenv("SNOWFLAKE_AUTHENTICATOR", "externalbrowser")
    connection_options = {
        "account": required_environment_variable("SNOWFLAKE_ACCOUNT"),
        "user": required_environment_variable("SNOWFLAKE_USER"),
        "authenticator": authenticator,
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "GEOPULSE_WH"),
        "database": os.getenv("SNOWFLAKE_DATABASE", "GEOPULSE_DB"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", "RAW"),
    }

    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        connection_options["role"] = role

    if authenticator.lower() == "snowflake":
        connection_options["password"] = required_environment_variable(
            "SNOWFLAKE_PASSWORD"
        )

    connection = snowflake.connector.connect(**connection_options)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_ROLE(),
                       CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA()
                """
            )
            session = cursor.fetchone()
            if session is None:
                raise RuntimeError("Snowflake returned no session details.")
            print("Snowflake connection successful.")
            print(
                "Account, user, role, warehouse, database, schema: "
                f"{session}"
            )
        finally:
            cursor.close()
    finally:
        connection.close()


if __name__ == "__main__":
    main()
