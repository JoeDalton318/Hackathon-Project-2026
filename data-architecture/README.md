# Data Architecture – Hackathon 2026 (Boussad)

Base de données **MongoDB Atlas** et explication du **flux de données** pour le pipeline de traitement de documents (upload → OCR → extraction → validation → stockage).

---

## 1. Connexion MongoDB Atlas

La base de données utilisée est **MongoDB Atlas** (cloud).

- **Variable d’environnement** (à configurer côté backend / orchestration) :  
  `MONGO_URL=mongodb+srv://<user>:<password>@hackaton.dcvuugn.mongodb.net/?appName=hackaton`
- Ne jamais commiter le mot de passe dans le dépôt. Utiliser un fichier `.env` (voir `.env.example` dans ce dossier).
- Le **backend (FastAPI)** et éventuellement le **pipeline (Airflow)** se connectent à Atlas via cette URL.

---

## 2. Flux de données – Comment ça marche

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────>│  Backend    │────>│  MinIO      │
│  (Upload)   │     │  (FastAPI)  │     │  (Bronze)   │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                           │ 1. Enregistre      │ Fichiers bruts
                           │    document dans   │ (Raw)
                           │    MongoDB         │
                           ▼                    │
                    ┌─────────────┐             │
                    │  MongoDB    │             │
                    │  documents  │             │
                    │  (statut:   │             │
                    │  en_attente)│             │
                    └──────┬──────┘             │
                           │                    │
                           │ 2. Déclenche       │
                           │    DAG Airflow     │
                           ▼                    │
                    ┌─────────────┐             │
                    │  Airflow    │────────────>│ 3. Lit fichier
                    │  (OCR →     │             │    depuis Bronze
                    │   IA →      │             │
                    │   Validation)│             │
                    └──────┬──────┘             │
                           │ 4. Écrit résultats │
                           │    MinIO Silver +  │
                           │    met à jour      │
                           │    MongoDB         │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  MongoDB    │     │  MinIO      │
                    │  documents  │     │  (Silver)   │
                    │  (statut:   │     │  ocr.txt,   │
                    │  termine,   │     │  extraction │
                    │  resultat_  │     │  .json      │
                    │  extraction)│     └─────────────┘
                    └──────┬──────┘
                           │
                           │ 5. Le frontend lit
                           │    via l’API
                           ▼
                    ┌─────────────┐
                    │  Frontend   │
                    │  (affichage │
                    │   doc +     │
                    │   résultat) │
                    └─────────────┘
```

### Étapes en résumé

| Étape | Qui | Quoi |
|-------|-----|------|
| 1 | Backend | Reçoit l’upload, stocke le fichier dans **MinIO (Bronze)** et crée un document dans **MongoDB** (`documents`) avec `statut_traitement: "en_attente"`. |
| 2 | Backend | Déclenche le **DAG Airflow** (traitement asynchrone). |
| 3 | Pipeline (Airflow) | Lit le fichier depuis MinIO Bronze, fait **OCR → IA (classification) → Validation** (Sirene, inter-documents). |
| 4 | Pipeline | Écrit les résultats dans **MinIO (Silver)** (ocr.txt, extraction.json) et met à jour le document dans **MongoDB** : `statut_traitement: "termine"`, `resultat_extraction`, `type_document_extrait`, etc. |
| 5 | Frontend | Appelle l’API pour récupérer la liste et le détail des documents ; l’API lit dans **MongoDB** (et peut servir le fichier depuis MinIO). |

**MongoDB** sert à stocker les **métadonnées** et le **résultat d’extraction** (type de document, champs métier, signales). Les **fichiers** et le **texte OCR** sont dans **MinIO** (Bronze = brut, Silver = traité).

---

## 3. À quoi sert chaque collection

### 3.1 Collection `users`

**Rôle :** Stocker les **utilisateurs** qui se connectent à l’application (auth, propriétaire des documents).

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant unique (généré par MongoDB). |
| `email` | string | Email de connexion (unique). |
| `password_hash` | string | Mot de passe hashé (jamais en clair). |
| `nom` | string | Nom affiché (optionnel). |
| `created_at` | Date | Date de création du compte. |

**Utilisation :** Connexion (auth), association des documents à un utilisateur (`user_id` dans `documents`).

---

### 3.2 Collection `documents`

**Rôle :** Une entrée = **un fichier uploadé** + son **statut de traitement** + le **résultat d’extraction** (type de document, données structurées, signales). C’est le cœur métier pour l’affichage et la recherche.

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant unique du document. |
| `user_id` | ObjectId | Référence vers `users._id` (propriétaire). |
| `nom_fichier_original` | string | Nom du fichier tel qu’uploadé. |
| `type_mime` | string | Ex. `application/pdf`, `image/png`. |
| `chemin_minio_bronze` | string | Chemin du fichier brut dans MinIO (zone Raw). |
| `chemin_minio_silver` | string | Dossier Silver (ocr.txt, extraction.json, etc.). |
| `statut_traitement` | string | `"en_attente"`, `"en_cours"`, `"termine"`, `"erreur"`. |
| `job_id` | string | Référence au job Airflow (optionnel). |
| `type_document_extrait` | string | Type détecté : `facture`, `devis`, `avoir`, `attestation_siret`, etc. |
| `resultat_extraction` | object | JSON renvoyé par l’IA + signales (type, données, signales). |
| `texte_ocr` | string | Texte OCR brut (optionnel si déjà dans MinIO). |
| `created_at` | Date | Date de création de l’entrée. |
| `updated_at` | Date | Dernière mise à jour (après traitement). |

**Utilisation :**  
- Backend : créer un document à l’upload, mettre à jour après le pipeline.  
- API : lister les documents d’un utilisateur, renvoyer le détail (dont `resultat_extraction`) pour l’affichage 50 % document / 50 % résultat.  
- Les **fichiers** eux-mêmes sont lus depuis **MinIO** via les chemins `chemin_minio_bronze` et `chemin_minio_silver`.

---

## 4. Architecture MinIO – Bronze / Silver / Gold (précision)

Data Lake en **3 zones** (Medallion). À utiliser de façon **stricte** par le backend et le pipeline.

### 4.1 Stratégie des buckets

- **Option A (recommandée)** : un seul bucket MinIO (ex. `hackathon-datalake`) avec des **préfixes** :
  - `bronze/`
  - `silver/`
  - `gold/`
- **Option B** : trois buckets séparés : `bronze`, `silver`, `gold`.

Les chemins ci‑dessous sont relatifs au bucket (ou au préfixe).

---

### 4.2 Zone Bronze (Raw) – documents bruts

**Rôle :** Stocker les fichiers **tels qu’uploadés**, sans transformation.

**Convention de chemin :**
```
bronze/uploads/{user_id}/{batch_id}/{filename}
```

| Élément | Description |
|--------|-------------|
| `user_id` | ID de l’utilisateur (ex. ObjectId MongoDB ou string). |
| `batch_id` | ID du lot d’upload (ex. UUID ou date-heure) pour grouper les fichiers d’un même envoi. |
| `filename` | Nom du fichier original (gérer les doublons : suffixe ou UUID si besoin). |

**Exemple :**
```
bronze/uploads/507f1f77bcf86cd799439011/batch_20260316_143022/facture-fournisseur.pdf
```

**Contenu :** Fichier binaire seul (PDF, PNG, JPG, etc.). Aucune modification.

**Qui écrit :** Backend (FastAPI) à l’upload.  
**Qui lit :** Pipeline (Airflow) pour lancer OCR et extraction.

---

### 4.3 Zone Silver (Clean) – résultats par document

**Rôle :** Stocker, **par document traité**, le fichier d’origine (ou copie), les artefacts du pipeline (image améliorée, OCR, JSON d’extraction).

**Convention de chemin (dossier par document) :**
```
silver/processed/{user_id}/{doc_id}/
```

Dans ce dossier, les **fichiers attendus** :

| Fichier | Description |
|---------|-------------|
| `original.pdf` ou `original.png` | Copie du fichier source (ou même nom que l’original). |
| `improved.png` | Image améliorée (prétraitement) utilisée pour l’OCR. |
| `ocr.txt` | Texte brut extrait par l’OCR. |
| `extraction.json` | JSON renvoyé par l’IA (type + données) + éventuels signales (identique à `resultat_extraction` en MongoDB). |

**Exemple :**
```
silver/processed/507f1f77bcf86cd799439011/674abc123def456789012345/
├── original.pdf
├── improved.png
├── ocr.txt
└── extraction.json
```

**Contenu :** Données “propres” et structurées **par document** (clean zone).

**Qui écrit :** Pipeline (Airflow) après OCR, IA et validation.  
**Qui lit :** Backend (API) pour servir le fichier / l’OCR / l’extraction au frontend.

Dans MongoDB, le champ `documents.chemin_minio_silver` doit contenir ce **dossier** (ex. `silver/processed/{user_id}/{doc_id}/`) ou le chemin du bucket complet, selon comment le backend résout les URLs MinIO.

---

### 4.4 Zone Gold (Curated) – agrégations pour CRM / conformité

**Rôle :** Données **agrégées ou dérivées** pour les 2 applications métier (CRM, outil conformité), prêtes pour l’auto-remplissage par l’IA.

**Convention (à définir selon les besoins) :**
```
gold/exports/{type}/{date ou critère}/
gold/by_fournisseur/{siret ou id}/
gold/attestations/
...
```

**Contenu typique :** Fichiers Parquet/JSON agrégés, listes fournisseurs, attestations avec dates d’expiration, etc. (optionnel pour la première version).

**Qui écrit :** Job Airflow ou API après traitement.  
**Qui lit :** Applications CRM et conformité (MERN).

---

### 4.5 Récapitulatif

| Zone | Préfixe / bucket | Chemin type | Contenu |
|------|-------------------|-------------|---------|
| **Bronze (Raw)** | `bronze/` | `bronze/uploads/{user_id}/{batch_id}/{filename}` | Fichier brut unique. |
| **Silver (Clean)** | `silver/` | `silver/processed/{user_id}/{doc_id}/` + `original.*`, `improved.png`, `ocr.txt`, `extraction.json` | Dossier par document avec 4 artefacts. |
| **Gold (Curated)** | `gold/` | À définir (ex. `gold/exports/`, `gold/by_fournisseur/`) | Agrégations, exports. |

MongoDB ne stocke **pas** les fichiers ; il stocke les **chemins** (`chemin_minio_bronze`, `chemin_minio_silver`) et la **copie** du résultat d’extraction dans `resultat_extraction` pour recherche et affichage.

---

## 5. Fichiers de ce dossier

| Fichier | Description |
|---------|--------------|
| `README.md` | Ce fichier : flux de données, rôle des collections, **architecture Bronze/Silver/Gold détaillée** (section 4). |
| `schemas/collections.md` | **Schéma complet** des collections (aligné avec docs/DONNEES.md). |
| `scripts/init_mongodb.py` | **Script Python** : vérifie la connexion, crée les collections et les index (voir section 6). |
| `scripts/requirements.txt` | Dépendances du script Python (`pymongo`, `python-dotenv`). |
| `init-scripts/02-mongodb-indexes.js` | Script JS pour créer les index (alternative avec `mongosh`). |
| `.env.example` | Exemple de variable `MONGO_URL` (sans mot de passe). |

---

## 6. Initialiser la base (script Python)

Pour une **base vide** : vérifier la connexion, créer les collections `users` et `documents`, et créer les index.

**Prérequis :** Python 3.8+, variable `MONGO_URL` (ou fichier `.env` dans `data-architecture/` avec `MONGO_URL=...`).

```bash
cd data-architecture/scripts
pip install -r requirements.txt
export MONGO_URL="mongodb+srv://user:password@cluster.mongodb.net/?appName=hackaton"
python init_mongodb.py
```

Avec un fichier `.env` (copie de `.env.example` à la racine de `data-architecture/`, en renseignant le vrai mot de passe) :

```bash
cd data-architecture/scripts
pip install -r requirements.txt
python init_mongodb.py
```

Le script affiche si la connexion est OK, crée les collections si besoin, puis les index. Idempotent : on peut le relancer sans doublon.

---

## 7. Index recommandés (performance)

- **`users`** : index unique sur `email`.  
- **`documents`** : index sur `user_id`, `statut_traitement`, `created_at` pour les listes et filtres.

Créés automatiquement par `scripts/init_mongodb.py` (ou manuellement avec `init-scripts/02-mongodb-indexes.js`).
