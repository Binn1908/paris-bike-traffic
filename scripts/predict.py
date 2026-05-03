import joblib
import pandas as pd
from pathlib import Path

MODELS_DIR = Path("models")

AVAILABLE_MODELS = ["lr", "rf", "lgbm", "xgb"]
DEFAULT_MODEL = "lgbm"


def load_model(model_name: str = DEFAULT_MODEL):
    """Charger un modèle entraîné depuis le disque."""
    if model_name not in AVAILABLE_MODELS:
        raise ValueError(
            f"Modèle '{model_name}' inconnu. Choisir parmi : {AVAILABLE_MODELS}"
        )

    model_path = MODELS_DIR / f"model_{model_name}.joblib"

    if not model_path.exists():
        raise FileNotFoundError(f"Fichier modèle introuvable : {model_path}")

    return joblib.load(model_path)


def predict(input_data: dict, model_name: str = DEFAULT_MODEL) -> float:
    """
    Effectuer une prédiction pour une seule entrée.

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
    model = load_model(model_name)
    df = pd.DataFrame([input_data])
    prediction = model.predict(df)[0]
    return max(0.0, round(float(prediction), 2))
    # La prédiction ne peut être < 0.


if __name__ == "__main__":
    # Exemple de prédiction pour les tests
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
    print(f"Nombre de vélos prédit par heure : {result}")
