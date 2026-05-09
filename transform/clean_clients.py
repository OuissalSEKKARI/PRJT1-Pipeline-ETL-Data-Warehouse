import re
import pandas as pd
from datetime import date
from utils.logger import get_logger
from transform.clean_commandes import charger_referentiel_villes


logger = get_logger('clean_clients')

def transform_clients(df: pd.DataFrame, df_regions: pd.DataFrame) -> pd.DataFrame:
    """
    R1 - Deduplicate on normalized email (keep most recent inscription)
    R2 - Standardize sexe → 'm' / 'f' / 'inconnu'
    R3 - Validate birth dates (age between 16 and 100)
    R4 - Validate email format
    R5 - Harmonize city names via regions referential
    """
    initial = len(df)
    logger.info(f"[TRANSFORM] clients — début: {initial} lignes")

    # R1 — Deduplicate on email
    df['email_norm'] = df['email'].str.lower().str.strip()
    df['date_inscription'] = pd.to_datetime(df['date_inscription'], errors='coerce')
    df = df.sort_values('date_inscription').drop_duplicates(
        subset=['email_norm'], keep='last'
    )
    logger.info(f"[TRANSFORM] R1 doublons — {initial - len(df)} doublons supprimés")

    # R2 — Standardize sexe
    mapping_sexe = {
        'm': 'm', 'M': 'm', '1': 'm', 'homme': 'm', 'male': 'm', 'h': 'm',
        'f': 'f', 'F': 'f', '0': 'f', 'femme': 'f', 'female': 'f'
    }
    df['sexe'] = df['sexe'].str.strip().map(mapping_sexe).fillna('inconnu')
    inconnus = (df['sexe'] == 'inconnu').sum()
    logger.info(f"[TRANSFORM] R2 sexe — {inconnus} valeurs non reconnues → 'inconnu'")

    # R3 — Validate birth dates
    df['date_naissance'] = pd.to_datetime(df['date_naissance'], errors='coerce')
    today = pd.Timestamp(date.today())
    df['age'] = (today - df['date_naissance']).dt.days // 365
    invalides = ((df['age'] < 16) | (df['age'] > 100)).sum()
    df.loc[(df['age'] < 16) | (df['age'] > 100), 'date_naissance'] = pd.NaT
    logger.info(f"[TRANSFORM] R3 dates naissance — {invalides} dates invalides supprimées")

    # Build age brackets
    df['tranche_age'] = pd.cut(
        df['age'].fillna(0),
        bins=[0, 18, 25, 35, 45, 55, 65, 200],
        labels=['<18', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']
    ).astype(str)

    # R4 — Validate email format
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    bad_emails = (~df['email'].str.match(pattern, na=False)).sum()
    df.loc[~df['email'].str.match(pattern, na=False), 'email'] = None
    logger.info(f"[TRANSFORM] R4 emails — {bad_emails} emails invalides supprimés")

    # R5 — Harmonize city names
    mapping_villes = charger_referentiel_villes(df_regions)
    df['ville'] = df['ville'].str.strip().str.lower().map(mapping_villes).fillna('Non renseignée')
    non_renseignes = (df['ville'] == 'Non renseignée').sum()
    logger.info(f"[TRANSFORM] R5 villes — {non_renseignes} villes non reconnues")
    # also map city codes
    for _, row in df_regions.iterrows():
        mapping_villes[row['code_ville'].lower().strip()] = row['nom_ville_standard']

    df['ville'] = df['ville'].str.strip().str.lower().map(mapping_villes).fillna('Non renseignée')
    non_renseignes = (df['ville'] == 'Non renseignée').sum()
    logger.info(f"[TRANSFORM] R5 villes — {non_renseignes} villes non reconnues")

    # Build full name
    df['nom_complet'] = df['prenom'].str.strip() + ' ' + df['nom'].str.strip()

    final = len(df)
    logger.info(f"[TRANSFORM] clients — fin: {final} lignes ({initial - final} supprimées au total)")
    return df