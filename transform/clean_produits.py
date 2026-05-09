import pandas as pd
from utils.logger import get_logger

logger = get_logger('clean_produits')

def transform_produits(df: pd.DataFrame) -> pd.DataFrame:
    """
    R1 - Standardize category casing → Title Case
    R2 - Fill null prix_catalogue with category median
    R3 - Flag inactive products (actif=false) — kept for SCD Type 2
    """
    initial = len(df)
    logger.info(f"[TRANSFORM] produits — début: {initial} lignes")

    # R1 — Standardize category casing
    for col in ['categorie', 'sous_categorie', 'marque', 'fournisseur']:
        df[col] = df[col].str.strip().str.title()
    logger.info(f"[TRANSFORM] R1 casse — catégories normalisées en Title Case")

    # R2 — Fill null prices with category median
    df['prix_catalogue'] = pd.to_numeric(df['prix_catalogue'], errors='coerce')
    null_prix = df['prix_catalogue'].isna().sum()
    if null_prix > 0:
        df['prix_catalogue'] = df.groupby('categorie')['prix_catalogue'].transform(
            lambda x: x.fillna(x.median())
        )
        logger.info(f"[TRANSFORM] R2 prix — {null_prix} prix nuls remplacés par médiane de catégorie")

    # R3 — Flag inactive products (keep them for SCD Type 2)
    inactifs = (~df['actif'].astype(bool)).sum()
    logger.info(f"[TRANSFORM] R3 inactifs — {inactifs} produits inactifs conservés pour SCD Type 2")

    # Rename columns to match DWH schema
    df = df.rename(columns={
        'id_produit': 'id_produit_nk',
        'nom': 'nom_produit',
        'prix_catalogue': 'prix_standard',
        'origine_pays': 'origine_pays',
    })

    final = len(df)
    logger.info(f"[TRANSFORM] produits — fin: {final} lignes")
    return df