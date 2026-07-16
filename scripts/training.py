import os
import sys
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from dotenv import load_dotenv
from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import create_engine
from xgboost import XGBRegressor

load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)

MODELS = {
    "lr": LinearRegression(),
    "rf": RandomForestRegressor(
        n_jobs=2,  # Modification de -1 pour alléger l'entraînement
        random_state=42,
        max_depth=30,
        min_samples_leaf=5,
        min_samples_split=20,
        max_features="sqrt",
        n_estimators=10,
    ),
    "lgbm": LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    ),
    "xgb": XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        objective="reg:squarederror",
        tree_method="hist",
        random_state=42,
        n_jobs=-1,
    ),
}

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

MLFLOW_EXPERIMENT_NAME = "paris-bike-traffic"

MODELS_DIR = Path("models")


def load_data():
    """
    Charge la table training_data depuis MySQL
    avec seulement les colonnes utilisées dans l'entraînement des modèles
    + la colonne 'Date et heure de comptage'.
    """
    engine = create_engine(DATABASE_URL)
    cols = FEATURE_COLS_NUM + FEATURE_COLS_CAT + [TARGET_COL, "Date et heure de comptage"]
    cols_sql = ", ".join(f"`{col}`" for col in cols)  # Les backticks `` protègent le nom des colonnes
    df = pd.read_sql(f"SELECT {cols_sql} FROM training_data", engine)
    return df


def prep_data(df):
    """
    Nettoie et divise les données en ensembles d'entraînement et de test.
    """
    for col in FEATURE_COLS_NUM:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Date et heure de comptage"] = pd.to_datetime(
        df["Date et heure de comptage"], errors="coerce"
    )

    df_clean = df.dropna(
        subset=FEATURE_COLS_NUM + FEATURE_COLS_CAT + [TARGET_COL, "Date et heure de comptage"]
    ).copy()
    
    df_clean = df_clean.sort_values("Date et heure de comptage")

    split = int(len(df_clean) * 0.8)
    train = df_clean.iloc[:split]
    test = df_clean.iloc[split:]

    X_train = train[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_train = train[TARGET_COL]
    X_test = test[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_test = test[TARGET_COL]
    
    date_ranges = {
        "train_start_date": str(train["Date et heure de comptage"].min()),
        "train_end_date": str(train["Date et heure de comptage"].max()),
        "test_start_date": str(test["Date et heure de comptage"].min()),
        "test_end_date": str(test["Date et heure de comptage"].max()),
    }

    return X_train, y_train, X_test, y_test, date_ranges


def build_pipeline(model_name, model):
    """
    Construit un pipeline sklearn avec prétraitement pour un modèle donné.
    """
    num_transformer = StandardScaler() if model_name == "lr" else "passthrough"

    preprocess = ColumnTransformer(
        transformers=[
            ("num", num_transformer, FEATURE_COLS_NUM),
            ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURE_COLS_CAT),
        ],
        remainder="drop",
    )

    return Pipeline(steps=[("prep", preprocess), ("model", model)])


def get_best_production_r2(model_name: str) -> float | None:
    """
    Récupère le R² du meilleur modèle en production pour un modèle donné.
    """
    client = (
        mlflow.MlflowClient()
    )  # Objet qui permet d'interagir avec le MLflow Model Registry
    registered_model_name = f"paris-bike-traffic-{model_name}"

    try:
        # Récupère toutes les versions du modèle avec l'alias 'production'
        version = client.get_model_version_by_alias(registered_model_name, "production")
        run = mlflow.get_run(version.run_id)
        return run.data.metrics.get("r2")
    except Exception:
        # Aucun modèle en production trouvé
        return None


def train(model_name: str = "lgbm"):
    """
    Entraîne un modèle, logge avec MLflow et promeut si meilleur.
    Retourne les métriques.
    """
    if model_name not in MODELS:
        raise ValueError(
            f"Modèle '{model_name}' inconnu. Valeurs acceptées : {list(MODELS.keys())}"
        )

    print(f"Chargement des données d'entraînement depuis la base de données MySQL...")
    df = load_data()
    print(f"{len(df)} lignes chargées.")

    print("Preprocessing des données en cours...")
    X_train, y_train, X_test, y_test, date_ranges = prep_data(df)

    # Création de l'expérience MLflow
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(run_name=f"train_{model_name}"):
        
        print("Logging des métadonnées des données...")
        mlflow.log_param("model_name", model_name)
        mlflow.log_param("train_size", len(X_train))
        mlflow.log_param("test_size", len(X_test))
        mlflow.log_param("data_rows_total", len(df))
        mlflow.log_params(date_ranges)
        mlflow.log_param("n_features", len(FEATURE_COLS_NUM) + len(FEATURE_COLS_CAT))
        
        print("Logging des hyperparamètres du modèle...")
        model = MODELS[model_name]
        params = model.get_params() if hasattr(model, "get_params") else {}
        mlflow.log_params(params)

        print(f"Entraînement du modèle {model_name}...")
        pipeline = build_pipeline(model_name, MODELS[model_name])
        pipeline.fit(X_train, y_train)

        print("Evaluation...")
        preds = pipeline.predict(X_test)
        mae = round(mean_absolute_error(y_test, preds), 4)
        rmse = round(root_mean_squared_error(y_test, preds), 4)
        r2 = round(r2_score(y_test, preds), 4)

        metrics = {
            "model": model_name,
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
        }

        print(f"Logging des métriques : {metrics}")
        mlflow.log_metric("mae", mae)
        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("r2", r2)

        registered_model_name = f"paris-bike-traffic-{model_name}"
        model_info = mlflow.sklearn.log_model(
            sk_model=pipeline,
            name=registered_model_name,
            registered_model_name=registered_model_name,
        )
        print(f"Modèle enregistré dans le MLflow Registry : {registered_model_name}")

        # Comparaison avec le modèle en production et promotion si meilleur
        client = mlflow.MlflowClient()
        new_version = model_info.registered_model_version

        best_r2 = get_best_production_r2(model_name)

        if best_r2 is None or r2 > best_r2:
            client.set_registered_model_alias(
                name=registered_model_name,
                alias="production",
                version=new_version
            )
            print(f"Nouveau modèle promu en production (R²: {r2} > {best_r2})")
        else:
            print(f"Modèle actuel conservé en production (R²: {best_r2} >= {r2})")
            
        MODELS_DIR.mkdir(exist_ok=True)
        model_path = MODELS_DIR / f"model_{model_name}.joblib"
        joblib.dump(pipeline, model_path)
        print(f"Modèle sauvegardé dans le chemin : {model_path}")

        return metrics


if __name__ == "__main__":
    model_name = sys.argv[1] if len(sys.argv) > 1 else "lgbm"
    train(model_name)