# PRJT1-Pipeline-ETL-Data-Warehouse

Miniprojet 1 - Pipeline ETL & Data Warehouse
Module : Ingenierie des Donnees & Business Intelligence
Annee universitaire : 2025-2026

---

## Description

Ce projet implemente un pipeline ETL complet pour l'entreprise fictive **Mexora**,
une plateforme e-commerce basee a Tanger.

Le pipeline extrait 4 fichiers de donnees sources, applique les regles de qualite,
construit un schema en etoile et charge le resultat dans un Data Warehouse
PostgreSQL. Le projet contient aussi les scripts SQL de creation du DWH, des index,
des vues materialisees de reporting et des controles d'integrite.

---

## Architecture du projet

```text
PRJT1-Pipeline-ETL-Data-Warehouse/
├── data/                       # Fichiers sources locaux
│   ├── commandes_mexora.csv    # 51 500 lignes brutes
│   ├── clients_mexora.csv      # 5 150 lignes brutes
│   ├── produits_mexora.json    # 40 produits
│   └── regions_maroc.csv       # Referentiel geographique propre, 20 villes
│
├── config/
│   ├── settings.example.py     # Template de configuration
│   └── settings.py             # Configuration locale non versionnee
│
├── extract/
│   └── extractor.py            # Lecture des 4 fichiers sources
│
├── transform/
│   ├── clean_commandes.py      # Nettoyage des commandes
│   ├── clean_clients.py        # Nettoyage des clients
│   ├── clean_produits.py       # Nettoyage des produits
│   └── build_dimensions.py     # Dimensions et table de faits
│
├── load/
│   └── loader.py               # Chargement vers PostgreSQL
│
├── utils/
│   └── logger.py               # Logging console + fichiers
│
├── logs/
│   └── etl_pipeline_final.log  # Derniere execution de reference
│
├── check_integrity.sql         # Controles post-chargement
├── create_dwh.sql              # Creation schemas, tables, index, vues
├── main.py                     # Point d'entree du pipeline
├── rapport_transformation.md   # Rapport detaille des transformations
├── requirements.txt            # Dependances Python
├── test_extract.py             # Script de test extraction/transformation rapide
└── test_transform.py           # Script de test des transformations
```

---

## Schema en etoile

```text
             DIM_TEMPS
                 |
DIM_CLIENT -- FAIT_VENTES -- DIM_PRODUIT
                 |
            DIM_REGION
                 |
            DIM_LIVREUR
```

Granularite : 1 ligne = 1 ligne de commande, associee a 1 produit, 1 client,
1 region, 1 livreur et 1 date.

---

## Transformations principales

| Source | Anomalie / besoin | Traitement |
| --- | --- | --- |
| commandes | Doublons sur `id_commande` | Suppression des doublons, `keep='last'` |
| commandes | Dates en formats mixtes | Standardisation via `pd.to_datetime(..., format='mixed')` |
| commandes | Noms de villes incoherents | Harmonisation via `regions_maroc.csv` |
| commandes | Statuts non standards | Remapping vers `livre`, `annule`, `en_cours`, `retourne` ou `inconnu` |
| commandes | Quantites nulles ou negatives | Suppression |
| commandes | Prix unitaire egal a 0 | Suppression des commandes de test |
| commandes | `id_livreur` manquant | Remplacement par la valeur sentinelle `-1` |
| clients | Doublons sur email | Deduplication sur email normalise |
| clients | Sexe encode differemment | Standardisation en `m`, `f`, `inconnu`, puis `m/f/i` dans le DWH |
| clients | Dates de naissance invalides | Invalidation si age < 16 ou > 100 |
| clients | Emails invalides | Mise a `null`, sans supprimer le client |
| clients | Villes incoherentes | Harmonisation via le referentiel regions |
| produits | Casse incoherente | Normalisation Title Case |
| produits | Prix catalogue null | Remplacement par la mediane de categorie |
| produits | Produits inactifs | Conservation pour les ventes historiques |

Le detail complet des regles et des volumes affectes est disponible dans
`rapport_transformation.md`.

---

## SCD Type 2

Le projet implemente une structure SCD Type 2 sur les dimensions produit et client :

1. **Produit P004 (iPhone 15)** : historisation du changement de sous-categorie
   `Telephones` vers `Smartphones` a partir du 2024-03-01.
2. **DIM_CLIENT** : colonnes SCD (`date_debut`, `date_fin`, `est_actif`) et
   segmentation Gold/Silver/Bronze calculee depuis le CA livre des 365 derniers jours.

Dans `build_fait_ventes()`, la jointure produit est sensible a la date de commande
afin de rattacher les ventes historiques a la bonne version SCD du produit.

---

## Installation et execution

### Prerequis

- Python 3.10+
- PostgreSQL 15+

### 1. Cloner le projet

```bash
git clone https://github.com/OuissalSEKKARI/PRJT1-Pipeline-ETL-Data-Warehouse.git
cd PRJT1-Pipeline-ETL-Data-Warehouse
```

### 2. Installer les dependances

```bash
pip install -r requirements.txt
```

### 3. Configurer le projet

```bash
cp config/settings.example.py config/settings.py
```

Ouvrir `config/settings.py`, verifier les chemins des fichiers sources et renseigner
les credentials PostgreSQL.

### 4. Creer la base et le schema DWH

```bash
psql -U postgres -c "CREATE DATABASE mexora_dwh;"
psql -U postgres -d mexora_dwh -f create_dwh.sql
```

Le script `create_dwh.sql` cree :

- les schemas `staging_mexora`, `dwh_mexora`, `reporting_mexora`
- les dimensions et la table `fait_ventes`
- les index
- les vues materialisees de reporting

### 5. Placer les fichiers de donnees

Les 4 fichiers attendus sont :

```text
data/commandes_mexora.csv
data/clients_mexora.csv
data/produits_mexora.json
data/regions_maroc.csv
```

### 6. Lancer le pipeline

```bash
python main.py
```

### 7. Verifier le resultat

```bash
psql -U postgres -d mexora_dwh -c "\dt dwh_mexora.*"
psql -U postgres -d mexora_dwh -f check_integrity.sql
```

---

## Resultats du dernier pipeline

Derniere execution de reference : `logs/etl_pipeline_final.log`, le 2026-05-25 a
23:23.

| Table | Lignes | Description |
| --- | ---: | --- |
| `dwh_mexora.dim_temps` | 2 192 | Calendrier 2020-2025 |
| `dwh_mexora.dim_region` | 20 | Villes marocaines |
| `dwh_mexora.dim_produit` | 41 | 40 produits + 1 version SCD Type 2 |
| `dwh_mexora.dim_client` | 4 996 | Clients segmentes Gold/Silver/Bronze |
| `dwh_mexora.dim_livreur` | 51 | Livreurs, incluant le livreur inconnu `-1` |
| `dwh_mexora.fait_ventes` | 36 705 | Lignes de ventes chargees apres jointures DWH |

Segments clients charges :

| Segment | Clients |
| --- | ---: |
| Gold | 2 143 |
| Silver | 746 |
| Bronze | 2 107 |

---

## Reporting SQL

`create_dwh.sql` cree trois vues materialisees dans `reporting_mexora` :

- `mv_ca_mensuel` : CA mensuel par region, ville, categorie et periode Ramadan
- `mv_top_produits` : classement des produits par trimestre
- `mv_performance_livreurs` : delais moyens et taux de retard des livreurs

`check_integrity.sql` controle notamment les volumes, les cles etrangeres orphelines,
les valeurs null critiques, les statuts, la couverture temporelle, le SCD Type 2 et
les vues materialisees.

---

## Technologies utilisees

- Python 3.10+
- Pandas
- SQLAlchemy
- psycopg2
- PostgreSQL 15+
- pgAdmin 4
