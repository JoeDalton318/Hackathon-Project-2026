"""
DAG de traitement des documents - Mode Event-Driven
Ce pipeline est declenche par le Backend API lors de chaque upload de document.
Il orchestre l'extraction OCR, la validation et le callback vers le Backend.
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import logging

# Configuration des parametres par defaut du DAG
default_args = {
    'owner': 'orchestration',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

# Definition du DAG principal - Event-driven (declenche par API Backend)
dag = DAG(
    'doc_pipeline',
    default_args=default_args,
    description='Pipeline de traitement event-driven declenche par upload document',
    schedule_interval=None,  # Declenche manuellement par le Backend
    catchup=False,
    tags=['documents', 'ocr', 'production', 'event-driven'],
)


def get_document_info(**context):
    """
    Recupere les informations du document a traiter depuis les parametres du DAG.
    Le Backend API passe le document_id (UUID) lors du declenchement.
    
    Returns:
        dict: Informations du document (document_id, minio_path, filename)
    """
    from pymongo import MongoClient
    import sys
    import os
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MONGODB_CONFIG
    
    # Recuperation du document_id passe par le Backend lors du trigger
    dag_run = context.get('dag_run')
    if not dag_run or not dag_run.conf:
        raise ValueError("DAG declenche sans configuration. Le Backend doit passer 'document_id'.")
    
    document_id = dag_run.conf.get('document_id')
    if not document_id:
        raise ValueError("Le parametre 'document_id' est obligatoire.")
    
    logging.info(f"Traitement du document: {document_id}")
    
    # Connexion MongoDB pour recuperer les metadata du document
    client = MongoClient(MONGODB_CONFIG['connection_string'])
    db = client[MONGODB_CONFIG['database']]
    collection = db['documents']
    
    # IMPORTANT: Le Backend utilise document_id comme UUID string, pas ObjectId
    doc = collection.find_one({'document_id': document_id})
    
    if not doc:
        client.close()
        raise ValueError(f"Document {document_id} introuvable dans MongoDB")
    
    document_info = {
        'document_id': document_id,
        'minio_path': doc.get('minio_path', ''),
        'filename': doc.get('original_filename', 'unknown'),
        'mime_type': doc.get('mime_type', 'application/pdf')
    }
    
    client.close()
    
    logging.info(f"Document info: {document_info}")
    context['task_instance'].xcom_push(key='document_info', value=document_info)
    
    return document_info


def download_document(**context):
    """
    Telecharge le document depuis MinIO vers le systeme local pour traitement.
    
    Returns:
        str: Chemin local du document telecharge
    """
    from minio import Minio
    import os
    import sys
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MINIO_CONFIG
    
    # Recuperation des infos document
    document_info = context['task_instance'].xcom_pull(
        task_ids='get_document',
        key='document_info'
    )
    
    if not document_info or not document_info.get('minio_path'):
        raise ValueError("Informations document manquantes")
    
    # Connexion MinIO
    client = Minio(
        MINIO_CONFIG['endpoint'],
        access_key=MINIO_CONFIG['access_key'],
        secret_key=MINIO_CONFIG['secret_key'],
        secure=MINIO_CONFIG['secure']
    )
    
    # Preparation du chemin local
    local_dir = "/tmp/documents"
    os.makedirs(local_dir, exist_ok=True)
    
    document_id = document_info['document_id']
    filename = document_info['filename']
    local_path = os.path.join(local_dir, f"{document_id}_{filename}")
    
    # Telechargement depuis datalake/raw/
    bucket = MINIO_CONFIG['bucket']
    raw_prefix = MINIO_CONFIG['prefixes']['raw']
    minio_path = document_info['minio_path']
    
    # Le minio_path stocké dans MongoDB contient déjà le préfixe raw/
    client.fget_object(bucket, minio_path, local_path)
    logging.info(f"Document telecharge: {bucket}/{minio_path} -> {local_path}")
    
    context['task_instance'].xcom_push(key='local_path', value=local_path)
    return local_path


def perform_ocr(**context):
    """
    Extrait les donnees structurees du document via OCR/NLP.
    Utilise le module nlp-ocr developpe par l'equipe NLP.
    
    Returns:
        dict: Donnees extraites structurees (ExtractionResult)
    """
    from minio import Minio
    import sys
    import json
    import os
    from datetime import datetime
    sys.path.insert(0, '/opt/airflow/nlp-ocr')
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MINIO_CONFIG
    
    # Recuperation du chemin local
    local_path = context['task_instance'].xcom_pull(
        task_ids='download_document',
        key='local_path'
    )
    
    document_info = context['task_instance'].xcom_pull(
        task_ids='get_document',
        key='document_info'
    )
    
    if not local_path:
        raise ValueError("Chemin document manquant")
    
    logging.info(f"Debut OCR/NER pour: {local_path}")
    
    # Import et appel du module OCR/NLP
    try:
        from nlp_ocr import extract
        result = extract(local_path)
        
        # Conversion en dict pour stockage
        extracted_data = {
            'document_type': result.classification.document_type,
            'overall_confidence': result.overall_confidence,
            'raw_text': result.raw_text[:1000],  # Limite pour eviter surcharge
            'fields': result.dict()  # Tous les champs structures
        }
        
        logging.info(f"OCR termine - Type: {extracted_data['document_type']}, Confidence: {extracted_data['overall_confidence']}")
    except ImportError:
        logging.warning("Module nlp_ocr non disponible - Mode simulation")
        extracted_data = {
            'document_type': 'inconnu',
            'overall_confidence': 0.0,
            'raw_text': 'Simulation OCR',
            'fields': {}
        }
    
    # Stockage du extraction.json dans MinIO datalake/clean/ (resultats OCR intermediaires)
    document_id = document_info['document_id']
    now = datetime.now()
    # Chemin relatif sans préfixe (sera ajouté lors de l'upload)
    extraction_relative = f"{now.year}/{now.month:02d}/{now.day:02d}/{document_id}/extraction.json"
    
    client = Minio(
        MINIO_CONFIG['endpoint'],
        access_key=MINIO_CONFIG['access_key'],
        secret_key=MINIO_CONFIG['secret_key'],
        secure=MINIO_CONFIG['secure']
    )
    
    bucket = MINIO_CONFIG['bucket']
    clean_prefix = MINIO_CONFIG['prefixes']['clean']
    
    # Création du bucket si nécessaire
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    
    # Chemin complet avec préfixe clean/
    clean_path = clean_prefix + extraction_relative
    
    # Ecriture dans un fichier temporaire puis upload
    temp_json = f"/tmp/{document_id}_extraction.json"
    with open(temp_json, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, ensure_ascii=False, indent=2)
    
    client.fput_object(bucket, clean_path, temp_json)
    os.remove(temp_json)
    
    logging.info(f"extraction.json stocke: {bucket}/{clean_path}")
    
    context['task_instance'].xcom_push(key='extracted_data', value=extracted_data)
    context['task_instance'].xcom_push(key='clean_path', value=clean_path)
    
    return extracted_data


def perform_validation(**context):
    """
    Valide les donnees extraites via le module de validation.
    Utilise le moteur de validation developpe par l'equipe Data Quality.
    
    Returns:
        dict: Resultats de validation (decision, alerts, anomalies)
    """
    import sys
    import json
    sys.path.insert(0, '/opt/airflow/validation')
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MINIO_CONFIG
    
    extracted_data = context['task_instance'].xcom_pull(
        task_ids='perform_ocr',
        key='extracted_data'
    )
    
    clean_path = context['task_instance'].xcom_pull(
        task_ids='perform_ocr',
        key='clean_path'
    )
    
    document_info = context['task_instance'].xcom_pull(
        task_ids='get_document',
        key='document_info'
    )
    
    if not extracted_data:
        raise ValueError("Donnees extraites manquantes")
    
    logging.info(f"Debut validation pour document {document_info['document_id']}")
    
    # Appel du module de validation
    try:
        # Le module de validation lit extraction.json depuis MinIO datalake/clean/
        # et produit validation_result.json dans clean/ egalement
        from validation.main import validate_batch_from_minio
        
        validation_result = validate_batch_from_minio(
            extraction_path=clean_path,
            store_minio=True
        )
        
        # Extraction des anomalies pour le callback Backend
        anomalies = validation_result.get('alerts', [])
        decision = validation_result.get('decision', 'review')
        
        logging.info(f"Validation terminee - Decision: {decision}, Anomalies: {len(anomalies)}")
    except ImportError:
        logging.warning("Module validation non disponible - Mode simulation")
        anomalies = []
        decision = 'approved'
        validation_result = {
            'decision': decision,
            'alerts': anomalies,
            'validated_at': 'simulation'
        }
    
    context['task_instance'].xcom_push(key='anomalies', value=anomalies)
    context['task_instance'].xcom_push(key='decision', value=decision)
    
    return validation_result


def callback_to_backend(**context):
    """
    Envoie les resultats du traitement au Backend API.
    Le Backend met a jour MongoDB et notifie le Frontend via WebSocket.
    
    Returns:
        dict: Reponse du Backend
    """
    import requests
    import sys
    import os
    sys.path.insert(0, '/opt/airflow/dags')
    from config import BACKEND_API_CONFIG
    
    # Recuperation de toutes les donnees du pipeline
    document_info = context['task_instance'].xcom_pull(
        task_ids='get_document',
        key='document_info'
    )
    
    extracted_data = context['task_instance'].xcom_pull(
        task_ids='perform_ocr',
        key='extracted_data'
    )
    
    anomalies = context['task_instance'].xcom_pull(
        task_ids='perform_validation',
        key='anomalies'
    ) or []
    
    decision = context['task_instance'].xcom_pull(
        task_ids='perform_validation',
        key='decision'
    ) or 'review'
    
    # Preparation du payload pour le callback Backend
    # Format aligne avec PipelineCallbackPayload du Backend (schemas/pipeline.py)
    # Status possibles: pending, processing, ocr_done, extraction_done, done, error
    status_map = {
        'approved': 'done',
        'review': 'done',  # Le Backend decide si c'est review ou approved via anomalies
        'blocked': 'error'
    }
    
    # Normalisation du document_type pour correspondre aux valeurs attendues par le backend
    _doc_type_raw = extracted_data.get('document_type') or 'inconnu'
    _doc_type_map = {'unknown': 'inconnu'}
    _doc_type = _doc_type_map.get(_doc_type_raw, _doc_type_raw)

    payload = {
        'document_id': document_info['document_id'],
        'status': status_map.get(decision, 'done'),
        'document_type': _doc_type,
        'extracted_data': extracted_data.get('fields', {}),
        'anomalies': anomalies,
        'error_message': None
    }
    
    # Appel de l'endpoint callback du Backend
    callback_url = BACKEND_API_CONFIG['base_url'] + '/api/internal/pipeline/result'
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    logging.info(f"Callback Backend pour document {document_info['document_id']}")
    
    try:
        response = requests.post(
            callback_url,
            json=payload,
            headers=headers,
            timeout=BACKEND_API_CONFIG['timeout']
        )
        
        response.raise_for_status()
        
        logging.info(f"Callback reussi: {response.status_code}")
        # Le backend retourne HTTP 204 No Content (pas de body JSON)
        if response.status_code == 204 or not response.content:
            return {"status": "ok"}
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Erreur callback Backend: {e}")
        raise


def archive_document(**context):
    """
    Archive les resultats valides dans datalake/curated/.
    Copie le fichier original ET les resultats (extraction.json, validation_result.json)
    depuis raw/ et clean/ vers curated/ apres traitement complet.
    
    Returns:
        dict: Chemins des documents archives
    """
    from minio import Minio
    import sys
    from datetime import datetime
    sys.path.insert(0, '/opt/airflow/dags')
    from config import MINIO_CONFIG
    
    document_info = context['task_instance'].xcom_pull(
        task_ids='get_document',
        key='document_info'
    )
    
    clean_path = context['task_instance'].xcom_pull(
        task_ids='perform_ocr',
        key='clean_path'
    )
    
    if not document_info:
        raise ValueError("Informations document manquantes")
    
    client = Minio(
        MINIO_CONFIG['endpoint'],
        access_key=MINIO_CONFIG['access_key'],
        secret_key=MINIO_CONFIG['secret_key'],
        secure=MINIO_CONFIG['secure']
    )
    
    bucket = MINIO_CONFIG['bucket']
    raw_prefix = MINIO_CONFIG['prefixes']['raw']
    clean_prefix = MINIO_CONFIG['prefixes']['clean']
    curated_prefix = MINIO_CONFIG['prefixes']['curated']
    
    # Chemins
    document_id = document_info['document_id']
    filename = document_info['filename']
    
    now = datetime.now()
    base_relative = f"{now.year}/{now.month:02d}/{now.day:02d}/{document_id}"
    
    archived_paths = {}
    from minio.commonconfig import CopySource
    
    try:
        # 1. Copie du fichier original depuis raw/ vers curated/
        original_source = document_info['minio_path']  # Déjà avec préfixe raw/
        original_dest = curated_prefix + base_relative + "/" + filename
        
        client.copy_object(
            bucket,
            original_dest,
            CopySource(bucket, original_source)
        )
        archived_paths['original'] = original_dest
        logging.info(f"Document original archive: {original_source} -> {original_dest}")
        
        # 2. Copie de extraction.json depuis clean/ vers curated/
        extraction_dest = curated_prefix + base_relative + "/extraction.json"
        client.copy_object(
            bucket,
            extraction_dest,
            CopySource(bucket, clean_path)
        )
        archived_paths['extraction'] = extraction_dest
        logging.info(f"Extraction archive: {clean_path} -> {extraction_dest}")
        
        # 3. Copie de validation_result.json depuis clean/ vers curated/ (si existe)
        validation_source = clean_path.replace('extraction.json', 'validation_result.json')
        try:
            validation_dest = curated_prefix + base_relative + "/validation_result.json"
            client.copy_object(
                bucket,
                validation_dest,
                CopySource(bucket, validation_source)
            )
            archived_paths['validation'] = validation_dest
            logging.info(f"Validation archive: {validation_source} -> {validation_dest}")
        except Exception:
            logging.warning(f"validation_result.json non trouvé: {validation_source}")
        
        logging.info(f"Archivage complet - {len(archived_paths)} fichiers dans {bucket}/curated/")
        return archived_paths
        
    except Exception as e:
        logging.error(f"Erreur archivage: {e}")
        raise


# Definition des taches du pipeline event-driven
get_document_task = PythonOperator(
    task_id='get_document',
    python_callable=get_document_info,
    provide_context=True,
    dag=dag,
)

download_task = PythonOperator(
    task_id='download_document',
    python_callable=download_document,
    provide_context=True,
    dag=dag,
)

ocr_task = PythonOperator(
    task_id='perform_ocr',
    python_callable=perform_ocr,
    provide_context=True,
    dag=dag,
)

validation_task = PythonOperator(
    task_id='perform_validation',
    python_callable=perform_validation,
    provide_context=True,
    dag=dag,
)

callback_task = PythonOperator(
    task_id='callback_backend',
    python_callable=callback_to_backend,
    provide_context=True,
    dag=dag,
)

archive_task = PythonOperator(
    task_id='archive_document',
    python_callable=archive_document,
    provide_context=True,
    dag=dag,
)

# Definition du flux d'execution du pipeline event-driven
# get_document -> download -> ocr -> validation -> callback + archive
# Le Backend recoit les resultats via callback et gere l'auto-fill CRM/Conformite
get_document_task >> download_task >> ocr_task >> validation_task >> [callback_task, archive_task]
