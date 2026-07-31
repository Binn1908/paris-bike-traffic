import os
import sys
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

# Ajoute le dossier racine du projet au path pour pouvoir importer les scripts
sys.path.append(str(Path(__file__).resolve().parent.parent))
# .../velo-paris

from scripts.load_db import load_db
from scripts.predict import predict, DEFAULT_MODEL
from scripts.preprocess import preprocess
from scripts.training import train

# Nécessite un fichier .env à la racine (API_KEY, en plus des variables MySQL)
load_dotenv()

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("La variable d'environnement API_KEY est manquante ou vide (voir .env).")

api_key_header = APIKeyHeader(name="X-API-KEY")


def verify_api_key(api_key: str = Depends(api_key_header)):
    """
    Vérifie que la clé API transmise dans le header X-API-Key correspond à celle
    définie dans .env. Utilisé pour protéger les endpoints internes (Airflow uniquement).
    """
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Clé API invalide.")
    
    
app = FastAPI(
    title="Paris Bike Traffic API",
    description="API pour le trafic cycliste à Paris : prétraitement des données, entraînement et prédiction des modèles.",
    version="1.0.0",
)


# Schémas de données avec Pydantic

class TrainingResponse(BaseModel):
    # BaseModel est une classe de Pydantic qui sert à valider la typologie des attributs transmis via les endpoints
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
    # Literal est de type str mais accepte uniquement les valeurs fournies dans la liste
    # Si model n'est pas donné par l'utilisateur, la prédiction se fera avec le modèle lgbm


class PredictResponse(BaseModel):
    model: str
    prediction: float


class LoadDbResponse(BaseModel):
    rows_loaded: int


# Définition des endpoints

@app.get("/")
def root():
    return {"message": "Paris Bike Traffic API — Endpoint disponibles : /load-db, /training, /predict"}


@app.post("/load-db", response_model=LoadDbResponse, dependencies=[Depends(verify_api_key)])
def load_db_endpoint():
    """
    Prétraite les données brutes et recharge la table training_data dans MySQL.
    Toujours exécuté intégralement (pas de mode incrémental).
    """
    try:
        preprocess()
        rows_loaded = load_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return LoadDbResponse(rows_loaded=rows_loaded)


@app.post("/training", response_model=TrainingResponse, dependencies=[Depends(verify_api_key)])
def training_endpoint(model: Literal["lr", "rf", "lgbm", "xgb"] = DEFAULT_MODEL):
    # La validation du paramètre model se passe directement dans la fonction
    # Cela évite de devoir passer le modèle comme une requête JSON
    """
    Réentraîne un modèle sur les données de la base de données et retourne le modèle utilisé et les métriques.
    """
    try:
        metrics = train(model_name=model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return metrics


@app.post("/predict", response_model=PredictResponse)
def predict_endpoint(request: PredictRequest):
    """
    Prédit le nombre de vélos par heure.
    """
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
    # L'endpoint predict retourne la prédiction, mais aussi le modèle retenu
    # C'est utile dans le cas où l'utilisateur n'aurait pas choisi un modèle