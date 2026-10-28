"""Private, user-writable local SQLite cache for records and source attribution."""
from __future__ import annotations

import sqlite3
from pathlib import Path
import pandas as pd
from .analytics import SPORTS


def db_path() -> Path:
    path = Path.home() / "GameSenseData"
    path.mkdir(parents=True, exist_ok=True)
    return path / "gamesense.sqlite3"


def _table(sport: str) -> str:
    if sport not in SPORTS:
        raise ValueError("Invalid sport")
    return {"Soccer": "sport_soccer", "NBA": "sport_nba", "AFL": "sport_afl", "F1": "sport_f1"}[sport]


def save(sport: str, df: pd.DataFrame, source: str = "Imported data") -> None:
    table = _table(sport)
    with sqlite3.connect(db_path()) as con:
        df.to_sql(table, con, if_exists="replace", index=False)
        con.execute("CREATE TABLE IF NOT EXISTS sources (sport TEXT PRIMARY KEY, source TEXT NOT NULL)")
        con.execute("INSERT OR REPLACE INTO sources (sport, source) VALUES (?, ?)", (sport, source))


def load(sport: str) -> pd.DataFrame | None:
    table = _table(sport)
    with sqlite3.connect(db_path()) as con:
        try:
            return pd.read_sql_query('SELECT * FROM "' + table + '"', con)
        except (pd.errors.DatabaseError, sqlite3.DatabaseError):
            return None


def load_source(sport: str) -> str | None:
    _table(sport)
    with sqlite3.connect(db_path()) as con:
        try:
            row = con.execute("SELECT source FROM sources WHERE sport = ?", (sport,)).fetchone()
            return row[0] if row else None
        except sqlite3.DatabaseError:
            return None
