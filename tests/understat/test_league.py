import pytest
import pandas as pd

from football_scraper.providers.understat.constants import BASE_URL
from football_scraper.providers.understat.client import UnderstatClient
from football_scraper.providers.understat.competitions import UnderstatCompetitionScraper
from football_scraper.providers.understat.league  import UnderstatLeagueScraper

@pytest.fixture
def client():
    client = UnderstatClient()
    competition_service = UnderstatCompetitionScraper(session=client.session)
    return UnderstatLeagueScraper(session=client.session,competition_service=competition_service)

def test_extract_teams(client):
    competitions = client.competition_service.build_competitions_dict(BASE_URL)

    if not competitions:
        pytest.skip("No competitions returned")

    result = client.extract_teams("La Liga", "2025")

    assert isinstance(result, pd.DataFrame)

    if result.empty:
        pytest.skip("No teams data returned")

    expected_cols = ["team_id", "team_name", "team_url"]
    for col in expected_cols:
        assert col in result.columns

    assert result["team_name"].notna().all()
    assert result["team_url"].str.startswith("https://").all()

@pytest.mark.parametrize("mode", ["total", "home", "away"])
def test_extract_standings(client, mode):
    competitions = client.competition_service.build_competitions_dict(BASE_URL)

    if not competitions:
        pytest.skip("No competitions available")

    df = client.extract_standings("La Liga", "2025", mode)
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip(f"No standings data for mode={mode}")

    assert len(df) > 0
    assert df.shape[1] > 0

def test_extract_standings_invalid_mode(client):
    client.competition_service.build_competitions_dict(BASE_URL)

    with pytest.raises(ValueError):
        client.extract_standings("La Liga", "2025", mode="invalid")

def test_extract_matches(client):
    competitions = client.competition_service.build_competitions_dict(BASE_URL)

    if not competitions:
        pytest.skip("No competitions available")

    df = client.extract_matches("La Liga", "2025")
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No matches data returned")

    expected_cols = ["match_date","match_time","match_url","team_local_url","team_away_url"]
    for col in expected_cols:
        assert col in df.columns

    assert df["match_url"].str.contains("match").all()
    assert df["team_local_url"].str.contains("team").all()
    assert df["team_away_url"].str.contains("team").all()
    assert df["match_date"].notna().all()
    assert df["match_time"].notna().all()

def test_extract_stats_players(client):
    competitions = client.competition_service.build_competitions_dict(BASE_URL)

    if not competitions:
        pytest.skip("No competitions available")

    df = client.extract_stats_players("La Liga", "2025")
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No player stats returned")

    expected_cols = [
        "Player", "Team", "Apps", "Min", "G", "NPG", "A",
        "xG", "NPxG", "xA", "xGChain", "xGBuildup",
        "xG90", "NPxG90", "xA90", "xGChain90", "xGBuildup90",
        "xG90 + xA90", "NPxG90 + xA90",
        "player_url", "team_url"
    ]
    for col in expected_cols:
        assert col in df.columns

    assert df["Player"].notna().all()
    assert df["Team"].notna().all()


    numeric_cols = ["Min", "G", "xG", "xA"]
    for col in numeric_cols:
        assert pd.api.types.is_numeric_dtype(df[col])

    assert df["player_url"].str.contains("player").all()
    assert df["team_url"].str.contains("2025").all()

