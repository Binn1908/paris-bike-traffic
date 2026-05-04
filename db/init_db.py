import os
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Chargement des variables d'environnement depuis le fichier .env
load_dotenv()

# Chemin vers le fichier CSV des données d'entraînement traitées
CSV_PATH = Path("data/processed/df_processed.csv")

# Construction de l'URL de connexion MySQL à partir des variables d'environnement
DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
    f"@{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT')}/{os.getenv('MYSQL_DB')}"
)


def init_db():
    # Lecture du fichier CSV contenant les données traitées
    print("Lecture des données d'entraînement traitées en cours...")
    df = pd.read_csv(CSV_PATH)
    print(f"{len(df)} lignes et {len(df.columns)} colonnes chargées")

    # Connexion à la base de données MySQL
    print("Connexion à la base de données MySQL...")
    engine = create_engine(DATABASE_URL)

    # Écriture des données dans la table training_data (remplacement si elle existe déjà)
    print("Écriture des données dans la table training_data...")
    df.to_sql("training_data", engine, if_exists="replace", index=False)

    # Vérification du nombre de lignes insérées
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM training_data")).scalar()
    print(f"Terminé ! {count} lignes écrites dans la table training_data")


if __name__ == "__main__":
    init_db()
