-- CSV format for the existing headered GeoPulse files.
CREATE FILE FORMAT IF NOT EXISTS GEOPULSE_DB.RAW.GEOPULSE_CSV_FORMAT
    TYPE = CSV
    FIELD_DELIMITER = ','
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    EMPTY_FIELD_AS_NULL = TRUE
    NULL_IF = ('')
    TIMESTAMP_FORMAT = 'YYYY-MM-DD HH24:MI:SS';

-- Internal stage used by the Python loader's PUT and COPY commands.
CREATE STAGE IF NOT EXISTS GEOPULSE_DB.RAW.GEOPULSE_UPLOAD_STAGE
    COMMENT = 'Temporary uploads for the GeoPulse source CSV files';
