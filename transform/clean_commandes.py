import pandas as pd
from utils.logger import get_logger

logger = get_logger('clean_commandes')

def charger_referentiel_villes(df_regions: pd.DataFrame) -> dict:
    """
    Builds a mapping from all known city variants → standard name.
    Covers codes, standard names, and common typo variants.
    """
    mapping = {}
    
    # Known manual variants (typos, abbreviations, dialectal names)
    variants_manuels = {
        'tanja': 'Tanger', 'tnja': 'Tanger', 'tng': 'Tanger',
        'tanger': 'Tanger', 'tangier': 'Tanger',
        'casa': 'Casablanca', 'casablanca': 'Casablanca', 'dar el beida': 'Casablanca',
        'rabat': 'Rabat', 'rbat': 'Rabat',
        'fes': 'Fès', 'fez': 'Fès', 'fès': 'Fès',
        'mrakech': 'Marrakech', 'marrakech': 'Marrakech', 'marrakesh': 'Marrakech',
        'agadir': 'Agadir',
        'meknes': 'Meknès', 'meknès': 'Meknès', 'meknès': 'Meknès',
        'oujda': 'Oujda',
        'kenitra': 'Kénitra', 'kénitra': 'Kénitra', 'qnitra': 'Kénitra',
        'sale': 'Salé', 'salé': 'Salé', 'salè': 'Salé',
        'tetouan': 'Tétouan', 'tétouan': 'Tétouan', 'tetuan': 'Tétouan',
        'nador': 'Nador',
        'el jadida': 'El Jadida', 'eljadida': 'El Jadida',
        'beni mellal': 'Beni Mellal', 'benimellal': 'Beni Mellal',
        'laayoune': 'Laâyoune', 'laâyoune': 'Laâyoune', 'layoune': 'Laâyoune',
        'ouarzazate': 'Ouarzazate',
        'safi': 'Safi',
        'mohammedia': 'Mohammedia',
        'settat': 'Settat',
        'al hoceima': 'Al Hoceïma', 'al hoceïma': 'Al Hoceïma', 'alhocima': 'Al Hoceïma',
    }
    mapping.update(variants_manuels)
    
    # Also map from the regions file itself
    for _, row in df_regions.iterrows():
        standard = row['nom_ville_standard']
        mapping[standard.lower().strip()] = standard
        mapping[row['code_ville'].lower().strip()] = standard

    return mapping

def transform_commandes(df: pd.DataFrame, df_regions: pd.DataFrame) -> pd.DataFrame:
    """
    Applies all cleaning rules on raw commandes.

    R1 - Remove duplicates on id_commande (keep last)
    R2 - Standardize dates to YYYY-MM-DD
    R3 - Harmonize city names via regions referential
    R4 - Standardize order statuts
    R5 - Remove rows with quantite <= 0
    R6 - Remove rows with prix_unitaire = 0 (test orders)
    R7 - Fill missing id_livreur with '-1'
    """
    initial = len(df)
    logger.info(f"[TRANSFORM] commandes — début: {initial} lignes")

    # R1 — Remove duplicates
    df = df.drop_duplicates(subset=['id_commande'], keep='last')
    logger.info(f"[TRANSFORM] R1 doublons — {initial - len(df)} lignes supprimées")

    # R2 — Standardize dates
    for col in ['date_commande', 'date_livraison']:
        before_na = df[col].isna().sum()
        df[col] = pd.to_datetime(
            df[col], format='mixed', dayfirst=True, errors='coerce'
        )
        after_na = df[col].isna().sum()
        logger.info(f"[TRANSFORM] R2 {col} — {after_na - before_na} dates invalides")
    df = df.dropna(subset=['date_commande'])

    # R3 — Harmonize city names
    mapping = charger_referentiel_villes(df_regions)
    df['ville_livraison'] = (
        df['ville_livraison']
        .str.strip()
        .str.lower()
        .map(mapping)
        .fillna('Non renseignée')
    )
    non_renseignes = (df['ville_livraison'] == 'Non renseignée').sum()
    logger.info(f"[TRANSFORM] R3 villes — {non_renseignes} villes non reconnues")

    # R4 — Standardize statuts
    mapping_statuts = {
        'livré': 'livré', 'livre': 'livré', 'LIVRE': 'livré', 'DONE': 'livré',
        'annulé': 'annulé', 'annule': 'annulé', 'KO': 'annulé',
        'en_cours': 'en_cours', 'OK': 'en_cours',
        'retourné': 'retourné', 'retourne': 'retourné'
    }
    df['statut'] = df['statut'].replace(mapping_statuts)
    invalides = ~df['statut'].isin(['livré', 'annulé', 'en_cours', 'retourné'])
    if invalides.sum() > 0:
        logger.warning(f"[TRANSFORM] R4 statuts — {invalides.sum()} valeurs non reconnues → 'inconnu'")
    else:
        logger.info(f"[TRANSFORM] R4 statuts — tous les statuts reconnus")
    df.loc[invalides, 'statut'] = 'inconnu'

    # R5 — Remove negative quantities
    avant = len(df)
    df = df[df['quantite'].astype(float) > 0]
    logger.info(f"[TRANSFORM] R5 quantités — {avant - len(df)} lignes supprimées (quantité <= 0)")

    # R6 — Remove test orders (prix = 0)
    avant = len(df)
    df = df[df['prix_unitaire'].astype(float) > 0]
    logger.info(f"[TRANSFORM] R6 prix nuls — {avant - len(df)} commandes test supprimées")

    # R7 — Fill missing livreurs
    manquants = df['id_livreur'].isna().sum()
    df['id_livreur'] = df['id_livreur'].fillna('-1')
    logger.info(f"[TRANSFORM] R7 livreurs — {manquants} valeurs manquantes → '-1'")

    # Final type conversions
    df['quantite']      = df['quantite'].astype(float).astype(int)
    df['prix_unitaire'] = df['prix_unitaire'].astype(float)
    df['montant_ttc']   = df['quantite'] * df['prix_unitaire']
    df['montant_ht']    = (df['montant_ttc'] / 1.20).round(2)

    final = len(df)
    logger.info(f"[TRANSFORM] commandes — fin: {final} lignes ({initial - final} supprimées au total)")
    return df