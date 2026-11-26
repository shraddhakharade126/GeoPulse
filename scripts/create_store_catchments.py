"""Create and validate 500-meter WGS84 store catchments using Sedona."""

import csv
import json
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, expr, lit, sum as spark_sum, when
from sedona.spark import SedonaContext

from prepare_spatial_data import (
    OUTPUT_DIRECTORY as DAY2_OUTPUT_DIRECTORY,
    create_sedona_session,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DAY3_OUTPUT_DIRECTORY = PROJECT_ROOT / "output" / "day3"
GPS_INPUT = DAY2_OUTPUT_DIRECTORY / "gps_pings"
STORES_INPUT = DAY2_OUTPUT_DIRECTORY / "store_locations"
GEOJSON_OUTPUT = DAY3_OUTPUT_DIRECTORY / "store_catchments.geojson"
SUMMARY_OUTPUT = DAY3_OUTPUT_DIRECTORY / "store_catchment_summary.csv"
EXPECTED_STORE_COUNT = 12
BUFFER_METERS = 500.0
BUFFER_DISTANCE_TOLERANCE_METERS = 1.0
EXPECTED_CIRCLE_AREA_SQUARE_METERS = 3.141592653589793 * BUFFER_METERS**2
AREA_TOLERANCE_FRACTION = 0.02


def require_parquet_directory(path: Path) -> None:
    """Fail with a direct instruction if a Day 2 prepared dataset is missing."""
    if not path.is_dir() or not any(path.glob("*.parquet")):
        raise FileNotFoundError(
            f"Prepared Parquet data is missing: {path}. "
            "Run scripts\\prepare_spatial_data.py first."
        )


def build_catchments(stores: DataFrame) -> DataFrame:
    """Create a metric buffer in UTM 43N and return its geometry in WGS84."""
    return (
        stores.withColumn(
            "store_geometry_wgs84",
            expr("ST_SetSRID(ST_Point(Longitude, Latitude), 4326)"),
        )
        .withColumn(
            "store_geometry_utm",
            expr(
                "ST_Transform(store_geometry_wgs84, "
                "'EPSG:4326', 'EPSG:32643')"
            ),
        )
        .withColumn(
            "catchment_utm",
            expr(f"ST_Buffer(store_geometry_utm, {BUFFER_METERS})"),
        )
        .withColumn(
            "catchment_geometry",
            expr("ST_Transform(catchment_utm, 'EPSG:32643', 'EPSG:4326')"),
        )
        .withColumn("catchment_area_sq_m", expr("ST_Area(catchment_utm)"))
        .withColumn(
            "buffer_edge_distance_m",
            expr("ST_Distance(store_geometry_utm, ST_Boundary(catchment_utm))"),
        )
    )


def validate_inputs(gps: DataFrame, stores: DataFrame) -> tuple[int, int]:
    """Check that the prepared Day 2 datasets exist and contain store points."""
    gps_count = gps.count()
    if "geometry" not in gps.columns:
        raise ValueError("Prepared GPS Parquet does not contain its geometry column.")
    if gps_count == 0:
        raise ValueError("Prepared GPS Parquet contains no records.")

    stores_count = stores.count()
    if stores_count != EXPECTED_STORE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_STORE_COUNT} prepared stores, found {stores_count}."
        )

    missing = stores.filter(
        col("StoreID").isNull()
        | col("StoreName").isNull()
        | col("Latitude").isNull()
        | col("Longitude").isNull()
    ).count()
    duplicate_ids = (
        stores.groupBy("StoreID")
        .count()
        .filter(col("count") != 1)
        .count()
    )
    if missing:
        raise ValueError(f"Prepared store dataset has {missing} incomplete rows.")
    if duplicate_ids:
        raise ValueError(f"Prepared store dataset has {duplicate_ids} duplicate IDs.")
    return gps_count, stores_count


def validate_catchments(catchments: DataFrame) -> list[dict[str, Any]]:
    """Verify one valid 500-meter polygon and metric area per store."""
    count = catchments.count()
    if count != EXPECTED_STORE_COUNT:
        raise ValueError(f"Expected 12 catchments, found {count}.")

    checks = catchments.agg(
        spark_sum(
            when(
                col("catchment_geometry").isNull()
                | (expr("ST_IsValid(catchment_geometry)") != lit(True))
                | (expr("ST_GeometryType(catchment_geometry)") != lit("ST_Polygon"))
                | (expr("ST_SRID(catchment_geometry)") != lit(4326)),
                1,
            ).otherwise(0)
        ).alias("invalid_catchments"),
        spark_sum(
            when(
                (col("buffer_edge_distance_m") < BUFFER_METERS - BUFFER_DISTANCE_TOLERANCE_METERS)
                | (col("buffer_edge_distance_m") > BUFFER_METERS + BUFFER_DISTANCE_TOLERANCE_METERS),
                1,
            ).otherwise(0)
        ).alias("incorrect_buffer_distances"),
        spark_sum(
            when(
                (col("catchment_area_sq_m") < EXPECTED_CIRCLE_AREA_SQUARE_METERS * (1 - AREA_TOLERANCE_FRACTION))
                | (col("catchment_area_sq_m") > EXPECTED_CIRCLE_AREA_SQUARE_METERS * (1 + AREA_TOLERANCE_FRACTION)),
                1,
            ).otherwise(0)
        ).alias("unexpected_areas"),
    ).first()
    if checks is None:
        raise RuntimeError("Sedona returned no catchment validation results.")
    if checks["invalid_catchments"]:
        raise ValueError(
            f"{checks['invalid_catchments']} catchments are null, invalid, non-polygon, "
            "or not tagged with WGS84 EPSG:4326."
        )
    if checks["incorrect_buffer_distances"]:
        raise ValueError(
            f"{checks['incorrect_buffer_distances']} catchments are not within "
            f"{BUFFER_DISTANCE_TOLERANCE_METERS:g} m of the requested buffer radius."
        )
    if checks["unexpected_areas"]:
        raise ValueError(
            f"{checks['unexpected_areas']} catchment areas are outside "
            f"{AREA_TOLERANCE_FRACTION:.0%} of the expected circular area."
        )

    duplicate_ids = (
        catchments.groupBy("StoreID")
        .count()
        .filter(col("count") != 1)
        .count()
    )
    if duplicate_ids:
        raise ValueError(
            f"Expected one catchment per store; found {duplicate_ids} duplicate IDs."
        )

    return (
        catchments.select(
            "StoreID",
            "StoreName",
            "catchment_area_sq_m",
            "buffer_edge_distance_m",
            expr("ST_AsGeoJSON(catchment_geometry)").alias("geometry_json"),
        )
        .orderBy("StoreID")
        .collect()
    )


def write_outputs(rows: list[dict[str, Any]]) -> None:
    """Write standards-compliant GeoJSON and a compact CSV area summary."""
    DAY3_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    features: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for row in rows:
        area = float(row["catchment_area_sq_m"])
        features.append(
            {
                "type": "Feature",
                "geometry": json.loads(row["geometry_json"]),
                "properties": {
                    "store_id": row["StoreID"],
                    "store_name": row["StoreName"],
                    "catchment_area_sq_m": area,
                },
            }
        )
        summary_rows.append(
            {
                "store_id": row["StoreID"],
                "store_name": row["StoreName"],
                "catchment_area_sq_m": f"{area:.2f}",
            }
        )

    feature_collection = {"type": "FeatureCollection", "features": features}
    with GEOJSON_OUTPUT.open("w", encoding="utf-8") as geojson_file:
        json.dump(feature_collection, geojson_file, ensure_ascii=False)
        geojson_file.write("\n")

    with SUMMARY_OUTPUT.open("w", encoding="utf-8", newline="") as summary_file:
        writer = csv.DictWriter(summary_file, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)


def main() -> None:
    """Load prepared Day 2 data, validate store catchments, and save Day 3 outputs."""
    require_parquet_directory(GPS_INPUT)
    require_parquet_directory(STORES_INPUT)
    spark: SparkSession = create_sedona_session(
        "GeoPulse-Day3-Store-Catchments"
    )
    try:
        SedonaContext.create(spark)
        gps = spark.read.parquet(str(GPS_INPUT))
        stores = spark.read.parquet(str(STORES_INPUT))
        gps_count, stores_count = validate_inputs(gps, stores)
        print(f"Loaded prepared GPS pings: {gps_count:,}")
        print(f"Loaded prepared store locations: {stores_count}")

        catchments = build_catchments(stores)
        rows = validate_catchments(catchments)
        write_outputs(rows)

        print(
            f"Validated {len(rows)} valid WGS84 polygons; each buffer radius is "
            f"{BUFFER_METERS:.0f} m in EPSG:32643."
        )
        print(f"GeoJSON: {GEOJSON_OUTPUT}")
        print(f"Store area summary: {SUMMARY_OUTPUT}")
        for row in rows:
            print(
                f"  {row['StoreID']} | {row['StoreName']} | "
                f"{float(row['catchment_area_sq_m']):,.2f} m^2 | "
                f"edge distance {float(row['buffer_edge_distance_m']):.2f} m"
            )
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
