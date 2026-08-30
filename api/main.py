import os
import sys
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import APIKeyHeader
from prometheus_client import Counter, Histogram, generate_latest, CollectorRegistry
from pydantic import BaseModel
from sqlalchemy import create_engine, text

# Ajoute le dossier racine du projet au path pour pouvoir importer les scripts
sys.path.append(str(Path(__file__).resolve().parent.parent))
# .../velo-paris

from scripts.ingest import ingest
from scripts.load_db import load_db
from scripts.predict import predict, DEFAULT_MODEL
from scripts.preprocess import preprocess
from scripts.training import train, get_best_model_name

# Nécessite un fichier .env à la racine (API_KEY, en plus des variables MySQL)
load_dotenv()

# Connexion à la base de données MySQL (utilisée par /get-counters)
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)
engine = create_engine(DATABASE_URL)

API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("La variable d'environnement API_KEY est manquante ou vide (voir .env).")

api_key_header = APIKeyHeader(name="X-API-Key")


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

registry = CollectorRegistry()

api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['endpoint', 'method', 'status_code', 'model'],
    registry=registry
)

api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['endpoint', 'method', 'status_code', 'model'],
    registry=registry
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
    model: Literal["lr", "rf", "lgbm", "xgb"] | None = None
    # Si model n'est pas donné par l'utilisateur, /predict choisit
    # automatiquement le modèle ayant le meilleur R² actuellement en production


class PredictResponse(BaseModel):
    model: str
    prediction: float


class LoadDbResponse(BaseModel):
    rows_loaded: int
    batch: int | None = None


# Définition des endpoints

@app.get("/")
def root():
    return {"message": "Paris Bike Traffic API — Endpoint disponibles : /load-db, /training, /predict"}


@app.post("/load-db", response_model=LoadDbResponse, dependencies=[Depends(verify_api_key)])
def load_db_endpoint():
    """
    Récupère le dernier chunk de données brutes, le prétraite, et met à jour
    la table training_data dans MySQL. Les lignes déjà présentes ne sont pas
    réinsérées ; seules les nouvelles lignes sont ajoutées et taguées avec
    un numéro de batch d'ingestion.
    """
    try:
        ingest()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        preprocess()
        rows_loaded, batch = load_db()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return LoadDbResponse(rows_loaded=rows_loaded, batch=batch)


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
    start_time = time.time()
    status_code = "200"

    model_name = request.model or get_best_model_name()

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
        prediction = predict(input_data, model_name=model_name)
        return PredictResponse(model=model_name, prediction=prediction)
        # L'endpoint predict retourne la prédiction, mais aussi le modèle retenu
        # C'est utile dans le cas où l'utilisateur n'aurait pas choisi un modèle
    except (ValueError, FileNotFoundError) as e:
        status_code = "400"
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        duration = time.time() - start_time
        api_requests_total.labels(
            endpoint="/predict", method="POST", status_code=status_code, model=model_name
        ).inc()
        api_request_duration_seconds.labels(
            endpoint="/predict", method="POST", status_code=status_code, model=model_name
        ).observe(duration)
        

@app.get("/metrics")
def metrics():
    """
    Expose les métriques Prometheus pour /predict.
    """
    return Response(content=generate_latest(registry), media_type="text/plain")
    

@app.get("/get-counters")
def get_counters():
    """
    Retourne la liste des noms de compteurs distincts présents dans training_data.
    Utilisé par l'interface Streamlit pour peupler le menu déroulant.
    """
    query = text('SELECT DISTINCT `Nom du compteur` FROM training_data ORDER BY `Nom du compteur`')
    with engine.connect() as conn:
        result = conn.execute(query)
        counters = [row[0] for row in result]
    return {"counters": counters}


@app.get("/best-model")
def best_model_endpoint():
    """
    Retourne le nom du modèle ayant actuellement le meilleur R² en production.
    Utilisé par l'interface Streamlit pour indiquer le modèle recommandé.
    """
    try:
        model_name = get_best_model_name()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"best_model": model_name}