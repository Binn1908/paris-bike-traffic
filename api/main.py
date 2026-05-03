from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Literal

import sys
from pathlib import Path

# Ajoute le dossier racine au path pour pouvoir importer les scripts
sys.path.append(str(Path(__file__).resolve().parent.parent))

from scripts.predict import predict, AVAILABLE_MODELS, DEFAULT_MODEL
from scripts.training import train

app = FastAPI(
    title="Paris Bike Traffic API",
    description="API de prédiction du trafic cycliste à Paris",
    version="1.0.0",
)


# --- Schémas de données ---


class TrainingResponse(BaseModel):
    model: str
    mae: float
    rmse: float
    r2: float


class PredictRequest(BaseModel):
    nom_du_compteur: str
    direction: str
    annee: int
    mois: int
    jour_du_mois: int
    heure: int
    jour_de_la_semaine: int
    week_end: int
    vacances: int
    lag_1h: float
    lag_24h: float
    lag_168h: float
    roll_mean_3h: float
    temperature: float
    precipitations: float
    model: Literal["lr", "rf", "lgbm", "xgb"] = DEFAULT_MODEL


class PredictResponse(BaseModel):
    model: str
    prediction: float


# --- Endpoints ---


@app.get("/")
def root():
    return {"message": "Paris Bike Traffic API — utilisez /training ou /predict"}


@app.post("/training", response_model=TrainingResponse)
def training_endpoint(model: Literal["lr", "rf", "lgbm", "xgb"] = DEFAULT_MODEL):
    """Réentraîne un modèle sur les données de la base de données et retourne les métriques."""
    try:
        metrics = train(model_name=model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return TrainingResponse(**metrics)


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(request: PredictRequest):
    """Prédit le nombre de vélos par heure pour un compteur donné."""
    input_data = {
        "Nom du compteur": request.nom_du_compteur,
        "Direction": request.direction,
        "Année": request.annee,
        "Mois": request.mois,
        "Jour du mois": request.jour_du_mois,
        "Heure": request.heure,
        "Jour de la semaine": request.jour_de_la_semaine,
        "Week-end": request.week_end,
        "Vacances": request.vacances,
        "lag_1h": request.lag_1h,
        "lag_24h": request.lag_24h,
        "lag_168h": request.lag_168h,
        "roll_mean_3h": request.roll_mean_3h,
        "Température (°C)": request.temperature,
        "Précipitations (mm)": request.precipitations,
    }

    try:
        prediction = predict(input_data, model_name=request.model)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    return PredictResponse(model=request.model, prediction=prediction)
