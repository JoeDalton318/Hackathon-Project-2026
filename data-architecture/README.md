# Data Architecture – Hackathon 2026 (Boussad)

Base de données **MongoDB Atlas** et explication du **flux de données** pour le pipeline de traitement de documents (upload → OCR → extraction → validation → stockage).

---

## 1. Connexion MongoDB Atlas

La base de données utilisée est **MongoDB Atlas** (cloud).

- **Variable d’environnement** (à configurer côté backend / orchestration) :  
  `MONGO_URL=mongodb+srv://<user>:<password>@hackaton.dcvuugn.mongodb.net/?appName=hackaton`
- Ne jamais commiter le mot de passe dans le dépôt. Utiliser un fichier `.env` (voir `.env.example` à la racine du projet).
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
                    │  (status:   │             │
                    │  pending)   │             │
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
| 1 | Backend | Reçoit l’upload, stocke le fichier dans **MinIO (Bronze)** et crée un document dans **MongoDB** (`documents`) avec `status: "pending"`. |
| 2 | Backend | Déclenche le **DAG Airflow** (traitement asynchrone). |
| 3 | Pipeline (Airflow) | Lit le fichier depuis MinIO Bronze, fait **OCR → IA (classification) → Validation** (Sirene, inter-documents). |
| 4 | Pipeline | Écrit les résultats dans **MinIO (Silver)** (ocr.txt, extraction.json) et met à jour le document dans **MongoDB** : `status: "done"`, `extracted_data`, `document_type`, `anomalies`, etc. |
| 5 | Frontend | Appelle l’API pour récupérer la liste et le détail des documents ; l’API lit dans **MongoDB** (et peut servir le fichier depuis MinIO). |

**MongoDB** sert à stocker les **métadonnées** et le **résultat d’extraction** (`extracted_data`, `anomalies`). Les **fichiers** et le **texte OCR** sont dans **MinIO** (Bronze = brut, Silver = traité).

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
| `minio_path` | string | Chemin du fichier dans MinIO (Bronze ou Silver selon convention). |
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

## 4. Architecture MinIO – un bucket partagé (datalake) + préfixes

**Backend, OCR et validation** utilisent la **même instance MinIO** : un seul bucket (`datalake`) avec des **préfixes** pour les couches Raw, Clean et Curated. Connexion via les variables du `.env` à la racine du projet.

| Variable d’environnement     | Rôle |
|------------------------------|------|
| `MINIO_ENDPOINT`             | Ex. `localhost:9000` (ou host du serveur MinIO partagé). |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Identifiants (ex. `minioadmin` / `minioadmin123`). |
| `MINIO_SECURE`               | `false` en local, `true` si HTTPS. |
| `MINIO_BUCKET`               | **Un seul bucket** partagé, ex. `datalake`. |
| `MINIO_RAW_PREFIX`           | Préfixe zone Raw, ex. `raw/`. |
| `MINIO_CURATED_PREFIX`       | Préfixe zone Curated, ex. `curated/`. |
| `MINIO_VALIDATION_PREFIX`    | Préfixe résultats de validation, ex. `curated/validation/`. |

**Exemple de `.env` (aligné OCR / validation) :**
```env
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_SECURE=false
MINIO_BUCKET=datalake
MINIO_CURATED_PREFIX=curated/
MINIO_VALIDATION_PREFIX=curated/validation/
```

---

### 4.1 Zone Raw – documents bruts

**Rôle :** Fichiers **tels qu’uploadés** (backend).  
**Préfixe :** `raw/` (ou valeur de `MINIO_RAW_PREFIX`).

**Clé d’objet :**
```
raw/{document_id}/{filename}
```
- `document_id` : UUID du document (clé métier MongoDB).
- `filename` : nom du fichier original.

**MongoDB :** `documents.minio_path` contient cette **clé complète** (avec préfixe). L’API génère des URLs de téléchargement via presigned URL sur le bucket `MINIO_BUCKET` avec cette clé.

**Qui écrit :** Backend à l’upload. **Qui lit :** Backend (presigned URL) ; pipeline OCR.

---

### 4.2 Zone Clean – résultats par document (OCR / extraction)

**Rôle :** Artefacts du pipeline (OCR, extraction) par document.  
**Préfixe :** convention à aligner avec le pipeline (ex. `clean/`).  
**Qui écrit :** Pipeline (Airflow / OCR). **Qui lit :** Backend, validation.

---

### 4.3 Zone Curated – agrégations et validation

**Rôle :** Données agrégées, exports, et **résultats de validation**.  
**Préfixes :** `curated/` et `curated/validation/` (`MINIO_CURATED_PREFIX`, `MINIO_VALIDATION_PREFIX`).  
**Qui écrit :** Jobs Airflow, API, module de validation. **Qui lit :** Backend, CRM, conformité.

---

### 4.4 Récapitulatif

| Couche   | Préfixe / variable           | Usage |
|----------|-----------------------------|-------|
| **Raw**  | `raw/` (`MINIO_RAW_PREFIX`)  | Upload backend ; lecture OCR. |
| **Clean**| à définir avec le pipeline  | OCR, extraction par document. |
| **Curated** | `curated/`               | Agrégations, exports. |
| **Validation** | `curated/validation/` | Résultats de validation. |

Un seul bucket **`MINIO_BUCKET`** (ex. `datalake`) pour tout le projet. MongoDB stocke la **clé d’objet** dans `minio_path` et les données structurées dans `extracted_data` et `anomalies`.

---

## 5. Fichiers de ce dossier

| Fichier | Description |
|---------|--------------|
| `README.md` | Ce fichier : flux de données, rôle des collections, **architecture MinIO** (section 4). |
| `schemas/collections.md` | **Schéma complet** des collections (aligné avec le backend FastAPI). |

---

## 6. Initialiser la base

Lancer le **backend** (FastAPI). Au démarrage, `backend/database/mongo.py` crée les index via `create_indexes()`. Les collections sont créées à la première écriture. Les variables d’environnement (ex. `MONGO_URL`, `MONGO_DB`, MinIO) sont à configurer à la **racine du projet** (voir `.env.example` à la racine).

---

## 7. Index recommandés (performance)

- **`users`** : index unique sur `email`.  
- **`documents`** : index sur `user_id` + `created_at`, `status`, `user_id` + `status` pour les listes et filtres.

Créés au **démarrage du backend** (`backend/database/mongo.py` → `create_indexes()`) ou manuellement avec `init-scripts/02-mongodb-indexes.js`. Le nom de la base est défini par `MONGO_DB` (défaut : `hackathon`) à la racine du projet.
