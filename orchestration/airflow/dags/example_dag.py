"""
DAG exemple simple pour demonstration
Ce DAG sert de template pour creer de nouveaux workflows
"""
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import logging

# Configuration des parametres du DAG
default_args = {
    'owner': 'gills',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Definition du DAG
dag = DAG(
    'example_simple_pipeline',
    default_args=default_args,
    description='Pipeline exemple pour apprendre la structure des DAGs',
    schedule_interval=None,  # Execution manuelle uniquement
    catchup=False,
    tags=['example', 'tutorial'],
)


def task_hello(**context):
    """
    Tache simple qui affiche un message
    Demonstre l'utilisation de logging
    """
    logging.info("Debut de la tache hello")
    message = "Hello from Airflow DAG"
    logging.info(f"Message: {message}")
    
    # Partage de donnees vers les taches suivantes via XCom
    context['task_instance'].xcom_push(key='greeting', value=message)
    
    return message


def task_process_data(**context):
    """
    Tache qui recupere des donnees de la tache precedente
    Demonstre l'utilisation de XCom pour communication inter-taches
    """
    # Recuperation des donnees de la tache precedente
    greeting = context['task_instance'].xcom_pull(
        task_ids='hello_task',
        key='greeting'
    )
    
    logging.info(f"Message recu: {greeting}")
    
    # Simulation de traitement
    processed_data = {
        'original': greeting,
        'uppercase': greeting.upper(),
        'length': len(greeting)
    }
    
    logging.info(f"Donnees traitees: {processed_data}")
    
    context['task_instance'].xcom_push(key='processed', value=processed_data)
    
    return processed_data


def task_save_result(**context):
    """
    Tache finale qui sauvegarde ou affiche le resultat
    Demonstre la fin d'un pipeline
    """
    processed = context['task_instance'].xcom_pull(
        task_ids='process_task',
        key='processed'
    )
    
    logging.info("Sauvegarde du resultat final")
    logging.info(f"Resultat: {processed}")
    
    # Dans un vrai pipeline, on sauvegarderait en base ou dans MinIO
    
    return "Pipeline complete avec succes"


# Definition des taches
hello_task = PythonOperator(
    task_id='hello_task',
    python_callable=task_hello,
    provide_context=True,
    dag=dag,
)

process_task = PythonOperator(
    task_id='process_task',
    python_callable=task_process_data,
    provide_context=True,
    dag=dag,
)

save_task = PythonOperator(
    task_id='save_task',
    python_callable=task_save_result,
    provide_context=True,
    dag=dag,
)

# Tache bash pour demonstration
bash_task = BashOperator(
    task_id='bash_example',
    bash_command='echo "Execution depuis Bash operator" && date',
    dag=dag,
)

# Definition du flux d'execution
# Syntaxe 1: Lineaire
hello_task >> process_task >> save_task

# Syntaxe 2: Parallele (bash_task s'execute independamment)
hello_task >> bash_task

