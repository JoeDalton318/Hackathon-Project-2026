# Orchestration & Pipeline Airflow

Documentation complète du système d'orchestration basé sur Apache Airflow pour le traitement automatisé des documents.

---

## Vue d'ensemble

Le système d'orchestration gère le workflow complet de traitement des documents, de l'upload jusqu'à l'archivage, en mode **event-driven** (déclenchement immédiat à chaque upload).

### Architecture

```
┌──────────────┐   Upload   ┌──────────────┐   Trigger   ┌──────────────┐
│   Frontend   │ ────────> │   Backend    │ ─────────> │   Airflow    │
│   (React)    │            │   (FastAPI)  │             │  (Pipeline)  │
└──────────────┘            └──────────────┘             └──────────────┘
                                   │                             │
                                   │                             │
                                   ▼                             ▼
                            ┌──────────────┐            ┌──────────────┐
                            │   MongoDB    │◄───────────│  NLP/OCR     │
                            │   (Atlas)    │            │  Validation  │
                            └──────────────┘            └──────────────┘
                                   │                             │
                                   │                             │
                                   ▼                             ▼
                            ┌────────────────────────────────────┐
                            │      MinIO Data Lake (S3)          │
                            │  Buckets: raw / clean / curated    │
                            └────────────────────────────────────┘
```

---

## Workflow complet

### 1. Déclenchement (Event-Driven)

```
Frontend upload document
    ↓
Backend API:
  - Crée enregistrement MongoDB (status: PENDING)
  - Upload fichier vers MinIO bucket "raw"
  - POST /airflow/api/v1/dags/doc_pipeline/dagRuns
    Body: { "conf": { "document_id": "uuid" } }
    ↓
Airflow reçoit trigger immédiat (pas de batch)
```

### 2. Pipeline Airflow (6 tâches)

**Task 1: `get_document`**
- Récupère document_id depuis `dag_run.conf`
- Lit MongoDB pour obtenir `minio_path`, `filename`, `mime_type`
- Stocke infos en XCom pour tâches suivantes

**Task 2: `download_document`**
- Télécharge fichier depuis MinIO bucket `raw`
- Stocke localement dans `/tmp/documents/`
- Retourne chemin local

**Task 3: `perform_ocr`**
- Appelle module NLP/OCR: `from nlp_ocr import extract`
- Extrait texte + données structurées (SIRET, montants, dates...)
- Stocke `extraction.json` dans MinIO `clean/YYYY/MM/DD/{document_id}/`
- Retourne `extracted_data` avec classification et champs

**Task 4: `perform_validation`**
- Lit `extraction.json` depuis MinIO bucket `clean`
- Appelle module validation pour règles métier
- Détecte anomalies (SIRET invalide, dates incohérentes, doublons...)
- Stocke `validation_result.json` dans MinIO `clean/`
- Retourne `anomalies` + `decision` (approved/review/blocked)

**Task 5: `callback_backend`**
- Formate payload selon schéma Backend: `PipelineCallbackPayload`
- POST `/api/internal/pipeline/result` avec header `X-Internal-Secret`
- Backend met à jour MongoDB + WebSocket notification au Frontend

**Task 6: `archive_document`** (parallèle à Task 5)
- Copie fichier original depuis `raw/` vers MinIO `curated/YYYY/MM/DD/{document_id}/`
- Copie `extraction.json` depuis `clean/` vers `curated/`
- Copie `validation_result.json` depuis `clean/` vers `curated/`
- Résultat final validé archivé dans `curated/` pour usage ultérieur

### 3. Chaînage des tâches

```
get_document 
    ↓
download_document 
    ↓
perform_ocr 
    ↓
perform_validation 
    ↓
├─> callback_backend
└─> archive_document
```

Les deux dernières tâches s'exécutent en **parallèle** pour optimiser le temps de traitement.

---

## Configuration

### Variables d'environnement (.env racine)

```bash
# MongoDB
MONGO_URL=mongodb+srv://...
MONGO_DB=hackathon

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_SECURE=False
MINIO_BUCKET_RAW=raw
MINIO_BUCKET_CLEAN=clean
MINIO_BUCKET_CURATED=curated

# Airflow
AIRFLOW_URL=http://localhost:8080
AIRFLOW_DAG_ID=doc_pipeline
AIRFLOW_USERNAME=airflow
AIRFLOW_PASSWORD=airflow

# Backend API
BACKEND_API_URL=http://localhost:8000
INTERNAL_API_SECRET=your_secret_key_here
API_TIMEOUT=10
```

### Fichier config.py

Centralise toutes les configurations Airflow. Charge automatiquement les variables depuis `.env` racine.

**Sections :**
- `MINIO_CONFIG` : Connexion MinIO + buckets
- `MONGODB_CONFIG` : Connexion MongoDB Atlas
- `BACKEND_API_CONFIG` : Endpoints Backend pour callback
- `PYTHON_MODULES` : Chemins modules OCR/Validation

---

## DAGs disponibles

### 1. `doc_pipeline` (Production - Event-Driven)

**Fichier :** `document_processing_pipeline.py`

- **Schedule :** `None` (déclenché par Backend API)
- **Tags :** `documents`, `ocr`, `production`, `event-driven`
- **Retries :** 2 (délai 5 min)
- **Tâches :** 6 (get_document → download → ocr → validation → callback + archive)

**Déclenchement :**
```bash
curl -X POST "http://localhost:8080/api/v1/dags/doc_pipeline/dagRuns" \
  -H "Content-Type: application/json" \
  -u "airflow:airflow" \
  -d '{"conf": {"document_id": "uuid-here"}}'
```

### 2. `monitoring_metrics` (Monitoring)

**Fichier :** `monitoring_metrics.py`

- **Schedule :** Toutes les heures
- **Tags :** `monitoring`, `metrics`
- **Tâches :** 4 (collect_stats → check_storage → analyze_perf → generate_report)

**Fonctionnalités :**
- Collecte statistiques traitement (nb docs, taux erreur, temps moyen)
- Vérifie santé MinIO + MongoDB
- Analyse performances pipeline
- Génère rapports métriques

### 3. `maintenance_cleanup` (Maintenance)

**Fichier :** `maintenance_cleanup.py`

- **Schedule :** Quotidien (2h du matin)
- **Tags :** `maintenance`, `cleanup`
- **Tâches :** 3 (cleanup_processed → cleanup_failed → cleanup_orphans)

**Politiques rétention :**
- Documents processed : 30 jours
- Documents failed : 7 jours
- Fichiers orphelins : suppression immédiate

---

## Intégration avec les modules Python

### Module NLP/OCR

**Localisation :** `/opt/airflow/nlp-ocr` (monté dans Docker)

**Utilisation dans Airflow :**
```python
from nlp_ocr import extract

result = extract(file_path)
# → ExtractionResult avec classification + champs structurés
```

**Sortie attendue :**
- `result.classification.document_type` : facture, rib, kbis...
- `result.overall_confidence` : score 0-1
- `result.facture.montant_ttc.value` : champs typés par document

**Stockage MinIO :**
```
curated/YYYY/MM/DD/{document_id}/extraction.json
```

### Module Validation

**Localisation :** `/opt/airflow/validation` (monté dans Docker)

**Utilisation :**
```python
from validation.main import validate_batch_from_minio

result = validate_batch_from_minio(
    extraction_path="curated/.../extraction.json",
    store_minio=True
)
```

**Sortie attendue :**
- `result['decision']` : approved / review / blocked
- `result['alerts']` : liste anomalies détectées
- `result['batch_stats']` : statistiques validation

**Stockage MinIO :**
```
curated/validation/batches/YYYY/MM/DD/{batch_id}/validation_result.json
curated/validation/documents/YYYY/MM/DD/{document_id}/validation_result.json
```

---

## Format du Callback Backend

### Endpoint

```
POST http://localhost:8000/api/internal/pipeline/result
```

### Headers

```
Content-Type: application/json
X-Internal-Secret: <INTERNAL_API_SECRET>
```

### Payload (PipelineCallbackPayload)

```json
{
  "document_id": "uuid",
  "status": "done",
  "document_type": "facture",
  "extracted_data": {
    "siret": "12345678901234",
    "montant_ttc": "1200.00",
    "raison_sociale": "ACME SAS",
    "iban": "FR76...",
    "date_emission": "2026-01-15"
  },
  "anomalies": [
    {
      "type": "SIRET_MISMATCH",
      "severity": "HIGH",
      "description": "SIRET different entre facture et attestation"
    }
  ],
  "error_message": null
}
```

### Status possibles

- `pending` : En attente
- `processing` : En cours
- `ocr_done` : OCR terminé
- `extraction_done` : Extraction terminée
- `done` : Traitement complet
- `error` : Erreur bloquante

---

## Déploiement

### Prérequis

- Docker & Docker Compose
- 4 GB RAM minimum
- Ports disponibles : 8080 (Airflow), 9000 (MinIO), 5432 (PostgreSQL)

### Lancement

```bash
cd orchestration
docker-compose up -d
```

**Services démarrés :**
- `postgres` : Base métadonnées Airflow (port 5432)
- `minio` : Data Lake S3 (port 9000)
- `airflow-init` : Initialisation BDD + utilisateurs
- `airflow-webserver` : UI Web (port 8080)
- `airflow-scheduler` : Moteur d'orchestration

### Accès UI

**Airflow Web UI :** http://localhost:8080
- Username: `airflow`
- Password: `airflow`

**MinIO Console :** http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin123`

### Vérification

```bash
# Logs Airflow Scheduler
docker-compose logs -f airflow-scheduler

# Logs Airflow Webserver
docker-compose logs -f airflow-webserver

# Santé des services
docker-compose ps
```

---

## Dépannage

### DAG non visible dans UI

**Cause :** Erreur de syntaxe Python

**Solution :**
```bash
docker-compose exec airflow-scheduler airflow dags list
# Vérifier les erreurs dans les logs
```

### Trigger DAG échoue (404)

**Cause :** DAG_ID incorrect ou API Airflow non activée

**Solution :**
- Vérifier `AIRFLOW_DAG_ID=doc_pipeline` dans `.env`
- Activer API dans `airflow.cfg`: `auth_backend = airflow.api.auth.backend.basic_auth`

### Callback Backend échoue (403 Forbidden)

**Cause :** Secret `X-Internal-Secret` incorrect

**Solution :**
- Synchroniser `INTERNAL_API_SECRET` entre `.env` racine et config Backend
- Vérifier header dans logs Airflow

### Module nlp_ocr / validation non trouvé

**Cause :** Montage Docker incomplet

**Solution :**
- Vérifier `docker-compose.yml` volumes:
  ```yaml
  volumes:
    - ../nlp-ocr:/opt/airflow/nlp-ocr
    - ../validation:/opt/airflow/validation
  ```

### Connexion MongoDB échoue

**Cause :** `MONGO_URL` invalide ou réseau bloqué

**Solution :**
- Tester connexion depuis Airflow container:
  ```bash
  docker-compose exec airflow-scheduler python -c "from pymongo import MongoClient; print(MongoClient('MONGO_URL').server_info())"
  ```

---

## Monitoring & Métriques

### Métriques collectées (DAG monitoring_metrics)

- **Traitement :**
  - Nombre documents traités (24h, 7j, 30j)
  - Taux de succès / erreur
  - Temps moyen de traitement

- **Stockage :**
  - Espace utilisé par bucket (raw, clean, curated)
  - Nombre fichiers par bucket
  - Fichiers orphelins détectés

- **Performance :**
  - Latence moyenne par tâche
  - Tâches les plus lentes (top 10)
  - Goulots d'étranglement détectés

### Logs

**Localisation :** `orchestration/airflow/logs/`

**Structure :**
```
logs/
├── dag_id=doc_pipeline/
│   ├── run_id=manual__2026-03-17/
│   │   ├── task_id=get_document/
│   │   ├── task_id=perform_ocr/
│   │   └── ...
├── scheduler/
└── dag_processor_manager/
```

**Consultation :**
- Via UI Airflow : DAG → Runs → Task → Logs
- Fichiers : `orchestration/airflow/logs/`

---

## Évolutions futures

### En cours

- [x] Pipeline event-driven opérationnel
- [x] Intégration OCR/NLP
- [x] Validation métier
- [x] Callback Backend
- [x] Monitoring automatisé

### Roadmap

- [ ] Retry intelligent avec backoff exponentiel
- [ ] Alerting Slack/Email sur erreurs
- [ ] Dashboard Grafana métriques temps réel
- [ ] Parallélisation multi-documents
- [ ] Support formats supplémentaires (Word, Excel)
- [ ] ML anomaly detection avancée

---

## Support & Contact

**Documentation complète :** Voir fichiers dans `docs/`

**Logs & Debug :**
```bash
# Logs temps réel
docker-compose logs -f airflow-scheduler

# Tester DAG manuellement
docker-compose exec airflow-scheduler \
  airflow dags test doc_pipeline 2026-03-17

# Shell dans container
docker-compose exec airflow-scheduler bash
```

**Vérification santé système :**
```bash
# Via API Airflow
curl http://localhost:8080/health

# Via commande
docker-compose exec airflow-scheduler airflow dags list-runs -d doc_pipeline
```

---

*Documentation Orchestration - Hackathon 2026*
