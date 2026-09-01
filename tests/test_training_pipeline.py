"""
Test d'intégration pour scripts/training.py (utilisé par l'endpoint /training).

Ce test part d'un jeu de données déjà prétraité par preprocess() (donc dans
le même format que ce que /load-db écrit en base), et vérifie que la chaîne
prep_data() -> build_pipeline() -> fit() -> predict() fonctionne réellement
de bout en bout et produit des métriques valides.

Seule la lecture MySQL (training.load_data()) est hors périmètre : c'est le
seul point du chemin /training qui nécessite une base de données réelle.
Tout le reste (split, pipeline, entraînement, évaluation) est exécuté tel
quel, sans mock.
"""
from pathlib import Path

import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error, r2_score

from scripts.preprocess import preprocess
from scripts.training import MODELS, build_pipeline, prep_data

VACANCES_PATH = Path("data/raw/vacances-scolaires-2023-2027.csv")
WEATHER_PATH = Path("data/raw/open-meteo-48.82N2.29E43m.csv")

DROPPED_COLUMNS = [
    "Identifiant du compteur", "Identifiant du site de comptage",
    "Date d'installation du site de comptage", "Identifiant technique compteur", "ID Photos",
    "test_lien_vers_photos_du_site_de_comptage_", "id_photo_1", "url_sites",
    "type_dimage", "mois_annee_comptage", "Lien vers photo du site de comptage"
]


def build_raw_csv(path: Path, n_hours: int = 250):
    """
    250h consécutives pour 1 compteur : suffisant pour que lag_24h et lag_168h
    (qui nécessitent respectivement 24h et 168h d'historique) aient de vraies
    valeurs sur une partie des lignes, condition nécessaire pour que prep_data()
    conserve des lignes après son dropna().
    """
    rows = []
    for h in range(n_hours):
        ts = (pd.Timestamp("2024-01-01T00:00") + pd.Timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
        row = {col: "" for col in DROPPED_COLUMNS}
        row["Nom du compteur"] = "Compteur Test A [Bike IN]"
        row["Nom du site de comptage"] = "Site Test"
        row["Date et heure de comptage"] = ts
        row["Comptage horaire"] = 10 + (h % 24)  # motif horaire périodique, simple et déterministe
        row["Coordonnées géographiques"] = "48.8566,2.3522"
        rows.append(row)

    pd.DataFrame(rows).to_csv(path, sep=";", index=False)


@pytest.fixture(scope="module")
def preprocessed_training_data(tmp_path_factory):
    """Génère des données déjà prétraitées, dans le même format que training_data en base."""
    tmp_dir = tmp_path_factory.mktemp("training_integration")
    raw_path = tmp_dir / "raw_counters_training.csv"
    output_path = tmp_dir / "df_processed.csv"

    build_raw_csv(raw_path)

    preprocess(
        raw_data_path=raw_path,
        vacances_path=VACANCES_PATH,
        weather_path=WEATHER_PATH,
        processed_data_path=output_path,
    )

    return pd.read_csv(output_path)


def test_prep_data_produces_clean_temporal_split(preprocessed_training_data):
    """
    prep_data() doit produire un split train/test sans NaN, avec toutes les
    lignes du train strictement antérieures à celles du test (aucun horodatage
    scindé entre les deux, comme documenté dans training.py).
    """
    X_train, y_train, X_test, y_test, date_ranges, clean_size = prep_data(preprocessed_training_data)

    assert clean_size > 0
    assert len(X_train) > 0
    assert len(X_test) > 0
    assert len(X_train) + len(X_test) == clean_size

    assert not X_train.isna().any().any()
    assert not X_test.isna().any().any()

    assert pd.Timestamp(date_ranges["train_end_date"]) < pd.Timestamp(date_ranges["test_start_date"])


def test_pipeline_trains_and_evaluates_successfully(preprocessed_training_data):
    """
    Le pipeline par défaut (lgbm, comme dans training.train()) doit s'entraîner
    et produire des métriques valides (ni NaN, ni erreur) sur des données
    réellement prétraitées.
    """
    X_train, y_train, X_test, y_test, _, _ = prep_data(preprocessed_training_data)

    pipeline = build_pipeline("lgbm", MODELS["lgbm"])
    pipeline.fit(X_train, y_train)
    preds = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, preds)
    r2 = r2_score(y_test, preds)

    assert mae >= 0
    assert not pd.isna(mae)
    assert r2 <= 1.0 + 1e-6
    assert not pd.isna(r2)


def test_all_registered_models_can_fit_without_error(preprocessed_training_data):
    """
    Chaque modèle défini dans training.MODELS doit pouvoir s'entraîner sans
    erreur avec le pipeline correspondant (le prétraitement diffère selon le
    modèle : StandardScaler uniquement pour la régression linéaire).
    """
    X_train, y_train, _, _, _, _ = prep_data(preprocessed_training_data)

    for model_name, model in MODELS.items():
        pipeline = build_pipeline(model_name, model)
        pipeline.fit(X_train, y_train)  # ne doit lever aucune exception