import mlflow
import pandas as pd

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