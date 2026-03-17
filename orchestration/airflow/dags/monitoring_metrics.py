"""
DAG de monitoring et metriques
Collecte et agrege les statistiques de traitement des documents
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
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
    'monitoring_metrics',
    default_args=default_args,
    description='Collecte des metriques et statistiques du pipeline',
    schedule_interval='0 * * * *',  # Execution toutes les heures
    catchup=False,
    tags=['monitoring', 'metrics'],
)


def collect_processing_stats(**context):
    """
    Collecte les statistiques de traitement depuis MongoDB Atlas
    
    Returns:
        dict: Statistiques agregees
    """
    from pymongo import MongoClient
    from datetime import datetime, timedelta
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    # Nombre total de documents traites
    total_processed = collection.count_documents({'status': 'PROCESSED'})
    
    # Documents traites dans la derniere heure
    one_hour_ago = datetime.now() - timedelta(hours=1)
    recent_processed = collection.count_documents({
        'status': 'PROCESSED',
        'upload_date': {'$gt': one_hour_ago}
    })
    
    # Nombre de documents en erreur
    total_errors = collection.count_documents({'status': 'ERROR'})
    
    client.close()
    
    stats = {
        'total_processed': total_processed,
        'recent_processed': recent_processed,
        'total_errors': total_errors,
        'error_rate': (total_errors / max(total_processed, 1)) * 100
    }
    
    logging.info(f"Statistiques collectees: {stats}")
    
    context['task_instance'].xcom_push(key='stats', value=stats)
    return stats


def check_storage_capacity(**context):
    """
    Verifie la capacite de stockage disponible dans MinIO
    
    Returns:
        dict: Informations sur l'utilisation du stockage
    """
    from minio import Minio
    
    client = Minio(
        "minio:9000",
        access_key="minio_admin",
        secret_key="minio_admin_pass",
        secure=False
    )
    
    buckets_info = []
    
    # Liste tous les buckets
    buckets = client.list_buckets()
    for bucket in buckets:
        # Compte les objets dans chaque bucket
        objects = list(client.list_objects(bucket.name, recursive=True))
        total_size = sum(obj.size for obj in objects)
        
        buckets_info.append({
            'bucket_name': bucket.name,
            'object_count': len(objects),
            'total_size_mb': total_size / (1024 * 1024)
        })
        
        logging.info(f"Bucket {bucket.name}: {len(objects)} objets, {total_size / (1024 * 1024):.2f} MB")
    
    context['task_instance'].xcom_push(key='storage_info', value=buckets_info)
    return buckets_info


def analyze_pipeline_performance(**context):
    """
    Analyse les performances du pipeline via les metadonnees Airflow
    
    Returns:
        dict: Metriques de performance
    """
    # Recuperation des statistiques des taches precedentes
    stats = context['task_instance'].xcom_pull(
        task_ids='collect_stats',
        key='stats'
    )
    
    storage_info = context['task_instance'].xcom_pull(
        task_ids='check_storage',
        key='storage_info'
    )
    
    # Calcul des metriques de performance
    performance_metrics = {
        'processing_rate': stats.get('recent_processed', 0),
        'error_rate': stats.get('error_rate', 0),
        'storage_usage_mb': sum(b['total_size_mb'] for b in storage_info),
        'total_objects': sum(b['object_count'] for b in storage_info)
    }
    
    # Alertes si necessaire
    if performance_metrics['error_rate'] > 5.0:
        logging.warning(f"Taux d'erreur eleve: {performance_metrics['error_rate']:.2f}%")
    
    if performance_metrics['storage_usage_mb'] > 10000:  # 10 GB
        logging.warning(f"Utilisation stockage elevee: {performance_metrics['storage_usage_mb']:.2f} MB")
    
    logging.info(f"Metriques de performance: {performance_metrics}")
    return performance_metrics


def generate_health_report(**context):
    """
    Generate un rapport de sante global du systeme
    
    Returns:
        dict: Rapport de sante complet
    """
    import json
    from datetime import datetime
    
    stats = context['task_instance'].xcom_pull(task_ids='collect_stats', key='stats')
    storage_info = context['task_instance'].xcom_pull(task_ids='check_storage', key='storage_info')
    
    health_report = {
        'timestamp': datetime.now().isoformat(),
        'system_status': 'HEALTHY' if stats.get('error_rate', 0) < 5.0 else 'DEGRADED',
        'statistics': stats,
        'storage': storage_info,
        'recommendations': []
    }
    
    # Ajout de recommendations basees sur les metriques
    if stats.get('error_rate', 0) > 5.0:
        health_report['recommendations'].append(
            "Taux d'erreur eleve - verifier les logs du pipeline de traitement"
        )
    
    if stats.get('recent_processed', 0) == 0:
        health_report['recommendations'].append(
            "Aucun document traite recemment - verifier l'ingestion des donnees"
        )
    
    logging.info(f"Rapport de sante genere: {json.dumps(health_report, indent=2)}")
    
    # TODO: Stocker le rapport dans une table dediee pour historique
    
    return health_report


# Definition des taches
collect_stats_task = PythonOperator(
    task_id='collect_stats',
    python_callable=collect_processing_stats,
    provide_context=True,
    dag=dag,
)

check_storage_task = PythonOperator(
    task_id='check_storage',
    python_callable=check_storage_capacity,
    provide_context=True,
    dag=dag,
)

analyze_performance_task = PythonOperator(
    task_id='analyze_performance',
    python_callable=analyze_pipeline_performance,
    provide_context=True,
    dag=dag,
)

generate_report_task = PythonOperator(
    task_id='generate_health_report',
    python_callable=generate_health_report,
    provide_context=True,
    dag=dag,
)

# Flux d'execution
# Les collectes peuvent s'executer en parallele, puis analyse et rapport
[collect_stats_task, check_storage_task] >> analyze_performance_task >> generate_report_task
