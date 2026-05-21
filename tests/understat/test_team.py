import pytest
import pandas as pd

from football_scraper.providers.understat.constants import BASE_URL
from football_scraper.providers.understat.client import UnderstatClient
from football_scraper.providers.understat.team import UnderstatTeamScraper


@pytest.fixture
def client():
    client = UnderstatClient()
    return UnderstatTeamScraper(session=client.session)


def test_extract_players(client):
    df = client.extract_players('Barcelona', '2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No players data returned")

    expected_cols = [ "id", "player_name", "team_title", "position","player_url", "team_url"]

    for col in expected_cols:
        assert col in df.columns

    assert df["player_name"].notna().all()
    assert df["player_url"].str.contains("player").all()

def test_extract_team_matches(client):
    df = client.extract_matches('Barcelona', '2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No matches data returned")

    expected_cols = [
        "match_date", "match_time", "match_url",
        "team_local_url", "team_away_url"
    ]

    for col in expected_cols:
        assert col in df.columns

    assert df["match_url"].str.contains("match").all()
    assert df["team_local_url"].str.contains("team").all()
    assert df["team_away_url"].str.contains("team").all()

    assert df["match_date"].notna().all()
    assert df["match_time"].notna().all()

def _assert_stats_df(df, key_column):
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No stats data returned")

    assert key_column in df.columns

    base_cols = [ "shots", "goals", "xG", "against_shots", "against_goals", "against_xG"]

    for col in base_cols:
        assert col in df.columns

    assert "xGD" in df.columns

def test_extract_stats_situation(client):
    df = client.extract_stats_situation('Barcelona', '2025')

    _assert_stats_df(df, "situation")

    assert "xG/Sh" in df.columns
    assert "xGA/ShA" in df.columns

def test_extract_stats_attack_speed(client):
    df = client.extract_stats_attack_speed('Barcelona', '2025')

    _assert_stats_df(df, "attack_speed")

def test_extract_stats_formation(client):
    df = client.extract_stats_formation('Barcelona', '2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No formation stats")

    assert "formation" in df.columns
    assert "xG90" in df.columns
    assert "xGA90" in df.columns

def test_extract_stats_game_state(client):
    df = client.extract_stats_game_state('Barcelona', '2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No game state stats")

    assert "game_state" in df.columns
    assert "xG90" in df.columns

def test_extract_stats_result(client):
    df = client.extract_stats_result('Barcelona', '2025')

    _assert_stats_df(df, "result_type")

def test_extract_stats_shot_zone(client):
    df = client.extract_stats_shot_zone('Barcelona', '2025')

    _assert_stats_df(df, "shot_zone")

def test_extract_stats_timing(client):
    df = client.extract_stats_timing('Barcelona', '2025')

    _assert_stats_df(df, "timing")

def test_extract_stats_player_team(client):
    df = client.extract_stats_player_team('Barcelona', '2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No player stats returned")

    expected_cols = [
        "Player", "Team", "Apps", "Min", "G", "NPG", "A",
        "xG", "NPxG", "xA",
        "xG90", "NPxG90", "xA90",
        "xG90 + xA90", "NPxG90 + xA90",
        "player_url", "team_url"
    ]
    for col in expected_cols:
        assert col in df.columns

    assert df["Player"].notna().all()
    assert df["Team"].notna().all()
    assert df["player_url"].str.contains("player").all()
    assert df["team_url"].str.contains( '2025').all()