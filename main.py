from extract.extractor import (
    extract_commandes, extract_clients,
    extract_produits, extract_regions
)
from transform.clean_commandes import transform_commandes
from transform.clean_clients import transform_clients
from transform.clean_produits import transform_produits
from transform.build_dimensions import (
    build_dim_temps, build_dim_region,
    build_dim_produit, build_dim_client,
    build_dim_livreur, build_fait_ventes,
    build_client_id_mapping
)
from load.loader import load_all
from utils.logger import get_logger

logger = get_logger('main')

def run_pipeline():
    logger.info("=" * 50)
    logger.info("MEXORA ETL PIPELINE — DÉMARRAGE")
    logger.info("=" * 50)

    # ── EXTRACT ──────────────────────────────
    logger.info("[1/3] EXTRACTION...")
    regions   = extract_regions()
    commandes = extract_commandes()
    clients   = extract_clients()
    produits  = extract_produits()

    # ── TRANSFORM ────────────────────────────
    logger.info("[2/3] TRANSFORMATION...")
    commandes_clean = transform_commandes(commandes, regions)
    clients_clean   = transform_clients(clients, regions)
    produits_clean  = transform_produits(produits)

    client_mapping  = build_client_id_mapping(clients)

    dim_temps   = build_dim_temps()
    dim_region  = build_dim_region(regions)
    dim_produit = build_dim_produit(produits_clean)
    dim_client  = build_dim_client(clients_clean, commandes_clean)
    dim_livreur = build_dim_livreur(commandes_clean)
    fait_ventes = build_fait_ventes(
        commandes_clean, dim_temps, dim_client,
        dim_produit, dim_region, dim_livreur,
        client_id_mapping=client_mapping
    )

    # ── LOAD ─────────────────────────────────
    logger.info("[3/3] CHARGEMENT...")
    load_all(dim_temps, dim_region, dim_produit,
             dim_client, dim_livreur, fait_ventes)

    logger.info("=" * 50)
    logger.info("PIPELINE TERMINÉ AVEC SUCCÈS ✅")
    logger.info("=" * 50)

if __name__ == "__main__":
    run_pipeline()