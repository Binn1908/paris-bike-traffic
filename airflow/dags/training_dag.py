import os
from datetime import datetime, timedelta

from airflow.providers.http.operators.http import SimpleHttpOperator

from airflow import DAG

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("La variable d'environnement API_KEY est manquante ou vide (voir .env).")

default_args = {
    "owner": "Chinnawat Wisetwongsa",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}


def create_train_task(model_name: str) -> SimpleHttpOperator:
    """
    Crée une tâche d'entraînement pour un modèle donné.
    """
    return SimpleHttpOperator(
        task_id=f"train_{model_name}",
        http_conn_id="api_connection",  # C'est la connection avec FastAPI (docker)
        endpoint=f"/training?model={model_name}",  # Requête URL, pas JSON
        method="POST",
        headers={"X-API-Key": API_KEY},
        log_response=True,
    )


with DAG(
    dag_id="paris_bike_traffic_training",
    description="Entraîne les 4 modèles séquentiellement sur les données MySQL",
    default_args=default_args,
    schedule_interval=None,  # Pas de planification : ce DAG est déclénché uniquement par ingestion_dag.py lorsqu'une dérive est détectée
    start_date=datetime(2026, 7, 1),
    catchup=False,
    max_active_runs=1,  # Empêche plusieurs exécutions simultanées du même DAG
    tags=["paris-bike-traffic"],
) as dag:

    train_lr = create_train_task("lr")
    train_rf = create_train_task("rf")
    train_lgbm = create_train_task("lgbm")
    train_xgb = create_train_task("xgb")

    train_lr >> train_rf >> train_lgbm >> train_xgb