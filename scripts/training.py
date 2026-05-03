import sqlite3
import joblib
import pandas as pd
from pathlib import Path

from lightgbm import LGBMRegressor
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

DB_PATH = Path("db/paris_bike_traffic.db")
MODELS_DIR = Path("models")

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

MODELS = {
    "lr": LinearRegression(),
    "rf": RandomForestRegressor(
        n_jobs=-1,
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


def load_data():
    """Charge les données d'entraînement depuis la base de données SQLite."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM training_data", conn)
    conn.close()
    return df


def preprocess_data(df):
    """Nettoie et divise les données en ensembles d'entraînement et de test."""
    for col in FEATURE_COLS_NUM:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df_clean = df.dropna(
        subset=FEATURE_COLS_NUM + FEATURE_COLS_CAT + [TARGET_COL]
    ).copy()

    df_clean["Date et heure de comptage"] = pd.to_datetime(
        df_clean["Date et heure de comptage"], errors="coerce"
    )
    df_clean = df_clean.sort_values("Date et heure de comptage")

    split = int(len(df_clean) * 0.8)
    train = df_clean.iloc[:split]
    test = df_clean.iloc[split:]

    X_train = train[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_train = train[TARGET_COL]
    X_test = test[FEATURE_COLS_NUM + FEATURE_COLS_CAT]
    y_test = test[TARGET_COL]

    return X_train, X_test, y_train, y_test


def build_pipeline(model_name, model):
    """Construit un pipeline sklearn avec prétraitement pour un modèle donné. La régression linéaire utilise le StandardScaler, les autres modèles le passthrough."""
    num_transformer = StandardScaler() if model_name == "lr" else "passthrough"

    preprocess = ColumnTransformer(
        transformers=[
            ("num", num_transformer, FEATURE_COLS_NUM),
            ("cat", OneHotEncoder(handle_unknown="ignore"), FEATURE_COLS_CAT),
        ],
        remainder="drop",
    )

    return Pipeline(steps=[("prep", preprocess), ("model", model)])


def train(model_name: str = "lgbm"):
    """Entraîne un modèle et le sauvegarde sur disque. Retourne les métriques d'évaluation."""
    if model_name not in MODELS:
        raise ValueError(
            f"Modèle '{model_name}' inconnu. Valeurs acceptées : {list(MODELS.keys())}"
        )

    print(f"Chargement des données d'entraînement depuis la base de données SQLite...")
    df = load_data()
    print(f"{len(df)} lignes chargées")

    print("Preprocessing des données en cours...")
    X_train, X_test, y_train, y_test = preprocess_data(df)

    print(f"Entraînement du modèle {model_name}...")
    pipeline = build_pipeline(model_name, MODELS[model_name])
    pipeline.fit(X_train, y_train)

    print("Evaluation...")
    preds = pipeline.predict(X_test)
    metrics = {
        "model": model_name,
        "mae": round(mean_absolute_error(y_test, preds), 4),
        "rmse": round(root_mean_squared_error(y_test, preds), 4),
        "r2": round(r2_score(y_test, preds), 4),
    }

    MODELS_DIR.mkdir(exist_ok=True)
    model_path = MODELS_DIR / f"model_{model_name}.joblib"
    joblib.dump(pipeline, model_path)
    print(f"Modèle sauvegardé dans le chemin {model_path}")
    print(f"Métriques : {metrics}")

    return metrics


if __name__ == "__main__":
    import sys

    model_name = sys.argv[1] if len(sys.argv) > 1 else "lgbm"
    # Si aucun modèle n'est fourni, on entraîne lgbm par défaut.
    train(model_name)
