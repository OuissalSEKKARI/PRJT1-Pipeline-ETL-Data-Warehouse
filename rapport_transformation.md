# Rapport des Transformations ETL — Mexora Analytics

**Miniprojet 1 — Pipeline ETL & Data Warehouse**  
Module : Ingénierie des Données & Business Intelligence  
Année universitaire : 2025–2026  
Date : 25/05/2026

---

## Introduction

Ce document constitue le livrable L4 du miniprojet Mexora. Il recense toutes les règles de transformation appliquées sur les données brutes, avec pour chaque règle : la règle métier, le code appliqué, et le nombre de lignes affectées issu des logs du pipeline.

Les données traitées proviennent de trois sources imparfaites :

- `commandes_mexora.csv` — **51 500 lignes brutes**
- `clients_mexora.csv` — **5 150 lignes brutes**
- `produits_mexora.json` — **40 produits**

Le référentiel géographique `regions_maroc.csv` est considéré propre et sert de table de correspondance (20 villes).

---

## 1. Transformations sur les Commandes

**Fichier source :** `commandes_mexora.csv`  
**Fonction :** `transform_commandes()` dans `transform/clean_commandes.py`  
**Lignes en entrée :** 51 500  
**Lignes en sortie :** 49 019  
**Total supprimé :** 2 481 lignes

---

### R1 — Suppression des doublons sur `id_commande`

**Règle métier :** Un identifiant de commande doit être unique. Les doublons résultent d'erreurs d'import dans le système source. En cas de doublon, on conserve la dernière occurrence (la plus récente).

**Code appliqué :**

```python
df = df.drop_duplicates(subset=['id_commande'], keep='last')
logger.info(f"[TRANSFORM] R1 doublons — {initial - len(df)} lignes supprimées")
```

**Lignes affectées :** 1 500 doublons supprimés (~2,9% des commandes brutes)

---

### R2 — Standardisation des dates

**Règle métier :** Les dates arrivent en trois formats différents (`15/11/2024`, `2024-11-15`, `Nov 15 2024`). Toutes sont converties au format standard `YYYY-MM-DD`. Les lignes avec `date_commande` non parsable sont supprimées car non exploitables.

**Code appliqué :**

```python
for col in ['date_commande', 'date_livraison']:
    df[col] = pd.to_datetime(
        df[col], format='mixed', dayfirst=True, errors='coerce'
    )
df = df.dropna(subset=['date_commande'])
```

**Lignes affectées :**

- `date_commande` : 0 dates invalides — toutes les dates ont été parsées avec succès
- `date_livraison` : 0 dates invalides — idem
- Lignes supprimées (date_commande nulle) : 0

---

### R3 — Harmonisation des noms de villes

**Règle métier :** Le champ `ville_livraison` contient des variantes orthographiques, des abréviations et des casses incohérentes (`tanger`, `TNG`, `TANGER`, `Tnja`). Toutes les villes sont normalisées vers le nom standard défini dans `regions_maroc.csv`. Les villes non reconnues sont marquées `Non renseignée`.

**Code appliqué :**

```python
mapping = charger_referentiel_villes(df_regions)
df['ville_livraison'] = (
    df['ville_livraison']
    .str.strip()
    .str.lower()
    .map(mapping)
    .fillna('Non renseignée')
)
```

**Extrait du mapping manuel utilisé :**

```python
variants_manuels = {
    'tanja': 'Tanger', 'tng': 'Tanger', 'tangier': 'Tanger',
    'casa': 'Casablanca', 'dar el beida': 'Casablanca',
    'mrakech': 'Marrakech', 'marrakesh': 'Marrakech',
    'sale': 'Salé', 'salè': 'Salé',
    ...
}
```

**Lignes affectées :** 0 villes non reconnues — le mapping couvre l'intégralité des variantes présentes dans les données

---

### R4 — Standardisation des statuts de commande

**Règle métier :** Le champ `statut` contient des valeurs non standards issues de systèmes tiers (`OK`, `KO`, `DONE`). Ces valeurs sont remappées vers les quatre statuts valides du DWH : `livré`, `annulé`, `en_cours`, `retourné`. Les valeurs non reconnues sont placées à `inconnu`.

**Code appliqué :**

```python
mapping_statuts = {
    'livré': 'livré', 'livre': 'livré', 'DONE': 'livré',
    'annulé': 'annulé', 'annule': 'annulé', 'KO': 'annulé',
    'en_cours': 'en_cours', 'OK': 'en_cours',
    'retourné': 'retourné', 'retourne': 'retourné'
}
df['statut'] = df['statut'].replace(mapping_statuts)
invalides = ~df['statut'].isin(['livré', 'annulé', 'en_cours', 'retourné'])
df.loc[invalides, 'statut'] = 'inconnu'
```

**Lignes affectées :** tous les statuts reconnus — 0 valeurs `inconnu` générées

---

### R5 — Suppression des quantités négatives ou nulles

**Règle métier :** Une quantité vendue doit être strictement positive. Les valeurs négatives ou nulles correspondent à des erreurs de saisie dans le système transactionnel source.

**Code appliqué :**

```python
avant = len(df)
df = df[df['quantite'].astype(float) > 0]
logger.info(f"[TRANSFORM] R5 quantités — {avant - len(df)} lignes supprimées")
```

**Lignes affectées :** 499 lignes supprimées (~1,0% des commandes après déduplication)

---

### R6 — Suppression des commandes test (prix = 0)

**Règle métier :** Les lignes avec `prix_unitaire = 0` correspondent à des commandes de test créées par les développeurs dans l'environnement de production. Elles ne représentent pas de ventes réelles et sont supprimées.

**Code appliqué :**

```python
avant = len(df)
df = df[df['prix_unitaire'].astype(float) > 0]
logger.info(f"[TRANSFORM] R6 prix nuls — {avant - len(df)} commandes test supprimées")
```

**Lignes affectées :** 482 commandes test supprimées (~1,0%)

---

### R7 — Remplacement des livreurs manquants

**Règle métier :** Environ 7% des commandes n'ont pas d'`id_livreur` renseigné. Plutôt que de supprimer ces lignes (ce qui ferait perdre des données de vente valides), on les remplace par la valeur sentinelle `-1`, correspondant à un livreur fictif `Livreur Inconnu` dans `DIM_LIVREUR`.

**Code appliqué :**

```python
manquants = df['id_livreur'].isna().sum()
df['id_livreur'] = df['id_livreur'].fillna('-1')
logger.info(f"[TRANSFORM] R7 livreurs — {manquants} valeurs manquantes → '-1'")
```

**Lignes affectées :** 3 427 valeurs manquantes remplacées par `-1` (~7,0% des commandes nettoyées)

---

### R8 — Calcul des montants HT et TTC

**Règle métier :** Après nettoyage des quantités et des prix unitaires, les montants de vente sont recalculés pour garantir la cohérence analytique. Le montant TTC correspond à `quantite * prix_unitaire`. Le montant HT est obtenu en retirant une TVA de 20%.

**Code appliqué :**

```python
df['quantite']      = df['quantite'].astype(float).astype(int)
df['prix_unitaire'] = df['prix_unitaire'].astype(float)
df['montant_ttc']   = df['quantite'] * df['prix_unitaire']
df['montant_ht']    = (df['montant_ttc'] / 1.20).round(2)
```

**Lignes affectées :** 49 019 lignes — calcul systématique sur toutes les commandes conservées

---

## 2. Transformations sur les Clients

**Fichier source :** `clients_mexora.csv`  
**Fonction :** `transform_clients()` dans `transform/clean_clients.py`  
**Lignes en entrée :** 5 150  
**Lignes en sortie :** 4 996  
**Total supprimé :** 154 lignes (doublons uniquement — les autres anomalies sont corrigées en place)

---

### R1 — Déduplication sur email normalisé

**Règle métier :** Des clients en doublon existent avec le même email mais des `id_client` différents, résultat d'une erreur lors d'une migration de système. La déduplication se fait sur l'email normalisé (minuscules, sans espaces). En cas de doublon, on conserve l'inscription la plus récente.

**Code appliqué :**

```python
df['email_norm'] = df['email'].str.lower().str.strip()
df['date_inscription'] = pd.to_datetime(df['date_inscription'], errors='coerce')
df = df.sort_values('date_inscription').drop_duplicates(
    subset=['email_norm'], keep='last'
)
```

**Note importante :** Un mapping `id_client_supprimé → id_client_survivant` est construit via `build_client_id_mapping()` pour remapper les clés étrangères dans `FAIT_VENTES` avant chargement. **154 IDs ont ainsi été remappés** dans la table de faits.

**Lignes affectées :** 154 doublons supprimés (~3,0% des clients bruts)

---

### R2 — Standardisation du champ `sexe`

**Règle métier :** Le champ `sexe` a été alimenté par plusieurs systèmes sources avec des encodages différents (`m/f`, `1/0`, `Homme/Femme`, `male/female`). Tous sont normalisés vers `m`, `f` ou `inconnu`.

**Code appliqué :**

```python
mapping_sexe = {
    'm': 'm', 'M': 'm', '1': 'm', 'homme': 'm', 'male': 'm', 'h': 'm',
    'f': 'f', 'F': 'f', '0': 'f', 'femme': 'f', 'female': 'f'
}
df['sexe'] = df['sexe'].str.strip().map(mapping_sexe).fillna('inconnu')
```

**Lignes affectées :** 890 valeurs non reconnues → `inconnu` (~17,8% des clients — indique une source d'import tierce avec encodage différent)

---

### R3 — Validation des dates de naissance

**Règle métier :** Les dates de naissance permettant de calculer un âge inférieur à 16 ans ou supérieur à 100 ans sont considérées invalides (erreurs de saisie ou données fantaisistes). Elles sont mises à `NaT` sans supprimer la ligne cliente.

**Code appliqué :**

```python
df['date_naissance'] = pd.to_datetime(df['date_naissance'], errors='coerce')
today = pd.Timestamp(date.today())
df['age'] = (today - df['date_naissance']).dt.days // 365
invalides = ((df['age'] < 16) | (df['age'] > 100)).sum()
df.loc[(df['age'] < 16) | (df['age'] > 100), 'date_naissance'] = pd.NaT
```

Une tranche d'âge est ensuite construite pour la dimension client :

```python
df['tranche_age'] = pd.cut(
    df['age'].fillna(0),
    bins=[0, 18, 25, 35, 45, 55, 65, 200],
    labels=['<18', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']
)
```

**Lignes affectées :** 174 dates de naissance invalidées → `NaT` (~3,5%)

---

### R4 — Validation du format email

**Règle métier :** Les emails sans `@`, sans domaine valide ou avec des caractères interdits sont mis à `null`. La ligne cliente est conservée car les autres attributs restent exploitables analytiquement.

**Code appliqué :**

```python
pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
bad_emails = (~df['email'].str.match(pattern, na=False)).sum()
df.loc[~df['email'].str.match(pattern, na=False), 'email'] = None
```

**Lignes affectées :** 243 emails invalides mis à `null` (~4,9%)

---

### R5 — Harmonisation des villes clients

**Règle métier :** Même logique que R3 des commandes. Le champ `ville` des clients est normalisé via le même référentiel géographique `regions_maroc.csv`.

**Code appliqué :**

```python
mapping_villes = charger_referentiel_villes(df_regions)
df['ville'] = df['ville'].str.strip().str.lower().map(mapping_villes).fillna('Non renseignée')
```

**Lignes affectées :** 0 villes non reconnues — couverture complète du référentiel

---

### R6 — Construction du nom complet

**Règle métier :** La dimension client expose un attribut `nom_complet` pour simplifier les affichages dans les dashboards. Il est construit en concaténant `prenom` et `nom`.

**Code appliqué :**

```python
df['nom_complet'] = df['prenom'].str.strip() + ' ' + df['nom'].str.strip()
```

**Lignes affectées :** 4 996 lignes — calcul systématique sur tous les clients conservés

---

## 3. Transformations sur les Produits

**Fichier source :** `produits_mexora.json`  
**Fonction :** `transform_produits()` dans `transform/clean_produits.py`  
**Lignes en entrée :** 40  
**Lignes en sortie :** 40 _(aucune ligne supprimée — les anomalies sont corrigées en place)_

---

### R1 — Normalisation de la casse (Title Case)

**Règle métier :** Les champs textuels `categorie`, `sous_categorie`, `marque` et `fournisseur` présentent des casses incohérentes selon la source d'alimentation (`electronique`, `Electronique`, `ELECTRONIQUE`). Tous sont normalisés en Title Case.

**Code appliqué :**

```python
for col in ['categorie', 'sous_categorie', 'marque', 'fournisseur']:
    df[col] = df[col].str.strip().str.title()
```

**Lignes affectées :** 40 lignes — normalisation systématique

---

### R2 — Remplacement des prix nuls par la médiane de catégorie

**Règle métier :** Certains produits anciens ont un `prix_catalogue` à `null`. Plutôt que de supprimer ces produits (qui ont des commandes associées), leur prix est estimé par la médiane des prix de leur catégorie. Ce choix est conservateur et évite de biaiser les analyses de CA.

**Code appliqué :**

```python
df['prix_catalogue'] = pd.to_numeric(df['prix_catalogue'], errors='coerce')
df['prix_catalogue'] = df.groupby('categorie')['prix_catalogue'].transform(
    lambda x: x.fillna(x.median())
)
```

**Lignes affectées :** 2 prix nuls remplacés par la médiane de leur catégorie

---

### R3 — Conservation des produits inactifs

**Règle métier :** Certains produits ont `actif = false` mais apparaissent dans des commandes historiques. Ils ne sont pas supprimés afin de préserver l'intégrité des analyses et des jointures. Dans `build_dim_produit()`, ces produits reçoivent un enregistrement fermé (`date_fin = aujourd'hui`, `est_actif = False`).

**Code appliqué :**

```python
inactifs = (~df['actif'].astype(bool)).sum()
logger.info(f"[TRANSFORM] R3 inactifs — {inactifs} produits inactifs conservés pour SCD Type 2")
```

**Lignes affectées :** 2 produits inactifs conservés avec enregistrement fermé

---

## 4. Construction des Dimensions

**Fichier :** `transform/build_dimensions.py`

---

### DIM_TEMPS

**Logique :** Génération d'un calendrier continu du 2020-01-01 au 2025-12-31. Enrichi avec les jours fériés marocains (liste fixe) et les périodes Ramadan (2022, 2023, 2024).

**Résultat :** 2 192 lignes générées

---

### DIM_PRODUIT — Historisation Type 2 sur iPhone 15 (P004)

**Logique :** Le produit P004 (iPhone 15) a changé de sous-catégorie de `Téléphones` à `Smartphones` en mars 2024. Deux enregistrements sont créés :

| id_produit_sk | id_produit_nk | sous_categorie | date_debut |  date_fin  | est_actif |
| :-----------: | :-----------: | :------------: | :--------: | :--------: | :-------: |
|       N       |     P004      |   Téléphones   | 2023-09-22 | 2024-02-28 |   False   |
|      N+1      |     P004      |  Smartphones   | 2024-03-01 | 9999-12-31 |   True    |

**Limite actuelle :** la dimension contient bien les deux versions du produit, mais `build_fait_ventes()` joint actuellement les ventes avec l'enregistrement actif uniquement. Les ventes historiques de P004 ne sont donc pas encore rattachées automatiquement à l'ancienne version `Téléphones`.

**Résultat :** 41 lignes (40 produits + 1 enregistrement SCD supplémentaire)

---

### DIM_CLIENT — Segmentation Gold / Silver / Bronze

**Logique :** Le segment est calculé dynamiquement à partir du CA des 365 derniers jours disponibles dans les données, en prenant comme référence la date maximale de `date_commande`, uniquement sur les commandes `livré` :

| Segment | Condition CA sur la période récente |
| :------ | :---------------------------------- |
| Gold    | ≥ 15 000 MAD                        |
| Silver  | ≥ 5 000 MAD                         |
| Bronze  | < 5 000 MAD                         |

Les clients sans commandes récentes sont classés `Bronze` par défaut.

**Résultat :** 4 996 clients — Gold : 2 143 / Silver : 746 / Bronze : 2 107

---

### Remapping des clés clients dans FAIT_VENTES

**Logique :** Les commandes référencent des `id_client` qui peuvent correspondre à des doublons supprimés lors de la déduplication des clients. La fonction `build_client_id_mapping()` construit un dictionnaire `{id_supprimé → id_survivant}` appliqué avant la jointure dans `build_fait_ventes()`.

**Lignes affectées :** 154 IDs clients remappés dans `fait_ventes`

---

## 5. Récapitulatif des règles — Vue synthétique

| Source    | Règle | Description                          | Lignes affectées |
| :-------- | :---: | :----------------------------------- | ---------------: |
| Commandes |  R1   | Doublons sur `id_commande` supprimés |            1 500 |
| Commandes |  R2   | Dates standardisées YYYY-MM-DD       |      0 invalides |
| Commandes |  R3   | Villes harmonisées via référentiel   |  0 non reconnues |
| Commandes |  R4   | Statuts remappés                     |       0 inconnus |
| Commandes |  R5   | Quantités ≤ 0 supprimées             |              499 |
| Commandes |  R6   | Commandes test (prix=0) supprimées   |              482 |
| Commandes |  R7   | Livreurs manquants → `-1`            |            3 427 |
| Commandes |  R8   | Montants TTC/HT recalculés           |   49 019 (toutes) |
| Clients   |  R1   | Doublons sur email supprimés         |              154 |
| Clients   |  R2   | Sexe standardisé m/f/inconnu         |    890 → inconnu |
| Clients   |  R3   | Dates naissance invalides → NaT      |              174 |
| Clients   |  R4   | Emails invalides → null              |              243 |
| Clients   |  R5   | Villes harmonisées                   |  0 non reconnues |
| Clients   |  R6   | Nom complet construit                |   4 996 (toutes) |
| Produits  |  R1   | Casse Title Case                     |      40 (toutes) |
| Produits  |  R2   | Prix nuls → médiane catégorie        |                2 |
| Produits  |  R3   | Produits inactifs conservés          |                2 |

---

## 6. Résultats du chargement PostgreSQL

| Table                    | Lignes chargées | Durée       |
| :----------------------- | --------------: | :---------- |
| `dwh_mexora.dim_temps`   |           2 192 | immédiat    |
| `dwh_mexora.dim_region`  |              20 | immédiat    |
| `dwh_mexora.dim_produit` |              41 | immédiat    |
| `dwh_mexora.dim_client`  |           4 996 | immédiat    |
| `dwh_mexora.dim_livreur` |              51 | immédiat    |
| `dwh_mexora.fait_ventes` |          49 019 | ~9 secondes |

Pipeline complet exécuté en **14 secondes** (02:51:36 → 02:51:50).

---

## 7. Gestion des erreurs

Le pipeline est orchestré dans `main.py` par la fonction `run_pipeline()`, qui exécute successivement les étapes Extract, Transform et Load. Le code actuel ne contient pas de bloc `try/except` global : une exception interrompra donc le pipeline et affichera le traceback Python standard.

Les cas d'erreur silencieux (ville non reconnue, email invalide, date de naissance hors plage) sont traités par valeur de remplacement plutôt que par exception, pour ne pas interrompre le pipeline sur des anomalies partielles attendues. Cette stratégie est documentée dans les logs avec le nombre exact de valeurs corrigées à chaque étape.

---

_Document généré dans le cadre du Miniprojet 1 — Mexora Analytics — 2025-2026_
