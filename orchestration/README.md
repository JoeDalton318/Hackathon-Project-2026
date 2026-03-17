# Orchestration Airflow - Pipeline de traitement de documents

## Vue d'ensemble

Ce repertoire contient l'orchestration complete du pipeline de traitement de documents pour le projet hackathon. L'architecture utilise Apache Airflow avec **LocalExecutor** pour simplifier le déploiement local.

## Configuration MongoDB Atlas

### Base de données cloud fournie par Samuel (Lead Backend)

Le projet utilise **MongoDB Atlas** (cloud) au lieu d'une base MongoDB locale.

**Connection string:**
```
mongodb+srv://admin:wYS7UuJm_G7prB_@hackaton.dcvuugn.mongodb.net/?appName=hackaton
```

**Database:** `hackathon_db`

**Configuration:**
- Fichier `.env` contient les credentials (non committe)
- Fichier `.env.example` contient le template
- Tous les DAGs utilisent automatiquement MongoDB Atlas via `config.py`

**Avantages:**
- Accessible depuis n'importe ou (cloud)
- Pas besoin d'exposer de ports locaux
- Partage entre toute l'equipe
- Backups automatiques

## Architecture

### Services Docker (7 services locaux)

1. **PostgreSQL**
   - Base de données métadonnées Airflow uniquement
   - Non exposé (usage interne)

2. **MinIO** (ports 9000/9001)
   - Data Lake compatible S3
   - Stockage des documents bruts et traités

3. **Airflow Init**
   - Initialisation automatique de la base Airflow
   - Création utilisateur admin
   - Exécuté au démarrage

4. **Airflow Webserver** (port 8080)
   - Interface utilisateur pour monitorer les DAGs
   - Authentification: admin/admin

5. **Airflow Scheduler**
   - Planification et déclenchement des tâches
   - Gestion des dépendances entre tâches
   - Utilise LocalExecutor (exécution locale, pas de cluster)

6. **Backend FastAPI** (port 8000)
   - API REST pour l'interface frontend

7. **Frontend React** (port 3000)
   - Interface utilisateur web

### Services externes

- **MongoDB Atlas** (Cloud)
  - Base de données principale du projet
  - Fournie par Samuel (Lead Backend)
  - Accessible depuis tous les services via connection string

## DAGs disponibles

### 1. document_processing_pipeline.py

Pipeline principal de traitement des documents.

**Schedule:** Toutes les 15 minutes

**Flux:**
```
scan_documents -> download_documents -> extract_text -> validate_data -> [store_to_database, archive_documents]
```

**Taches:**
- `scan_documents`: Detecte nouveaux documents dans MinIO
- `download_documents`: Telecharge localement pour traitement
- `extract_text`: Extraction OCR via module nlp-ocr
- `validate_data`: Validation via module validation
- `store_to_database`: Insertion MongoDB Atlas
- `archive_documents`: Archivage dans bucket dedie

### 2. monitoring_metrics.py

Surveillance et collecte de metriques systeme.

**Schedule:** Toutes les heures

**Flux:**
```
[collect_stats, check_storage] -> analyze_performance -> generate_health_report
```

**Taches:**
- `collect_stats`: Statistiques de traitement depuis MongoDB Atlas
- `check_storage`: Utilisation stockage MinIO
- `analyze_performance`: Analyse des metriques
- `generate_health_report`: Rapport de sante global

**Alertes:**
- Taux d'erreur > 5%
- Utilisation stockage > 10 GB
- Absence de traitement recent

### 3. maintenance_cleanup.py

Nettoyage et optimisation du systeme.

**Schedule:** Tous les jours a 2h du matin

**Flux:**
```
[cleanup_old_docs, cleanup_failed_docs, cleanup_orphans] -> vacuum_db -> generate_cleanup_report
```

**Taches:**
- `cleanup_old_docs`: Suppression documents > 30 jours
- `cleanup_failed_docs`: Archivage documents en erreur > 7 jours
- `cleanup_orphans`: Suppression fichiers orphelins MinIO
- `vacuum_db`: Optimisation MongoDB Atlas (auto-geree)
- `generate_cleanup_report`: Rapport des operations

## Configuration

### Fichier config.py

Centralise tous les parametres des DAGs:

- **MINIO_CONFIG**: Configuration Data Lake
- **POSTGRES_CONFIG**: Configuration base de donnees
- **RETENTION_POLICY**: Politiques de retention
- **MONITORING_THRESHOLDS**: Seuils d'alerte
- **SCHEDULES**: Planification des DAGs

### Modification des parametres

Pour modifier un parametre, editer `config.py` et relancer le scheduler:

```bash
docker-compose restart airflow-scheduler
```

## Utilisation

### Acces a l'interface Airflow

```
URL: http://localhost:8080
User: admin
Password: admin
```

### Activer/Desactiver un DAG

Dans l'interface web, utiliser le toggle a gauche du nom du DAG.

### Declencher manuellement un DAG

1. Cliquer sur le nom du DAG
2. Cliquer sur le bouton "Trigger DAG" en haut a droite
3. Optionnel: Ajouter une configuration JSON

### Consulter les logs

**Via l'interface:**
1. Cliquer sur le DAG
2. Cliquer sur l'execution (run)
3. Cliquer sur la tache
4. Onglet "Log"

**Via ligne de commande:**
```bash
docker-compose logs -f airflow-scheduler
docker-compose logs -f airflow-webserver
```

### Monitoring des performances

Le DAG `monitoring_metrics` genere automatiquement des rapports de sante. Pour consulter:

```bash
# Se connecter au container
docker exec -it hackathon_airflow_webserver bash

# Consulter les XComs (resultats partages)
airflow tasks test monitoring_metrics generate_health_report 2026-03-16
```

## Integration avec les autres modules

### Module NLP-OCR (Juba)

Montes dans `/opt/airflow/nlp-ocr`

**Utilisation dans un DAG:**
```python
import sys
sys.path.insert(0, '/opt/airflow/nlp-ocr')
from scripts.tesseract_ocr import perform_ocr

text = perform_ocr(image_path)
```

### Module Validation (Maria)

Montes dans `/opt/airflow/validation`

**Utilisation dans un DAG:**
```python
import sys
sys.path.insert(0, '/opt/airflow/validation')
from scripts.data_validator import validate_data

result = validate_data(data)
```

## Bonnes pratiques

### Developpement de nouveaux DAGs

1. Creer le fichier dans `orchestration/airflow/dags/`
2. Utiliser la configuration centralisee (`config.py`)
3. Ajouter des logs explicites avec `logging.info()`
4. Utiliser XCom pour partager des donnees entre taches
5. Gerer les erreurs avec try/except et logs

### Structure recommandee d'un DAG

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import timedelta
import logging

# Import config centralisee
from config import DEFAULT_DAG_ARGS, get_minio_client

default_args = {
    **DEFAULT_DAG_ARGS,
    'start_date': days_ago(1)
}

dag = DAG(
    'nom_du_dag',
    default_args=default_args,
    description='Description claire',
    schedule_interval='*/30 * * * *',
    catchup=False,
    tags=['categorie']
)

def ma_fonction(**context):
    """Documentation de la fonction"""
    logging.info("Debut de la tache")
    # Implementation
    logging.info("Fin de la tache")
    return resultat

task = PythonOperator(
    task_id='ma_tache',
    python_callable=ma_fonction,
    provide_context=True,
    dag=dag
)
```

### Gestion des erreurs

```python
def fonction_robuste(**context):
    try:
        # Logique metier
        resultat = traiter_donnees()
        logging.info(f"Traitement reussi: {resultat}")
        return resultat
    except Exception as e:
        logging.error(f"Erreur lors du traitement: {e}")
        # Option: raise pour que Airflow retente
        raise
```

### Communication entre taches

```python
def tache_1(**context):
    donnees = {"key": "value"}
    context['task_instance'].xcom_push(key='mon_resultat', value=donnees)

def tache_2(**context):
    donnees = context['task_instance'].xcom_pull(
        task_ids='tache_1',
        key='mon_resultat'
    )
```

## Debuggage

### DAG non visible dans l'interface

1. Verifier la syntaxe Python: `python dags/mon_dag.py`
2. Consulter les logs du scheduler: `docker-compose logs airflow-scheduler`
3. Verifier l'absence d'erreurs d'import

### Tache qui echoue systematiquement

1. Consulter les logs detailles dans l'interface
2. Tester la fonction isolement:
   ```bash
   docker exec -it hackathon_airflow_webserver python
   >>> from dags.mon_dag import ma_fonction
   >>> ma_fonction()
   ```

### Performance degradee

1. Consulter le DAG `monitoring_metrics`
2. Verifier la charge du scheduler: `docker stats hackathon_airflow_scheduler`
3. Ajuster le parallelisme dans la configuration Airflow si necessaire
4. Note: LocalExecutor execute les taches localement (pas de scaling horizontal)

## Maintenance

### Backup de la base de metadonnees Airflow

```bash
docker exec hackathon_postgres pg_dump -U hackathon_user hackathon_db > backup.sql
```

### Nettoyage manuel de la base Airflow

```bash
docker exec -it hackathon_airflow_webserver bash
airflow db clean --clean-before-timestamp "2026-03-01"
```

### Reinitialisation complete

```bash
cd orchestration
docker-compose down -v
docker-compose up -d
```

## Metriques importantes

### Indicateurs de sante

- Taux de reussite des DAGs: > 95%
- Temps moyen de traitement par document: < 5 minutes
- Taux d'erreur global: < 5%
- Disponibilite du systeme: > 99%

### Capacite

- Documents traites par heure: Configuration actuelle ~240/h (15 min interval)
- Stockage max recommande: 50 GB
- Retention par defaut: 30 jours

## Troubleshooting

### Erreur: "Executor reports task instance finished (failed) although the task says its queued"

Solution: Redemarrer le scheduler
```bash
docker-compose restart airflow-scheduler
```

### Erreur: "Missing dependencies"

Solution: Installer la dependance dans le container scheduler
```bash
docker exec -it hackathon_airflow_scheduler pip install nom_package
```
Note: Les dépendances doivent être ajoutées à `orchestration/requirements.txt` pour être persistantes

### Tasks bloquees en "running"

Solution: Clear l'etat de la tache dans l'interface ou via CLI
```bash
airflow tasks clear nom_dag -t nom_tache -s 2026-03-16
```

## Contact

Pour toute question sur l'orchestration:
- Lead Pipeline & PM: Gills
- Repository: https://github.com/JoeDalton318/Hackathon-Project-2026
