import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.types import Integer

# Nécessite un fichier .env à la racine (MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
load_dotenv()

# Construction de l'URL de connexion MySQL à partir des variables d'environnement
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)

# Chemin vers le fichier CSV des données d'entraînement traitées
CSV_PATH = Path("data/processed/df_processed.csv")

# Nom de la colonne de date utilisée pour filtrer les nouvelles lignes
DATE_COL = "Date et heure de comptage"


def get_existing_state(engine):
    """
    Récupère l'état actuel de la table training_data : la date la plus
    récente déjà présente et le dernier numéro de batch d'ingestion utilisé.

    Si la table n'existe pas encore ou si elle est vide,
    les deux valeurs retournées sont None.

    Retourne un tuple (max_date, max_batch).
    """
    with engine.connect() as conn:
        try:
            row_count = conn.execute(
                text("SELECT COUNT(*) FROM training_data")
            ).scalar()
        except (OperationalError, ProgrammingError):
            # La table n'existe pas encore : premier chargement
            print("Table training_data introuvable : premier chargement.")
            return None, None

        max_date = conn.execute(
            text(f"SELECT MAX(`{DATE_COL}`) FROM training_data")
        ).scalar()
        max_batch = conn.execute(
            text("SELECT MAX(batch) FROM training_data")
        ).scalar()

    print(f"Table training_data : {row_count} lignes, dernier batch = {max_batch}.")

    return max_date, max_batch


def load_db():
    """
    Lecture des données d'entraînement traitées et ajout des nouvelles
    lignes dans la table MySQL training_data, taguées avec un numéro de
    batch d'ingestion.

    Les lignes déjà présentes (dont la date ne dépasse pas le maximum déjà
    en base) sont ignorées, sauf lors du tout premier chargement où
    l'ensemble du fichier est inséré.
    """
    print("Connexion à la base de données MySQL...")
    engine = create_engine(DATABASE_URL)
    
    print("Vérification de l'état actuel de la table training_data...")
    max_date, max_batch = get_existing_state(engine)
    next_batch = 1 if max_batch is None else max_batch + 1

    print("Import des données d'entraînement traitées en cours...")
    df = pd.read_csv(CSV_PATH)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL])
    print(f"{len(df)} lignes et {len(df.columns)} colonnes lues depuis le CSV.")

    if max_date is None:
        # Premier chargement : aucune donnée existante
        df_new = df
    else:
        df_new = df[df[DATE_COL] > max_date]  # max_date est déjà en format datetime

    print(f"{len(df_new)} nouvelles lignes détectées pour le batch {next_batch}.")

    if len(df_new) == 0:
        print("Aucune nouvelle donnée à insérer.")
        return 0, max_batch

    df_new = df_new.copy()
    df_new["batch"] = next_batch

    print("Écriture des nouvelles lignes dans la table training_data...")
    df_new.to_sql(
        "training_data",
        engine,
        if_exists="append",
        index=False,
        dtype={"batch": Integer},
    )

    # Vérification du nombre total de lignes désormais en base
    with engine.connect() as conn:
        total_count = conn.execute(text("SELECT COUNT(*) FROM training_data")).scalar()
    print(f"Terminé ! {len(df_new)} lignes ajoutées, {total_count} lignes au total.")

    return len(df_new), next_batch


if __name__ == "__main__":
    load_db()