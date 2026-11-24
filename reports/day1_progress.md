# GeoPulse — Day 1 progress

**Date:** 2026-11-24

**Status:** Local setup and source validation complete; Snowflake account
execution and connection testing require credentials.

## 1. Existing project inspected

The project already contains:

- An HTML/CSS/JavaScript dashboard in `index.html`, `styles.css`, and `app.js`.
- `data/gps_pings.csv` with 100,000 synthetic GPS records.
- 10,000 unique devices in the GPS dataset.
- `data/store_locations.csv` with 12 stores.
- `data/commercial_zones.csv` with 8 commercial zones.
- Existing Snowflake setup and report files.

No existing CSV was regenerated or modified. The dashboard was not modified.
Table creation, CSV loading, spatial joins, and dbt work were not performed.

## 2. Local source verification

The existing validation command was run without a Snowflake connection:

```powershell
.\.venv\Scripts\python.exe scripts\load_to_snowflake.py --validate-only
```

Verified output:

| Dataset | Rows | Additional check |
| --- | ---: | --- |
| GPS pings | 100,000 | 10,000 unique devices |
| Store locations | 12 | Existing source preserved |
| Commercial zones | 8 | Existing source preserved |

The validation reported zero missing values and zero duplicate GPS rows.
It explicitly used validation-only mode and did not connect to Snowflake.

## 3. Snowflake resources prepared

`snowflake/create_database.sql` creates the following resources with
`IF NOT EXISTS`, so rerunning it is safe:

- Database: `GEOPULSE_DB`
- Schema: `GEOPULSE_DB.RAW`
- Warehouse: `GEOPULSE_WH`

The SQL is intended for a single worksheet run after selecting a role that is
authorized to create databases and warehouses. At the bottom of the script,
`SHOW` statements list the created resources for manual verification.

### Beginner explanation: database, schema, and warehouse

- A **database** is the main container for project data.
- A **schema** is a folder-like namespace inside the database. `RAW` will
  organize original source data in later tasks.
- A **warehouse** is temporary compute used to run SQL. It is separate from
  the database and may consume account credits.

`GEOPULSE_WH` is an `XSMALL` warehouse. It is created initially suspended,
automatically resumes when a query needs it, and automatically suspends after
60 seconds of inactivity. XSMALL and the short suspend delay keep test compute
small. No additional warehouse is needed for Day 1.

## 4. Python connector preparation

The repository now includes:

- `scripts/test_snowflake_connection.py`, a connection-only test that prints the
  active account, user, role, warehouse, database, and schema.
- `.env.example`, containing placeholder values only.
- `.gitignore`, which protects local `.env` files.
- `python-dotenv` and `snowflake-connector-python` in `requirements.txt`.

The test loads `.env` from the project root. It does not create tables, load
CSV files, run spatial SQL, or regenerate datasets.

Browser SSO is the recommended beginner setup:

```dotenv
SNOWFLAKE_ACCOUNT=your-account-identifier
SNOWFLAKE_USER=your-login-name
SNOWFLAKE_AUTHENTICATOR=externalbrowser
SNOWFLAKE_ROLE=SYSADMIN
SNOWFLAKE_WAREHOUSE=GEOPULSE_WH
SNOWFLAKE_DATABASE=GEOPULSE_DB
SNOWFLAKE_SCHEMA=RAW
```

Copy `.env.example` to `.env`, replace the placeholders, and keep real
credentials out of Git. The account value is the Snowflake account identifier,
not the full login URL.

## 5. SQL execution status

No Snowflake credentials or active account session were available. Therefore,
the SQL script could not be executed or verified in this environment.

To run and verify it:

1. Sign in to Snowsight.
2. Select a role authorized to create the resources.
3. Open `snowflake/create_database.sql`.
4. Run the complete script.
5. Confirm `GEOPULSE_DB` appears in the database results.
6. Confirm `RAW` appears under that database.
7. Confirm `GEOPULSE_WH` appears in the warehouse results.

These worksheet results are the account-side verification evidence.

## 6. Connection test status

The test script is prepared but was not run with credentials. Run it only after
the `.env` file contains real, authorized account values:

```powershell
.\.venv\Scripts\python.exe scripts\test_snowflake_connection.py
```

**Not claimed:** Successful connection. No successful Snowflake connection has
been tested in this task because credentials were not available.
The test was also run once without `.env`; it stopped with the clear setup
error `SNOWFLAKE_ACCOUNT is not set` and made no account connection.
