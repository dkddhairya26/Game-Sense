import pandas as pd
import pytest
from gamesense.analytics import clean_data, rankings, recent_form
from gamesense.demo import demo_data

def test_all_sports_demo():
    for sport in ['Soccer','NBA','AFL','F1']:
        cleaned, report = clean_data(demo_data(sport), sport)
        assert len(cleaned) == 360
        assert report['duplicates_removed'] == 0
        assert len(rankings(cleaned, sport)) == 5

def test_duplicate_and_invalid_date_removed():
    data = pd.DataFrame([{'date':'2025-01-01','season':2025,'competitor':'A','team':'T','points':12}, {'date':'2025-01-01','season':2025,'competitor':'A','team':'T','points':12}, {'date':'bad','season':2025,'competitor':'B','team':'T','points':8}])
    clean, report = clean_data(data, 'NBA')
    assert len(clean) == 1
    assert report['duplicates_removed'] == 1
    assert report['invalid_rows_removed'] == 1

def test_missing_metrics_not_zero():
    df = pd.DataFrame([{'date':'2025-01-01','season':2025,'competitor':'A','team':'T'}])
    clean, _ = clean_data(df, 'NBA')
    assert pd.isna(clean.iloc[0]['rating'])
    assert recent_form(clean, 'A') is None

def test_missing_required_columns_rejected():
    with pytest.raises(ValueError, match='Missing required'):
        clean_data(pd.DataFrame({'competitor':['A']}), 'F1')
