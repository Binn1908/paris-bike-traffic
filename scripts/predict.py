import os
from datetime import datetime

import mlflow
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)

AVAILABLE_MODELS = ["lr", "rf", "lgbm", "xgb"]
DEFAULT_MODEL = "lgbm"


def load_model(model_name: str = DEFAULT_MODEL):
    """
    Charge la version en production du modèle depuis le MLflow Model Registry.
    """
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(
            f"Modèle '{model_name}' inconnu. Valeurs acceptées : {AVAILABLE_MODELS}"
        )

    model_uri = f"models:/paris-bike-traffic-{model_name}@production"

    try:
        return mlflow.sklearn.load_model(model_uri)
    except mlflow.exceptions.MlflowException as e:
        raise FileNotFoundError(
            f"Aucun modèle '{model_name}' en production dans le MLflow Registry : {e}"
        )


def log_prediction(input_data: dict, prediction: float, model_name: str):
    """
    Enregistre une prédiction (features en entrée, le modèle utilisé et la valeur prédite) dans la
    table MySQL predictions, pour permettre une future détection de dérive
    côté prédiction (comparaison avec training_data).
    """
    row = {
        **input_data,
        "prediction": prediction,
        "model": model_name,
        "request_time": datetime.now(),
    }
    df = pd.DataFrame([row])

    engine = create_engine(DATABASE_URL)
    df.to_sql("predictions", engine, if_exists="append", index=False)


def predict(input_data: dict, model_name: str = DEFAULT_MODEL) -> float:
    """
    Effectue une prédiction.

    Args :
        input_data : dict avec les clés suivantes :
            - Nom du compteur (str)
            - Direction (str)
            - Année (int)
            - Mois (int)
            - Jour du mois (int)
            - Heure (int)
            - Jour de la semaine (int)
            - Week-end (int)
            - Vacances (int)
            - lag_1h (float)
            - lag_24h (float)
            - lag_168h (float)
            - roll_mean_3h (float)
            - Température (°C) (float)
            - Précipitations (mm) (float)
        model_name: l'un de "lr", "rf", "lgbm", "xgb"

    Output :
        Nombre de vélos prédit par heure (float)
    """
    model = load_model(model_name)  # Techniquement, c'est toujours un pipeline :)
    df = pd.DataFrame([input_data])
    prediction = model.predict(df)[0]
    prediction = max(0.0, round(float(prediction), 2))
    # La prédiction ne peut être < 0
    print(f"Nombre de vélos prédit par heure : {prediction}")
    
    log_prediction(input_data, prediction, model_name)
    
    print("Prédiction enregistrée dans la table MySQL predictions.")
    
    return prediction


if __name__ == "__main__":
    # Exemple de prédiction pour tester
    sample_input = {
        "Nom du compteur": "10 avenue de la Grande Armée 10 avenue de la Grande Armée [Bike IN]",
        "Direction": "Bike IN",
        "Année": 2025,
        "Mois": 5,
        "Jour du mois": 3,
        "Heure": 8,
        "Jour de la semaine": 5,
        "Week-end": 1,
        "Vacances": 0,
        "lag_1h": 120.0,
        "lag_24h": 95.0,
        "lag_168h": 110.0,
        "roll_mean_3h": 105.0,
        "Température (°C)": 18.0,
        "Précipitations (mm)": 0.0,
    }

    result = predict(sample_input, model_name="lgbm")