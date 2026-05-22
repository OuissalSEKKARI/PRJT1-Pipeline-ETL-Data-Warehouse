import logging

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

def load_table(df, table_name, schema, engine):
    """
    Charge une dimension avec TRUNCATE + INSERT au lieu de replace.
    Évite l'erreur DependentObjectsStillExist sur les FK et vues matérialisées.
    """
    with engine.begin() as conn:
        # Vérifier si la table existe déjà
        exists = conn.execute(text(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = '{schema}'
                AND table_name = '{table_name}'
            )
        """)).scalar()

        if exists:
            # TRUNCATE CASCADE pour vider sans supprimer la table
            conn.execute(text(f'TRUNCATE TABLE {schema}.{table_name} CASCADE'))
            logging.info(f"[LOAD] {table_name} — table vidée (TRUNCATE CASCADE)")

    # INSERT des nouvelles données
    df.to_sql(
        name=table_name,
        con=engine,
        schema=schema,
        if_exists='append',   # append car la table existe déjà après TRUNCATE
        index=False,
        method='multi',
        chunksize=1000
    )
    logging.info(f"[LOAD] {table_name} — {len(df)} lignes chargées")

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

    # ← AJOUT : vider fait_ventes EN PREMIER car il référence les dimensions
    with engine.begin() as conn:
        conn.execute(text('TRUNCATE TABLE dwh_mexora.fait_ventes CASCADE'))
        logger.info("[LOAD] fait_ventes — vidée en premier")


    # Load dimensions first (fact table depends on them)
    load_table(dim_temps,   'dim_temps',   SCHEMA_DWH, engine)
    load_table(dim_region,  'dim_region',  SCHEMA_DWH, engine)
    load_table(dim_produit, 'dim_produit', SCHEMA_DWH, engine)
    load_table(dim_client,  'dim_client',  SCHEMA_DWH, engine)
    load_table(dim_livreur, 'dim_livreur', SCHEMA_DWH, engine)

    # Load fact table last
    load_table(fait_ventes, 'fait_ventes', SCHEMA_DWH, engine)

    logger.info("[LOAD] ✅ Chargement terminé avec succès!")