# PRJT1-Pipeline-ETL-Data-Warehouse

Miniprojet 1 — Pipeline ETL & Data Warehouse  
Module : Ingénierie des Données & Business Intelligence  
Année universitaire : 2025–2026

---

## Description

Ce projet implémente un pipeline ETL complet pour l'entreprise fictive **Mexora**,
une plateforme e-commerce basée à Tanger.

Le pipeline extrait 4 fichiers de données brutes intentionnellement imparfaits,
les nettoie, construit un schéma en étoile et charge le tout dans un
Data Warehouse PostgreSQL.

---

## Architecture du projet

```
mexora_etl/
├── data/                      # Fichiers sources (non versionnés)
│   ├── commandes_mexora.csv   # 50 000 lignes de commandes
│   ├── clients_mexora.csv     # 5 000 clients
│   ├── produits_mexora.json   # 40 produits
│   └── regions_maroc.csv      # Référentiel géographique (propre)
│
├── config/
│   ├── settings.example.py    # Template de configuration (à copier)
│   └── settings.py            # Configuration locale (non versionnée)
│
├── extract/
│   └── extractor.py           # Lecture des 4 fichiers sources
│
├── transform/
│   ├── clean_commandes.py     # Nettoyage des commandes
│   ├── clean_clients.py       # Nettoyage des clients
│   ├── clean_produits.py      # Nettoyage des produits
│   └── build_dimensions.py    # Construction du schéma en étoile
│
├── load/
│   └── loader.py              # Chargement vers PostgreSQL
│
├── utils/
│   └── logger.py              # Système de logging
│
├── logs/                      # Logs générés automatiquement
├── generate_data.py           # Script de génération des données
├── main.py                    # Point d'entrée du pipeline
└── requirements.txt           # Dépendances Python
```

---

## Schéma en étoile

```
             DIM_TEMPS
                 |
DIM_CLIENT — FAIT_VENTES — DIM_PRODUIT
                 |
            DIM_REGION
                 |
            DIM_LIVREUR
```

Granularité : 1 ligne = 1 ligne de commande (1 produit dans 1 commande)

---

## Erreurs intentionnelles traitées

| Fichier   | Erreur                           | Traitement                       |
| --------- | -------------------------------- | -------------------------------- |
| commandes | ~3% doublons sur id_commande     | Suppression (keep last)          |
| commandes | Dates en 3 formats mixtes        | Standardisation YYYY-MM-DD       |
| commandes | Noms de villes incohérents       | Harmonisation via référentiel    |
| commandes | ~8% statuts non standards        | Remapping vers valeurs valides   |
| commandes | Quantités négatives (~1%)        | Suppression                      |
| commandes | Prix = 0 (~1%)                   | Suppression (commandes test)     |
| commandes | 7% id_livreur manquants          | Remplacement par '-1'            |
| clients   | Doublons sur email               | Déduplication (keep last)        |
| clients   | Sexe encodé différemment         | Standardisation m/f/inconnu      |
| clients   | Dates de naissance invalides     | Invalidation (âge < 16 ou > 100) |
| clients   | Emails mal formatés              | Suppression                      |
| produits  | Casse incohérente des catégories | Title Case                       |
| produits  | Prix null sur anciens produits   | Médiane de la catégorie          |
| produits  | Produits inactifs avec commandes | Conservés pour SCD Type 2        |

---

## SCD Type 2 implémentés

1. **Produit P004 (iPhone 15)** — catégorie `Téléphones` → `Smartphones` en mars 2024
2. **DIM_CLIENT.ville** — historique des déménagements conservé
3. **DIM_CLIENT.segment_client** — historique Bronze → Silver → Gold conservé

---

## Installation et exécution

### Prérequis

- Python 3.10+
- PostgreSQL 15+

### 1. Cloner le projet

```bash
git clone https://github.com/OuissalSEKKARI/PRJT1-Pipeline-ETL-Data-Warehouse.git
cd PRJT1-Pipeline-ETL-Data-Warehouse
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configurer la base de données

```bash
cp config/settings.example.py config/settings.py
```

Ouvrir `config/settings.py` et renseigner vos credentials PostgreSQL.

Créer la base de données :

```bash
psql -U postgres -c "CREATE DATABASE mexora_dwh;"
```

### 4. Placer les fichiers de données

Copier les 4 fichiers dans le dossier `data/` :

```
data/commandes_mexora.csv
data/clients_mexora.csv
data/produits_mexora.json
data/regions_maroc.csv
```

### 5. Lancer le pipeline

```bash
python main.py
```

### 6. Vérifier le résultat

```bash
psql -U postgres -d mexora_dwh -c "\dt dwh_mexora.*"
```

---

## Résultats du pipeline

| Table                  | Lignes | Description                          |
| ---------------------- | ------ | ------------------------------------ |
| dwh_mexora.dim_temps   | 2,192  | Calendrier 2020–2025                 |
| dwh_mexora.dim_region  | 20     | Villes marocaines                    |
| dwh_mexora.dim_produit | 41     | Produits (dont 1 SCD Type 2)         |
| dwh_mexora.dim_client  | 4,996  | Clients segmentés Gold/Silver/Bronze |
| dwh_mexora.dim_livreur | 51     | Livreurs                             |
| dwh_mexora.fait_ventes | 49,019 | Lignes de commandes nettoyées        |

---

## Technologies utilisées

- Python 3.10 — pipeline ETL
- Pandas — transformation des données
- SQLAlchemy — connexion et chargement PostgreSQL
- PostgreSQL 15 — Data Warehouse
- pgAdmin 4 — administration de la base
