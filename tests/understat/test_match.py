import pytest
import pandas as pd
import requests

from football_scraper.providers.understat.client import UnderstatClient
from football_scraper.providers.understat.match import UnderstatMatchScraper

@pytest.fixture
def client():
    session = requests.Session()
    return UnderstatMatchScraper(session=session)

def test_extract_lineups(client):
    url_match = "https://understat.com/match/29479"

    df = client.extract_lineups(url_match)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No lineup data returned")

    expected_cols = ["player_url", "team_url", "team_name"]
    for col in expected_cols:
        assert col in df.columns

    assert df["player_url"].str.contains("player").any()

def test_extract_match_stats(client):
    url_match = "https://understat.com/match/29479"

    df = client.extract_match_stats(url_match)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No match stats returned")

    expected_cols = ["stat", "home", "away","home_pct", "away_pct"]
    for col in expected_cols:
        assert col in df.columns

    assert df["stat"].notna().all()

def test_extract_shotmap_match(client):
    url_match = "https://understat.com/match/29479"

    df = client.extract_shotmap(url_match)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No shotmap data returned")

    expected_cols = [ "match_url", "player_url","team_local_url", "team_away_url"]
    for col in expected_cols:
        assert col in df.columns

    assert df["xG"].notna().all()

def test_extract_timing_chart(client):
    url_match = "https://understat.com/match/29479"

    result = client.extract_timing_chart(url_match)

    assert isinstance(result, tuple)
    assert len(result) == 5

    df, df_home, goals_home, df_away, goals_away = result

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df_home, pd.DataFrame)
    assert isinstance(goals_home, pd.DataFrame)
    assert isinstance(df_away, pd.DataFrame)
    assert isinstance(goals_away, pd.DataFrame)

    if df.empty:
        pytest.skip("No timing chart data")

def test_plot_timing_chart(client):
    url_match = "https://understat.com/match/29479"

    fig = client.plot_timing_chart(url_match)

    import matplotlib.figure
    assert isinstance(fig, matplotlib.figure.Figure)
