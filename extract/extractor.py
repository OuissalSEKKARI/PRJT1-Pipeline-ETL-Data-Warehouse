import pandas as pd
import json
from utils.logger import get_logger
from config.settings import COMMANDES_FILE, CLIENTS_FILE, PRODUITS_FILE, REGIONS_FILE

logger = get_logger('extractor')

def extract_commandes() -> pd.DataFrame:
    """
    Extracts raw orders from CSV.
    Everything read as string to avoid implicit type conversions.
    """
    df = pd.read_csv(COMMANDES_FILE, encoding='utf-8', dtype=str)
    logger.info(f"[EXTRACT] commandes — {len(df)} lignes extraites")
    return df

def extract_clients() -> pd.DataFrame:
    """
    Extracts raw clients from CSV.
    """
    df = pd.read_csv(CLIENTS_FILE, encoding='utf-8', dtype=str)
    logger.info(f"[EXTRACT] clients — {len(df)} lignes extraites")
    return df

def extract_produits() -> pd.DataFrame:
    """
    Extracts raw products from JSON.
    """
    with open(PRODUITS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    df = pd.DataFrame(data['produits'])
    logger.info(f"[EXTRACT] produits — {len(df)} lignes extraites")
    return df

def extract_regions() -> pd.DataFrame:
    """
    Extracts the clean geographic reference file.
    """
    df = pd.read_csv(REGIONS_FILE, encoding='utf-8', dtype=str)
    logger.info(f"[EXTRACT] regions — {len(df)} lignes extraites")
    return df