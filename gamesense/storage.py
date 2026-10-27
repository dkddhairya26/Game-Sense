"""SQLite storage: a separate table per sport, preserving uploaded source records."""
from pathlib import Path
import sqlite3
import pandas as pd
from .analytics import SPORTS

def db_path() -> Path:
    path = Path.home() / 'GameSenseData'
    path.mkdir(parents=True, exist_ok=True)
    return path / 'gamesense.sqlite3'

def save(sport: str, df: pd.DataFrame) -> None:
    if sport not in SPORTS:
        raise ValueError('Invalid sport')
    with sqlite3.connect(db_path()) as con:
        df.to_sql('sport_' + sport.lower(), con, if_exists='replace', index=False)

def load(sport: str) -> pd.DataFrame | None:
    if sport not in SPORTS:
        raise ValueError('Invalid sport')
    with sqlite3.connect(db_path()) as con:
        try:
            return pd.read_sql_query('SELECT * FROM sport_' + sport.lower(), con)
        except pd.errors.DatabaseError:
            return None
