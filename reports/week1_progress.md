# GeoPulse Week 1 progress — Snowflake lakehouse

**Status:** Implementation prepared; Snowflake-side execution is pending.
**Scope:** Week 1 only. Apache Sedona and Week 2 work are not included.

## Previously completed and preserved

- The HTML/CSS/JavaScript Leaflet dashboard is present.
- `generate_gps_data.py` and all three synthetic Pune CSVs are present.
- The generator was not rerun for this work.
- The Day 1 Snowflake database setup SQL, connection check, and guide were
  already present before the Day 2–7 work began.

## Existing source data checked locally

| Source CSV | Verified rows |
| --- | ---: |
| `data/gps_pings.csv` | 100,000 |
| `data/store_locations.csv` | 12 |
| `data/commercial_zones.csv` | 8 |

The GPS CSV contains 10,000 unique devices, zero missing values, zero duplicate
rows, and timestamps covering all 24 hours. Its coordinates are within the
requested Pune bounds. These are local CSV inspection results, not Snowflake
query results.

## Implemented for Week 1

- `snowflake/create_tables.sql`: creates the three RAW tables with numeric
  coordinates, timestamps, and `GEOGRAPHY` columns.
- `snowflake/file_format.sql`: defines the header-aware CSV format and internal
  upload stage.
- `snowflake/load_data.sql`: copies staged CSVs into temporary load tables and
  merges into final tables using stable keys. The merge creates points with
  longitude first, latitude second.
- `scripts/load_to_snowflake.py`: validates local sources, uploads with the
  Snowflake Python Connector, executes the idempotent load script, and checks
  loaded row counts and non-NULL geography values.
- `snowflake/validation.sql`: provides source-count, duplicate, coordinate,
  missing-value, and geography checks.
- `snowflake/spatial_queries.sql`: provides distance, 500-meter Store A, nearby
  counts for each store, and spatial-filter examples.
- `.env.example` contains placeholders only; `.gitignore` excludes local `.env`.
- `snowflake/README.md` and the root README document setup and execution.

## Local checks run

- Existing source CSVs were inspected without modification and then checked by
  `scripts/load_to_snowflake.py --validate-only`.
- Validation-only output: 100,000 GPS pings, 10,000 devices, 12 stores, and
  8 zones; zero missing values and zero duplicate GPS rows.
- The validation-only run explicitly reported that no Snowflake connection was
  attempted.
- Python syntax checks passed for the new loader and connection-test scripts;
  Pylance reported no diagnostics or unresolved imports.
- `snowflake-connector-python` 4.8.1 and `python-dotenv` installed successfully
  in the project's `.venv`.

## Still requires account access and manual execution

No Snowflake credentials or account session were available to this task.
Therefore **no Snowflake SQL was executed**, and none of these are claimed as
completed:

- Account signup/access and Snowsight login.
- Creation/verification of `GEOPULSE_DB`, `RAW`, the warehouse, tables, stage,
  and file format.
- Upload/load and comparison of Snowflake counts with the CSVs.
- Snowflake validation and spatial query execution or result recording.

After the account is accessible, follow `snowflake/README.md`: run
`create_database.sql`, `create_tables.sql`, and `file_format.sql` in Snowsight,
then run `scripts/load_to_snowflake.py` from the project root. Finally execute
`validation.sql` and `spatial_queries.sql` in Snowsight, and replace this
section's pending status with the actual worksheet results.

**Week 1 acceptance:** Not yet met until those account-side steps succeed and
their actual query results are recorded.
