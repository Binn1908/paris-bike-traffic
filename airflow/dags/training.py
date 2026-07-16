from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator

default_args = {
    "owner": "binn",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def make_retrain_task(model_name: str) -> SimpleHttpOperator:
    """Crée une tâche de ré-entraînement pour un modèle donné."""
    return SimpleHttpOperator(
        task_id=f"retrain_{model_name}",
        http_conn_id="api_connection",
        endpoint=f"/training?model={model_name}",
        method="POST",
        log_response=True,
    )


with DAG(
    dag_id="paris_bike_retraining",
    description="Ré-entraîne les 4 modèles séquentiellement sur les données MySQL",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    tags=["paris-bike-traffic"],
) as dag:

    retrain_lr = make_retrain_task("lr")
    retrain_rf = make_retrain_task("rf")
    retrain_lgbm = make_retrain_task("lgbm")
    retrain_xgb = make_retrain_task("xgb")

    retrain_lr >> retrain_rf >> retrain_lgbm >> retrain_xgb