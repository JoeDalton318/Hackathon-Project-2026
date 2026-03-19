# Data Architecture – Hackathon 2026 (Boussad)

Base de données **MongoDB Atlas** et explication du **flux de données** pour le pipeline de traitement de documents (upload → OCR → extraction → validation → stockage).

---

## 1. Connexion MongoDB Atlas

La base de données utilisée est **MongoDB Atlas** (cloud).

- **Variable d’environnement** (à configurer côté backend / orchestration) :  
  `MONGO_URL=mongodb+srv://<user>:<password>@hackaton.dcvuugn.mongodb.net/?appName=hackaton`
- Ne jamais commiter le mot de passe dans le dépôt. Utiliser un fichier **`backend/.env`** (non versionné).
- Le **backend (FastAPI)** et éventuellement le **pipeline (Airflow)** se connectent à Atlas via cette URL.

---

## 2. Flux de données – Comment ça marche

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Frontend   │────>│  Backend    │────>│  MinIO      │
│  (Upload)   │     │  (FastAPI)  │     │  (Raw)      │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                           │ 1. Enregistre      │ Fichiers bruts
                           │    document dans   │ (Raw)
                           │    MongoDB         │
                           ▼                    │
                    ┌─────────────┐             │
                    │  MongoDB    │             │
                    │  documents  │             │
                    │  (status:   │             │
                    │  pending)   │             │
                    └──────┬──────┘             │
                           │                    │
                           │ 2. Déclenche       │
                           │    DAG Airflow     │
                           ▼                    │
                    ┌─────────────┐             │
                    │  Airflow    │────────────>│ 3. Lit fichier
                    │  (OCR →     │             │    depuis raw/
                    │   IA →      │             │
                    │   Validation)│             │
                    └──────┬──────┘             │
                           │ 4. Écrit résultats │
                           │    MinIO clean/ +  │
                           │    met à jour      │
                           │    MongoDB         │
                           ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  MongoDB    │     │  MinIO      │
                    │  documents  │     │  (Clean)    │
                    │  (status:   │     │  ocr.txt,   │
                    │  done,      │     │  extraction │
                    │  extracted_ │     │  .json      │
                    │  data)      │     └─────────────┘
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
| 1 | Backend | Reçoit l’upload, stocke le fichier dans **MinIO** sous le préfixe **raw/** (bucket `datalake`) et crée un document dans **MongoDB** (`documents`) avec `status: "pending"`. |
| 2 | Backend | Déclenche le **DAG Airflow** (traitement asynchrone). |
| 3 | Pipeline (Airflow) | Lit le fichier depuis **raw/**, fait **OCR → IA (classification) → Validation** (Sirene, inter-documents). |
| 4 | Pipeline | Écrit les résultats sous **clean/** (OCR, extraction) et éventuellement **curated/** ; met à jour **MongoDB** : `status: "done"`, `extracted_data`, `document_type`, `anomalies`, etc. |
| 5 | Frontend | Appelle l’API pour récupérer la liste et le détail des documents ; l’API lit dans **MongoDB** (et peut servir le fichier depuis MinIO). |

**MongoDB** sert à stocker les **métadonnées** et le **résultat d’extraction** (`extracted_data`, `anomalies`). Les **fichiers** sont dans **MinIO** : un bucket **`datalake`** avec les préfixes **raw/** (brut), **clean/** (traité par le pipeline), **curated/** (données prêtes / validation selon convention d’équipe).

---

## 3. À quoi sert chaque collection

### 3.1 Collection `users`

**Rôle :** Stocker les **utilisateurs** qui se connectent à l’application (auth, propriétaire des documents). Clé métier : `user_id` (UUID string).

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant unique (généré par MongoDB). |
| `user_id` | string | UUID, identifiant métier (référencé par `documents.user_id`). |
| `email` | string | Email de connexion (unique). |
| `hashed_password` | string | Mot de passe hashé (jamais en clair). |
| `nom` | string | Nom affiché (optionnel). |
| `role` | string | `"user"` ou `"admin"`. |
| `created_at` | Date | Date de création du compte. |

**Utilisation :** Connexion (auth), association des documents à un utilisateur (`user_id` dans `documents`).

---

### 3.2 Collection `documents`

**Rôle :** Une entrée = **un fichier uploadé** + son **statut de traitement** + le **résultat d’extraction** (type de document, données structurées, anomalies). Clé métier : `document_id` (UUID string).

| Champ | Type | Description |
|-------|------|-------------|
| `_id` | ObjectId | Identifiant unique du document. |
| `document_id` | string | UUID, identifiant métier (utilisé par l’API). |
| `user_id` | string | Référence vers `users.user_id` (propriétaire). |
| `original_filename` | string | Nom du fichier tel qu’uploadé. |
| `mime_type` | string | Ex. `application/pdf`, `image/png`. |
| `minio_path` | string | Clé d’objet dans le bucket `datalake` (ex. préfixe **raw/** pour l’upload initial). |
| `status` | string | `"pending"`, `"processing"`, `"ocr_done"`, `"extraction_done"`, `"done"`, `"error"`. |
| `document_type` | string | Type détecté : `facture`, `devis`, `kbis`, `rib`, `attestation_urssaf`, `attestation_siret`, `unknown`. |
| `extracted_data` | object | Données structurées extraites par l’IA. |
| `anomalies` | array | Liste des anomalies / signales. |
| `created_at` | Date | Date de création de l’entrée. |
| `updated_at` | Date | Dernière mise à jour (après traitement). |

**Utilisation :**  
- Backend : créer un document à l’upload, mettre à jour après le pipeline.  
- API : lister les documents d’un utilisateur, renvoyer le détail (dont `extracted_data`, `anomalies`) pour l’affichage.  
- Les **fichiers** sont lus depuis **MinIO** via le champ `minio_path`.

---

## 4. Architecture MinIO – 1 bucket + 3 préfixes

**Backend, OCR et validation** partagent la **même instance MinIO** et **un seul bucket** : `datalake`. Les trois couches (Raw, Clean, Curated) sont des **préfixes** dans ce bucket, configurés dans le `.env` (souvent **`backend/.env`** pour FastAPI).

| Variable d’environnement | Rôle |
|--------------------------|------|
| `MINIO_ENDPOINT` | Ex. `localhost:9000` (ou host du serveur MinIO partagé). |
| `MINIO_ROOT_USER` | Identifiant (ex. `minioadmin`). |
| `MINIO_ROOT_PASSWORD` | Secret (ex. `minioadmin123`). |
| `MINIO_SECURE` | `false` en local, `true` si HTTPS. |
| `MINIO_BUCKET` | **Un seul bucket** : `datalake`. |
| `MINIO_RAW_PREFIX` | Préfixe Raw : `raw/` |
| `MINIO_CLEAN_PREFIX` | Préfixe Clean : `clean/` |
| `MINIO_CURATED_PREFIX` | Préfixe Curated : `curated/` |

**Exemple de `.env` (référence projet) :**
```env
MINIO_ENDPOINT=localhost:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_SECURE=false
MINIO_BUCKET=datalake
MINIO_RAW_PREFIX=raw/
MINIO_CLEAN_PREFIX=clean/
MINIO_CURATED_PREFIX=curated/
```

---

### 4.1 Zone Raw (`MINIO_RAW_PREFIX`)

**Rôle :** Fichiers **tels qu’uploadés** par le backend.

**Clé d’objet type :**
```
raw/{document_id}/{filename}
```

- `document_id` : UUID du document (clé métier MongoDB).  
- `filename` : nom du fichier original.

**MongoDB :** `documents.minio_path` stocke la **clé complète** (avec préfixe). L’API utilise le bucket `datalake` + cette clé pour les presigned URLs.

**Qui écrit :** Backend à l’upload. **Qui lit :** Backend (téléchargement) ; pipeline OCR.

---

### 4.2 Zone Clean (`MINIO_CLEAN_PREFIX`)

**Rôle :** Artefacts du pipeline (OCR, extraction, fichiers intermédiaires) par document.

**Clé d’objet type :** `clean/{document_id}/...` (convention à aligner avec le DAG Airflow / OCR).

**Qui écrit :** Pipeline (Airflow, OCR). **Qui lit :** Backend, module de validation.

---

### 4.3 Zone Curated (`MINIO_CURATED_PREFIX`)

**Rôle :** Données **prêtes à l’emploi** : agrégations, exports, résultats de validation ou rapports finaux (sous-chemins possibles sous `curated/`, ex. `curated/validation/`, selon convention d’équipe — sans variable d’env dédiée si tout passe par le préfixe `curated/`).

**Qui écrit :** Jobs Airflow, API, validation. **Qui lit :** Backend, CRM, conformité.

---

### 4.4 Récapitulatif

| Couche | Variable | Préfixe | Usage |
|--------|----------|---------|--------|
| **Raw** | `MINIO_RAW_PREFIX` | `raw/` | Upload initial ; lecture par le pipeline. |
| **Clean** | `MINIO_CLEAN_PREFIX` | `clean/` | OCR, extraction, artefacts intermédiaires. |
| **Curated** | `MINIO_CURATED_PREFIX` | `curated/` | Données finales, exports, validation (sous-dossiers possibles). |

**Structure logique dans MinIO :**
```
datalake/
├── raw/          ← MINIO_RAW_PREFIX
├── clean/        ← MINIO_CLEAN_PREFIX
└── curated/      ← MINIO_CURATED_PREFIX
```

MongoDB ne stocke **pas** les fichiers ; il stocke la **clé d’objet** dans `minio_path` et les champs `extracted_data` / `anomalies`.

---

## 5. Fichiers de ce dossier

| Fichier | Description |
|---------|--------------|
| `README.md` | Ce fichier : flux de données, rôle des collections, **architecture MinIO** (section 4). |
| `schemas/collections.md` | **Schéma complet** des collections (aligné avec le backend FastAPI). |

---

## 6. Initialiser la base

Lancer le **backend** (FastAPI). Au démarrage, `backend/database/mongo.py` crée les index via `create_indexes()`. Les collections sont créées à la première écriture. Les variables d’environnement (`MONGO_URL`, `MONGO_DB`, MinIO, etc.) sont à configurer dans **`backend/.env`** (fichier chargé par `app/config.py`). Ne jamais commiter ce fichier.

---

## 7. Index recommandés (performance)

- **`users`** : index unique sur `email`.  
- **`documents`** : index sur `user_id` + `created_at`, `status`, `user_id` + `status` pour les listes et filtres.

Créés au **démarrage du backend** (`backend/database/mongo.py` → `create_indexes()`). Le nom de la base est défini par `MONGO_DB` (ex. `hackathon`) dans `backend/.env`.
