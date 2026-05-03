import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path("db/paris_bike_traffic.db")
CSV_PATH = Path("data/processed/df_processed.csv")


def init_db():
    print("Reading processed training data...")
    df = pd.read_csv(CSV_PATH)

    print(f"Loaded {len(df)} rows, {len(df.columns)} columns")

    print("Connecting to SQLite database...")
    conn = sqlite3.connect(DB_PATH)

    print("Writing to database...")
    df.to_sql("training_data", conn, if_exists="replace", index=False)

    # Verify
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM training_data")
    count = cursor.fetchone()[0]
    print(f"Done! {count} rows written to training_data table")

    conn.close()


if __name__ == "__main__":
    init_db()
