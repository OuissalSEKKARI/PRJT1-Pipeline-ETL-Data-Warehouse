import os

# Copy this file to settings.py and fill in your values.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

COMMANDES_FILE = os.path.join(DATA_DIR, "commandes_mexora.csv")
CLIENTS_FILE = os.path.join(DATA_DIR, "clients_mexora.csv")
PRODUITS_FILE = os.path.join(DATA_DIR, "produits_mexora.json")
REGIONS_FILE = os.path.join(DATA_DIR, "regions_maroc.csv")

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
