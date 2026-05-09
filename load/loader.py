import pandas as pd
from sqlalchemy import create_engine, text
from config.settings import DATABASE_URL, SCHEMA_STAGING, SCHEMA_DWH
from utils.logger import get_logger

logger = get_logger('loader')

def get_engine():
    return create_engine(DATABASE_URL)

def create_schemas(engine):
    """Creates the schemas if they don't exist yet."""
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_STAGING}"))
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA_DWH}"))
        conn.commit()
    logger.info(f"[LOAD] Schémas créés: {SCHEMA_STAGING}, {SCHEMA_DWH}")

def load_table(
    df: pd.DataFrame,
    table_name: str,
    schema: str,
    engine,
    if_exists: str = 'replace'
):
    """
    Loads a DataFrame into PostgreSQL.
    if_exists='replace' drops and recreates the table each run.
    """
    df.to_sql(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists=if_exists,
        index=False,
        method='multi',
        chunksize=1000
    )
    logger.info(f"[LOAD] {schema}.{table_name} — {len(df)} lignes chargées")

def load_all(
    dim_temps,
    dim_region,
    dim_produit,
    dim_client,
    dim_livreur,
    fait_ventes
):
    engine = get_engine()
    create_schemas(engine)

    logger.info("[LOAD] Début du chargement vers PostgreSQL...")

    # Load dimensions first (fact table depends on them)
    load_table(dim_temps,   'dim_temps',   SCHEMA_DWH, engine)
    load_table(dim_region,  'dim_region',  SCHEMA_DWH, engine)
    load_table(dim_produit, 'dim_produit', SCHEMA_DWH, engine)
    load_table(dim_client,  'dim_client',  SCHEMA_DWH, engine)
    load_table(dim_livreur, 'dim_livreur', SCHEMA_DWH, engine)

    # Load fact table last
    load_table(fait_ventes, 'fait_ventes', SCHEMA_DWH, engine)

    logger.info("[LOAD] ✅ Chargement terminé avec succès!")