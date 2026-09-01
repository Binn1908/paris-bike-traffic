import os
import tempfile
from datetime import datetime, timedelta

import mlflow
import pandas as pd
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from dotenv import load_dotenv
from evidently.metric_preset import DataDriftPreset
from evidently.pipeline.column_mapping import ColumnMapping
from evidently.report import Report
from sqlalchemy import create_engine, text

from airflow import DAG
from scripts.features import FEATURE_COLS_CAT, FEATURE_COLS_NUM, TARGET_COL

load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)

ALL_COLS = FEATURE_COLS_NUM + FEATURE_COLS_CAT + [TARGET_COL]

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("La variable d'environnement API_KEY est manquante ou vide (voir .env).")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")

MLFLOW_EXPERIMENT_NAME = "drift_checks"

default_args = {
    "owner": "Chinnawat Wisetwongsa",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}


def check_drift(**context):
    """
    Détermine la suite à donner après le chargement d'un nouveau batch :
    - "no_new_data" : rien de nouveau (rows_loaded == 0), pas de vérification de dérive.
    - "bootstrap" : premier batch jamais chargé, aucun ensemble de référence disponible.
    - "drift" / "no_drift" : résultat de la comparaison Evidently entre le nouveau
    batch et l'ensemble de référence (tous les batches précédents).
    Le rapport Evidently est systématiquement suivi dans MLflow.
    """
    ti = context["ti"]
    load_db_response = ti.xcom_pull(task_ids="call_load_db")  # On récupère la réponse de la tâche précédente
    rows_loaded = load_db_response["rows_loaded"]
    batch = load_db_response["batch"]

    if rows_loaded == 0:
        print("Aucune nouvelle ligne chargée : vérification de dérive ignorée.")
        return "no_new_data"

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        reference_count = conn.execute(
            text("SELECT COUNT(*) FROM training_data WHERE batch < :batch"),
            {"batch": batch},
        ).scalar()

    if reference_count == 0:
        print(f"Batch {batch} : aucun batch antérieur, premier entraînement (bootstrap).")
        return "bootstrap"

    print(f"Batch {batch} : {reference_count} lignes de référence trouvées, comparaison Evidently en cours...")

    df_reference = pd.read_sql(
        text(f"SELECT {', '.join(f'`{c}`' for c in ALL_COLS)} FROM training_data WHERE batch < :batch"),
        engine,
        params={"batch": batch},
    )
    df_new = pd.read_sql(
        text(f"SELECT {', '.join(f'`{c}`' for c in ALL_COLS)} FROM training_data WHERE batch = :batch"),
        engine,
        params={"batch": batch},
    )

    column_mapping = ColumnMapping(
        numerical_features=FEATURE_COLS_NUM,
        categorical_features=FEATURE_COLS_CAT,
        target=TARGET_COL,
    )

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=df_reference, current_data=df_new, column_mapping=column_mapping)
    result = report.as_dict()

    dataset_drift = result["metrics"][0]["result"]["dataset_drift"]  # bool
    n_drifted_columns = result["metrics"][0]["result"]["number_of_drifted_columns"]

    # Suivi dans MLflow (expérience séparée de l'entraînement pour ne pas polluer les comparaisons de modèles)
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name=f"drift_check_batch_{batch}"):
        mlflow.log_param("batch", batch)
        mlflow.log_param("reference_rows", reference_count)
        mlflow.log_param("new_rows", len(df_new))
        mlflow.log_metric("dataset_drift", int(dataset_drift))
        mlflow.log_metric("number_of_drifted_columns", n_drifted_columns)

        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = os.path.join(tmp_dir, f"drift_report_batch_{batch}.html")
            report.save_html(report_path)
            mlflow.log_artifact(report_path)

    print(f"Batch {batch} : dérive détectée = {dataset_drift} ({n_drifted_columns} colonnes en dérive).")
    return "drift" if dataset_drift else "no_drift"


def branch_on_drift(**context):
    """
    Route vers trigger_training si un (ré)entraînement est nécessaire
    (bootstrap ou dérive détectée), sinon vers skip_training.
    """
    ti = context["ti"]
    check_drift_result = ti.xcom_pull(task_ids="check_drift")

    if check_drift_result in ("bootstrap", "drift"):
        return "trigger_training"
    return "skip_training"


with DAG(
    dag_id="paris_bike_traffic_data_ingestion",
    description="Ingestion périodique de nouvelles données, vérification de dérive (ou bootstrap), et déclenchement de l'entraînement si besoin",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 8, 4),
    catchup=False,
    max_active_runs=1,
    tags=["paris-bike-traffic"],
) as dag:

    call_load_db_task = SimpleHttpOperator(
        task_id="call_load_db",
        http_conn_id="api_connection",
        endpoint="/load-db",
        method="POST",
        headers={"X-API-Key": API_KEY},
        response_filter=lambda response: response.json(),
        log_response=True,
    )

    check_drift_task = PythonOperator(
        task_id="check_drift",
        python_callable=check_drift,
    )

    branch_on_drift_task = BranchPythonOperator(
        task_id="branch_on_drift",
        python_callable=branch_on_drift,
    )

    trigger_training_task = TriggerDagRunOperator(
        task_id="trigger_training",
        trigger_dag_id="paris_bike_traffic_training",
        wait_for_completion=True,
    )

    do_nothing_task = EmptyOperator(task_id="skip_training")

    call_load_db_task >> check_drift_task >> branch_on_drift_task >> [trigger_training_task, do_nothing_task]