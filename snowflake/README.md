# GeoPulse Snowflake setup — Day 1

This guide covers account access, the first SQL worksheet, and optional Python
connectivity. It does not load data from Python or perform spatial analysis.
No Snowflake resource is considered configured until you run and verify the SQL
in your own account.

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

## 4. Upload the three CSV files in Snowsight

After the database/schema creation succeeds:

1. In Snowsight, open **Data → Databases**, select `GEOPULSE_DB`, then its
   `RAW` schema. Alternatively, use the **Add Data / Load Data** workflow if
   that is how your Snowsight version presents local uploads.
2. Choose the option to load files from your computer and select one file at a
   time from this project's `data` folder. Choose CSV and confirm that the
   first row contains column headers.
3. Set the destination database to `GEOPULSE_DB`, schema to `RAW`, and use
   these table names:

   | Local file | Table |
   | --- | --- |
   | `data/gps_pings.csv` | `GPS_PINGS` |
   | `data/store_locations.csv` | `STORE_LOCATIONS` |
   | `data/commercial_zones.csv` | `COMMERCIAL_ZONES` |

4. Review the preview and inferred column types before starting each load.
   `Timestamp` should be interpreted as a timestamp (format
   `YYYY-MM-DD HH24:MI:SS`); latitude/longitude and `Radius_Meters` should be
   numeric. Confirm the load succeeded and the reported row count is sensible.
5. Do not upload the PDFs, dashboard files, or ZIP archive as data tables.

If Snowsight asks for a warehouse during loading, select `GEOPULSE_WH`. Its
auto-resume setting may start compute and incur credits.

## 5. Install and configure the Python connector

From the project root, install the dependency recorded in `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

In the VS Code PowerShell terminal, set non-secret connection settings for the
current terminal session. Use your Snowflake account identifier (not the full
web URL) and your login name:

```powershell
$env:SNOWFLAKE_ACCOUNT = "your-account-identifier"
$env:SNOWFLAKE_USER = "your-login-name"
$env:SNOWFLAKE_ROLE = "SYSADMIN"
$env:SNOWFLAKE_WAREHOUSE = "GEOPULSE_WH"
$env:SNOWFLAKE_DATABASE = "GEOPULSE_DB"
$env:SNOWFLAKE_SCHEMA = "RAW"
```

The example defaults to `externalbrowser` authentication, which asks Snowflake
to authenticate through your browser rather than storing your password in
source code. Run it in the same terminal session:

```powershell
python snowflake/connect_test.py
```

The script prints the active account, user, role, warehouse, database, and
schema if the connection succeeds. Its query can resume the warehouse and
consume credits. If your account requires password authentication instead,
set `SNOWFLAKE_AUTHENTICATOR` to `snowflake` and make `SNOWFLAKE_PASSWORD`
available to the process through an approved secret manager or your operating
system's protected environment-variable mechanism. Never put the password in
the script, README, shell command history, or Git.

Environment variables set with PowerShell `$env:...` last only for that
terminal session. Set them again in a new terminal. Do not put real secrets in
`.env.example` or commit a local `.env` file.

## 6. Day 1 completion checklist

- [ ] You can sign in to Snowsight.
- [ ] You ran `snowflake/create_database.sql` successfully.
- [ ] `SHOW DATABASES`, `SHOW SCHEMAS`, and `SHOW WAREHOUSES` list the expected
  objects.
- [ ] You optionally loaded the three CSVs through Snowsight and confirmed each
  table's row count.
- [ ] If using Python, `snowflake/connect_test.py` connected and displayed the
  expected session context.

Official references:

- [Snowflake trial signup](https://signup.snowflake.com/)
- [Snowsight worksheets](https://docs.snowflake.com/en/user-guide/ui-snowsight-worksheets)
- [Load local files in Snowsight](https://docs.snowflake.com/en/user-guide/data-load-local-file-system)
- [Install the Python connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-install)
- [Connect with the Python connector](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect)
