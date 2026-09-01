"""
Test d'intégration pour scripts/preprocess.py (utilisé par l'endpoint /load-db).

Contrairement à des tests unitaires isolant chaque fonction, ce test fait
tourner preprocess() dans son intégralité, sur un petit fichier de données
brutes fabriqué pour l'occasion. Les fichiers météo et vacances scolaires
utilisés sont les vrais fichiers du dépôt (data/raw/), puisqu'ils sont
versionnés dans git et donc disponibles tels quels en CI. Seul le fichier
de comptage vélo est fabriqué : le vrai fichier est trop volumineux et
exclu de git (voir data/raw/README.md).

Objectif : vérifier que le prétraitement produit un résultat correct de
bout en bout (suppression des valeurs aberrantes, déduplication,
enrichissement géographique et météo, variable vacances, lags) sur des
données dont on connaît la valeur attendue à l'avance.
"""
from pathlib import Path

import pandas as pd
import pytest

from scripts.preprocess import preprocess

VACANCES_PATH = Path("data/raw/vacances-scolaires-2023-2027.csv")
WEATHER_PATH = Path("data/raw/open-meteo-48.82N2.29E43m.csv")

DROPPED_COLUMNS = [
    "Identifiant du compteur", "Identifiant du site de comptage",
    "Date d'installation du site de comptage", "Identifiant technique compteur", "ID Photos",
    "test_lien_vers_photos_du_site_de_comptage_", "id_photo_1", "url_sites",
    "type_dimage", "mois_annee_comptage", "Lien vers photo du site de comptage"
]


def build_raw_csv(path: Path):
    """
    Fabrique un petit fichier de comptage vélo brut couvrant :
    - 6h consécutives pour 2 compteurs, en période de vacances scolaires (1er-8 janvier 2024)
    - 1 ligne hors vacances (15 janvier 2024)
    - 1 ligne aberrante (Comptage horaire >= 1500) à supprimer
    - 1 doublon exact (même compteur, même horodatage qu'une ligne existante) à dédupliquer
    """
    rows = []

    def add(counter, ts, count, coords="48.8566,2.3522"):
        row = {col: "" for col in DROPPED_COLUMNS}
        row["Nom du compteur"] = counter
        row["Nom du site de comptage"] = "Site Test"
        row["Date et heure de comptage"] = ts
        row["Comptage horaire"] = count
        row["Coordonnées géographiques"] = coords
        rows.append(row)

    for h in range(6):
        ts = f"2024-01-01T{h:02d}:00"
        add("Compteur Test A [Bike IN]", ts, 10 + h)
        add("Compteur Test B [Bike OUT]", ts, 20 + h)

    add("Compteur Test A [Bike IN]", "2024-01-15T08:00", 50)  # hors vacances
    add("Compteur Test A [Bike IN]", "2024-01-01T06:00", 5000)  # aberrant
    add("Compteur Test A [Bike IN]", "2024-01-01T00:00", 999)  # doublon

    pd.DataFrame(rows).to_csv(path, sep=";", index=False)


@pytest.fixture(scope="module")
def preprocessed_output(tmp_path_factory):
    """Exécute preprocess() une seule fois et partage le résultat entre les tests."""
    tmp_dir = tmp_path_factory.mktemp("preprocess_integration")
    raw_path = tmp_dir / "raw_counters_sample.csv"
    output_path = tmp_dir / "df_processed.csv"

    build_raw_csv(raw_path)

    preprocess(
        raw_data_path=raw_path,
        vacances_path=VACANCES_PATH,
        weather_path=WEATHER_PATH,
        processed_data_path=output_path,
    )

    return pd.read_csv(output_path, parse_dates=["Date et heure de comptage"])


def test_outliers_removed_and_rows_deduplicated(preprocessed_output):
    """15 lignes brutes -> 14 après suppression de l'aberrante -> 13 après déduplication."""
    assert len(preprocessed_output) == 13
    assert preprocessed_output["Comptage horaire"].max() < 1500


def test_expected_columns_present_and_metadata_columns_dropped(preprocessed_output):
    for col in ["Direction", "Latitude", "Longitude", "Température (°C)", "Vacances", "lag_1h"]:
        assert col in preprocessed_output.columns

    for col in DROPPED_COLUMNS:
        assert col not in preprocessed_output.columns


def test_direction_and_coordinates_correctly_extracted(preprocessed_output):
    row = preprocessed_output[preprocessed_output["Nom du compteur"] == "Compteur Test B [Bike OUT]"].iloc[0]

    assert row["Direction"] == "Bike OUT"
    assert row["Latitude"] == pytest.approx(48.8566)
    assert row["Longitude"] == pytest.approx(2.3522)


def test_vacances_flag_matches_real_reference_file(preprocessed_output):
    """1er janvier 2024 est en vacances de Noël, le 15 janvier ne l'est pas."""
    jan_1 = preprocessed_output[preprocessed_output["Date et heure de comptage"].dt.date.astype(str) == "2024-01-01"]
    jan_15 = preprocessed_output[preprocessed_output["Date et heure de comptage"].dt.date.astype(str) == "2024-01-15"]

    assert (jan_1["Vacances"] == 1).all()
    assert (jan_15["Vacances"] == 0).all()


def test_lag_1h_matches_previous_hour_per_counter(preprocessed_output):
    """Pour un compteur donné, lag_1h à l'heure H doit correspondre au Comptage horaire de l'heure H-1."""
    counter_a = preprocessed_output[
        preprocessed_output["Nom du compteur"] == "Compteur Test A [Bike IN]"
    ].sort_values("Date et heure de comptage").reset_index(drop=True)

    # Première ligne du compteur : pas d'heure précédente disponible -> NaN
    assert pd.isna(counter_a.loc[0, "lag_1h"])

    # Les 5 lignes suivantes sont consécutives (01h à 05h) : lag_1h = comptage de l'heure précédente
    for i in range(1, 6):
        assert counter_a.loc[i, "lag_1h"] == counter_a.loc[i - 1, "Comptage horaire"]