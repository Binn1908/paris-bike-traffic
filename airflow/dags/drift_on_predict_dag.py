import os
import tempfile
from datetime import datetime, timedelta

import mlflow
import pandas as pd
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from dotenv import load_dotenv
from evidently.metric_preset import DataDriftPreset
from evidently.pipeline.column_mapping import ColumnMapping
from evidently.report import Report
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from airflow import DAG
from scripts.features import FEATURE_COLS_CAT, FEATURE_COLS_NUM

load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)

# Contrairement à ingestion_dag.py, on ne compare que les features :
# la table predictions n'a pas de "Comptage horaire" (valeur réelle),
# seulement "prediction" (valeur prédite par le modèle).
FEATURE_COLS = FEATURE_COLS_NUM + FEATURE_COLS_CAT

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
MLFLOW_EXPERIMENT_NAME = "drift_checks_on_prediction"

default_args = {
    "owner": "Chinnawat Wisetwongsa",
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}


def check_batch_column(engine):
    """
    Ajoute la colonne batch à la table predictions si elle n'existe
    pas encore (MySQL ne supporte pas ADD COLUMN IF NOT EXISTS,
    donc on vérifie manuellement via information_schema).
    """
    with engine.connect() as conn:
        column_exists = conn.execute(
            text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() "
                "AND table_name = 'predictions' "
                "AND column_name = 'batch'"
            )
        ).scalar()

    if column_exists == 0:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE predictions ADD COLUMN batch INT DEFAULT NULL"))


def check_prediction_drift(**context):
    """
    Compare les prédictions récentes (non encore vérifiées) aux données
    d'entraînement, pour détecter une dérive côté features des requêtes
    envoyées à /predict.

    Retourne :
    - "no_predictions_yet" : la table predictions n'existe pas
    - "insufficient_predictions" : prédiction reportée
    - "drift" / "no_drift" : résultat de la comparaison Evidently
    """
    engine = create_engine(DATABASE_URL)
    
    try:
        check_batch_column(engine)
    except (OperationalError, ProgrammingError):
        print("Table predictions introuvable : vérification de dérive ignorée.")
        return "no_predictions_yet"

    cols_sql = ", ".join(f"`{c}`" for c in FEATURE_COLS)

    df_current = pd.read_sql(
        text(f"SELECT {cols_sql} FROM predictions WHERE batch IS NULL"),
        engine,
    )

    if len(df_current) < 50:
        print(f"Seulement {len(df_current)} nouvelle(s) prédiction(s) à vérifier (seuil : 50). Vérification reportée.")
        return "insufficient_predictions"
    
    try:
        with engine.connect() as conn:
            training_data_count = conn.execute(
                text("SELECT COUNT(*) FROM training_data")
            ).scalar()
    except (OperationalError, ProgrammingError):
        print("Table training_data introuvable : vérification de dérive ignorée.")
        return "no_reference_data"

    if training_data_count == 0:
        print("Table training_data vide : vérification de dérive ignorée.")
        return "no_reference_data"

    with engine.connect() as conn:
        max_batch = conn.execute(
            text("SELECT MAX(batch) FROM predictions")
        ).scalar()
    next_batch = 1 if max_batch is None else max_batch + 1

    print(f"Check batch {next_batch} : {len(df_current)} prédictions à vérifier, comparaison Evidently en cours...")

    df_reference = pd.read_sql(
        text(f"SELECT {cols_sql} FROM training_data"),
        engine,
    )

    column_mapping = ColumnMapping(
        numerical_features=FEATURE_COLS_NUM,
        categorical_features=FEATURE_COLS_CAT,
    )

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=df_reference, current_data=df_current, column_mapping=column_mapping)
    result = report.as_dict()

    dataset_drift = result["metrics"][0]["result"]["dataset_drift"]
    n_drifted_columns = result["metrics"][0]["result"]["number_of_drifted_columns"]

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name=f"drift_check_on_prediction_batch_{next_batch}"):
        mlflow.log_param("batch_checked", next_batch)
        mlflow.log_param("reference_rows", len(df_reference))
        mlflow.log_param("current_rows", len(df_current))
        mlflow.log_metric("dataset_drift", int(dataset_drift))
        mlflow.log_metric("number_of_drifted_columns", n_drifted_columns)

        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = os.path.join(tmp_dir, f"prediction_drift_report_batch_{next_batch}.html")
            report.save_html(report_path)
            mlflow.log_artifact(report_path)

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE predictions SET batch = :batch WHERE batch IS NULL"),
            {"batch": next_batch},
        )

    print(f"Batch {next_batch} : dérive détectée = {dataset_drift} ({n_drifted_columns} colonnes en dérive).")
    return "drift" if dataset_drift else "no_drift"


def branch_on_prediction_drift(**context):
    """
    Route vers trigger_training si une dérive a été détectée côté
    prédictions, sinon vers skip_training.
    """
    ti = context["ti"]
    result = ti.xcom_pull(task_ids="check_prediction_drift")

    if result == "drift":
        return "trigger_training"
    return "skip_training"


with DAG(
    dag_id="paris_bike_traffic_prediction_drift",
    description="Vérifie la dérive des features envoyées à /predict par rapport aux données d'entraînement",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 8, 4),
    catchup=False,
    max_active_runs=1,
    tags=["paris-bike-traffic"],
) as dag:

    check_prediction_drift_task = PythonOperator(
        task_id="check_prediction_drift",
        python_callable=check_prediction_drift,
    )

    branch_on_prediction_drift_task = BranchPythonOperator(
        task_id="branch_on_prediction_drift",
        python_callable=branch_on_prediction_drift,
    )

    trigger_training_task = TriggerDagRunOperator(
        task_id="trigger_training",
        trigger_dag_id="paris_bike_traffic_training",
        wait_for_completion=True,
    )

    do_nothing_task = EmptyOperator(task_id="skip_training")

    check_prediction_drift_task >> branch_on_prediction_drift_task >> [trigger_training_task, do_nothing_task]