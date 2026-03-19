# Documentation complète — Backend & API Hackathon 2026
> Rédigé par Samuel — Lead API & Backend
> Dernière mise à jour : 17/03/2026

---

## Backend

Documentation du backend.

- Le **front CRM** envoie les documents et récupère les fiches fournisseurs
- Le **front Conformité** récupère l'état de conformité des fournisseurs
- **Airflow** (le pipeline de traitement) est déclenché par ce backend et lui renvoie les résultats
- **MinIO** (le stockage de fichiers) est alimenté par ce backend
- **MongoDB** (la base de données) est gérée exclusivement par ce backend

Concrètement, le backend fait 5 choses :
1. Recevoir les fichiers uploadés par lee front
2. Les stocker dans MinIO
3. Déclencher leur traitement par Airflow
4. Recevoir les résultats du traitement (OCR, extraction, anomalies)
5. Exposer ces résultats aux fronts via une API REST + WebSocket

Le backend est développé avec **FastAPI** (Python 3.13).

---

## Vue d'ensemble de l'architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND                               │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ routers/ │ →  │services/ │ →  │database/ │              │
│  │ (HTTP)   │    │ (logique)│    │(MongoDB  │              │
│  └──────────┘    └──────────┘    │ MinIO)   │              │
│       ↑               ↑          └──────────┘              │
│       │               │                                     │
│  ┌──────────┐    ┌──────────┐                              │
│  │ schemas/ │    │ models/  │                              │
│  │ (API I/O)│    │  (BDD)   │                              │
│  └──────────┘    └──────────┘                              │
│                                                             │
│  ┌──────────┐                                              │
│  │  core/   │  (sécurité, logs, JWT)                       │
│  └──────────┘                                              │
└─────────────────────────────────────────────────────────────┘
         ↑                ↑                  ↑
    Fronts React      Airflow            MinIO / MongoDB
```

---

## Structure des dossiers — explication complète

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          → Point d'entrée de l'application
│   └── config.py        → Configuration centralisée (.env)
│
├── core/
│   ├── __init__.py
│   ├── logging.py       → Configuration des logs
│   ├── security.py      → Protection endpoint interne Airflow
│   └── jwt.py           → Création/vérification tokens JWT + auth
│
├── database/
│   ├── __init__.py
│   ├── mongo.py         → Connexion MongoDB
│   └── minio.py         → Connexion MinIO + création des buckets
│
├── models/
│   ├── __init__.py
│   ├── document.py      → Structure d'un document en base MongoDB
│   └── user.py          → Structure d'un utilisateur en base MongoDB
│
├── schemas/
│   ├── __init__.py
│   ├── document.py      → Format des réponses API pour les documents
│   ├── pipeline.py      → Format du callback Airflow → API
│   ├── crm.py           → Format de la fiche fournisseur
│   ├── compliance.py    → Format du dossier de conformité
│   ├── auth.py          → Format login/register/token
│   └── response.py      → Enveloppe standard {success, data}
│
├── services/
│   ├── __init__.py
│   ├── document_service.py  → Logique métier documents (MongoDB)
│   ├── minio_service.py     → Upload et téléchargement fichiers
│   ├── airflow_service.py   → Déclenchement pipeline Airflow
│   ├── auth_service.py      → Logique register/login
│   └── ws_manager.py        → Gestion connexions WebSocket
│
└── routers/
    ├── __init__.py
    ├── documents.py     → Endpoints upload, consultation, suppression
    ├── pipeline.py      → Endpoint callback interne Airflow
    ├── crm.py           → Endpoint fiche fournisseur
    ├── compliance.py    → Endpoint conformité
    ├── auth.py          → Endpoints login/logout/register/me
    └── ws.py            → Endpoint WebSocket temps réel
```

---

## Principe de fonctionnement — les 3 couches

Le backend est organisé en 3 couches :

**1. Routers** — reçoivent les requêtes HTTP, valident les données, appellent les services, retournent les réponses. Aucune logique métier ici.

**2. Services** — contiennent toute la logique métier. Lisent/écrivent en base, appellent les services externes.

**3. Database** — gèrent les connexions aux bases de données.

Cette séparation permet de modifier une couche sans toucher aux autres.

---

## Dossier `app/` — Point d'entrée et configuration

---

### `app/main.py` — Point d'entrée

C'est le premier fichier exécuté quand on lance le serveur. Il fait 4 choses :

**1. Lifespan — démarrage et arrêt propre**

```
Au démarrage :
  1. Configure les logs
  2. Ouvre la connexion MongoDB
  3. Crée les buckets MinIO si inexistants (raw, clean, curated)

À l'arrêt :
  1. Ferme proprement la connexion MongoDB
```

**2. Middleware CORS**

Autorise les fronts React (ports 3000 et 3001) à appeler l'API depuis le navigateur.
Sans ça, le navigateur bloquerait toutes les requêtes cross-origin.

**3. Gestionnaire d'erreurs global**

Intercepte toutes les erreurs HTTP et les reformate avec l'enveloppe standard :
```json
{ "success": false, "error": "Message d'erreur", "code": "HTTP_404" }
```

**4. Montage des routers sous `/api`**

Tous les endpoints sont préfixés `/api`. Exemple : `/api/documents/upload`.

---

### `app/config.py` — Configuration centralisée

Toutes les variables de configuration sont définies ici et lues depuis le fichier `.env`.
Si une variable obligatoire est manquante au démarrage, **l'app refusera de démarrer**.

**Variables disponibles :**

| Variable | Description | Défaut |
|---|---|---|
| `MONGO_URL` | URL de connexion MongoDB | obligatoire |
| `MONGO_DB` | Nom de la base de données | `hackathon` |
| `MINIO_ENDPOINT` | Adresse du serveur MinIO | obligatoire |
| `MINIO_ACCESS_KEY` | Clé d'accès MinIO | obligatoire |
| `MINIO_SECRET_KEY` | Clé secrète MinIO | obligatoire |
| `MINIO_SECURE` | HTTPS pour MinIO | `false` |
| `MINIO_BUCKET_RAW` | Nom du bucket brut | `raw` |
| `MINIO_BUCKET_CLEAN` | Nom du bucket OCR | `clean` |
| `MINIO_BUCKET_CURATED` | Nom du bucket structuré | `curated` |
| `AIRFLOW_URL` | URL du serveur Airflow | obligatoire |
| `AIRFLOW_DAG_ID` | Identifiant du DAG | `doc_pipeline` |
| `AIRFLOW_USERNAME` | Login Airflow | `airflow` |
| `AIRFLOW_PASSWORD` | Mot de passe Airflow | `airflow` |
| `INTERNAL_API_SECRET` | Secret partagé avec Airflow | obligatoire |
| `JWT_SECRET_KEY` | Clé de signature des tokens JWT | obligatoire |
| `JWT_ALGORITHM` | Algorithme JWT | `HS256` |
| `JWT_EXPIRE_MINUTES` | Durée de vie du token | `480` |
| `CORS_ORIGINS` | URLs autorisées (fronts) | `localhost:3000,3001` |

---

## Dossier `core/` — Utilitaires transversaux

---

### `core/logging.py` — Configuration des logs

Configure le format des logs au démarrage de l'app.
Tous les logs apparaissent dans la console avec horodatage, niveau et message.

---

### `core/security.py` — Protection endpoint interne

Le callback Airflow (`POST /api/internal/pipeline/result`) est un endpoint
que seul Airflow doit pouvoir appeler. Ce fichier expose une fonction de vérification
qui est exécutée automatiquement avant chaque appel à cet endpoint.

Airflow doit inclure le header suivant dans sa requête :
```
X-Internal-Secret: <valeur de INTERNAL_API_SECRET dans le .env>
```

Si le header est absent ou incorrect → `403 Forbidden`, la requête est bloquée.

---

### `core/jwt.py` — Authentification JWT

C'est ici que sont gérés les tokens JWT et les mots de passe.

**Tokens JWT**

Quand un utilisateur se connecte, l'API génère un token JWT — une chaîne signée
contenant l'identité de l'utilisateur et une date d'expiration.

```
Token = Header.Payload.Signature
Payload contient : { "user_id": "uuid", "email": "...", "exp": timestamp }
```

Le front stocke ce token et l'envoie dans chaque requête :
```
Authorization: Bearer eyJhbGci...
```

L'API vérifie la signature du token sans aller en base de données.

**Mots de passe**

Les mots de passe sont hashés avec `bcrypt` avant d'être stockés en base.
Un hash bcrypt est irréversible — même si la base est compromise, les mots de passe
ne peuvent pas être retrouvés.

**`get_current_user`**

C'est la dépendance FastAPI qui protège les endpoints. Ajoutée sur un endpoint,
elle extrait et vérifie le token automatiquement avant d'entrer dans la fonction.
Si le token est invalide ou expiré → `401 Unauthorized`.

---

## Dossier `database/` — Connexions aux bases de données

---

### `database/mongo.py` — Connexion MongoDB

Gère la connexion à MongoDB via `motor` (driver async).

**Pourquoi `motor` ?**
FastAPI traite les requêtes en async — si on utilisait le driver classique `pymongo`,
chaque requête BDD bloquerait le serveur entier. `motor` libère le serveur pendant
qu'il attend la réponse MongoDB.

**Pattern connection pool**
Un seul client MongoDB est créé au démarrage et partagé sur toutes les requêtes.
C'est plus performant que d'ouvrir/fermer une connexion à chaque requête.

**`get_db()`**
Unique point d'accès à la base dans tout le projet. Tous les services l'utilisent.

---

### `database/minio.py` — Connexion MinIO

Gère la connexion à MinIO et la création des buckets.

**MinIO** est un serveur de stockage de fichiers compatible avec l'API Amazon S3.
Il stocke les documents uploadés dans 3 buckets distincts :

| Bucket | Contenu | Alimenté par |
|---|---|---|
| `raw` | Fichiers bruts (PDF, images) | Ce backend (upload) |
| `clean` | Texte extrait par l'OCR | Airflow (équipe NLP/OCR) |
| `curated` | Données structurées finales | Airflow (équipe Data) |

Au démarrage, l'API vérifie que ces 3 buckets existent et les crée si nécessaire.

---

## Dossier `models/` — Structure des données en base

Les modèles définissent exactement ce qui est stocké dans MongoDB.
C'est la représentation interne — jamais exposée directement vers l'extérieur.

---

### `models/document.py` — Modèle Document

Chaque fichier uploadé crée un enregistrement MongoDB avec cette structure :

| Champ | Type | Description |
|---|---|---|
| `document_id` | UUID | Identifiant unique généré à l'upload |
| `original_filename` | string | Nom du fichier original |
| `mime_type` | string | Type du fichier (pdf, jpeg, png, tiff) |
| `minio_path` | string | Chemin dans MinIO : `{uuid}/{filename}` |
| `status` | enum | État dans le pipeline de traitement |
| `document_type` | enum | Type détecté par l'IA |
| `extracted_data` | dict | Données extraites par OCR/NER |
| `anomalies` | liste | Incohérences détectées |
| `created_at` | datetime | Date d'upload |
| `updated_at` | datetime | Date de dernière mise à jour |

**Cycle de vie du statut :**
```
PENDING → PROCESSING → OCR_DONE → EXTRACTION_DONE → DONE
                                                    ↘ ERROR
```

**Types de documents reconnus :**
`FACTURE`, `DEVIS`, `KBIS`, `RIB`, `ATTESTATION_URSSAF`, `ATTESTATION_SIRET`, `UNKNOWN`

---

### `models/user.py` — Modèle Utilisateur

Structure d'un compte utilisateur en base :

| Champ | Type | Description |
|---|---|---|
| `user_id` | UUID | Identifiant unique |
| `email` | string | Email (unique) |
| `hashed_password` | string | Hash bcrypt du mot de passe |
| `nom` | string | Nom affiché |
| `role` | enum | `USER` ou `ADMIN` |
| `created_at` | datetime | Date de création |

---

## Dossier `schemas/` — Format des données exposées par l'API

Les schemas définissent ce que l'API reçoit et renvoie.
Ils sont différents des modèles : ils ne contiennent jamais le `hashed_password`,
peuvent regrouper des données de plusieurs modèles, etc.

---

### `schemas/response.py` — Enveloppe standard

Toutes les réponses de l'API ont cette structure :

**Succès :**
```json
{
  "success": true,
  "data": { ... }
}
```

**Erreur :**
```json
{
  "success": false,
  "error": "Message d'erreur lisible",
  "code": "HTTP_404"
}
```

---

### `schemas/document.py` — Schemas documents

- `UploadResponse` : retourné après un upload (document_id, filename, status)
- `DocumentOut` : représentation complète d'un document pour le front
- `DocumentListOut` : liste paginée avec total, page, limit, items

---

### `schemas/pipeline.py` — Payload callback Airflow

Structure du JSON qu'Airflow envoie à l'API quand le traitement est terminé :

```json
{
  "document_id": "uuid",
  "status": "done",
  "document_type": "facture",
  "extracted_data": {
    "siret": "12345678901234",
    "montant_ttc": "1200.00",
    "date_emission": "2026-01-15",
    "raison_sociale": "ACME SAS",
    "iban": "FR76...",
    "adresse": "12 rue de la Paix, Paris",
    "tva_intracommunautaire": "FR12345678901"
  },
  "anomalies": [],
  "error_message": null
}
```

---

### `schemas/crm.py` — Fiche fournisseur

Réponse de `GET /api/crm/supplier/{siret}` :

```json
{
  "success": true,
  "data": {
    "siret": "12345678901234",
    "raison_sociale": "ACME SAS",
    "iban": "FR76...",
    "adresse": "12 rue de la Paix, Paris",
    "tva_intracommunautaire": "FR12345678901",
    "conformite_status": "ok",
    "documents": [...]
  }
}
```

---

### `schemas/compliance.py` — Dossier de conformité

Réponse de `GET /api/compliance/dossier/{siret}` :

```json
{
  "success": true,
  "data": {
    "siret": "12345678901234",
    "is_compliant": false,
    "anomalies": [
      {
        "type": "SIRET_MISMATCH",
        "severity": "HIGH",
        "description": "SIRET différent entre la facture et l'attestation URSSAF",
        "document_ids": ["uuid1", "uuid2"]
      }
    ],
    "documents_summary": [...]
  }
}
```

---

### `schemas/auth.py` — Authentification

- `LoginRequest` : email + password
- `RegisterRequest` : email + password + nom
- `TokenResponse` : token JWT + infos utilisateur
- `UserOut` : infos utilisateur (jamais le hashed_password)

---

## Dossier `services/` — Logique métier

---

### `services/document_service.py` — Gestion des documents

Toutes les interactions avec la collection MongoDB `documents`.

| Fonction | Description |
|---|---|
| `create_record()` | Crée un enregistrement avec UUID, statut PENDING |
| `get_record()` | Récupère un document par son document_id |
| `update_from_callback()` | Met à jour après réception résultats Airflow |
| `update_minio_path()` | Met à jour le chemin MinIO après upload |
| `update_status()` | Met à jour uniquement le statut |
| `list_records()` | Liste paginée avec filtres optionnels |
| `get_supplier_documents()` | Tous les documents d'un SIRET |
| `delete_record()` | Supprime un document de MongoDB |

---

### `services/minio_service.py` — Stockage fichiers

| Fonction | Description |
|---|---|
| `upload_raw()` | Upload un fichier dans le bucket `raw` |
| `get_presigned_url()` | Génère une URL temporaire (15 min) pour téléchargement |

**URL pré-signée** : plutôt que de servir les fichiers via l'API (charge serveur),
on génère une URL directement vers MinIO valable 15 minutes. Le front télécharge
depuis MinIO directement.

---

### `services/airflow_service.py` — Déclenchement pipeline

Appelle l'API REST d'Airflow pour déclencher le DAG de traitement après chaque upload.
Passe le `document_id` au DAG :
```json
{ "conf": { "document_id": "uuid" } }
```

Si Airflow est indisponible → retourne `False` sans planter.
Le pipeline peut être relancé via `POST /api/documents/{id}/process`.

---

### `services/auth_service.py` — Authentification

| Fonction | Description |
|---|---|
| `create_user()` | Vérifie unicité email, hash le mot de passe, insère en base |
| `authenticate_user()` | Vérifie email + mot de passe, retourne l'utilisateur ou None |
| `get_user_by_id()` | Récupère un utilisateur par son user_id |

---

### `services/ws_manager.py` — WebSocket temps réel

Gère toutes les connexions WebSocket actives.
Structure interne : `{ document_id → [liste de WebSockets connectés] }`

| Méthode | Description |
|---|---|
| `connect()` | Accepte et enregistre une nouvelle connexion |
| `disconnect()` | Supprime une connexion fermée |
| `broadcast()` | Envoie un message à tous les clients d'un document_id |

---

## Dossier `routers/` — Endpoints de l'API

Tous les endpoints sont préfixés `/api`.

---

### `routers/auth.py` — Authentification

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | Non | Créer un compte |
| POST | `/api/auth/login` | Non | Se connecter, reçoit un JWT |
| POST | `/api/auth/logout` | Oui | Déconnexion |
| GET | `/api/auth/me` | Oui | Infos utilisateur courant |

**Flux de connexion :**
```
1. POST /api/auth/login → reçoit { "token": "eyJ...", "user": {...} }
2. Stocker le token côté front
3. Envoyer Authorization: Bearer <token> sur chaque requête suivante
```

---

### `routers/documents.py` — Documents

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/documents/` | Oui | Liste paginée des documents |
| POST | `/api/documents/upload` | Oui | Upload 1 ou plusieurs fichiers |
| POST | `/api/documents/upload-folder` | Oui | Upload un ZIP |
| GET | `/api/documents/{id}` | Oui | Détail complet d'un document |
| GET | `/api/documents/{id}/status` | Oui | Statut seul (pour polling) |
| GET | `/api/documents/{id}/anomalies` | Oui | Anomalies détectées |
| GET | `/api/documents/{id}/download` | Oui | URL de téléchargement |
| POST | `/api/documents/{id}/process` | Oui | Relancer le pipeline manuellement |
| DELETE | `/api/documents/{id}` | Oui | Supprimer un document |

**Flux d'upload complet :**
```
1. POST /api/documents/upload (fichier en multipart/form-data)
   → Vérifie le type MIME (PDF, JPEG, PNG, TIFF uniquement)
   → Crée un enregistrement MongoDB (status: PENDING)
   → Upload le fichier dans MinIO bucket raw/
   → Déclenche le DAG Airflow avec le document_id
   → Retourne { document_id, filename, status: "pending" }

2. Ouvrir WebSocket sur /api/ws/documents/{document_id}
   → Reçoit les mises à jour en temps réel

3. Quand WebSocket reçoit status: "done"
   → Appeler GET /api/documents/{document_id} pour les données complètes
```

---

### `routers/pipeline.py` — Callback interne Airflow

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/internal/pipeline/result` | Secret | Réception résultats Airflow |

Cet endpoint est **exclusivement pour Airflow**. Le front ne l'appelle jamais.

```
Header: X-Internal-Secret: <INTERNAL_API_SECRET>
Body: PipelineCallbackPayload
```

Séquence à la réception :
```
1. Vérification du secret → 403 si invalide
2. Mise à jour MongoDB ($set partiel)
3. Broadcast WebSocket → tous les fronts connectés reçoivent la mise à jour
```

---

### `routers/ws.py` — WebSocket temps réel

| Méthode | Endpoint | Description |
|---|---|---|
| WS | `/api/ws/documents/{document_id}` | Suivi temps réel d'un document |

**Payload reçu par le front :**
```json
{
  "document_id": "uuid",
  "status": "done",
  "document_type": "facture",
  "anomalies": []
}
```

---

### `routers/crm.py` — CRM Fournisseur

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/crm/supplier/{siret}` | Oui | Fiche fournisseur agrégée |

Récupère tous les documents d'un fournisseur par SIRET, fusionne leurs
`extracted_data`, et retourne une fiche prête pour l'auto-remplissage.

---

### `routers/compliance.py` — Conformité

| Méthode | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/compliance/dossier/{siret}` | Oui | Dossier de conformité complet |

`is_compliant: true` uniquement si aucune anomalie sur l'ensemble du dossier.

---

## Intégration avec les autres équipes

---

### Frontend (CRM + Conformité)

**Ce que le front doit faire :**
```
1. POST  /api/auth/login                  → obtenir le token JWT
2. POST  /api/documents/upload            → uploader les fichiers
3. WS    /api/ws/documents/{id}           → suivre l'avancement
4. GET   /api/documents/{id}              → récupérer les résultats
5. GET   /api/crm/supplier/{siret}        → auto-remplir le CRM
6. GET   /api/compliance/dossier/{siret}  → afficher la conformité
```

**Header obligatoire sur toutes les requêtes protégées :**
```
Authorization: Bearer <token>
```

---

### Airflow (Orchestration)

**Ce que l'API fait pour Airflow :**
```
POST {AIRFLOW_URL}/api/v1/dags/doc_pipeline/dagRuns
Body: { "conf": { "document_id": "uuid" } }
```

**Ce qu'Airflow doit faire pour l'API :**
```
POST /api/internal/pipeline/result
Header: X-Internal-Secret: <valeur partagée en privé>
Body: {
  "document_id": "uuid",
  "status": "done",
  "document_type": "facture",
  "extracted_data": { ... },
  "anomalies": [ ... ]
}
```

Le secret `INTERNAL_API_SECRET` doit être partagé entre Samuel et l'équipe Airflow
en privé — pas dans le repo Git.

---

### NLP/OCR

Les résultats OCR arrivent via Airflow dans le champ `extracted_data` du callback.

**Noms de clés attendus dans `extracted_data` :**

> ⚠️ Ces noms doivent être identiques entre ce que l'OCR produit et ce que le CRM lit.

```json
{
  "siret": "12345678901234",
  "tva_intracommunautaire": "FR12345678901",
  "montant_ht": "1000.00",
  "montant_ttc": "1200.00",
  "date_emission": "2026-01-15",
  "raison_sociale": "ACME SAS",
  "iban": "FR76...",
  "adresse": "12 rue de la Paix, Paris"
}
```

---

### Data / MinIO

L'API crée les 3 buckets au démarrage : `raw`, `clean`, `curated`.
Le bucket `raw` est alimenté par l'API. Les buckets `clean` et `curated`
sont alimentés par Airflow.

Les noms des buckets doivent correspondre aux variables du `.env` :
`MINIO_BUCKET_RAW`, `MINIO_BUCKET_CLEAN`, `MINIO_BUCKET_CURATED`.

---

## Bilan actuel

---

### Terminé et fonctionnel

| Fonctionnalité | Endpoint | Prêt pour |
|---|---|---|
| Register / Login / Logout / Me | `/api/auth/*` | Frontend |
| Upload multi-fichiers | `POST /api/documents/upload` | Frontend, Airflow |
| Upload dossier ZIP | `POST /api/documents/upload-folder` | Frontend |
| Stockage MinIO (bucket raw) | — | Airflow, Data |
| Création enregistrement MongoDB | — | Toute l'équipe |
| Déclenchement DAG Airflow | — | Airflow |
| WebSocket suivi temps réel | `WS /api/ws/documents/{id}` | Frontend |
| Callback résultats Airflow | `POST /api/internal/pipeline/result` | Airflow |
| Consultation document complet | `GET /api/documents/{id}` | Frontend |
| Statut seul (polling) | `GET /api/documents/{id}/status` | Frontend |
| Anomalies seules | `GET /api/documents/{id}/anomalies` | Frontend |
| Téléchargement URL pré-signée | `GET /api/documents/{id}/download` | Frontend |
| Liste paginée avec filtres | `GET /api/documents/` | Frontend |
| Relance manuelle pipeline | `POST /api/documents/{id}/process` | Frontend |
| Suppression document | `DELETE /api/documents/{id}` | Frontend |
| Auto-remplissage CRM | `GET /api/crm/supplier/{siret}` | Frontend CRM |
| Conformité fournisseur | `GET /api/compliance/dossier/{siret}` | Frontend Conformité |
| Health check | `GET /health` | DevOps |
| Format réponse standard | Tous les endpoints | Frontend |
| Protection endpoint interne | Header X-Internal-Secret | Airflow |

---

### En attente

| Fonctionnalité | En attente de | Détail |
|---|---|---|
| Auto-remplissage CRM complet | Équipe OCR/NLP | Aligner les noms de clés dans `extracted_data` |
| Conformité avec vraies anomalies | Équipe Validation/Airflow | Les anomalies doivent être peuplées dans le callback |
| Test end-to-end pipeline | Équipe Airflow | DAG doit appeler le callback avec le bon format |
| Buckets `clean` et `curated` utilisés | Équipe Data/Airflow | L'API les crée, Airflow doit les alimenter |

---

## Comment lancer l'API

```bash
cd backend
pip install -r requirements.txt
cd .. # à la racine du projet
make fastapi-dev
```

**Swagger :** `http://localhost:8000/docs`

Permet de tester tous les endpoints directement dans le navigateur.
Pour les endpoints protégés, cliquer sur "Authorize" en haut à droite
et coller le token JWT obtenu au login.

---

*Document rédigé par Samuel — Lead API & Backend — Hackathon 2026*