"""Offline check that all-history worker saves successes incrementally."""
import pandas as pd

from gamesense.window import DownloadWorker
from gamesense import window


def _season(year):
    return pd.DataFrame([{
        "date": f"{year}-05-01", "season": str(year),
        "competitor": "Actual mock record", "team": "Example GP",
        "points": 25, "finish_position": 1, "grid_position": 3,
        "laps": 55, "fastest_lap": 1, "record_type": "race",
    }])


def test_worker_emits_each_season_without_waiting_for_whole_archive(monkeypatch):
    monkeypatch.setattr(window,"fetch_season",
                        lambda sport,year,contact_email=None:
                        (_season(year),f"Jolpica F1 · {year} race results"))
    worker=DownloadWorker("F1",[2025,2024])
    ready=[]
    summaries=[]
    worker.season_ready.connect(lambda df,src: ready.append((df,src)))
    worker.completed.connect(summaries.append)
    worker.run()
    assert len(ready)==2
    assert ready[0][0]["season"].iloc[0]=="2025"
    assert ready[1][0]["season"].iloc[0]=="2024"
    assert "2 season" in summaries[0]


def test_worker_cancel_preserves_already_emitted_season(monkeypatch):
    monkeypatch.setattr(window,"fetch_season",
                        lambda sport,year,contact_email=None:
                        (_season(year),f"Jolpica F1 · {year} race results"))
    worker=DownloadWorker("F1",[2026,2025,2024])
    seen=[]
    def receive(df,source):
        seen.append(source)
        worker.cancel()
    worker.season_ready.connect(receive)
    worker.run()
    assert len(seen)==1
