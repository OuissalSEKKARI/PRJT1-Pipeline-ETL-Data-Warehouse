-- =============================================================
--  check_integrity.sql  —  Mexora Analytics DWH
--  Vérification complète de l'intégrité référentielle
--  et de la qualité des données chargées
--
--  Exécution :
--    psql -U postgres -d mexora_dwh -f check_integrity.sql
-- =============================================================


-- =============================================================
--  1. COMPTAGE DES LIGNES PAR TABLE
-- =============================================================

SELECT '══ COMPTAGE DES TABLES ══' AS section;

SELECT
    schemaname                          AS schema,
    tablename                           AS table_name,
    n_live_tup                          AS nb_lignes_estimees
FROM pg_stat_user_tables
WHERE schemaname IN ('dwh_mexora', 'reporting_mexora')
ORDER BY schemaname, tablename;


-- =============================================================
--  2. VÉRIFICATION DES CLÉS ÉTRANGÈRES
--     (orphelins dans la table de faits)
-- =============================================================

SELECT '══ ORPHELINS CLÉS ÉTRANGÈRES ══' AS section;

-- Commandes sans date valide
SELECT
    'fait_ventes → dim_temps'   AS relation,
    COUNT(*)                    AS nb_orphelins
FROM dwh_mexora.fait_ventes f
WHERE NOT EXISTS (
    SELECT 1 FROM dwh_mexora.dim_temps t
    WHERE t.id_date = f.id_date
);

-- Commandes sans produit valide
SELECT
    'fait_ventes → dim_produit' AS relation,
    COUNT(*)                    AS nb_orphelins
FROM dwh_mexora.fait_ventes f
WHERE NOT EXISTS (
    SELECT 1 FROM dwh_mexora.dim_produit p
    WHERE p.id_produit_sk = f.id_produit
);

-- Commandes sans client valide
SELECT
    'fait_ventes → dim_client'  AS relation,
    COUNT(*)                    AS nb_orphelins
FROM dwh_mexora.fait_ventes f
WHERE NOT EXISTS (
    SELECT 1 FROM dwh_mexora.dim_client c
    WHERE c.id_client_sk = f.id_client
);

-- Commandes sans région valide
SELECT
    'fait_ventes → dim_region'  AS relation,
    COUNT(*)                    AS nb_orphelins
FROM dwh_mexora.fait_ventes f
WHERE NOT EXISTS (
    SELECT 1 FROM dwh_mexora.dim_region r
    WHERE r.id_region = f.id_region
);


-- =============================================================
--  3. VÉRIFICATION DES VALEURS NULL CRITIQUES
-- =============================================================

SELECT '══ VALEURS NULL CRITIQUES ══' AS section;

SELECT
    'montant_ttc NULL'          AS probleme,
    COUNT(*)                    AS nb_lignes
FROM dwh_mexora.fait_ventes
WHERE montant_ttc IS NULL

UNION ALL

SELECT
    'quantite_vendue NULL'      AS probleme,
    COUNT(*)                    AS nb_lignes
FROM dwh_mexora.fait_ventes
WHERE quantite_vendue IS NULL

UNION ALL

SELECT
    'id_date NULL'              AS probleme,
    COUNT(*)                    AS nb_lignes
FROM dwh_mexora.fait_ventes
WHERE id_date IS NULL

UNION ALL

SELECT
    'statut_commande NULL'      AS probleme,
    COUNT(*)                    AS nb_lignes
FROM dwh_mexora.fait_ventes
WHERE statut_commande IS NULL;


-- =============================================================
--  4. VÉRIFICATION DES MESURES
-- =============================================================

SELECT '══ STATISTIQUES DES MESURES ══' AS section;

SELECT
    COUNT(*)                            AS nb_total_ventes,
    SUM(montant_ttc)                    AS ca_ttc_total,
    ROUND(AVG(montant_ttc), 2)          AS panier_moyen,
    MIN(montant_ttc)                    AS montant_min,
    MAX(montant_ttc)                    AS montant_max,
    SUM(quantite_vendue)                AS qte_totale,
    ROUND(AVG(delai_livraison_jours),1) AS delai_moyen
FROM dwh_mexora.fait_ventes
WHERE statut_commande = 'livré';


-- =============================================================
--  5. VÉRIFICATION DES STATUTS
-- =============================================================

SELECT '══ RÉPARTITION DES STATUTS ══' AS section;

SELECT
    statut_commande,
    COUNT(*)                            AS nb_commandes,
    ROUND(COUNT(*) * 100.0
        / SUM(COUNT(*)) OVER (), 2)     AS pct
FROM dwh_mexora.fait_ventes
GROUP BY statut_commande
ORDER BY nb_commandes DESC;


-- =============================================================
--  6. VÉRIFICATION SCD TYPE 2
-- =============================================================

SELECT '══ VÉRIFICATION SCD TYPE 2 ══' AS section;

-- Produits avec plusieurs versions
SELECT
    'dim_produit — produits multi-versions' AS verification,
    COUNT(*)                                AS nb_produits
FROM (
    SELECT id_produit_nk
    FROM dwh_mexora.dim_produit
    GROUP BY id_produit_nk
    HAVING COUNT(*) > 1
) sub;

-- Clients avec plusieurs versions
SELECT
    'dim_client — clients multi-versions'   AS verification,
    COUNT(*)                                AS nb_clients
FROM (
    SELECT id_client_nk
    FROM dwh_mexora.dim_client
    GROUP BY id_client_nk
    HAVING COUNT(*) > 1
) sub;

-- Vérification qu'il n'y a qu'une version active par entité
SELECT
    'dim_produit — doublons est_actif=TRUE' AS verification,
    COUNT(*)                                AS nb_doublons
FROM (
    SELECT id_produit_nk
    FROM dwh_mexora.dim_produit
    WHERE est_actif = TRUE
    GROUP BY id_produit_nk
    HAVING COUNT(*) > 1
) sub;


-- =============================================================
--  7. VÉRIFICATION DE LA DIMENSION TEMPS
-- =============================================================

SELECT '══ COUVERTURE TEMPORELLE ══' AS section;

SELECT
    MIN(annee)          AS annee_debut,
    MAX(annee)          AS annee_fin,
    COUNT(*)            AS nb_jours_total,
    SUM(CASE WHEN est_weekend     THEN 1 ELSE 0 END) AS nb_weekends,
    SUM(CASE WHEN est_ferie_maroc THEN 1 ELSE 0 END) AS nb_feries,
    SUM(CASE WHEN periode_ramadan THEN 1 ELSE 0 END) AS nb_jours_ramadan
FROM dwh_mexora.dim_temps;


-- =============================================================
--  8. VÉRIFICATION DES VUES MATÉRIALISÉES
-- =============================================================

SELECT '══ VUES MATÉRIALISÉES ══' AS section;

SELECT
    'mv_ca_mensuel'             AS vue,
    COUNT(*)                    AS nb_lignes
FROM reporting_mexora.mv_ca_mensuel

UNION ALL

SELECT
    'mv_top_produits'           AS vue,
    COUNT(*)                    AS nb_lignes
FROM reporting_mexora.mv_top_produits

UNION ALL

SELECT
    'mv_performance_livreurs'   AS vue,
    COUNT(*)                    AS nb_lignes
FROM reporting_mexora.mv_performance_livreurs;


-- =============================================================
--  9. RAPPORT FINAL
-- =============================================================

SELECT '══ RAPPORT FINAL ══' AS section;

SELECT
    CASE
        WHEN nb_orphelins_date = 0
         AND nb_orphelins_produit = 0
         AND nb_orphelins_client = 0
         AND nb_orphelins_region = 0
         AND nb_null_ttc = 0
        THEN '✅ INTÉGRITÉ RÉFÉRENTIELLE : OK — Aucun problème détecté'
        ELSE '❌ PROBLÈMES DÉTECTÉS — Voir les sections ci-dessus'
    END AS resultat_global
FROM (
    SELECT
        (SELECT COUNT(*) FROM dwh_mexora.fait_ventes f
         WHERE NOT EXISTS (SELECT 1 FROM dwh_mexora.dim_temps t WHERE t.id_date = f.id_date))
            AS nb_orphelins_date,
        (SELECT COUNT(*) FROM dwh_mexora.fait_ventes f
         WHERE NOT EXISTS (SELECT 1 FROM dwh_mexora.dim_produit p WHERE p.id_produit_sk = f.id_produit))
            AS nb_orphelins_produit,
        (SELECT COUNT(*) FROM dwh_mexora.fait_ventes f
         WHERE NOT EXISTS (SELECT 1 FROM dwh_mexora.dim_client c WHERE c.id_client_sk = f.id_client))
            AS nb_orphelins_client,
        (SELECT COUNT(*) FROM dwh_mexora.fait_ventes f
         WHERE NOT EXISTS (SELECT 1 FROM dwh_mexora.dim_region r WHERE r.id_region = f.id_region))
            AS nb_orphelins_region,
        (SELECT COUNT(*) FROM dwh_mexora.fait_ventes WHERE montant_ttc IS NULL)
            AS nb_null_ttc
) checks;
