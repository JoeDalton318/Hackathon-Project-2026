"""
DAG de traitement des documents
Ce pipeline orchestre l'ingestion, l'extraction OCR et la validation des documents
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import logging

# Configuration des parametres par defaut du DAG
default_args = {
    'owner': 'gills',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Definition du DAG principal
dag = DAG(
    'document_processing_pipeline',
    default_args=default_args,
    description='Pipeline complet de traitement de documents avec OCR et validation',
    schedule_interval='*/15 * * * *',  # Execution toutes les 15 minutes
    catchup=False,
    tags=['documents', 'ocr', 'production'],
)


def scan_new_documents(**context):
    """
    Detecte les nouveaux documents dans le bucket MinIO
    
    Returns:
        list: Liste des chemins des documents a traiter
    """
    from minio import Minio
    
    # Configuration du client MinIO
    client = Minio(
        "minio:9000",
        access_key="minio_admin",
        secret_key="minio_admin_pass",
        secure=False
    )
    
    bucket_name = "documents-raw"
    
    # Verification de l'existence du bucket
    if not client.bucket_exists(bucket_name):
        logging.info(f"Creation du bucket {bucket_name}")
        client.make_bucket(bucket_name)
        return []
    
    # Liste des objets non traites
    # TODO: Implementer la logique de filtrage des documents deja traites
    objects = client.list_objects(bucket_name, recursive=True)
    document_paths = [obj.object_name for obj in objects]
    
    logging.info(f"Nombre de documents detectes: {len(document_paths)}")
    
    # Passage des chemins au contexte pour les taches suivantes
    context['task_instance'].xcom_push(key='document_paths', value=document_paths)
    
    return document_paths


def download_documents(**context):
    """
    Telecharge les documents depuis MinIO vers le systeme local
    
    Returns:
        list: Liste des chemins locaux des documents telecharges
    """
    from minio import Minio
    import os
    
    # Recuperation des chemins depuis la tache precedente
    document_paths = context['task_instance'].xcom_pull(
        task_ids='scan_documents', 
        key='document_paths'
    )
    
    if not document_paths:
        logging.warning("Aucun document a telecharger")
        return []
    
    client = Minio(
        "minio:9000",
        access_key="minio_admin",
        secret_key="minio_admin_pass",
        secure=False
    )
    
    local_dir = "/tmp/documents"
    os.makedirs(local_dir, exist_ok=True)
    
    local_paths = []
    for doc_path in document_paths:
        local_path = os.path.join(local_dir, doc_path.replace('/', '_'))
        client.fget_object("documents-raw", doc_path, local_path)
        local_paths.append(local_path)
        logging.info(f"Document telecharge: {doc_path} -> {local_path}")
    
    context['task_instance'].xcom_push(key='local_paths', value=local_paths)
    return local_paths


def extract_text_ocr(**context):
    """
    Extrait le texte des documents via OCR
    Utilise le module OCR du dossier nlp-ocr
    
    Returns:
        list: Liste des textes extraits avec metadata
    """
    import sys
    sys.path.insert(0, '/opt/airflow/nlp-ocr')
    
    # Import du module OCR developpe par Juba
    # TODO: Remplacer par l'implementation reelle une fois disponible
    
    local_paths = context['task_instance'].xcom_pull(
        task_ids='download_documents',
        key='local_paths'
    )
    
    if not local_paths:
        logging.warning("Aucun document a traiter")
        return []
    
    extracted_data = []
    for doc_path in local_paths:
        # Simulation de l'extraction OCR
        # TODO: Appeler tesseract_ocr.perform_ocr(doc_path)
        extracted_text = f"Texte extrait de {doc_path}"
        
        extracted_data.append({
            'source_path': doc_path,
            'extracted_text': extracted_text,
            'confidence_score': 0.95,  # Score de confiance OCR
        })
        
        logging.info(f"OCR complete pour: {doc_path}")
    
    context['task_instance'].xcom_push(key='extracted_data', value=extracted_data)
    return extracted_data


def validate_extracted_data(**context):
    """
    Valide les donnees extraites via OCR
    Utilise le module de validation du dossier validation
    
    Returns:
        list: Donnees validees prets pour insertion en base
    """
    import sys
    sys.path.insert(0, '/opt/airflow/validation')
    
    # Import du module de validation developpe par Maria
    # TODO: Remplacer par l'implementation reelle une fois disponible
    
    extracted_data = context['task_instance'].xcom_pull(
        task_ids='extract_text',
        key='extracted_data'
    )
    
    if not extracted_data:
        logging.warning("Aucune donnee a valider")
        return []
    
    validated_data = []
    for data in extracted_data:
        # Simulation de la validation
        # TODO: Appeler data_validator.validate_data(data)
        
        is_valid = len(data.get('extracted_text', '')) > 0
        
        if is_valid:
            validated_data.append({
                **data,
                'validation_status': 'VALID',
                'validation_errors': []
            })
            logging.info(f"Validation reussie pour: {data['source_path']}")
        else:
            logging.error(f"Validation echouee pour: {data['source_path']}")
    
    context['task_instance'].xcom_push(key='validated_data', value=validated_data)
    return validated_data


def store_to_database(**context):
    """
    Stocke les donnees validees dans MongoDB Atlas
    
    Returns:
        int: Nombre de documents inseres
    """
    from pymongo import MongoClient
    from datetime import datetime
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    validated_data = context['task_instance'].xcom_pull(
        task_ids='validate_data',
        key='validated_data'
    )
    
    if not validated_data:
        logging.warning("Aucune donnee a stocker")
        return 0
    
    # Connexion a MongoDB Atlas
    client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    inserted_count = 0
    for data in validated_data:
        try:
            # Insertion dans la collection documents
            document = {
                'filename': data['source_path'].split('/')[-1],
                'content': data['extracted_text'],
                'metadata': {
                    'confidence': data['confidence_score'],
                    'source_path': data['source_path']
                },
                'status': 'PROCESSED',
                'upload_date': datetime.now()
            }
            
            collection.insert_one(document)
            inserted_count += 1
            logging.info(f"Document insere: {data['source_path']}")
        except Exception as e:
            logging.error(f"Erreur insertion: {e}")
            continue
    
    client.close()
    
    logging.info(f"Nombre total de documents inseres: {inserted_count}")
    return inserted_count


def archive_processed_documents(**context):
    """
    Archive les documents traites dans un bucket separe
    Deplace les fichiers de documents-raw vers documents-processed
    
    Returns:
        int: Nombre de documents archives
    """
    from minio import Minio
    
    document_paths = context['task_instance'].xcom_pull(
        task_ids='scan_documents',
        key='document_paths'
    )
    
    if not document_paths:
        return 0
    
    client = Minio(
        "minio:9000",
        access_key="minio_admin",
        secret_key="minio_admin_pass",
        secure=False
    )
    
    # Creation du bucket d'archives si necessaire
    if not client.bucket_exists("documents-processed"):
        client.make_bucket("documents-processed")
    
    archived_count = 0
    for doc_path in document_paths:
        try:
            # Copie vers le bucket d'archives
            client.copy_object(
                "documents-processed",
                doc_path,
                f"/documents-raw/{doc_path}"
            )
            
            # Suppression du bucket source
            client.remove_object("documents-raw", doc_path)
            
            archived_count += 1
            logging.info(f"Document archive: {doc_path}")
        except Exception as e:
            logging.error(f"Erreur archivage de {doc_path}: {e}")
    
    logging.info(f"Nombre total de documents archives: {archived_count}")
    return archived_count


def auto_fill_business_applications(**context):
    """
    ROLE GILLS - Lead Pipeline & PM
    
    Remplissage automatique des applications métiers internes (CRM, Outil conformité)
    Envoie les données structurées validées vers l'API Backend
    qui alimente les formulaires des frontends développés par Soufiane
    
    Cette tâche fait le pont entre le pipeline Airflow et les applications métiers.
    
    Returns:
        dict: Statistiques d'envoi aux applications métiers
    """
    import requests
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG, BACKEND_API_CONFIG
    from pymongo import MongoClient
    
    # Récupération des données validées depuis MongoDB
    client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    # Récupérer les documents récemment traités (dernière heure)
    from datetime import datetime, timedelta
    recent_docs = collection.find({
        'status': 'PROCESSED',
        'upload_date': {'$gte': datetime.now() - timedelta(hours=1)},
        'auto_filled': {'$ne': True}  # Pas encore envoyés aux apps métiers
    })
    
    stats = {
        'crm_sent': 0,
        'conformity_sent': 0,
        'total_processed': 0,
        'errors': 0
    }
    
    # URL de l'API Backend développée par Samuel
    backend_api_url = BACKEND_API_CONFIG['base_url']
    
    for doc in recent_docs:
        try:
            # Préparer les données structurées pour les applications métiers
            business_payload = {
                'document_id': str(doc['_id']),
                'filename': doc['filename'],
                'extracted_data': doc.get('metadata', {}),
                'timestamp': doc['upload_date'].isoformat(),
                'status': doc['status']
            }
            
            # Envoi vers l'endpoint CRM
            try:
                crm_url = backend_api_url + BACKEND_API_CONFIG['endpoints']['crm_autofill']
                crm_response = requests.post(
                    crm_url,
                    json=business_payload,
                    timeout=BACKEND_API_CONFIG['timeout']
                )
                if crm_response.status_code == 200:
                    stats['crm_sent'] += 1
                    logging.info(f"CRM rempli pour document {doc['filename']}")
            except Exception as e:
                logging.error(f"Erreur envoi CRM: {e}")
                stats['errors'] += 1
            
            # Envoi vers l'endpoint Outil de Conformité
            try:
                conformity_url = backend_api_url + BACKEND_API_CONFIG['endpoints']['conformity_autofill']
                conformity_response = requests.post(
                    conformity_url,
                    json=business_payload,
                    timeout=BACKEND_API_CONFIG['timeout']
                )
                if conformity_response.status_code == 200:
                    stats['conformity_sent'] += 1
                    logging.info(f"Conformité remplie pour document {doc['filename']}")
            except Exception as e:
                logging.error(f"Erreur envoi Conformité: {e}")
                stats['errors'] += 1
            
            # Marquer le document comme envoyé aux apps métiers
            collection.update_one(
                {'_id': doc['_id']},
                {'$set': {'auto_filled': True, 'auto_fill_date': datetime.now()}}
            )
            
            stats['total_processed'] += 1
            
        except Exception as e:
            logging.error(f"Erreur traitement document {doc.get('filename', 'unknown')}: {e}")
            stats['errors'] += 1
    
    client.close()
    
    logging.info(f"Auto-remplissage terminé - Stats: {stats}")
    
    # Passage des stats au contexte pour monitoring
    context['task_instance'].xcom_push(key='autofill_stats', value=stats)
    
    return stats


# Definition des taches du pipeline
scan_task = PythonOperator(
    task_id='scan_documents',
    python_callable=scan_new_documents,
    provide_context=True,
    dag=dag,
)

download_task = PythonOperator(
    task_id='download_documents',
    python_callable=download_documents,
    provide_context=True,
    dag=dag,
)

ocr_task = PythonOperator(
    task_id='extract_text',
    python_callable=extract_text_ocr,
    provide_context=True,
    dag=dag,
)

validation_task = PythonOperator(
    task_id='validate_data',
    python_callable=validate_extracted_data,
    provide_context=True,
    dag=dag,
)

storage_task = PythonOperator(
    task_id='store_to_database',
    python_callable=store_to_database,
    provide_context=True,
    dag=dag,
)

archive_task = PythonOperator(
    task_id='archive_documents',
    python_callable=archive_processed_documents,
    provide_context=True,
    dag=dag,
)

autofill_task = PythonOperator(
    task_id='auto_fill_business_apps',
    python_callable=auto_fill_business_applications,
    provide_context=True,
    dag=dag,
)

# Definition du flux d'execution du pipeline
# scan -> download -> ocr -> validate -> store -> [archive, autofill]
# L'auto-remplissage des apps métiers se fait après le stockage en BDD
scan_task >> download_task >> ocr_task >> validation_task >> storage_task >> [archive_task, autofill_task]
