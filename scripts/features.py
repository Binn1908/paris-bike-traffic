"""
Définitions partagées des colonnes utilisées pour l'entraînement et la
détection de dérive. Source unique de vérité : toute modification ici
se répercute automatiquement dans scripts/training.py et
airflow/dags/ingestion_dag.py, sans duplication manuelle.
"""
FEATURE_COLS_NUM = [
    "Année",
    "Mois",
    "Jour du mois",
    "Heure",
    "Jour de la semaine",
    "Week-end",
    "Vacances",
    "lag_1h",
    "lag_24h",
    "lag_168h",
    "roll_mean_3h",
    "Température (°C)",
    "Précipitations (mm)",
]

FEATURE_COLS_CAT = ["Nom du compteur", "Direction"]

TARGET_COL = "Comptage horaire"