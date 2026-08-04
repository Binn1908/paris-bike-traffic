import shutil
from datetime import datetime
from pathlib import Path

RAW_DATA_FOLDER = Path("data/raw")
CHUNK_PATTERN = "comptage-velo-donnees-compteurs-*.csv"
FINAL_RAW_FILE = RAW_DATA_FOLDER / "comptage-velo-donnees-compteurs.csv"
# Nom fixe attendu par preprocess() — indépendant de la date du chunk ingéré

DATE_FORMAT = "%d.%m.%Y"


def extract_date(path: Path) -> datetime:
    """
    Extrait la date de fin de chunk à partir du nom de fichier
    (ex: comptage-velo-donnees-compteurs-13.06.2026.csv -> 13/06/2026).
    """
    date_str = path.stem.removeprefix("comptage-velo-donnees-compteurs-")
    return datetime.strptime(date_str, DATE_FORMAT)


def find_latest_chunk() -> Path:
    """
    Scanne le dossier des données brutes et retourne le chunk le plus récent
    (date la plus tardive dans le nom de fichier).
    """
    chunks = list(RAW_DATA_FOLDER.glob(CHUNK_PATTERN))
    if not chunks:
        raise FileNotFoundError("Aucun fichier de chunk trouvé dans data/raw.")

    return max(chunks, key=extract_date)


def ingest() -> str:
    """
    Sélectionne le chunk le plus récent et en crée une copie sous un nom fixe,
    afin que preprocess() puisse le retrouver au même emplacement.
    Le fichier daté d'origine reste inchangé dans data/raw.
    """
    latest_chunk = find_latest_chunk()
    print(f"Chunk le plus récent trouvé : {latest_chunk.name}")

    shutil.copy2(latest_chunk, FINAL_RAW_FILE)
    print(f"Copié vers : {FINAL_RAW_FILE.name}")

    return latest_chunk.name


if __name__ == "__main__":
    ingest()