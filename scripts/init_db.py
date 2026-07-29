import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Nécessite un fichier .env à la racine (MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_DB)
load_dotenv()

# Construction de l'URL de connexion MySQL à partir des variables d'environnement
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)

# Chemin vers le fichier CSV des données d'entraînement traitées
CSV_PATH = Path("data/processed/df_processed.csv")


def init_db():
    """
    Lecture des données d'entraînement et écriture dans la base de données MySQL
    """
    print("Import des données d'entraînement traitées en cours...")
    df = pd.read_csv(CSV_PATH)
    print(f"{len(df)} lignes et {len(df.columns)} colonnes chargées.")

    print("Connexion à la base de données MySQL...")
    engine = create_engine(DATABASE_URL)

    print("Écriture des données dans la table training_data...")
    df.to_sql("training_data", engine, if_exists="replace", index=False)
    # index=False évite l'ajout d'une colonne index

    # Vérification du nombre de lignes insérées
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM training_data")).scalar()
    print(f"Terminé ! {count} lignes écrites.")


if __name__ == "__main__":
    init_db()