import pytest
import pandas as pd

from football_scraper.providers.three_sixty_five_scores.constants import COMPETITIONS_URL
from football_scraper.providers.three_sixty_five_scores.client import Scores365Client
from football_scraper.providers.three_sixty_five_scores.team import Scores365TeamScraper

@pytest.fixture
def client():
    client = Scores365Client()
    return Scores365TeamScraper(session=client.session,competition_service=client.competition)

def test_extract_squad(client):
    df = client.extract_squad_and_competition_available("https://www.365scores.com/football/team/fc-barcelona-132")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["id", "name", "position", "birthdate", "player_image"]
    for col in expected_cols:
        assert col in df.columns

    assert df["id"].notna().any()

def test_extract_competitions(client):
    df = client.extract_competition_available("https://www.365scores.com/football/team/fc-barcelona-132")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "id" in df.columns
    assert "competition_image" in df.columns

def test_extract_recent_form(client):
    df = client.extract_recent_form( "https://www.365scores.com/football/team/fc-barcelona-132")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "match_date" in df.columns
    assert "match_time" in df.columns    

def test_extract_next_matches_team(client):
    df = client.extract_next_matches("https://www.365scores.com/football/team/fc-barcelona-132" )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "id" in df.columns
    assert "roundNum" in df.columns
    assert "roundName" in df.columns
    assert "match_date" in df.columns
    assert "match_time" in df.columns

def test_extract_results_team(client):
    df = client.extract_results("https://www.365scores.com/football/team/fc-barcelona-132" ,season_year="2025")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "match_date" in df.columns
    assert "match_time" in df.columns

    # validación simple de fechas
    assert df["match_date"].dropna().astype(str).str.len().gt(8).any()

def test_extract_stats_team(client):
    df = client.extract_stats_team("https://www.365scores.com/football/team/fc-barcelona-132",competition_name="LaLiga")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["id_player", "player", "value", "name_stat"]

    for col in expected_cols:
        assert col in df.columns

    assert df["id_player"].notna().any()
    assert df["player"].notna().any()

def test_extract_transfers_rumors(client):
    df = client.extract_transfers_rumors("https://www.365scores.com/football/team/fc-barcelona-132")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "player_id" in df.columns or "player_image" in df.columns
    if "player_image" in df.columns:
        assert df["player_image"].dropna().astype(str).str.contains("Athletes").any()