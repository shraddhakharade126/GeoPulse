# GeoPulse Snowflake setup — Day 1

This guide covers account access, the first SQL worksheet, and optional Python
connectivity. It does not load data from Python or perform spatial analysis.
No Snowflake resource is considered configured until you run and verify the SQL
in your own account.

## Day 1 scope

Day 1 covers account access, database/schema setup, warehouse selection, and a
connection check only. It does not create project tables, stage or load CSV
data, run spatial joins, or configure dbt. Those work items belong to later
days.

## 1. Create or access an account

- If Infotact Solutions has provided an account URL and login, use those details
  and ask the account administrator which role to use.
- Otherwise, open [Snowflake's account signup page](https://signup.snowflake.com/)
  and follow its account-registration flow. Choose the cloud/region and account
  options available to you, verify your email, and sign in to Snowsight.
- Keep your account URL/identifier and login private. Do not send passwords,
  MFA codes, or private keys in chat or commit them to this repository.
- A trial/account's features and credit terms depend on the offer shown during
  signup. Review those terms before running compute.

## 2. Open a SQL worksheet

1. Sign in to Snowsight using your Snowflake account URL.
2. Open **Projects → Worksheets** (the exact navigation label can vary slightly
   by Snowsight version) and create a worksheet.
3. Select a role with permission to create databases and warehouses. Prefer
   `SYSADMIN` if it is available and authorized; otherwise use the role your
   account administrator recommends.
4. Open `snowflake/create_database.sql` in VS Code, copy its contents into the
   worksheet, and run all statements.
5. Review the results of the three `SHOW` commands at the bottom. They should
   list `GEOPULSE_DB`, its `RAW` schema, and `GEOPULSE_WH`.

The script uses `IF NOT EXISTS`, so rerunning it will not create duplicate
objects. Snowflake SQL has not been run from this repository; the `SHOW` results
in your worksheet are the verification step.

## 3. Database, schema, and warehouse

- **Database (`GEOPULSE_DB`)**: the top-level container for this project's
  Snowflake data.
- **Schema (`RAW`)**: a namespace inside the database for the original uploaded
  CSV tables. Later processing can use separate schemas, but is out of scope
  for Day 1.
- **Warehouse (`GEOPULSE_WH`)**: compute used to run queries and load data; it
  is separate from the database where data is stored.

The setup uses an `XSMALL` warehouse, creates it suspended, enables auto-resume,
and suspends it after 60 idle seconds. Running queries or loading data can
consume credits. Leave it unused when you are finished; you can also suspend it
from **Admin → Warehouses** in Snowsight.

## 4. Create the tables, file format, and internal stage

In a Snowsight SQL worksheet, run these scripts in order:

1. `snowflake/create_database.sql` (already created for Day 1).
2. `snowflake/create_tables.sql`.
3. `snowflake/file_format.sql`.

The tables retain the original coordinate columns. The file format skips each
CSV header, accepts quoted fields, and parses timestamps as
`YYYY-MM-DD HH24:MI:SS`. The internal stage is used by the loader.

## 5. Configure the connector and validate the local CSVs

Copy `.env.example` to `.env`, then replace the account and user placeholders
with your own values. The `.env` file is Git-ignored. Keep passwords out of it;
the default `externalbrowser` authenticator uses browser sign-in.

Install the requirements from the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Before any Snowflake login, validate the existing files locally:

```powershell
.\.venv\Scripts\python.exe scripts\load_to_snowflake.py --validate-only
```

The loader checks the file schemas, record/device minimums, 12 store rows,
8 zone rows, timestamps, missing values, duplicates, radii, and Pune coordinate
bounds. This mode does not connect to Snowflake and does not change any CSV.

## 6. Load the existing files once the account is accessible

After you run the three SQL setup scripts and confirm that you can sign in,
run this from the project root:

```powershell
.\.venv\Scripts\python.exe scripts\load_to_snowflake.py
```

It reads the three CSVs without regenerating them, uploads them to the
`GEOPULSE_UPLOAD_STAGE` internal stage, uses the configured format and `COPY
INTO` to populate temporary load tables, then `MERGE`s into the final tables.
GPS rows use `DEVICE_ID` plus `EVENT_TIMESTAMP` as the merge key; store and zone
rows use their IDs. Re-running this loader updates matching rows instead of
adding another copy. It compares final Snowflake row counts and checks that all
GEOGRAPHY values are non-NULL.

If you prefer setting variables in the current PowerShell session instead of
using `.env`, set `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
`SNOWFLAKE_AUTHENTICATOR=externalbrowser`, and optionally `SNOWFLAKE_ROLE`.
The account setting is the Snowflake account identifier, not the full web URL.
For password authentication, set `SNOWFLAKE_AUTHENTICATOR=snowflake` and get
`SNOWFLAKE_PASSWORD` from an approved secret manager or protected environment
setting. Never put passwords in source code or shell command history.

You may also use Snowsight's **Add Data / Load Data** wizard to upload one CSV
at a time from the `data` folder. Choose CSV, select `GEOPULSE_DB.RAW`, keep the
header row enabled, and review the inferred timestamp and numeric types. That
wizard loads directly into the selected table, so **do not use it and the
Python loader for the same files**: a direct second load can create duplicates.
The Python loader is the recommended rerunnable path.

For a connection-only check, run
`.\.venv\Scripts\python.exe snowflake\connect_test.py`; it prints the current
account/session context without loading any data.

## 7. Validate and run the basic spatial queries

In Snowsight, run `snowflake/validation.sql` to compare Snowflake counts and
quality checks with the CSV source counts. Then run
`snowflake/spatial_queries.sql` to populate any missing points and try the
distance, 500-meter Store A filter, and per-store nearby-ping count queries.
`STORE001` is the documented example for Store A. Snowflake must be accessible
before these results can be recorded.

## 8. Week 1 status

The SQL and Python workflow is implemented, but database creation, loading,
and spatial-query execution are pending until you sign in and run them in your
Snowflake account. See `reports/week1_progress.md` for the verified local
source counts and the tasks that still need account-side execution.

Official references:

- [Snowflake trial signup](https://signup.snowflake.com/)
- [Snowsight worksheets](https://docs.snowflake.com/en/user-guide/ui-snowsight-worksheets)
- [Load local files in Snowsight](https://docs.snowflake.com/en/user-guide/data-load-local-file-system)
- [Install the Python connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-install)
- [Connect with the Python connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect)
