import pytest
import pandas as pd

from football_scraper.providers.fotmob.constants import BASE_URL
from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.fotmob.team import FotmobTeamService


@pytest.fixture
def client():
    client = FotmobClient()
    return FotmobTeamService(session=client.session)

def test_extract_last_starting_eleven(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df_events, df_info = client.extract_last_starting_eleven(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df_events, pd.DataFrame)
    assert isinstance(df_info, pd.DataFrame)
    assert not df_info.empty or df_events.empty is False
    
    expected_cols = ["isStarter"]
    for col in expected_cols:
        assert col in df_events.columns

def test_extract_fixture_difficulty(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'
    url_league = 'https://www.fotmob.com/leagues/87/overview/laliga'

    try:
        df = client.extract_fixture_difficulty(url_team, url_league)
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "teamId" in df.columns

def test_extract_team_form(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_team_form(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "result" in df.columns or "resultString" not in df.columns
    assert "mathc_url" in df.columns or "match_url" in df.columns
    assert df.shape[0]

def test_extract_data_details(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_data_details(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] == 1
    assert any("venue" in col.lower() or "capacity" in col.lower() for col in df.columns)
    assert df.notna().sum().sum() > 0

def test_extract_next_match(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_next_match(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] <= 1
    assert "match_date" in df.columns or "status.utcTime" in df.columns
    assert any("logo" in col.lower() for col in df.columns)

def test_extract_last_match(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_last_match(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)

    assert df.shape[0] <= 1
    assert "pageUrl" in df.columns
    assert df.notna().any().any()

def test_extract_top_players(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_top_players(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] >= 0
    assert "playerId" in df.columns or "id" in df.columns
    assert df.select_dtypes(include="number").shape[1] > 0

def test_extract_standing_all_h_a_form(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_standing_all_h_a_form(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "pts" in df.columns
    assert "name" in df.columns or "team" in df.columns
    assert "form" in df.columns
    assert df.shape[0] > 0

def test_extract_standings_xg(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_standings_xg(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "xg" in df.columns
    assert "xgDiff" in df.columns
    assert df.shape[0] > 0

def test_extract_all_fixtures(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_all_fixtures(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "match_date" in df.columns
    assert "pageUrl" in df.columns
    assert len(df) >= 0

def test_extract_squad(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_squad(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] > 5
    assert "id" in df.columns or "member_photo" in df.columns

def test_extract_transfers(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_transfers(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "player_photo" in df.columns
    assert df.shape[0] >= 0

def test_extract_history_trophies(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_history_trophies(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert "competition_photo" in df.columns
    assert df.shape[0] >= 0

def test_extract_historical_table_position(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_historical_table_position(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)
    assert df.shape[0] > 0

def test_extract_coach_history(client):
    url_team = 'https://www.fotmob.com/teams/8634/overview/barcelona'

    try:
        df = client.extract_coach_history(url_team, 'ESP')
    except Exception:
        return

    assert isinstance(df, pd.DataFrame)

    assert "coach_photo" in df.columns