"""
Configuration centralisee pour tous les DAGs Airflow
Ce module contient les parametres partages entre les differents pipelines.
Toutes les variables sont chargees depuis le fichier .env a la racine du projet.
"""
import os

# Configuration MinIO Data Lake - Variables d'environnement alignees avec le Backend
# ARCHITECTURE: 1 bucket unique avec prefixes (raw/, clean/, curated/)
MINIO_CONFIG = {
    'endpoint': os.getenv('MINIO_ENDPOINT', 'minio:9000'),
    'access_key': os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
    'secret_key': os.getenv('MINIO_SECRET_KEY', 'minioadmin123'),
    'secure': os.getenv('MINIO_SECURE', 'false').lower() == 'true',
    'bucket': os.getenv('MINIO_BUCKET', 'datalake'),  # Bucket unique
    'prefixes': {
        'raw': os.getenv('MINIO_RAW_PREFIX', 'raw/'),
        'clean': os.getenv('MINIO_CLEAN_PREFIX', 'clean/'),
        'curated': os.getenv('MINIO_CURATED_PREFIX', 'curated/')
    }
}

# Configuration MongoDB Atlas (Cloud) - Alignee avec le Backend
MONGODB_CONFIG = {
    'connection_string': os.getenv('MONGO_URL'),
    'database': os.getenv('MONGO_DB', 'hackathon')
}

# Configuration API Backend - Developpee par Samuel (Lead API & Backend)
# Utilisee pour le callback apres traitement pipeline
BACKEND_API_CONFIG = {
    'base_url': os.getenv('BACKEND_API_URL', 'http://backend:8000'),
    'internal_secret': os.getenv('INTERNAL_API_SECRET'),
    'endpoints': {
        'callback': '/api/internal/pipeline/result',
        'crm_autofill': '/api/crm/auto-fill',
        'conformity_autofill': '/api/conformity/auto-fill',
        'health': '/health'
    },
    'timeout': int(os.getenv('API_TIMEOUT', 10))
}

# Parametres de retention des donnees
RETENTION_POLICY = {
    'processed_documents_days': 30,
    'failed_documents_days': 7,
    'archive_after_days': 90
}

# Seuils d'alerte pour le monitoring
MONITORING_THRESHOLDS = {
    'error_rate_percent': 5.0,
    'storage_limit_mb': 10000,
    'processing_time_seconds': 300,
    'min_hourly_processed': 10
}

# Configuration des chemins pour les modules Python
PYTHON_MODULES = {
    'ocr_path': '/opt/airflow/nlp-ocr',
    'validation_path': '/opt/airflow/validation',
    'temp_dir': '/tmp/documents'
}

# Parametres DAG par defaut
DEFAULT_DAG_ARGS = {
    'owner': 'gills',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay_minutes': 5
}

# Configuration des schedules
SCHEDULES = {
    'processing_pipeline': None,             # Event-driven (declenche par Backend API)
    'monitoring': '0 * * * *',               # Toutes les heures
    'maintenance': '0 2 * * *'               # Tous les jours a 2h
}

# Tags pour categorisation des DAGs
DAG_TAGS = {
    'production': ['production', 'critical'],
    'monitoring': ['monitoring', 'metrics'],
    'maintenance': ['maintenance', 'cleanup']
}


def get_minio_client():
    """
    Factory pour creer un client MinIO configure
    
    Returns:
        Minio: Instance de client MinIO
    """
    from minio import Minio
    
    return Minio(
        MINIO_CONFIG['endpoint'],
        access_key=MINIO_CONFIG['access_key'],
        secret_key=MINIO_CONFIG['secret_key'],
        secure=MINIO_CONFIG['secure']
    )


def get_mongodb_client():
    """
    Factory pour creer un client MongoDB configure
    
    Returns:
        MongoClient: Instance de client MongoDB
    """
    from pymongo import MongoClient
    
    return MongoClient(MONGODB_CONFIG['connection_string'])


def get_mongodb_database():
    """
    Factory pour obtenir la base de donnees MongoDB
    
    Returns:
        Database: Instance de la base de donnees MongoDB
    """
    client = get_mongodb_client()
    return client[MONGODB_CONFIG['database']]


def ensure_buckets_exist():
    """
    Verifie et cree les buckets MinIO necessaires
    Utilise par les DAGs au demarrage
    """
    client = get_minio_client()
    
    for bucket_name in MINIO_CONFIG['buckets'].values():
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"Bucket cree: {bucket_name}")


def validate_config():
    """
    Valide que toutes les configurations necessaires sont presentes
    
    Returns:
        bool: True si la configuration est valide
    """
    required_configs = [
        MINIO_CONFIG,
        MONGODB_CONFIG,
        RETENTION_POLICY,
        MONITORING_THRESHOLDS
    ]
    
    for config in required_configs:
        if not config:
            return False
    
    return True
