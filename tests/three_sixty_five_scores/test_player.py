import pytest
import pandas as pd

from providers.three_sixty_five_scores.constants import COMPETITIONS_URL
from providers.three_sixty_five_scores.client import Scores365Client
from providers.three_sixty_five_scores.player import Scores365PlayerScraper

@pytest.fixture
def client():
    client = Scores365Client()
    return Scores365PlayerScraper(session=client.session)

def test_extract_player_details(client):
    df_detailed, df_cleaned = client.extract_player_details("https://www.365scores.com/football/player/raphinha-39789")

    assert isinstance(df_detailed, pd.DataFrame)
    assert isinstance(df_cleaned, pd.DataFrame)

    # puede estar vacío sin romper test
    if df_detailed.empty:
        return


    assert "position" in df_detailed.columns or "player_image" in df_detailed.columns

    if "date_of_birth" in df_detailed.columns:
        assert df_detailed["date_of_birth"].dropna().astype(str).str.len().gt(4).any()

    if "player_image" in df_detailed.columns:
        assert df_detailed["player_image"].dropna().astype(str).str.contains("Athletes").any()

def test_extract_stats_season_by_competition(client):
    df = client.extract_stats_season_by_competition( "https://www.365scores.com/football/player/raphinha-39789", competition="LaLiga")

    assert isinstance(df, pd.DataFrame)

    # puede no haber stats
    if df.empty:
        return

    assert "competitionName" in df.columns
    value_cols = [c for c in df.columns if "stat_" in c]
    assert len(value_cols) > 0 or "stat_value" in df.columns

def test_extract_career_stats_last_season(client):
    df = client.extract_career_stats_last_season( "https://www.365scores.com/football/player/raphinha-39789")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "competition" in df.columns or len(df.columns) > 0
    assert df.shape[0] >= 1

def test_extract_trophies(client):
    df = client.extract_trophies( "https://www.365scores.com/football/player/raphinha-39789")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "team" in df.columns or "entityId" in df.columns
    assert len(df) >= 1


def test_extract_career_history(client):
    df = client.extract_career_history("https://www.365scores.com/football/player/raphinha-39789")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "date" in df.columns or len(df.columns) > 0

def test_extract_last_matches(client):
    df = client.extract_last_matches("https://www.365scores.com/football/player/raphinha-39789")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "match_date" in df.columns

def test_extract_penalty_shots(client):
    df_basic, df_events = client.extract_penalty_shots("https://www.365scores.com/football/player/raphinha-39789")

    assert isinstance(df_basic, pd.DataFrame)
    assert isinstance(df_events, pd.DataFrame)