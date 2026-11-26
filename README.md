# GeoPulse: Hyper-Local Retail Mobility Analytics

## 1. Project Overview

GeoPulse is a data analytics project designed to analyze local mobility patterns and retail activity to generate meaningful business insights.

The project focuses on understanding how people move within specific geographic areas, identifying high-traffic and low-traffic locations, and analyzing customer movement patterns around retail locations.

By collecting, cleaning, analyzing, and visualizing location-based data, GeoPulse aims to help businesses understand local customer activity and make better business decisions.

## 2. Problem Statement

Retail businesses need to understand where potential customers are located, how frequently people visit particular areas, and when specific locations experience higher activity.

Without proper data analysis, it can be difficult to identify suitable business locations, understand customer movement patterns, and recognize opportunities for business growth.

GeoPulse addresses this challenge through data analytics and interactive visualizations.

## 3. Project Objectives

- Collect relevant retail and mobility datasets.
- Clean and validate collected data.
- Analyze geographical and customer movement patterns.
- Identify high-activity and low-activity locations.
- Understand location-based trends and patterns.
- Create meaningful visualizations and interactive dashboards.
- Generate actionable insights to support retail business decisions.

## 4. Scope of the Project

The project covers the following areas:

1. **Data Collection:** Gather relevant datasets from different sources.
2. **Data Preprocessing:** Handle missing values, duplicate records, and inconsistent data.
3. **Exploratory Data Analysis:** Understand patterns, distributions, and trends.
4. **Geographical Analysis:** Analyze activity across different locations.
5. **Retail Mobility Analysis:** Study location-based activity and footfall patterns where data is available.
6. **Data Visualization:** Present findings through charts, graphs, and maps.
7. **Dashboard Development:** Build an interactive dashboard for exploring analytical results.
8. **Business Insights:** Generate findings that can support retail planning and decision-making.

## 5. Proposed Project Workflow

Data Collection
↓
Data Cleaning and Preprocessing
↓
Exploratory Data Analysis (EDA)
↓
Geographical and Mobility Analysis
↓
Data Visualization
↓
Interactive Dashboard Development
↓
Business Insights and Reporting

## 6. Technologies and Tools

The following tools are potential choices for implementation, subject to project requirements:

- Python – Data analysis and processing
- Pandas – Data manipulation
- NumPy – Numerical operations
- Matplotlib and Seaborn – Data visualization
- Jupyter Notebook – Exploratory data analysis
- Power BI – Interactive dashboard development
- SQL – Data querying and management
- Git and GitHub – Version control and project management

## 7. Expected Outcomes

- A cleaned and validated dataset.
- Exploratory data analysis results.
- Geographical and retail mobility insights.
- Meaningful charts and visualizations.
- An interactive analytical dashboard.
- A final project report and presentation.

## 8. Project Deliverables

- Source Code (if applicable)
- Project Documentation
- Project Report
- Presentation (PPT)
- Model Evaluation Results (if applicable)
- Final Project Demonstration (if applicable)

## 9. Project Information

| Detail | Information |
|---|---|
| Project Name | GeoPulse |
| Project Title | Hyper-Local Retail Mobility Analytics |
| Organization | Infotact Solutions |
| Internship Role | Data Associate L1 Intern |
| Domain | Data Analytics |
| Project Duration | 1 Month |
| Start Date | 10 November 2026 |
| End Date | 10 December 2026 |

## 10. Conclusion

GeoPulse aims to transform location-based retail and mobility data into useful analytical insights. By combining data processing, exploratory analysis, geographical visualization, and interactive dashboards, the project seeks to help businesses better understand local activity patterns and make informed decisions.

---

## 11. Initial Dashboard Design

The repository includes a responsive dashboard prototype in `index.html`.
It sketches an overview for footfall activity, local areas, mobility trends, and
high-level insights. The activity panel uses an interactive OpenStreetMap view
centered on Pune; the heat circles and dashboard figures are illustrative only,
not based on a collected or validated dataset. The reporting-period selector
and sample report export demonstrate the intended interactions.

Open `index.html` in a browser with an internet connection to preview the map
and dashboard. Replace the sample values and markers with verified project data
before using the dashboard to make or communicate business decisions.

**Note:** This README describes the proposed project and its initial dashboard
design. Actual datasets, implementation details, tools, and analytical results
will be updated as development progresses.

## Synthetic GPS data

The project includes a reproducible generator for fictional Pune mobility data.
It does not use real people's location data or external APIs. From the project
root, install the Python dependencies and run the script:

```powershell
python -m pip install -r requirements.txt
python generate_gps_data.py
```

In VS Code, open the project folder, select the Python interpreter you want to
use, and run those commands in the integrated terminal. The script creates the
`data` folder when needed and writes `gps_pings.csv`, `store_locations.csv`,
and `commercial_zones.csv` there. It generates 100,000 GPS pings for 10,000
devices for one simulated day and prints dataset validation summaries.

## Snowflake setup

The [Snowflake Week 1 guide](./snowflake/README.md) explains account access,
worksheet setup, table creation, loading, validation, and spatial SQL. Run
`snowflake/create_database.sql`, `snowflake/create_tables.sql`, and
`snowflake/file_format.sql` in your own Snowflake worksheet before running
`scripts/load_to_snowflake.py`. The Python loader has a local
`--validate-only` mode and does not regenerate the source CSVs.

Snowflake-side setup and query execution remain pending until run and verified
in the account. See [the Week 1 report](./reports/week1_progress.md) for the
actual local validation results and manual steps still required.

## Week 2 Day 2: Spark and Sedona preparation

The Day 2 pipeline reads the existing three CSVs, validates their headers,
Spark data types, row counts, and missing values, then saves them as Parquet
under `output/day2/`. GPS pings additionally receive a Sedona `geometry`
column. Point creation uses longitude as X and latitude as Y and checks those
coordinates before writing. The source CSVs and dashboard are not changed.
No buffers are created by this pipeline.

### Prerequisites

- Python 3.9 or later and Java 17 or 21. Spark 4.0 does not support Java 25;
  if your only installed Java is 25, install Temurin 21, then set `JAVA_HOME`
  to the installed JDK directory before starting the pipeline:

```powershell
winget install --id EclipseAdoptium.Temurin.21.JDK --exact
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\<installed-jdk-folder>"
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
```

Replace `<installed-jdk-folder>` with the actual directory name created by the
installer. The script checks the selected Java version before starting Spark.
- From the project root, install the pinned PySpark/Sedona pair into the
  project's virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The pipeline fetches the matching Sedona JVM jar through Maven when Spark
starts, so Maven Central must be reachable the first time it runs.

### Run

```powershell
.\.venv\Scripts\python.exe scripts\prepare_spatial_data.py
```

The output folders are `output/day2/gps_pings/`,
`output/day2/store_locations/`, and `output/day2/commercial_zones/`.
Rerunning replaces only those three Day 2 Parquet folders. These generated
outputs are excluded from Git; rerun the pipeline to recreate them.

## Week 2 Day 3: Store catchments

Day 3 uses the prepared Day 2 GPS and store Parquet datasets. Run the Day 2
preparation command above first if those folders do not yet exist. The store
points are tagged EPSG:4326, transformed to UTM Zone 43N (EPSG:32643), buffered
by 500 meters in that projected CRS, and transformed back to EPSG:4326 for the
GeoJSON. Sedona validates the one-polygon-per-store count, validity, WGS84
SRID, boundary distance, and approximate circular area. The GPS Parquet is
loaded and checked as a prerequisite; this day does not perform spatial joins.

Run from the project root:

```powershell
.\.venv\Scripts\python.exe scripts\create_store_catchments.py
```

Outputs are `output/day3/store_catchments.geojson` (a WGS84 GeoJSON
FeatureCollection with all 12 stores) and
`output/day3/store_catchment_summary.csv` (store ID, name, and area in square
meters). No source CSVs or dashboard files are modified. This script uses the
GeoTools wrapper matching Sedona 1.7.1 for `ST_Transform`; Maven Central must
be reachable when Spark first resolves its JVM dependencies.

### Day 3 verification status

The source store CSV has 12 locations. The pipeline enforces one output
polygon per unique store, polygon validity, EPSG:4326 output SRID, buffer-edge
distance within 1 meter of 500 meters, and area within 2% of a 500-meter
circle. These checks have not yet been observed on a Sedona run because this
environment has only Java 25 (PySpark 4.0 requires Java 17 or 21) and the Day 2
Parquet folders have not been generated. Install a supported JDK, run Day 2
preparation, and then run the Day 3 command above before treating the outputs
as validated.

