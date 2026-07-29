from pathlib import Path

import pandas as pd

# Emplacement des fichiers sources et du fichier de sortie, relatifs à la racine du projet
RAW_DATA_PATH = Path("data/raw/comptage-velo-donnees-compteurs.csv")
VACANCES_PATH = Path("data/raw/vacances-scolaires-2023-2026.csv")
WEATHER_PATH = Path("data/raw/open-meteo-48.82N2.29E43m.csv")
PROCESSED_DATA_PATH = Path("data/processed/df_processed.csv")


def load_data(raw_data_path=RAW_DATA_PATH, vacances_path=VACANCES_PATH, weather_path=WEATHER_PATH):
    """
    Charge les fichiers sources et convertit les colonnes de dates en objets datetime.
    """
    df = pd.read_csv(raw_data_path, sep=";")

    # Suppression des colonnes inutiles
    col_a_supprimer = [
        "Identifiant du compteur", "Identifiant du site de comptage",
        "Date d'installation du site de comptage", "Identifiant technique compteur", "ID Photos",
        "test_lien_vers_photos_du_site_de_comptage_", "id_photo_1", "url_sites",
        "type_dimage", "mois_annee_comptage", "Lien vers photo du site de comptage"
    ]
    df.drop(col_a_supprimer, axis=1, inplace=True)

    # Conversion de 'Date et heure de comptage' en format datetime et heure locale
    df["Date et heure de comptage"] = (
        pd.to_datetime(df["Date et heure de comptage"], utc=True)
        .dt.tz_convert("Europe/Paris")
        .dt.tz_localize(None)
    )

    # Importation du dataset relatif aux vacances scolaires
    df_vacances_scolaires = pd.read_csv(
        vacances_path,
        sep=";",
        parse_dates=["Date"],
        dayfirst=True,
        encoding="latin-1"
    )

    # Importation du dataset avec des données météorologiques
    df_weather = pd.read_csv(weather_path, header=2)
    
    df_weather["Date et heure de comptage"] = (
        pd.to_datetime(df_weather["time"], utc=True)
        .dt.tz_convert("Europe/Paris")
        .dt.tz_localize(None)
    )
    
    df_weather.drop("time", axis=1, inplace=True)
    
    df_weather = df_weather.rename(columns={
        "temperature_2m (°C)": "Température (°C)",
        "precipitation (mm)": "Précipitations (mm)",
    })

    return df, df_vacances_scolaires, df_weather


def remove_outliers(df):
    """
    Supprime les lignes dont le comptage horaire dépasse un seuil jugé aberrant.
    """
    df = df[df["Comptage horaire"] < 1500]
    
    return df


def deduplicate(df):
    """
    Supprime les doublons (même compteur, même horodatage).
    """
    df = df.drop_duplicates(subset=["Nom du compteur", "Date et heure de comptage"])
    
    return df


def add_direction(df):
    """
    Crée une colonne avec le sens de la voie, extrait du nom du compteur.
    """
    df["Direction"] = df["Nom du compteur"].str.extract(
        r"(Bike IN|Bike OUT|E-O|O-E|N-S|S-N|NE-SO|SO-NE|NO-SE|SE-NO)"
    )
    
    return df


def add_coordinates(df):
    """
    Extrait la latitude et la longitude de la colonne 'Coordonnées géographiques'
    et les convertit en valeurs numériques.
    """
    df[["Latitude", "Longitude"]] = df["Coordonnées géographiques"].str.split(",", expand=True)
    
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    
    df.drop("Coordonnées géographiques", axis=1, inplace=True)
    
    return df


def add_weather_features(df, df_weather):
    """
    Enrichit le dataset principal avec la température et les précipitations horaires.
    """
    df = df.merge(df_weather, on="Date et heure de comptage", how="left")
    
    return df


def fill_nan(df):
    """
    Gère les valeurs manquantes identifiées lors de l'exploration des données.
    """
    # Compléter les lignes vides dans la colonne 'Nom du site de comptage'
    replace_nan = {
        "27 quai de la Tournelle": "27 quai de la Tournelle",
        "Grande Armée": "10 avenue de la Grande Armée",
        "Face au 48 quai de la marne": "Face au 48 quai de la marne",
        "Pont des Invalides": "Pont des Invalides",
        "Quai des Tuileries": "Quai des Tuileries",
        "Totem 64 Rue de Rivoli": "Totem 64 Rue de Rivoli",
    }
    for value, remplacement in replace_nan.items():
        mask = df["Nom du site de comptage"].isna() & df["Nom du compteur"].str.contains(value, na=False)
        df.loc[mask, "Nom du site de comptage"] = remplacement

    # Compléter les lignes potentiellement vides dans la colonne 'Direction'
    df["Direction"] = df["Direction"].fillna("N/A")

    # Compléter les lignes vides dans les colonnes 'Latitude' et 'Longitude'
    df["Latitude"] = df.groupby("Nom du site de comptage")["Latitude"].transform(lambda row: row.ffill().bfill())
    df["Longitude"] = df.groupby("Nom du site de comptage")["Longitude"].transform(lambda row: row.ffill().bfill())

    # Remplir les lignes vides de température/précipitations avec la moyenne du jour
    df["Date"] = df["Date et heure de comptage"].dt.date
    
    df_weather_means = df.groupby("Date")[["Température (°C)", "Précipitations (mm)"]].mean().rename(columns={
        "Température (°C)": "Température_moy_jour",
        "Précipitations (mm)": "Précipitations_moy_jour",
    })
    
    df = df.merge(df_weather_means, on="Date", how="left")
    
    df["Température (°C)"] = df["Température (°C)"].fillna(df["Température_moy_jour"])
    df["Précipitations (mm)"] = df["Précipitations (mm)"].fillna(df["Précipitations_moy_jour"])
    
    df.drop(columns=["Date", "Température_moy_jour", "Précipitations_moy_jour"], inplace=True)

    df = df.dropna(subset=["Nom du compteur", "Nom du site de comptage", "Comptage horaire", "Date et heure de comptage"])

    return df


def add_calendar_features(df, df_vacances_scolaires):
    """
    Génère des features calendaires, un indicateur de vacances scolaires,
    puis des lags (1h, 24h, 168h) et une moyenne glissante sur 3h.
    """
    df["Jour du mois"] = df["Date et heure de comptage"].dt.day
    df["Mois"] = df["Date et heure de comptage"].dt.month
    df["Année"] = df["Date et heure de comptage"].dt.year
    df["Heure"] = df["Date et heure de comptage"].dt.hour
    df["Jour de la semaine"] = df["Date et heure de comptage"].dt.dayofweek
    df["Week-end"] = (df["Date et heure de comptage"].dt.dayofweek >= 5).astype(int)

    # Création de la variable 'Vacances'
    df["Date"] = pd.to_datetime(df["Date et heure de comptage"]).dt.date
    df_vacances_scolaires["Date"] = df_vacances_scolaires["Date"].dt.date
    vacances_set = set(df_vacances_scolaires["Date"])
    df["Vacances"] = (df["Date"].isin(vacances_set)).astype(int)
    df.drop(["Date"], axis=1, inplace=True)

    # Création des lags et de la moyenne glissante, par compteur
    df = df.sort_values(["Nom du compteur", "Date et heure de comptage"]).copy()

    df["lag_1h"] = df.groupby("Nom du compteur")["Comptage horaire"].shift(1)
    df["lag_24h"] = df.groupby("Nom du compteur")["Comptage horaire"].shift(24)
    df["lag_168h"] = df.groupby("Nom du compteur")["Comptage horaire"].shift(168)

    df["roll_mean_3h"] = (
        df.groupby("Nom du compteur")["Comptage horaire"]
        .shift(1)
        .rolling(window=3)
        .mean()
    )

    return df


def overwrite_data(df):
    """
    Harmonise les coordonnées de trois sites spécifiques.
    """
    coordonnees_ref = {
        "Pont National": (48.82639, 2.38448),
        "Pont de la Concorde": (48.86373, 2.31973),
        "Pont du Garigliano": (48.83994, 2.26692),
    }
    for site, coordonnees in coordonnees_ref.items():
        df.loc[df["Nom du site de comptage"] == site, ["Latitude", "Longitude"]] = coordonnees

    return df


def preprocess_raw_data(
    raw_data_path=RAW_DATA_PATH,
    vacances_path=VACANCES_PATH,
    weather_path=WEATHER_PATH,
    processed_data_path=PROCESSED_DATA_PATH,
):
    """
    Chaîne toutes les étapes de prétraitement et écrit df_processed.csv.
    """
    print("Chargement des fichiers sources...")
    df, df_vacances_scolaires, df_weather = load_data(raw_data_path, vacances_path, weather_path)
    print(f"{len(df)} lignes chargées.")

    print("Suppression des valeurs aberrantes et des doublons...")
    df = remove_outliers(df)
    df = deduplicate(df)

    print("Enrichissement géographique...")
    df = add_direction(df)
    df = add_coordinates(df)

    print("Fusion avec les données météorologiques...")
    df = add_weather_features(df, df_weather)

    print("Gestion des valeurs manquantes...")
    df = fill_nan(df)

    print("Ajout des variables calendaires et des lags...")
    df = add_calendar_features(df, df_vacances_scolaires)

    print("Harmonisation des sites spécifiques...")
    df = overwrite_data(df)

    print(f"Écriture du dataset prétraité dans {processed_data_path}...")
    processed_data_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(processed_data_path, index=False, encoding="utf-8")
    print(f"{len(df)} lignes enregistrées dans le fichier CSV.")


if __name__ == "__main__":
    preprocess_raw_data()