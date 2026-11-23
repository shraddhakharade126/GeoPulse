"""Validate the existing CSVs and load them idempotently into Snowflake."""

import argparse
import os
from pathlib import Path

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data"
DATABASE = "GEOPULSE_DB"
SCHEMA = "RAW"
WAREHOUSE = "GEOPULSE_WH"
UPLOAD_STAGE = f"{DATABASE}.{SCHEMA}.GEOPULSE_UPLOAD_STAGE"
LATITUDE_BOUNDS = (18.40, 18.65)
LONGITUDE_BOUNDS = (73.75, 74.00)
LOCATION_TYPES = {"Residential", "Commercial", "Office", "Shopping", "Transit"}


def require_columns(frame: pd.DataFrame, expected: list[str], filename: str) -> None:
    """Raise a clear error if a CSV has an unexpected schema."""
    if list(frame.columns) != expected:
        raise ValueError(
            f"{filename} columns must be {expected}, got {list(frame.columns)}."
        )
    if frame.isna().any().any():
        raise ValueError(f"{filename} contains missing values.")


def validate_coordinates(frame: pd.DataFrame, filename: str) -> None:
    """Ensure coordinates are in the simulated Pune area."""
    latitude_ok = frame["Latitude"].between(*LATITUDE_BOUNDS).all()
    longitude_ok = frame["Longitude"].between(*LONGITUDE_BOUNDS).all()
    if not latitude_ok or not longitude_ok:
        raise ValueError(f"{filename} contains coordinates outside the Pune bounds.")


def load_and_validate_sources() -> dict[str, pd.DataFrame]:
    """Read existing source files and validate their schemas and quality."""
    gps_path = DATA_DIRECTORY / "gps_pings.csv"
    stores_path = DATA_DIRECTORY / "store_locations.csv"
    zones_path = DATA_DIRECTORY / "commercial_zones.csv"
    for path in (gps_path, stores_path, zones_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required source CSV is missing: {path}")

    gps = pd.read_csv(gps_path)
    stores = pd.read_csv(stores_path)
    zones = pd.read_csv(zones_path)
    require_columns(
        gps,
        ["DeviceID", "Latitude", "Longitude", "Timestamp", "Location_Type"],
        gps_path.name,
    )
    require_columns(
        stores,
        ["StoreID", "StoreName", "Latitude", "Longitude"],
        stores_path.name,
    )
    require_columns(
        zones,
        ["ZoneID", "ZoneName", "Latitude", "Longitude", "Radius_Meters"],
        zones_path.name,
    )

    if len(gps) < 100_000 or gps["DeviceID"].nunique() < 10_000:
        raise ValueError("gps_pings.csv must contain at least 100,000 rows and devices.")
    if gps.duplicated().any():
        raise ValueError("gps_pings.csv contains duplicate records.")
    if gps.duplicated(subset=["DeviceID", "Timestamp"]).any():
        raise ValueError("gps_pings.csv repeats a device/timestamp key.")
    if not set(gps["Location_Type"]).issubset(LOCATION_TYPES):
        raise ValueError("gps_pings.csv contains an unsupported Location_Type.")
    timestamps = pd.to_datetime(
        gps["Timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    if timestamps.isna().any():
        raise ValueError("gps_pings.csv contains an invalid Timestamp.")

    validate_coordinates(gps, gps_path.name)
    validate_coordinates(stores, stores_path.name)
    validate_coordinates(zones, zones_path.name)
    if len(stores) != 12 or stores["StoreID"].duplicated().any():
        raise ValueError("store_locations.csv must contain 12 unique StoreIDs.")
    if len(zones) != 8 or zones["ZoneID"].duplicated().any():
        raise ValueError("commercial_zones.csv must contain 8 unique ZoneIDs.")
    if zones["Radius_Meters"].le(0).any():
        raise ValueError("commercial_zones.csv must have positive radii.")

    return {"gps": gps, "stores": stores, "zones": zones}


def print_source_summary(sources: dict[str, pd.DataFrame]) -> None:
    """Print locally validated counts without connecting to Snowflake."""
    gps = sources["gps"]
    print("Local source validation passed.")
    print(f"GPS pings: {len(gps):,} rows, {gps['DeviceID'].nunique():,} devices")
    print(f"Store locations: {len(sources['stores']):,} rows")
    print(f"Commercial zones: {len(sources['zones']):,} rows")
    print("Missing values: 0; duplicate GPS rows: 0")


def required_environment_variable(name: str) -> str:
    """Return a required setting without exposing its value."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and configure it."
        )
    return value


def create_connection() -> snowflake.connector.SnowflakeConnection:
    """Connect using browser SSO or environment-based password authentication."""
    authenticator = os.getenv("SNOWFLAKE_AUTHENTICATOR", "externalbrowser")
    options: dict[str, str] = {
        "account": required_environment_variable("SNOWFLAKE_ACCOUNT"),
        "user": required_environment_variable("SNOWFLAKE_USER"),
        "authenticator": authenticator,
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", WAREHOUSE),
        "database": os.getenv("SNOWFLAKE_DATABASE", DATABASE),
        "schema": os.getenv("SNOWFLAKE_SCHEMA", SCHEMA),
    }
    role = os.getenv("SNOWFLAKE_ROLE")
    if role:
        options["role"] = role
    if authenticator.lower() == "snowflake":
        options["password"] = required_environment_variable("SNOWFLAKE_PASSWORD")
    return snowflake.connector.connect(**options)


def put_source_file(
    cursor: snowflake.connector.cursor.SnowflakeCursor,
    path: Path,
    stage_directory: str,
) -> None:
    """Upload a CSV to its private folder in the configured internal stage."""
    file_uri = path.resolve().as_uri().replace("'", "''")
    cursor.execute(
        f"PUT '{file_uri}' @{UPLOAD_STAGE}/{stage_directory} "
        "AUTO_COMPRESS=TRUE OVERWRITE=TRUE"
    )
    results = cursor.fetchall()
    if not results or str(results[0][1]).upper() not in {"UPLOADED", "SKIPPED"}:
        raise RuntimeError(f"Snowflake did not upload {path.name}: {results}")


def execute_load_sql(
    cursor: snowflake.connector.cursor.SnowflakeCursor,
) -> None:
    """Run the small, semicolon-delimited load script in the active session."""
    script_path = PROJECT_ROOT / "snowflake" / "load_data.sql"
    sql_script = script_path.read_text(encoding="utf-8")
    for statement in sql_script.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)


def fetch_count(
    cursor: snowflake.connector.cursor.SnowflakeCursor, table_name: str
) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {DATABASE}.{SCHEMA}.{table_name}")
    result = cursor.fetchone()
    if result is None:
        raise RuntimeError(f"Snowflake returned no count for {table_name}.")
    return int(result[0])


def verify_loaded_data(
    cursor: snowflake.connector.cursor.SnowflakeCursor,
    sources: dict[str, pd.DataFrame],
) -> None:
    """Compare final Snowflake row counts and GEOGRAPHY values with the CSVs."""
    expected_counts = {
        "GPS_PINGS": len(sources["gps"]),
        "STORE_LOCATIONS": len(sources["stores"]),
        "COMMERCIAL_ZONES": len(sources["zones"]),
    }
    for table_name, expected_count in expected_counts.items():
        actual_count = fetch_count(cursor, table_name)
        if actual_count != expected_count:
            raise RuntimeError(
                f"{table_name} has {actual_count:,} rows; "
                f"the source CSV has {expected_count:,}."
            )
        print(f"{table_name}: {actual_count:,} rows (matches source)")

    cursor.execute(
        f"""
        SELECT COUNT(DISTINCT DEVICE_ID),
               COALESCE(COUNT_IF(GEO_LOCATION IS NULL), 0)
        FROM {DATABASE}.{SCHEMA}.GPS_PINGS
        """
    )
    gps_result = cursor.fetchone()
    expected_devices = sources["gps"]["DeviceID"].nunique()
    if gps_result is None or int(gps_result[0]) != expected_devices:
        raise RuntimeError("Snowflake GPS_PINGS unique-device count mismatches the CSV.")
    if int(gps_result[1]) != 0:
        raise RuntimeError("Snowflake GPS_PINGS contains NULL GEOGRAPHY points.")

    for table_name in ("STORE_LOCATIONS", "COMMERCIAL_ZONES"):
        cursor.execute(
            f"""
            SELECT COALESCE(COUNT_IF(GEO_LOCATION IS NULL), 0)
            FROM {DATABASE}.{SCHEMA}.{table_name}
            """
        )
        result = cursor.fetchone()
        if result is None or int(result[0]) != 0:
            raise RuntimeError(f"{table_name} contains NULL GEOGRAPHY points.")
    print(f"Unique GPS devices: {expected_devices:,}; NULL GEOGRAPHY points: 0")


def run_loader(validate_only: bool) -> None:
    """Validate local inputs, then optionally stage and merge them in Snowflake."""
    load_dotenv(PROJECT_ROOT / ".env")
    sources = load_and_validate_sources()
    print_source_summary(sources)
    if validate_only:
        print("Validation-only mode: no Snowflake connection was attempted.")
        return

    csv_paths = {
        "gps_pings": DATA_DIRECTORY / "gps_pings.csv",
        "store_locations": DATA_DIRECTORY / "store_locations.csv",
        "commercial_zones": DATA_DIRECTORY / "commercial_zones.csv",
    }
    connection = create_connection()
    try:
        cursor = connection.cursor()
        try:
            for stage_directory, path in csv_paths.items():
                put_source_file(cursor, path, stage_directory)
            execute_load_sql(cursor)

            expected_stage_counts = {
                "GPS_PINGS_LOAD": len(sources["gps"]),
                "STORE_LOCATIONS_LOAD": len(sources["stores"]),
                "COMMERCIAL_ZONES_LOAD": len(sources["zones"]),
            }
            for table_name, expected_count in expected_stage_counts.items():
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                result = cursor.fetchone()
                if result is None or int(result[0]) != expected_count:
                    actual_count = None if result is None else int(result[0])
                    raise RuntimeError(
                        f"{table_name} has {actual_count} rows after COPY; "
                        f"expected {expected_count}."
                    )

            verify_loaded_data(cursor, sources)
        finally:
            cursor.close()
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate GeoPulse CSVs and load them into Snowflake."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate local CSVs without connecting to Snowflake.",
    )
    arguments = parser.parse_args()
    run_loader(validate_only=arguments.validate_only)


if __name__ == "__main__":
    main()
