-- =============================================================
--  create_dwh.sql  —  Mexora Analytics Data Warehouse
--  Création complète : schémas, dimensions, faits,
--  index, et vues matérialisées
--
--  Exécution :
--    psql -U postgres -d mexora_dwh -f create_dwh.sql
-- =============================================================


-- =============================================================
--  0. SCHÉMAS
-- =============================================================

CREATE SCHEMA IF NOT EXISTS staging_mexora;
CREATE SCHEMA IF NOT EXISTS dwh_mexora;
CREATE SCHEMA IF NOT EXISTS reporting_mexora;

-- =============================================================
--  1. SUPPRESSION DES TABLES (si re-exécution)
--     Ordre inverse des dépendances FK
-- =============================================================

DROP TABLE IF EXISTS dwh_mexora.fait_ventes   CASCADE;
DROP TABLE IF EXISTS dwh_mexora.dim_client     CASCADE;
DROP TABLE IF EXISTS dwh_mexora.dim_produit    CASCADE;
DROP TABLE IF EXISTS dwh_mexora.dim_livreur    CASCADE;
DROP TABLE IF EXISTS dwh_mexora.dim_region     CASCADE;
DROP TABLE IF EXISTS dwh_mexora.dim_temps      CASCADE;

DROP MATERIALIZED VIEW IF EXISTS reporting_mexora.mv_ca_mensuel           CASCADE;
DROP MATERIALIZED VIEW IF EXISTS reporting_mexora.mv_top_produits          CASCADE;
DROP MATERIALIZED VIEW IF EXISTS reporting_mexora.mv_performance_livreurs  CASCADE;


-- =============================================================
--  2. DIMENSION TEMPS
-- =============================================================

CREATE TABLE dwh_mexora.dim_temps (
    id_date          INTEGER      PRIMARY KEY,  -- format YYYYMMDD
    date_complete    DATE         NOT NULL,
    jour             SMALLINT     NOT NULL CHECK (jour BETWEEN 1 AND 31),
    mois             SMALLINT     NOT NULL CHECK (mois BETWEEN 1 AND 12),
    trimestre        SMALLINT     NOT NULL CHECK (trimestre BETWEEN 1 AND 4),
    annee            SMALLINT     NOT NULL,
    semaine          SMALLINT,
    libelle_jour     VARCHAR(20),
    libelle_mois     VARCHAR(20),
    est_weekend      BOOLEAN      DEFAULT FALSE,
    est_ferie_maroc  BOOLEAN      DEFAULT FALSE,
    periode_ramadan  BOOLEAN      DEFAULT FALSE
);

COMMENT ON TABLE dwh_mexora.dim_temps IS
    'Dimension temporelle couvrant 2020-2025. '
    'Inclut jours fériés marocains et périodes Ramadan.';


-- =============================================================
--  3. DIMENSION RÉGION
-- =============================================================

CREATE TABLE dwh_mexora.dim_region (
    id_region     SERIAL       PRIMARY KEY,
    code_ville    VARCHAR(10)  NOT NULL UNIQUE,
    ville         VARCHAR(100) NOT NULL,
    province      VARCHAR(100),
    region_admin  VARCHAR(100),
    zone_geo      VARCHAR(50),
    population    INTEGER,
    code_postal   INTEGER,
    pays          VARCHAR(50)  DEFAULT 'Maroc'
);

COMMENT ON TABLE dwh_mexora.dim_region IS
    'Référentiel géographique officiel du Maroc. '
    'Source : regions_maroc.csv — fichier propre sans problèmes.';


-- =============================================================
--  4. DIMENSION PRODUIT  (SCD Type 2)
-- =============================================================

CREATE TABLE dwh_mexora.dim_produit (
    -- Clé surrogate (SK) : clé technique du DWH
    id_produit_sk    SERIAL       PRIMARY KEY,
    -- Clé naturelle (NK) : identifiant source
    id_produit_nk    VARCHAR(20)  NOT NULL,

    nom_produit      VARCHAR(200) NOT NULL,
    categorie        VARCHAR(100),
    sous_categorie   VARCHAR(100),
    marque           VARCHAR(100),
    fournisseur      VARCHAR(100),
    prix_standard    DECIMAL(10,2),
    origine_pays     VARCHAR(50),

    -- Colonnes SCD Type 2 :
    -- Quand la catégorie ou le prix d'un produit change,
    -- on insère une nouvelle ligne au lieu d'écraser l'ancienne.
    -- Les ventes historiques restent liées à l'ancienne version.
    date_debut       DATE         NOT NULL DEFAULT CURRENT_DATE,
    date_fin         DATE         NOT NULL DEFAULT '9999-12-31',
    est_actif        BOOLEAN      NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE dwh_mexora.dim_produit IS
    'Dimension produit avec SCD Type 2. '
    'Chaque changement de catégorie ou de prix génère une nouvelle ligne. '
    'est_actif=TRUE identifie la version courante.';

COMMENT ON COLUMN dwh_mexora.dim_produit.date_fin IS
    '9999-12-31 = enregistrement courant (pas encore fermé).';


-- =============================================================
--  5. DIMENSION CLIENT  (SCD Type 2)
-- =============================================================

CREATE TABLE dwh_mexora.dim_client (
    -- Clé surrogate
    id_client_sk       SERIAL      PRIMARY KEY,
    -- Clé naturelle
    id_client_nk       VARCHAR(20) NOT NULL,

    nom_complet        VARCHAR(200),
    tranche_age        VARCHAR(10),
    sexe               CHAR(1)     CHECK (sexe IN ('m','f','i')),
    ville              VARCHAR(100),
    region_admin       VARCHAR(100),
    segment_client     VARCHAR(20) CHECK (segment_client IN ('Gold','Silver','Bronze')),
    canal_acquisition  VARCHAR(50),

    -- SCD Type 2 : le segment client change dans le temps
    -- (ex: un client Bronze peut devenir Gold l'année suivante)
    -- On conserve l'historique pour analyser les ventes
    -- avec le bon segment au moment de l'achat.
    date_debut         DATE        NOT NULL DEFAULT CURRENT_DATE,
    date_fin           DATE        NOT NULL DEFAULT '9999-12-31',
    est_actif          BOOLEAN     NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE dwh_mexora.dim_client IS
    'Dimension client avec SCD Type 2 sur le segment_client. '
    'Un client Bronze devenu Gold aura 2 lignes dans cette table.';


-- =============================================================
--  6. DIMENSION LIVREUR
-- =============================================================

CREATE TABLE dwh_mexora.dim_livreur (
    id_livreur       SERIAL      PRIMARY KEY,
    id_livreur_nk    VARCHAR(20),
    nom_livreur      VARCHAR(100),
    type_transport   VARCHAR(50),
    zone_couverture  VARCHAR(100)
);

-- Ligne spéciale pour les livreurs inconnus (id_livreur_nk = '-1')
INSERT INTO dwh_mexora.dim_livreur
    (id_livreur_nk, nom_livreur, type_transport, zone_couverture)
VALUES
    ('-1', 'Livreur Inconnu', 'Inconnu', 'Non renseignée');

COMMENT ON TABLE dwh_mexora.dim_livreur IS
    'Dimension livreur. '
    'La ligne id_livreur_nk=-1 représente les livraisons sans livreur identifié '
    '(7% des commandes source).';


-- =============================================================
--  7. TABLE DE FAITS  —  FAIT_VENTES
--
--  Granularité : 1 ligne = 1 ligne de commande
--  (une commande peut avoir plusieurs produits →
--   plusieurs lignes dans fait_ventes)
--
--  Mesures :
--    additives     : quantite_vendue, montant_ht, montant_ttc,
--                    cout_livraison
--    semi-additives: delai_livraison_jours (moyenne ≠ somme)
--    non-additives : remise_pct (taux → toujours recalculer)
-- =============================================================

CREATE TABLE dwh_mexora.fait_ventes (
    id_vente               BIGSERIAL    PRIMARY KEY,

    -- Clés étrangères vers les dimensions
    id_date                INTEGER      NOT NULL
                               REFERENCES dwh_mexora.dim_temps(id_date),
    id_produit             INTEGER      NOT NULL
                               REFERENCES dwh_mexora.dim_produit(id_produit_sk),
    id_client              INTEGER      NOT NULL
                               REFERENCES dwh_mexora.dim_client(id_client_sk),
    id_region              INTEGER      NOT NULL
                               REFERENCES dwh_mexora.dim_region(id_region),
    id_livreur             INTEGER
                               REFERENCES dwh_mexora.dim_livreur(id_livreur),

    -- Mesures additives (peuvent être sommées sur toutes les dimensions)
    quantite_vendue        INTEGER      NOT NULL CHECK (quantite_vendue > 0),
    montant_ht             DECIMAL(12,2) NOT NULL,
    montant_ttc            DECIMAL(12,2) NOT NULL,
    cout_livraison         DECIMAL(8,2)  DEFAULT 0,

    -- Mesure semi-additive (moyenne valide, somme n'a pas de sens)
    delai_livraison_jours  SMALLINT,

    -- Mesure non-additive (taux → ne jamais sommer, toujours recalculer)
    remise_pct             DECIMAL(5,2)  DEFAULT 0,

    -- Statut de la commande
    statut_commande        VARCHAR(20)
                               CHECK (statut_commande IN
                                   ('livré','annulé','en_cours','retourné','inconnu')),

    -- Métadonnées ETL
    date_chargement        TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE dwh_mexora.fait_ventes IS
    'Table de faits centrale. Granularité : 1 ligne = 1 commande. '
    '36 705 lignes chargées après nettoyage et jointures DWH (51 500 lignes brutes).';

COMMENT ON COLUMN dwh_mexora.fait_ventes.montant_ht IS
    'Mesure additive : peut être sommée par région, produit, période.';

COMMENT ON COLUMN dwh_mexora.fait_ventes.delai_livraison_jours IS
    'Mesure semi-additive : valide en moyenne, pas en somme.';

COMMENT ON COLUMN dwh_mexora.fait_ventes.remise_pct IS
    'Mesure non-additive : taux en %. Ne jamais sommer.';


-- =============================================================
--  8. INDEX
-- =============================================================

-- Index simples sur les clés étrangères (accélèrent les jointures)
CREATE INDEX idx_fv_date     ON dwh_mexora.fait_ventes(id_date);
CREATE INDEX idx_fv_produit  ON dwh_mexora.fait_ventes(id_produit);
CREATE INDEX idx_fv_client   ON dwh_mexora.fait_ventes(id_client);
CREATE INDEX idx_fv_region   ON dwh_mexora.fait_ventes(id_region);
CREATE INDEX idx_fv_livreur  ON dwh_mexora.fait_ventes(id_livreur);

-- Index composite : requêtes analytiques par date + région (les plus fréquentes)
CREATE INDEX idx_fv_date_region
    ON dwh_mexora.fait_ventes(id_date, id_region)
    INCLUDE (montant_ttc, quantite_vendue);

-- Index partiel : filtre sur commandes livrées uniquement (KPI principaux)
CREATE INDEX idx_fv_livre
    ON dwh_mexora.fait_ventes(statut_commande)
    WHERE statut_commande = 'livré';

-- Index sur dim_produit pour les lookups SCD
CREATE INDEX idx_dp_nk_actif
    ON dwh_mexora.dim_produit(id_produit_nk, est_actif);

-- Index sur dim_client pour les lookups SCD
CREATE INDEX idx_dc_nk_actif
    ON dwh_mexora.dim_client(id_client_nk, est_actif);

-- Index sur dim_temps pour les filtres temporels fréquents
CREATE INDEX idx_dt_annee_mois
    ON dwh_mexora.dim_temps(annee, mois);

CREATE INDEX idx_dt_ramadan
    ON dwh_mexora.dim_temps(periode_ramadan)
    WHERE periode_ramadan = TRUE;


-- =============================================================
--  9. VUES MATÉRIALISÉES
-- =============================================================

-- ------------------------------------------------------------
--  Vue 1 — CA mensuel par région et catégorie
--  Répond aux questions :
--    → Quelle région génère le plus de CA ?
--    → Y a-t-il un effet Ramadan sur l'alimentation ?
-- ------------------------------------------------------------

CREATE MATERIALIZED VIEW reporting_mexora.mv_ca_mensuel AS
SELECT
    t.annee,
    t.mois,
    t.trimestre,
    t.libelle_mois,
    t.periode_ramadan,
    r.region_admin,
    r.zone_geo,
    r.ville,
    p.categorie,
    -- Mesures
    SUM(f.montant_ttc)              AS ca_ttc,
    SUM(f.montant_ht)               AS ca_ht,
    SUM(f.quantite_vendue)          AS volume_vendu,
    COUNT(DISTINCT f.id_vente)      AS nb_commandes,
    COUNT(DISTINCT f.id_client)     AS nb_clients_actifs,
    ROUND(AVG(f.montant_ttc), 2)    AS panier_moyen
FROM dwh_mexora.fait_ventes      f
JOIN dwh_mexora.dim_temps        t ON f.id_date    = t.id_date
JOIN dwh_mexora.dim_region       r ON f.id_region  = r.id_region
JOIN dwh_mexora.dim_produit      p ON f.id_produit = p.id_produit_sk
WHERE f.statut_commande = 'livré'
GROUP BY
    t.annee, t.mois, t.trimestre, t.libelle_mois, t.periode_ramadan,
    r.region_admin, r.zone_geo, r.ville,
    p.categorie
WITH DATA;

CREATE INDEX ON reporting_mexora.mv_ca_mensuel(annee, mois);
CREATE INDEX ON reporting_mexora.mv_ca_mensuel(region_admin);
CREATE INDEX ON reporting_mexora.mv_ca_mensuel(categorie);
CREATE INDEX ON reporting_mexora.mv_ca_mensuel(periode_ramadan);


-- ------------------------------------------------------------
--  Vue 2 — Top produits par trimestre
--  Répond à la question :
--    → Quels sont les 10 produits les plus vendus par trimestre ?
-- ------------------------------------------------------------

CREATE MATERIALIZED VIEW reporting_mexora.mv_top_produits AS
SELECT
    t.annee,
    t.trimestre,
    r.ville,
    r.region_admin,
    p.id_produit_nk,
    p.nom_produit,
    p.categorie,
    p.marque,
    -- Mesures
    SUM(f.quantite_vendue)          AS qte_totale,
    SUM(f.montant_ttc)              AS ca_total,
    COUNT(DISTINCT f.id_client)     AS nb_clients_distincts,
    COUNT(DISTINCT f.id_vente)      AS nb_commandes,
    -- Rang dans la catégorie par trimestre
    RANK() OVER (
        PARTITION BY t.annee, t.trimestre, p.categorie
        ORDER BY SUM(f.montant_ttc) DESC
    )                               AS rang_categorie,
    -- Rang global par trimestre
    RANK() OVER (
        PARTITION BY t.annee, t.trimestre
        ORDER BY SUM(f.montant_ttc) DESC
    )                               AS rang_global
FROM dwh_mexora.fait_ventes      f
JOIN dwh_mexora.dim_temps        t ON f.id_date    = t.id_date
JOIN dwh_mexora.dim_produit      p ON f.id_produit = p.id_produit_sk
JOIN dwh_mexora.dim_region       r ON f.id_region  = r.id_region
WHERE f.statut_commande = 'livré'
GROUP BY
    t.annee, t.trimestre,
    r.ville, r.region_admin,
    p.id_produit_nk, p.nom_produit, p.categorie, p.marque
WITH DATA;

CREATE INDEX ON reporting_mexora.mv_top_produits(annee, trimestre);
CREATE INDEX ON reporting_mexora.mv_top_produits(ville);
CREATE INDEX ON reporting_mexora.mv_top_produits(rang_global);


-- ------------------------------------------------------------
--  Vue 3 — Performance livreurs (taux de retard)
--  Répond à la question :
--    → Quel livreur a le meilleur taux de livraison ?
-- ------------------------------------------------------------

CREATE MATERIALIZED VIEW reporting_mexora.mv_performance_livreurs AS
SELECT
    l.id_livreur_nk,
    l.nom_livreur,
    l.zone_couverture,
    t.annee,
    t.mois,
    -- Mesures
    COUNT(*)                                                    AS nb_livraisons,
    ROUND(AVG(f.delai_livraison_jours), 1)                      AS delai_moyen_jours,
    COUNT(*) FILTER (WHERE f.delai_livraison_jours > 3)         AS nb_retards,
    ROUND(
        COUNT(*) FILTER (WHERE f.delai_livraison_jours > 3)
        * 100.0 / NULLIF(COUNT(*), 0), 2
    )                                                           AS taux_retard_pct
FROM dwh_mexora.fait_ventes      f
JOIN dwh_mexora.dim_livreur      l ON f.id_livreur = l.id_livreur
JOIN dwh_mexora.dim_temps        t ON f.id_date    = t.id_date
WHERE f.statut_commande IN ('livré', 'retourné')
  AND f.delai_livraison_jours IS NOT NULL
GROUP BY
    l.id_livreur_nk, l.nom_livreur, l.zone_couverture,
    t.annee, t.mois
WITH DATA;

CREATE INDEX ON reporting_mexora.mv_performance_livreurs(annee, mois);
CREATE INDEX ON reporting_mexora.mv_performance_livreurs(nom_livreur);


-- =============================================================
--  10. MESSAGE DE CONFIRMATION
-- =============================================================

DO $$
BEGIN
    RAISE NOTICE '=============================================';
    RAISE NOTICE ' DWH Mexora créé avec succès !';
    RAISE NOTICE '---------------------------------------------';
    RAISE NOTICE ' Schémas  : staging_mexora, dwh_mexora, reporting_mexora';
    RAISE NOTICE ' Tables   : dim_temps, dim_region, dim_produit,';
    RAISE NOTICE '            dim_client, dim_livreur, fait_ventes';
    RAISE NOTICE ' Index    : 10 index créés';
    RAISE NOTICE ' Vues mat.: mv_ca_mensuel, mv_top_produits,';
    RAISE NOTICE '            mv_performance_livreurs';
    RAISE NOTICE '=============================================';
END $$;
