# Copy this file to settings.py and fill in your values

DB_USER     = "postgres"
DB_PASSWORD = "YOUR_PASSWORD_HERE"
DB_HOST     = "localhost"
DB_PORT     = "5432"
DB_NAME     = "mexora_dwh"

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

SCHEMA_STAGING   = "staging_mexora"
SCHEMA_DWH       = "dwh_mexora"
SCHEMA_REPORTING = "reporting_mexora"