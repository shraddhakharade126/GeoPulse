"""Join prepared GPS points to the existing 500-meter store catchments."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import abs as spark_abs
from pyspark.sql.functions import col, expr
from pyspark.sql.types import StringType, StructField, StructType
from sedona.spark import SedonaContext

from prepare_spatial_data import OUTPUT_DIRECTORY as DAY2_OUTPUT_DIRECTORY
from prepare_spatial_data import create_sedona_session


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GPS_INPUT = DAY2_OUTPUT_DIRECTORY / "gps_pings"
CATCHMENTS_INPUT = PROJECT_ROOT / "output" / "day3" / "store_catchments.geojson"
OUTPUT_DIRECTORY = PROJECT_ROOT / "outputs"
MATCHES_PARQUET = OUTPUT_DIRECTORY / "gps_store_matches.parquet"
MATCHES_CSV = OUTPUT_DIRECTORY / "gps_store_matches.csv"
SUMMARY_JSON = OUTPUT_DIRECTORY / "gps_store_matches_summary.json"
EXPECTED_STORE_COUNT = 12
GPS_COLUMNS = ["DeviceID", "Latitude", "Longitude", "Timestamp", "Location_Type"]
PING_KEY = ["DeviceID", "Timestamp"]


def require_path(path: Path, description: str) -> None:
    """Raise an actionable setup error when a required Day 2/Day 3 input is absent."""
    if not path.exists():
        raise FileNotFoundError(
            f"{description} not found: {path}. Run the Day 2 and Day 3 pipelines "
            "first; this task does not regenerate GPS data or catchments."
        )


def read_catchments(spark: SparkSession) -> DataFrame:
    """Read the Day 3 GeoJSON feature collection with its RFC 7946 WGS84 CRS."""
    with CATCHMENTS_INPUT.open("r", encoding="utf-8") as geojson_file:
        feature_collection = json.load(geojson_file)

    if not isinstance(feature_collection, dict):
        raise ValueError(f"{CATCHMENTS_INPUT} must contain a JSON object.")
    if feature_collection.get("type") != "FeatureCollection":
        raise ValueError(f"{CATCHMENTS_INPUT} must contain a GeoJSON FeatureCollection.")
    declared_crs = feature_collection.get("crs")
    if declared_crs:
        crs_properties = (
            declared_crs.get("properties")
            if isinstance(declared_crs, dict)
            else None
        )
        crs_name = (
            crs_properties.get("name", "").upper()
            if isinstance(crs_properties, dict)
            else ""
        )
        if crs_name not in {
            "EPSG:4326",
            "OGC:CRS84",
            "URN:OGC:DEF:CRS:OGC:1.3:CRS84",
        }:
            raise ValueError(
                f"Catchment GeoJSON declares unsupported CRS {crs_name!r}; "
                "expected WGS84/EPSG:4326."
            )
    features = feature_collection.get("features")
    if not isinstance(features, list):
        raise ValueError("Catchment GeoJSON has no feature list.")

    records: list[tuple[Optional[str], Optional[str], Optional[str]]] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError(f"Catchment feature {index} is not a GeoJSON Feature.")
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry")
        if not isinstance(properties, dict):
            raise ValueError(f"Catchment feature {index} has invalid properties.")
        store_id = properties.get("store_id")
        store_name = properties.get("store_name")
        if not store_id or not store_name or not isinstance(geometry, dict):
            raise ValueError(
                f"Catchment feature {index} must have store_id, store_name, and geometry."
            )
        records.append((str(store_id), str(store_name), json.dumps(geometry)))

    if len(records) != EXPECTED_STORE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_STORE_COUNT} store catchments, found {len(records)}."
        )
    store_ids = [record[0] for record in records]
    if len(set(store_ids)) != EXPECTED_STORE_COUNT:
        raise ValueError("Catchment GeoJSON contains duplicate or missing store IDs.")

    schema = StructType(
        [
            StructField("StoreID", StringType(), nullable=False),
            StructField("StoreName", StringType(), nullable=False),
            StructField("geometry_json", StringType(), nullable=False),
        ]
    )
    catchments = spark.createDataFrame(records, schema=schema).withColumn(
        "catchment_geometry",
        expr("ST_SetSRID(ST_GeomFromGeoJSON(geometry_json), 4326)"),
    )

    invalid_count = catchments.filter(
        col("catchment_geometry").isNull()
        | (expr("ST_IsValid(catchment_geometry)") != True)
        | (expr("ST_GeometryType(catchment_geometry)") != "ST_Polygon")
        | (expr("ST_SRID(catchment_geometry)") != 4326)
    ).count()
    if invalid_count:
        raise ValueError(
            f"{invalid_count} catchment features are invalid or not WGS84 polygons."
        )
    return catchments.select("StoreID", "StoreName", "catchment_geometry")


def prepare_gps(gps: DataFrame) -> DataFrame:
    """Check Day 2 schema and label point geometries with the WGS84 SRID."""
    missing_columns = set(GPS_COLUMNS + ["geometry"]) - set(gps.columns)
    if missing_columns:
        raise ValueError(
            f"Prepared GPS Parquet is missing required columns: "
            f"{sorted(missing_columns)}."
        )
    if gps.count() == 0:
        raise ValueError("Prepared GPS Parquet contains no records.")

    null_geometry_count = gps.filter(col("geometry").isNull()).count()
    if null_geometry_count:
        raise ValueError(
            f"Prepared GPS Parquet has {null_geometry_count} NULL geometries."
        )

    duplicate_ping_keys = (
        gps.groupBy(*PING_KEY).count().filter(col("count") != 1).count()
    )
    if duplicate_ping_keys:
        raise ValueError(
            f"Prepared GPS Parquet has {duplicate_ping_keys} duplicate "
            "DeviceID/Timestamp ping keys."
        )

    # Day 2 writes WGS84 point coordinates; attach the CRS metadata before the join.
    prepared = gps.withColumn(
        "geometry", expr("ST_SetSRID(geometry, 4326)")
    )
    mismatched_srid = prepared.filter(expr("ST_SRID(geometry) != 4326")).count()
    if mismatched_srid:
        raise ValueError(f"{mismatched_srid} GPS points are not in EPSG:4326.")
    coordinate_mismatches = prepared.filter(
        (spark_abs(expr("ST_X(geometry) - Longitude")) > 1e-9)
        | (spark_abs(expr("ST_Y(geometry) - Latitude")) > 1e-9)
    ).count()
    if coordinate_mismatches:
        raise ValueError(
            f"{coordinate_mismatches} GPS geometries do not match their "
            "longitude/latitude columns."
        )
    return prepared


def write_matches_csv(matches: DataFrame) -> None:
    """Write one CSV file at the requested path, with geometry represented as WKT."""
    csv_columns = [
        *GPS_COLUMNS,
        "StoreID",
        "StoreName",
        expr("ST_AsText(geometry)").alias("geometry_wkt"),
    ]
    csv_frame = matches.select(*csv_columns).coalesce(1)
    with tempfile.TemporaryDirectory(
        prefix=".gps_store_matches_", dir=OUTPUT_DIRECTORY
    ) as temporary_directory:
        csv_frame.write.option("header", "true").mode("overwrite").csv(
            temporary_directory
        )
        part_files = list(Path(temporary_directory).glob("part-*.csv"))
        if len(part_files) != 1:
            raise RuntimeError(
                f"Expected one Spark CSV part file, found {len(part_files)}."
            )
        os.replace(str(part_files[0]), str(MATCHES_CSV))


def get_store_ping_counts(
    catchments: DataFrame, matches: DataFrame
) -> list[dict[str, Any]]:
    """Return a count for every store, including stores with no matched pings."""
    store_counts = matches.groupBy("StoreID", "StoreName").count().withColumnRenamed(
        "count", "ping_count"
    )
    rows = (
        catchments.select("StoreID", "StoreName")
        .join(store_counts, ["StoreID", "StoreName"], "left")
        .fillna({"ping_count": 0})
        .orderBy("StoreID")
        .collect()
    )
    return [
        {
            "store_id": row["StoreID"],
            "store_name": row["StoreName"],
            "ping_count": int(row["ping_count"]),
        }
        for row in rows
    ]


def write_parquet(matches: DataFrame) -> None:
    """Persist all matching GPS/store rows in a Spark Parquet dataset."""
    matches.write.mode("overwrite").parquet(str(MATCHES_PARQUET))


def main() -> None:
    """Run the Sedona point-in-polygon join and save match and validation outputs."""
    require_path(GPS_INPUT, "Day 2 GPS Parquet")
    require_path(CATCHMENTS_INPUT, "Day 3 store catchment GeoJSON")
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    spark: SparkSession = create_sedona_session("GeoPulse-Day4-GPS-Store-Join")
    try:
        SedonaContext.create(spark)
        gps = prepare_gps(spark.read.parquet(str(GPS_INPUT)))
        catchments = read_catchments(spark)

        gps_count = gps.count()
        # Both inputs are explicitly tagged EPSG:4326. GeoJSON is RFC 7946 WGS84.
        matches = gps.alias("gps").join(
            catchments.alias("store"),
            expr("ST_Contains(store.catchment_geometry, gps.geometry)"),
            "inner",
        ).select(
            *[col(f"gps.{column}") for column in GPS_COLUMNS],
            col("gps.geometry").alias("geometry"),
            col("store.StoreID").alias("StoreID"),
            col("store.StoreName").alias("StoreName"),
        )

        total_matches = matches.count()
        matched_points = matches.select(*PING_KEY).distinct().count()
        unmatched_points = gps_count - matched_points
        multi_store_points = (
            matches.groupBy(*PING_KEY)
            .count()
            .filter(col("count") > 1)
            .count()
        )
        unmatched_frame = gps.alias("gps").join(
            catchments.alias("store"),
            expr("ST_Contains(store.catchment_geometry, gps.geometry)"),
            "left_anti",
        )
        actual_unmatched = unmatched_frame.count()
        if actual_unmatched != unmatched_points:
            raise RuntimeError(
                "Unmatched count does not reconcile: "
                f"left-anti={actual_unmatched}, total-minus-matched={unmatched_points}."
            )

        store_ping_counts = get_store_ping_counts(catchments, matches)
        write_parquet(matches)
        write_matches_csv(matches)

        summary = {
            "total_gps_points": gps_count,
            "matched_gps_points": matched_points,
            "unmatched_gps_points": unmatched_points,
            "total_matches": total_matches,
            "points_matching_multiple_stores": multi_store_points,
            "extra_matches_from_multiple_catchments": total_matches - matched_points,
            "coordinate_reference_system": "EPSG:4326",
            "spatial_predicate": "ST_Contains(catchment_polygon, gps_point)",
            "store_wise_ping_counts": store_ping_counts,
        }
        with SUMMARY_JSON.open("w", encoding="utf-8") as summary_file:
            json.dump(summary, summary_file, indent=2)
            summary_file.write("\n")

        print("GPS-to-store spatial join completed.")
        print(f"Total GPS points: {gps_count:,}")
        print(f"Matched GPS points: {matched_points:,}")
        print(f"Unmatched GPS points: {unmatched_points:,}")
        print(f"Total GPS/store matches: {total_matches:,}")
        print(f"Points matched to multiple stores: {multi_store_points:,}")
        print(f"Extra matches due to overlapping catchments: {total_matches - matched_points:,}")
        print("Store-wise ping counts:")
        for store in store_ping_counts:
            print(
                f"  {store['store_id']} | {store['store_name']} | "
                f"{store['ping_count']:,}"
            )
        print(f"Parquet: {MATCHES_PARQUET}")
        print(f"CSV: {MATCHES_CSV}")
        print(f"Validation summary: {SUMMARY_JSON}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
