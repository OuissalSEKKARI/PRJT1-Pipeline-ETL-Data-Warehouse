import pandas as pd
from datetime import date, timedelta
from utils.logger import get_logger

logger = get_logger('build_dimensions')

# ─────────────────────────────────────────────
# DIM_TEMPS
# ─────────────────────────────────────────────

def build_dim_temps(date_debut: str = '2020-01-01', date_fin: str = '2025-12-31') -> pd.DataFrame:
    """
    Generates the full time dimension between two dates.
    Includes Moroccan holidays and Ramadan periods.
    """
    dates = pd.date_range(start=date_debut, end=date_fin, freq='D')

    feries_maroc = [
        '2020-01-01', '2020-01-11', '2020-05-01', '2020-07-30',
        '2020-08-14', '2020-11-06', '2020-11-18',
        '2021-01-01', '2021-01-11', '2021-05-01', '2021-07-30',
        '2021-08-14', '2021-11-06', '2021-11-18',
        '2022-01-01', '2022-01-11', '2022-05-01', '2022-07-30',
        '2022-08-14', '2022-11-06', '2022-11-18',
        '2023-01-01', '2023-01-11', '2023-05-01', '2023-07-30',
        '2023-08-14', '2023-11-06', '2023-11-18',
        '2024-01-01', '2024-01-11', '2024-05-01', '2024-07-30',
        '2024-08-14', '2024-11-06', '2024-11-18',
        '2025-01-01', '2025-01-11', '2025-05-01', '2025-07-30',
        '2025-08-14', '2025-11-06', '2025-11-18',
    ]

    ramadan_periodes = [
        ('2022-04-02', '2022-05-01'),
        ('2023-03-22', '2023-04-20'),
        ('2024-03-10', '2024-04-09'),
        ('2025-03-01', '2025-03-30'),
    ]

    df = pd.DataFrame({
        'id_date':         dates.strftime('%Y%m%d').astype(int),
        'date_complete':   dates.date,          # FIX: colonne obligatoire NOT NULL
        'jour':            dates.day,
        'mois':            dates.month,
        'trimestre':       dates.quarter,
        'annee':           dates.year,
        'semaine':         dates.isocalendar().week.astype(int),
        'libelle_jour':    dates.strftime('%A'),
        'libelle_mois':    dates.strftime('%B'),
        'est_weekend':     dates.dayofweek >= 5,
        'est_ferie_maroc': dates.strftime('%Y-%m-%d').isin(feries_maroc),
        'periode_ramadan': False,
    })

    for debut, fin in ramadan_periodes:
        mask = (df['date_complete'].astype(str) >= debut) & \
               (df['date_complete'].astype(str) <= fin)
        df.loc[mask, 'periode_ramadan'] = True

    # NE PAS supprimer date_complete — colonne NOT NULL dans PostgreSQL
    logger.info(f"[BUILD] dim_temps — {len(df)} lignes générées")
    return df


# ─────────────────────────────────────────────
# DIM_REGION
# ─────────────────────────────────────────────

def build_dim_region(df_regions: pd.DataFrame) -> pd.DataFrame:
    """
    Builds region dimension from the clean reference file.
    """
    df = df_regions[['code_ville', 'nom_ville_standard', 'province',
                      'region_admin', 'zone_geo']].copy()

    # FIX: renommer pour correspondre à la colonne 'ville' dans PostgreSQL
    df = df.rename(columns={'nom_ville_standard': 'ville'})

    df.insert(0, 'id_region', range(1, len(df) + 1))
    df['pays'] = 'Maroc'
    logger.info(f"[BUILD] dim_region — {len(df)} lignes")
    return df


# ─────────────────────────────────────────────
# DIM_PRODUIT (with SCD Type 2)
# ─────────────────────────────────────────────

def build_dim_produit(df_produits: pd.DataFrame) -> pd.DataFrame:
    """
    Builds product dimension with SCD Type 2 support.
    Inactive products get a closed record (date_fin = today).
    The iPhone 15 category change (Téléphones → Smartphones)
    is handled as a Type 2 change.
    """
    today = date.today().strftime('%Y-%m-%d')
    scd_change_date = '2024-03-01'

    rows = []
    sk = 1

    for _, p in df_produits.iterrows():
        # SCD Type 2 — iPhone 15: was 'Téléphones', became 'Smartphones'
        if p['id_produit_nk'] == 'P004':
            rows.append({
                'id_produit_sk':  sk,
                'id_produit_nk':  p['id_produit_nk'],
                'nom_produit':    p['nom_produit'],
                'categorie':      p['categorie'],
                'sous_categorie': 'Téléphones',
                'marque':         p['marque'],
                'fournisseur':    p['fournisseur'],
                'prix_standard':  p['prix_standard'],
                'origine_pays':   p['origine_pays'],
                'date_debut':     '2023-09-22',
                'date_fin':       '2024-02-28',
                'est_actif':      False,
            })
            sk += 1
            rows.append({
                'id_produit_sk':  sk,
                'id_produit_nk':  p['id_produit_nk'],
                'nom_produit':    p['nom_produit'],
                'categorie':      p['categorie'],
                'sous_categorie': p['sous_categorie'],
                'marque':         p['marque'],
                'fournisseur':    p['fournisseur'],
                'prix_standard':  p['prix_standard'],
                'origine_pays':   p['origine_pays'],
                'date_debut':     scd_change_date,
                'date_fin':       '9999-12-31',
                'est_actif':      True,
            })
            sk += 1
        else:
            est_actif = bool(p['actif'])
            rows.append({
                'id_produit_sk':  sk,
                'id_produit_nk':  p['id_produit_nk'],
                'nom_produit':    p['nom_produit'],
                'categorie':      p['categorie'],
                'sous_categorie': p['sous_categorie'],
                'marque':         p['marque'],
                'fournisseur':    p['fournisseur'],
                'prix_standard':  p['prix_standard'],
                'origine_pays':   p['origine_pays'],
                'date_debut':     p.get('date_creation', '2020-01-01'),
                'date_fin':       today if not est_actif else '9999-12-31',
                'est_actif':      est_actif,
            })
            sk += 1

    df = pd.DataFrame(rows)
    logger.info(f"[BUILD] dim_produit — {len(df)} lignes (dont SCD Type 2)")
    return df


# ─────────────────────────────────────────────
# DIM_CLIENT (with SCD Type 2)
# ─────────────────────────────────────────────

def build_dim_client(
    df_clients: pd.DataFrame,
    df_commandes: pd.DataFrame,
    dim_region: pd.DataFrame          # FIX: ajout pour récupérer region_admin
) -> pd.DataFrame:
    """
    Builds client dimension with:
    - Gold/Silver/Bronze segmentation based on last 12 months CA
    - SCD Type 2 structure (date_debut, date_fin, est_actif)
    - region_admin joined from dim_region
    - sexe normalisé en CHAR(1) : 'm' / 'f' / 'i'
    """
    # Calcul des segments depuis les commandes
    date_limite = pd.to_datetime(df_commandes['date_commande']).max() - timedelta(days=365)
    df_recents = df_commandes[
        (df_commandes['date_commande'] >= date_limite) &
        (df_commandes['statut'] == 'livré')
    ].copy()
    df_recents['montant_ttc'] = (
        df_recents['quantite'].astype(float) *
        df_recents['prix_unitaire'].astype(float)
    )
    ca_par_client = (
        df_recents.groupby('id_client')['montant_ttc']
        .sum()
        .reset_index()
        .rename(columns={'montant_ttc': 'ca_12m'})
    )

    def segmenter(ca):
        if ca >= 15000: return 'Gold'
        elif ca >= 5000: return 'Silver'
        else: return 'Bronze'

    ca_par_client['segment_client'] = ca_par_client['ca_12m'].apply(segmenter)

    # Merge segments
    df = df_clients.merge(
        ca_par_client[['id_client', 'segment_client']],
        on='id_client', how='left'
    )
    df['segment_client'] = df['segment_client'].fillna('Bronze')

    # FIX: normaliser sexe → CHAR(1) uniquement 'm', 'f', 'i'
    def normaliser_sexe(s):
        if pd.isna(s):
            return 'i'
        s = str(s).strip().lower()
        if s in ('m', 'homme', 'male', 'h', '1'):
            return 'm'
        elif s in ('f', 'femme', 'female', '0'):
            return 'f'
        else:
            return 'i'

    df['sexe'] = df['sexe'].apply(normaliser_sexe)

    # FIX: joindre region_admin depuis dim_region
    region_map = dim_region[['ville', 'region_admin']].drop_duplicates(subset=['ville'])
    df = df.merge(region_map, on='ville', how='left')
    df['region_admin'] = df['region_admin'].fillna('Non renseignée')

    # Build dimension
    df = df.rename(columns={'id_client': 'id_client_nk'})
    df.insert(0, 'id_client_sk', range(1, len(df) + 1))

    # SCD Type 2 columns
    df['date_debut'] = df['date_inscription'].dt.strftime('%Y-%m-%d').fillna('2020-01-01')
    df['date_fin']   = '9999-12-31'
    df['est_actif']  = True

    # Colonnes finales — region_admin ajoutée
    df = df[[
        'id_client_sk', 'id_client_nk', 'nom_complet', 'tranche_age',
        'sexe', 'ville', 'region_admin',
        'segment_client', 'canal_acquisition',
        'date_debut', 'date_fin', 'est_actif'
    ]]

    logger.info(f"[BUILD] dim_client — {len(df)} lignes")
    logger.info(f"[BUILD] segments — {df['segment_client'].value_counts().to_dict()}")
    return df


# ─────────────────────────────────────────────
# BUILD_CLIENT_ID_MAPPING
# ─────────────────────────────────────────────

def build_client_id_mapping(df_clients_raw: pd.DataFrame) -> dict:
    """
    For duplicate clients (same email, different id_client),
    maps the removed duplicate ID → the surviving ID.
    Used to remap order foreign keys before loading FAIT_VENTES.
    """
    df = df_clients_raw.copy()
    df['email_norm'] = df['email'].str.lower().str.strip()
    df['date_inscription'] = pd.to_datetime(df['date_inscription'], errors='coerce')

    surviving = (
        df.sort_values('date_inscription')
        .drop_duplicates(subset=['email_norm'], keep='last')
        [['email_norm', 'id_client']]
        .rename(columns={'id_client': 'id_client_surviving'})
    )

    merged = df.merge(surviving, on='email_norm', how='left')

    mapping = {}
    for _, row in merged.iterrows():
        if row['id_client'] != row['id_client_surviving']:
            mapping[row['id_client']] = row['id_client_surviving']

    logger.info(f"[BUILD] client_id_mapping — {len(mapping)} IDs remappés")
    return mapping


# ─────────────────────────────────────────────
# DIM_LIVREUR
# ─────────────────────────────────────────────

def build_dim_livreur(df_commandes: pd.DataFrame) -> pd.DataFrame:
    """
    Builds delivery driver dimension from unique livreur IDs in commandes.
    Livreur -1 = unknown driver.
    """
    livreurs = df_commandes['id_livreur'].dropna().unique()

    transport_types = ['Moto', 'Camionnette', 'Vélo', 'Voiture']
    zones = ['Nord', 'Sud', 'Est', 'Ouest', 'Centre', 'Grand Casablanca']

    import random
    random.seed(42)

    rows = []
    for i, lid in enumerate(sorted(livreurs), start=1):
        if lid == '-1':
            rows.append({
                'id_livreur':     i,
                'id_livreur_nk':  '-1',
                'nom_livreur':    'Livreur Inconnu',
                'type_transport': None,
                'zone_couverture': None,
            })
        else:
            rows.append({
                'id_livreur':     i,
                'id_livreur_nk':  lid,
                'nom_livreur':    f"Livreur {lid}",
                'type_transport': random.choice(transport_types),
                'zone_couverture': random.choice(zones),
            })

    df = pd.DataFrame(rows)
    logger.info(f"[BUILD] dim_livreur — {len(df)} lignes")
    return df


# ─────────────────────────────────────────────
# FAIT_VENTES
# ─────────────────────────────────────────────

def build_fait_ventes(
    df_commandes: pd.DataFrame,
    dim_temps: pd.DataFrame,
    dim_client: pd.DataFrame,
    dim_produit: pd.DataFrame,
    dim_region: pd.DataFrame,
    dim_livreur: pd.DataFrame,
    client_id_mapping: dict = {},
) -> pd.DataFrame:
    """
    Builds the central fact table by joining commandes
    with all dimension surrogate keys.
    Granularity: 1 row = 1 order line (1 product in 1 order)
    """
    df = df_commandes.copy()

    if client_id_mapping:
        df['id_client'] = df['id_client'].replace(client_id_mapping)
        logger.info(f"[BUILD] fait_ventes — IDs clients remappés")

    # Convert dates to id_date format (YYYYMMDD integer)
    df['id_date'] = pd.to_datetime(
        df['date_commande']
    ).dt.strftime('%Y%m%d').astype(int)

    df['id_date_livraison'] = pd.to_datetime(
        df['date_livraison'], errors='coerce'
    ).dt.strftime('%Y%m%d').astype(float).astype('Int64')

    # Calculate delivery delay
    df['delai_livraison_jours'] = (
        pd.to_datetime(df['date_livraison'], errors='coerce') -
        pd.to_datetime(df['date_commande'])
    ).dt.days

    # Join client SK
    client_map = dim_client[['id_client_nk', 'id_client_sk', 'est_actif']].copy()
    client_map = client_map[client_map['est_actif'] == True]
    df = df.merge(
        client_map[['id_client_nk', 'id_client_sk']],
        left_on='id_client', right_on='id_client_nk', how='left'
    )

    # Join produit SK - date-aware SCD Type 2 join
    df['date_commande_dt'] = pd.to_datetime(df['date_commande'])

    produit_map = dim_produit[['id_produit_nk', 'id_produit_sk', 'date_debut', 'date_fin']].copy()
    produit_map['date_debut'] = pd.to_datetime(produit_map['date_debut'])
    produit_map['date_fin']   = pd.to_datetime(produit_map['date_fin'])

    df = df.merge(produit_map, left_on='id_produit', right_on='id_produit_nk', how='left')
    df = df[
        (df['date_commande_dt'] >= df['date_debut']) &
        (df['date_commande_dt'] <= df['date_fin'])
    ]

    # Join region SK — FIX: colonne 'ville' (renommée dans build_dim_region)
    region_map = dim_region[['ville', 'id_region']]
    df = df.merge(region_map, left_on='ville_livraison', right_on='ville', how='left')

    # Join livreur SK
    df = df.rename(columns={'id_livreur': 'id_livreur_source'})
    livreur_map = dim_livreur[['id_livreur_nk', 'id_livreur']]
    df = df.merge(
        livreur_map,
        left_on='id_livreur_source', right_on='id_livreur_nk', how='left'
    )

    # Calculate amounts
    df['montant_ttc'] = df['quantite'].astype(float) * df['prix_unitaire'].astype(float)
    df['montant_ht']  = (df['montant_ttc'] / 1.20).round(2)

    # Select and rename final columns
    fait = df[[
        'id_date',
        'id_produit_sk',
        'id_client_sk',
        'id_region',
        'id_livreur',
        'quantite',
        'montant_ht',
        'montant_ttc',
        'delai_livraison_jours',
        'statut',
    ]].rename(columns={
        'id_produit_sk':  'id_produit',
        'id_client_sk':   'id_client',
        'quantite':       'quantite_vendue',
        'statut':         'statut_commande',
    })

    # Add surrogate key
    fait.insert(0, 'id_vente', range(1, len(fait) + 1))

    # Log null FKs
    for col in ['id_produit', 'id_client', 'id_region']:
        nulls = fait[col].isna().sum()
        if nulls > 0:
            logger.warning(f"[BUILD] fait_ventes — {nulls} valeurs nulles sur {col}")

    logger.info(f"[BUILD] fait_ventes — {len(fait)} lignes")
    return fait
