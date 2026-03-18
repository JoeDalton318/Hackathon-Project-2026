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

## 4. Architecture MinIO – alignée backend (Raw / Clean / Curated)

Le backend utilise **3 buckets MinIO** configurés via les variables d’environnement (voir `backend/app/config.py`) : **RAW**, **CLEAN**, **CURATED**. Création au démarrage via `database/minio.py` → `init_buckets()`.

| Variable d’environnement   | Rôle (équivalent Medallion) |
|---------------------------|-----------------------------|
| `MINIO_BUCKET_RAW`        | Zone Raw – fichiers bruts uploadés. |
| `MINIO_BUCKET_CLEAN`      | Zone Clean – résultats par document (OCR, extraction). |
| `MINIO_BUCKET_CURATED`    | Zone Curated – agrégations, exports (CRM, conformité). |

---

### 4.1 Zone Raw – documents bruts (implémentée)

**Rôle :** Stocker les fichiers **tels qu’uploadés**, sans transformation.

**Bucket :** `MINIO_BUCKET_RAW`.

**Clé d’objet (convention backend actuelle) :**
```
{document_id}/{filename}
```
- `document_id` : UUID du document (clé métier dans MongoDB).
- `filename` : nom du fichier original.

**Exemple :**
```
a1b2c3d4-e5f6-7890-abcd-ef1234567890/facture-2026-001.pdf
```

**MongoDB :** Le champ `documents.minio_path` contient **cette clé uniquement** (sans nom de bucket). L’API génère des URLs de téléchargement via **presigned URL** sur le bucket RAW avec cette clé.

**Qui écrit :** Backend (FastAPI) à l’upload (`minio_service.upload_raw`).  
**Qui lit :** Backend (presigned URL pour le frontend) ; pipeline (Airflow) pour lire le fichier et lancer OCR/extraction.

---

### 4.2 Zone Clean – résultats par document (prévue)

**Rôle :** Stocker, **par document traité**, les artefacts du pipeline (OCR, extraction, etc.).  
**Bucket :** `MINIO_BUCKET_CLEAN`. Créé par `init_buckets()`, non encore utilisé par le backend pour l’upload ou les presigned URLs.

**Convention envisagée (à valider avec le pipeline) :** par exemple `{document_id}/original.pdf`, `{document_id}/ocr.txt`, `{document_id}/extraction.json`, etc. Le backend pourra ensuite mettre à jour `documents.minio_path` vers une clé dans CLEAN si besoin, ou gérer un second champ dédié.

**Qui écrit :** Pipeline (Airflow) après OCR et extraction.  
**Qui lit :** Backend (API) pour servir fichiers / OCR / extraction au frontend (à implémenter si besoin).

---

### 4.3 Zone Curated – agrégations (prévue)

**Rôle :** Données **agrégées ou dérivées** pour CRM et conformité.  
**Bucket :** `MINIO_BUCKET_CURATED`. Créé par `init_buckets()`, réservé pour jobs Airflow ou API futures.

**Convention :** À définir (ex. exports par type, par fournisseur, attestations, etc.).

---

### 4.4 Récapitulatif

| Zone   | Variable env           | Usage actuel backend                         |
|--------|------------------------|----------------------------------------------|
| **Raw**   | `MINIO_BUCKET_RAW`    | Upload : `{document_id}/{filename}` ; presigned URL. |
| **Clean** | `MINIO_BUCKET_CLEAN`  | Bucket créé ; usage à définir (pipeline).   |
| **Curated** | `MINIO_BUCKET_CURATED` | Bucket créé ; usage à définir (exports).   |

MongoDB ne stocke **pas** les fichiers ; il stocke la **clé d’objet** dans `minio_path` (zone Raw aujourd’hui) et les données structurées dans `extracted_data` et `anomalies`.

---

## 5. Fichiers de ce dossier

| Fichier | Description |
|---------|--------------|
| `README.md` | Ce fichier : flux de données, rôle des collections, **architecture MinIO** (section 4). |
| `schemas/collections.md` | **Schéma complet** des collections (aligné avec le backend FastAPI). |
| `init-scripts/02-mongodb-indexes.js` | Script JS pour créer les index manuellement avec `mongosh` (optionnel). |

---

## 6. Initialiser la base

- **Recommandé :** Lancer le **backend** (FastAPI). Au démarrage, `backend/database/mongo.py` crée les index via `create_indexes()`. Les collections sont créées à la première écriture.
- **Optionnel (sans lancer le backend) :** Exécuter le script JS avec `mongosh` :
  ```bash
  mongosh "<MONGO_URL>" --file data-architecture/init-scripts/02-mongodb-indexes.js
  ```
  Les variables d’environnement (ex. `MONGO_URL`, `MONGO_DB`) sont à configurer à la **racine du projet** (voir `.env.example` à la racine).

---

## 7. Index recommandés (performance)

- **`users`** : index unique sur `email`.  
- **`documents`** : index sur `user_id` + `created_at`, `status`, `user_id` + `status` pour les listes et filtres.

Créés au **démarrage du backend** (`backend/database/mongo.py` → `create_indexes()`) ou manuellement avec `init-scripts/02-mongodb-indexes.js`. Le nom de la base est défini par `MONGO_DB` (défaut : `hackathon`) à la racine du projet.
