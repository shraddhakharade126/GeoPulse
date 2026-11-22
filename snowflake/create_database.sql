-- Create GeoPulse's database. This is safe to run more than once.
CREATE DATABASE IF NOT EXISTS GEOPULSE_DB
    COMMENT = 'GeoPulse retail mobility analytics';

-- Keep uploaded source files in a dedicated raw-data schema.
CREATE SCHEMA IF NOT EXISTS GEOPULSE_DB.RAW
    COMMENT = 'Raw CSV data loaded from the synthetic GeoPulse datasets';

-- Start small and keep compute costs down by suspending after one idle minute.
-- The warehouse is created suspended and resumes automatically when used.
CREATE WAREHOUSE IF NOT EXISTS GEOPULSE_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Small warehouse for the GeoPulse Day 1 data setup';

-- Set the worksheet session context for the next steps.
USE DATABASE GEOPULSE_DB;
USE SCHEMA RAW;

-- Verify that the database, schema, and warehouse were created.
SHOW DATABASES LIKE 'GEOPULSE_DB';
SHOW SCHEMAS IN DATABASE GEOPULSE_DB;
SHOW WAREHOUSES LIKE 'GEOPULSE_WH';
