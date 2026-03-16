# DAG Airflow exemple - À personnaliser par l'équipe
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'hackathon',
    'depends_on_past': False,
    'start_date': datetime(2026, 3, 16),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'example_dag',
    default_args=default_args,
    description='DAG exemple pour démarrer',
    schedule_interval=timedelta(days=1),
    catchup=False,
)

def example_task():
    """Fonction exemple - à remplacer par votre logique"""
    print("DAG en cours d'exécution...")
    return "Success"

task1 = PythonOperator(
    task_id='example_task',
    python_callable=example_task,
    dag=dag,
)
