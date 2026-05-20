import pytest
import pandas as pd
import requests

from providers.scoresway.post_match import ScoreswayPostMatchScraper

url= "https://www.scoresway.com/en_GB/soccer/primera-divisi%C3%B3n-2025-2026/80zg2v1cuqcfhphn56u4qpyqc/match/view/3rpa9gg887sphjnou8h1uv6s4/match-summary"


@pytest.fixture
def client():
    session = requests.Session()
    return ScoreswayPostMatchScraper(session)

def test_extract_match_info(client):

    df = client.extract_match_info(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "id_match" in df.columns

def test_extract_match_summary_ux(client):

    df = client.extract_match_summary_ux(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "event_type" in df.columns

def test_extract_key_events(client):
    goals_df, cards_df, subs_df = client.extract_key_events(url)

    assert isinstance(goals_df, pd.DataFrame)
    assert isinstance(cards_df, pd.DataFrame)
    assert isinstance(subs_df, pd.DataFrame)


    if not goals_df.empty:
        assert "contestantId" in goals_df.columns
        assert "scorerId" in goals_df.columns


    if not cards_df.empty:
        assert "playerId" in cards_df.columns
        assert "contestantId" in cards_df.columns

    if not subs_df.empty:
        assert "playerOnId" in subs_df.columns
        assert "playerOffId" in subs_df.columns

def test_extract_referees(client):

    df = client.extract_referees(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

def test_extract_home_formation(client):

    lineup, stats = client.extract_home_formation(url)

    assert isinstance(lineup, pd.DataFrame)
    assert isinstance(stats, pd.DataFrame)

    assert "playerId" in lineup.columns

def test_extract_away_formation(client):

    lineup, stats = client.extract_away_formation(url)

    assert isinstance(lineup, pd.DataFrame)
    assert isinstance(stats, pd.DataFrame)

    assert "playerId" in lineup.columns

def test_extract_player_stats_match_ux(client):
    df = client.extract_player_stats_match_ux(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0

    assert "player" in df.columns
    assert "team" in df.columns

def test_extract_team_kits(client):

    df = client.extract_team_kits(url)

    assert isinstance(df, pd.DataFrame)
    assert "side" in df.columns
    assert set(df["side"].unique()).issubset({"home", "away"})

def test_extract_match_stats(client):

    df = client.extract_match_stats(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "side" in df.columns

def test_extract_match_stats_ux(client):
    df = client.extract_match_stats_ux(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "category" in df.columns
    assert "stat" in df.columns
    assert "home" in df.columns
    assert "away" in df.columns

def test_extract_managers(client):

    df = client.extract_managers(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
