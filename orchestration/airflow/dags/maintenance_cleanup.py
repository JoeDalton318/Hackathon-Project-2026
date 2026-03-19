"""
DAG de maintenance et nettoyage
Gere le nettoyage des anciennes donnees et l'optimisation des ressources
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta, datetime
import logging

default_args = {
    'owner': 'gills',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'maintenance_cleanup',
    default_args=default_args,
    description='Nettoyage et maintenance du systeme',
    schedule_interval='0 2 * * *',  # Execution tous les jours a 2h du matin
    catchup=False,
    tags=['maintenance', 'cleanup'],
)


def cleanup_old_documents(**context):
    """
    Supprime les documents archives de plus de 30 jours
    
    Returns:
        int: Nombre de documents supprimes
    """
    from pymongo import MongoClient
    from datetime import datetime, timedelta
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    retention_days = 30
    
    client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    # Calcul de la date de retention
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    # Suppression des documents anciens
    result = collection.delete_many({
        'upload_date': {'$lt': cutoff_date},
        'status': 'PROCESSED'
    })
    
    deleted_count = result.deleted_count
    client.close()
    
    logging.info(f"Documents supprimes (> {retention_days} jours): {deleted_count}")
    return deleted_count


def cleanup_failed_documents(**context):
    """
    Archive ou supprime les documents en erreur apres plusieurs tentatives
    
    Returns:
        int: Nombre de documents nettoyes
    """
    from pymongo import MongoClient
    from datetime import datetime, timedelta
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    max_retention_days = 7
    
    client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    # Calcul de la date de retention
    cutoff_date = datetime.now() - timedelta(days=max_retention_days)
    
    # Marquage des documents en erreur comme archives
    result = collection.update_many(
        {
            'status': 'ERROR',
            'upload_date': {'$lt': cutoff_date}
        },
        {'$set': {'status': 'ARCHIVED_ERROR'}}
    )
    
    archived_count = result.modified_count
    client.close()
    
    logging.info(f"Documents en erreur archives (> {max_retention_days} jours): {archived_count}")
    return archived_count


def cleanup_minio_orphans(**context):
    """
    Supprime les fichiers orphelins dans MinIO
    Fichiers presents dans MinIO mais absents de la base de donnees
    
    Returns:
        int: Nombre de fichiers orphelins supprimes
    """
    from minio import Minio
    from pymongo import MongoClient
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    client = Minio(
        "minio:9000",
        access_key="minio_admin",
        secret_key="minio_admin_pass",
        secure=False
    )
    
    # Recuperation de tous les noms de fichiers en base
    mongo_client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = mongo_client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    db_filenames = set(doc['filename'] for doc in collection.find({}, {'filename': 1}))
    mongo_client.close()
    
    deleted_count = 0
    
    # Verification du bucket processed
    if client.bucket_exists("documents-processed"):
        objects = client.list_objects("documents-processed", recursive=True)
        
        for obj in objects:
            filename = obj.object_name.split('/')[-1]
            
            # Si le fichier n'est pas reference en base, suppression
            if filename not in db_filenames:
                client.remove_object("documents-processed", obj.object_name)
                deleted_count += 1
                logging.info(f"Fichier orphelin supprime: {obj.object_name}")
    
    logging.info(f"Total fichiers orphelins supprimes: {deleted_count}")
    return deleted_count


def vacuum_database(**context):
    """
    Execute compact sur MongoDB Atlas pour optimiser les performances
    Note: Compact n'est pas disponible sur MongoDB Atlas (auto-géré)
    Cette fonction log simplement une confirmation
    
    Returns:
        bool: Succes de l'operation
    """
    from pymongo import MongoClient
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    # MongoDB Atlas gère automatiquement l'optimisation
    # Pas besoin de compact manuel
    logging.info("MongoDB Atlas: Optimisation auto-gérée, pas de compact nécessaire")
    return True


def generate_cleanup_report(**context):
    """
    Generate un rapport recapitulatif des operations de nettoyage
    
    Returns:
        dict: Rapport de nettoyage
    """
    import json
    
    # Recuperation des resultats des taches precedentes
    old_docs_deleted = context['task_instance'].xcom_pull(task_ids='cleanup_old_docs')
    failed_docs_archived = context['task_instance'].xcom_pull(task_ids='cleanup_failed_docs')
    orphans_deleted = context['task_instance'].xcom_pull(task_ids='cleanup_orphans')
    vacuum_success = context['task_instance'].xcom_pull(task_ids='vacuum_db')
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'operations': {
            'old_documents_deleted': old_docs_deleted or 0,
            'failed_documents_archived': failed_docs_archived or 0,
            'orphan_files_deleted': orphans_deleted or 0,
            'database_vacuum': 'SUCCESS' if vacuum_success else 'FAILED'
        },
        'total_space_recovered': 'estimated based on deletions'
    }
    
    logging.info(f"Rapport de nettoyage: {json.dumps(report, indent=2)}")
    
    # TODO: Stocker le rapport dans une table d'audit pour historique
    
    return report


# Definition des taches
cleanup_old_task = PythonOperator(
    task_id='cleanup_old_docs',
    python_callable=cleanup_old_documents,
    provide_context=True,
    dag=dag,
)

cleanup_failed_task = PythonOperator(
    task_id='cleanup_failed_docs',
    python_callable=cleanup_failed_documents,
    provide_context=True,
    dag=dag,
)

cleanup_orphans_task = PythonOperator(
    task_id='cleanup_orphans',
    python_callable=cleanup_minio_orphans,
    provide_context=True,
    dag=dag,
)

vacuum_task = PythonOperator(
    task_id='vacuum_db',
    python_callable=vacuum_database,
    provide_context=True,
    dag=dag,
)

report_task = PythonOperator(
    task_id='generate_cleanup_report',
    python_callable=generate_cleanup_report,
    provide_context=True,
    dag=dag,
)

# Flux d'execution
# Les nettoyages peuvent s'executer en parallele, puis VACUUM, puis rapport
[cleanup_old_task, cleanup_failed_task, cleanup_orphans_task] >> vacuum_task >> report_task
