"""Reproducible, clearly fictional records for offline UI testing.
These are NOT real player performances and must not be cited as real sports data.
"""
from datetime import date, timedelta
import random
import pandas as pd
from .analytics import SPORTS

NAMES = {
    'Soccer': [('Alex Morganfield', 'North City'), ('Sam Rivera', 'North City'), ('Jordan Lee', 'Harbour FC'), ('Taylor Brooks', 'Harbour FC'), ('Casey Vale', 'United Athletic')],
    'NBA': [('Marcus Reed', 'Metro Hoops'), ('Devon Carter', 'Metro Hoops'), ('Chris Lane', 'Coastal Five'), ('Jayden Cole', 'Coastal Five'), ('Robin Hayes', 'Valley Basketball')],
    'AFL': [('Jack Wilson', 'Northern Eagles'), ('Liam Parker', 'Northern Eagles'), ('Noah Smith', 'Southern Lions'), ('Ethan Blake', 'Southern Lions'), ('Oliver Green', 'Western Magpies')],
    'F1': [('Aiden Cross', 'Apex Racing'), ('Leo Hart', 'Apex Racing'), ('Mason Quinn', 'Velocity GP'), ('Finn Archer', 'Velocity GP'), ('Riley Stone', 'Orbit Motorsport')],
}

def demo_data(sport: str) -> pd.DataFrame:
    rng = random.Random(700 + list(SPORTS).index(sport))
    rows = []
    for season in [2023, 2024, 2025, 2026]:
        for i in range(18):
            for competitor, team in NAMES[sport]:
                row = {'date': (date(season, 2, 1) + timedelta(days=i * 11)).isoformat(), 'season': season, 'competitor': competitor, 'team': team}
                if sport == 'Soccer':
                    row.update(goals=rng.randint(0, 3), assists=rng.randint(0, 2), shots=rng.randint(0, 7), passes=rng.randint(10, 90), tackles=rng.randint(0, 6))
                elif sport == 'NBA':
                    row.update(points=rng.randint(8, 44), rebounds=rng.randint(1, 17), assists=rng.randint(1, 15), steals=rng.randint(0, 5), blocks=rng.randint(0, 4))
                elif sport == 'AFL':
                    row.update(disposals=rng.randint(8, 40), marks=rng.randint(1, 14), tackles=rng.randint(0, 12), goals=rng.randint(0, 6), clearances=rng.randint(0, 12))
                else:
                    finish = rng.randint(1, 20)
                    row.update(points=[25,18,15,12,10,8,6,4,2,1][finish-1] if finish <= 10 else 0, finish_position=finish, grid_position=rng.randint(1, 20), laps=rng.randint(48, 72), fastest_lap=rng.randint(0, 1))
                rows.append(row)
    return pd.DataFrame(rows)
