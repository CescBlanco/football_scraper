import pandas as pd
import pytest
import requests

from football_scraper.providers.espn.match import ESPNMatchScraper

@pytest.fixture
def client():
    session = requests.Session()

    return ESPNMatchScraper(session=session)

def test_extract_basic_info_invalid_url(client):
    
    with pytest.raises(ValueError, match="Match ID not found"):
        client.extract_basic_info("invalid-url")

def test_extract_basic_info_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df_match, df_events = client.extract_basic_info(url)

    assert isinstance(df_match, pd.DataFrame)
    assert isinstance(df_events, pd.DataFrame)

    assert not df_match.empty

    expected_columns = ["match_id","home_team","away_team","home_score","away_score",
        "competition","season","status", ]
    for col in expected_columns:
        assert col in df_match.columns

def test_extract_match_stats_invalid_url(client):

    with pytest.raises(ValueError):
        client.extract_match_stats("invalid-url")

def test_extract_match_stats_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df = client.extract_match_stats(url)

    assert isinstance(df, pd.DataFrame)

    assert not df.empty

    assert "stat" in df.columns
    assert "home" in df.columns
    assert "away" in df.columns

def test_extract_teams_form_invalid_url(client):

    with pytest.raises(ValueError):
        client.extract_teams_form_pre_match("invalid-url")

def test_extract_teams_form_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df = client.extract_teams_form_pre_match(url)

    assert isinstance(df, pd.DataFrame)

    assert not df.empty

    expected_columns = [ "match_id", "team", "result", "team_home","team_away","competition"]

    for col in expected_columns:
        assert col in df.columns

def test_extract_head_to_head_invalid_url(client):

    with pytest.raises(ValueError):
        client.extract_head_to_head("invalid-url")

def test_extract_head_to_head_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df = client.extract_head_to_head(url)

    assert isinstance(df, pd.DataFrame)

    expected_columns = [ "match_id", "team_home", "team_away", "competition"]
    for col in expected_columns:
        assert col in df.columns

def test_extract_lineups_invalid_url(client):

    with pytest.raises(ValueError):
        client.extract_lineups("invalid-url")

def test_extract_lineups_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df = client.extract_lineups(url)

    assert isinstance(df, pd.DataFrame)

    assert not df.empty

    expected_columns = ["match_id","team","formation","type","number","name"]

    for col in expected_columns:
        assert col in df.columns

def test_extract_match_commentary_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df = client.extract_match_commentary(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

def test_extract_match_timeline_real_match(client):

    url = 'https://www.espn.com/soccer/match/_/gameId/750528/alverca-fc-porto'
    df = client.extract_match_timeline(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty