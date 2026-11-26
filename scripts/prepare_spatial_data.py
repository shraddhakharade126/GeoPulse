"""Load the existing GeoPulse CSVs into validated Spark/Sedona Parquet outputs."""

import csv
import os
import re
import shutil
import subprocess
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import abs as spark_abs
from pyspark.sql.functions import coalesce, col, expr, lit, sum as spark_sum, trim, when
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)
from sedona.spark import SedonaContext


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIRECTORY = PROJECT_ROOT / "data"
OUTPUT_DIRECTORY = PROJECT_ROOT / "output" / "day2"
SEDONA_VERSION = "1.7.1"
SEDONA_JAR = (
    "org.apache.sedona:sedona-spark-shaded-4.0_2.13:"
    f"{SEDONA_VERSION}"
)
GEOTOOLS_WRAPPER = f"org.datasyslab:geotools-wrapper:{SEDONA_VERSION}-28.5"
TIMESTAMP_FORMAT = "yyyy-MM-dd HH:mm:ss"

DATASETS = {
    "gps_pings": (
        "gps_pings.csv",
        StructType(
            [
                StructField("DeviceID", StringType(), True),
                StructField("Latitude", DoubleType(), True),
                StructField("Longitude", DoubleType(), True),
                StructField("Timestamp", TimestampType(), True),
                StructField("Location_Type", StringType(), True),
            ]
        ),
    ),
    "store_locations": (
        "store_locations.csv",
        StructType(
            [
                StructField("StoreID", StringType(), True),
                StructField("StoreName", StringType(), True),
                StructField("Latitude", DoubleType(), True),
                StructField("Longitude", DoubleType(), True),
            ]
        ),
    ),
    "commercial_zones": (
        "commercial_zones.csv",
        StructType(
            [
                StructField("ZoneID", StringType(), True),
                StructField("ZoneName", StringType(), True),
                StructField("Latitude", DoubleType(), True),
                StructField("Longitude", DoubleType(), True),
                StructField("Radius_Meters", IntegerType(), True),
            ]
        ),
    ),
}


def validate_header(csv_path: Path, expected_columns: list[str]) -> None:
    """Reject missing files or CSV headers that do not match the Spark schema."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Required source CSV is missing: {csv_path}")

    with csv_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        header = next(csv.reader(source_file), None)
    if header != expected_columns:
        raise ValueError(
            f"{csv_path.name} columns must be {expected_columns}, got {header}."
        )


def validate_java_runtime() -> None:
    """Fail early with setup guidance when the selected Java is unsupported."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_executable = Path(java_home) / "bin" / "java.exe"
        if not java_executable.is_file():
            raise RuntimeError(
                f"JAVA_HOME does not contain bin\\java.exe: {java_home}"
            )
    else:
        java_path = shutil.which("java")
        if java_path is None:
            raise RuntimeError(
                "Java was not found. Install JDK 17 or 21 and set JAVA_HOME."
            )
        java_executable = Path(java_path)

    version = subprocess.run(
        [str(java_executable), "-version"],
        capture_output=True,
        check=True,
        text=True,
    )
    version_text = version.stdout + version.stderr
    version_match = re.search(r'version "(\d+)', version_text)
    if version_match is None:
        raise RuntimeError(f"Could not determine Java version: {version_text.strip()}")

    major_version = int(version_match.group(1))
    if major_version not in {17, 21}:
        raise RuntimeError(
            f"PySpark 4.0 requires Java 17 or 21; found Java {major_version}. "
            "Install a supported JDK and set JAVA_HOME before running this script."
        )


def read_dataset(
    spark: SparkSession, csv_name: str, schema: StructType
) -> DataFrame:
    """Read one existing CSV using its declared types and strict CSV parsing."""
    csv_path = DATA_DIRECTORY / csv_name
    expected_columns = [field.name for field in schema.fields]
    validate_header(csv_path, expected_columns)

    return (
        spark.read.option("header", "true")
        .option("mode", "FAILFAST")
        .option("timestampFormat", TIMESTAMP_FORMAT)
        .schema(schema)
        .csv(str(csv_path))
    )


def validate_dataframe(dataset_name: str, frame: DataFrame) -> int:
    """Print the schema/count/null summary and fail if required values are missing."""
    row_count = frame.count()
    missing_expressions = [
        coalesce(
            spark_sum(
                when(
                    col(field.name).isNull()
                    | (trim(col(field.name).cast("string")) == ""),
                    lit(1),
                ).otherwise(lit(0))
            ),
            lit(0),
        ).alias(field.name)
        for field in frame.schema.fields
    ]
    missing_counts = frame.agg(*missing_expressions).first().asDict()

    print(f"\n{dataset_name}: {row_count:,} rows")
    print("Columns and Spark data types:")
    for field in frame.schema.fields:
        print(f"  {field.name}: {field.dataType.simpleString()}")
    print("Missing values by column:")
    for column_name, missing_count in missing_counts.items():
        print(f"  {column_name}: {missing_count}")

    missing_total = sum(missing_counts.values())
    if missing_total:
        raise ValueError(
            f"{dataset_name} contains {missing_total:,} missing values."
        )
    return row_count


def add_and_check_gps_geometry(gps: DataFrame) -> DataFrame:
    """Create WGS84 points with longitude first and verify their coordinates."""
    # ST_Point follows X/Y order: X is longitude and Y is latitude.
    prepared = gps.withColumn(
        "geometry", expr("ST_Point(Longitude, Latitude)")
    )
    checks = prepared.agg(
        spark_sum(when(col("geometry").isNull(), 1).otherwise(0)).alias(
            "null_geometries"
        ),
        spark_sum(
            when(
                (spark_abs(expr("ST_X(geometry) - Longitude")) > 1e-9)
                | (spark_abs(expr("ST_Y(geometry) - Latitude")) > 1e-9),
                1,
            ).otherwise(0)
        ).alias("coordinate_mismatches"),
    ).first()

    if checks is None:
        raise RuntimeError("Sedona returned no GPS geometry validation results.")
    if checks["null_geometries"] or checks["coordinate_mismatches"]:
        raise RuntimeError(
            "GPS geometry validation failed: "
            f"{checks['null_geometries']} NULL geometries, "
            f"{checks['coordinate_mismatches']} coordinate mismatches."
        )

    print(
        "GPS geometry check passed: "
        f"{prepared.count():,} points; longitude=X and latitude=Y."
    )
    return prepared


def write_parquet(dataset_name: str, frame: DataFrame) -> Path:
    """Persist one prepared dataset beneath its dedicated Day 2 output folder."""
    output_path = OUTPUT_DIRECTORY / dataset_name
    # Overwrite only this dataset's own output folder so reruns stay repeatable.
    frame.write.mode("overwrite").parquet(str(output_path))
    print(f"Parquet saved: {output_path}")
    return output_path


def create_sedona_session(app_name: str) -> SparkSession:
    """Create the shared Spark/Sedona session, including CRS transform support."""
    validate_java_runtime()
    return (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.jars.packages", f"{SEDONA_JAR},{GEOTOOLS_WRAPPER}")
        .config(
            "spark.sql.extensions",
            "org.apache.sedona.sql.SedonaSqlExtensions",
        )
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config(
            "spark.kryo.registrator",
            "org.apache.sedona.core.serde.SedonaKryoRegistrator",
        )
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )


def main() -> None:
    """Prepare all three source datasets and stop Spark even if processing fails."""
    spark = create_sedona_session("GeoPulse-Day2-Spatial-Preparation")
    try:
        SedonaContext.create(spark)

        loaded: dict[str, DataFrame] = {}
        row_counts: dict[str, int] = {}
        for dataset_name, (csv_name, schema) in DATASETS.items():
            frame = read_dataset(spark, csv_name, schema)
            row_counts[dataset_name] = validate_dataframe(dataset_name, frame)
            loaded[dataset_name] = frame

        loaded["gps_pings"] = add_and_check_gps_geometry(loaded["gps_pings"])
        for dataset_name, frame in loaded.items():
            write_parquet(dataset_name, frame)

        print("\nDay 2 preparation completed successfully.")
        for dataset_name, row_count in row_counts.items():
            print(f"  {dataset_name}: {row_count:,} rows")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
