import pytest
import pandas as pd
import requests

from football_scraper.providers.espn.competitions import ESPNCompetitionScraper
from football_scraper.providers.espn.league import ESPNLeagueScraper
from football_scraper.providers.espn.team import ESPNTeamScraper
from football_scraper.providers.espn.player import ESPNPlayerScraper

LEAGUE = "Portuguese Primeira Liga"
TEAM = "FC Porto"
SEASON = "2025"
PLAYER = "Alberto Costa"

@pytest.fixture
def competition_service():
    session = requests.Session()

    return ESPNCompetitionScraper(session=session)


@pytest.fixture
def league_service(competition_service):
    session = requests.Session()

    return ESPNLeagueScraper(session=session,competition_service=competition_service )


@pytest.fixture
def team_service(league_service):
    session = requests.Session()

    return ESPNTeamScraper( session=session, league_service=league_service )


@pytest.fixture
def client(team_service):
    session = requests.Session()

    return ESPNPlayerScraper( session=session, team_service=team_service)


def test_extract_bio( client):
    bio_df, history_df = client.extract_bio( LEAGUE, TEAM, "2025", PLAYER)

    assert isinstance(bio_df, pd.DataFrame)
    assert isinstance(history_df, pd.DataFrame)

    if not bio_df.empty:
        assert len(bio_df.columns) > 0

    if not history_df.empty:

        expected_cols = [ "team", "team_url", "team_photo", "seasons"]
        for col in expected_cols:
            assert col in history_df.columns


def test_extract_bio_invalid_league_type( client):
    with pytest.raises(TypeError):
        client.extract_bio( 123, TEAM, "2025", PLAYER )


def test_extract_bio_invalid_team_type( client):
    with pytest.raises(TypeError):
        client.extract_bio( LEAGUE, 123, "2025", PLAYER)


def test_extract_bio_invalid_player(client):
    with pytest.raises(ValueError):
        client.extract_bio( LEAGUE, TEAM, "2025", "player_that_does_not_exist_123")


def test_extract_stats_current_year( client):
    df = client.extract_stats_current_year( LEAGUE, TEAM, "2025", PLAYER)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "competition" in df.columns


def test_extract_stats_current_year_invalid_player(client):
    with pytest.raises(ValueError):
        client.extract_stats_current_year( LEAGUE, TEAM, "2025", "player_that_does_not_exist_123")


def test_extract_last5_matches_current_year( client):
    df = client.extract_last5_matches_current_year(LEAGUE,TEAM,"2025",PLAYER )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "team_tricode", "team_name", "team_url", "team_logo", "date", "venue",
        "opponent", "opponent_full_name", "opponent_url", "opponent_logo", "competition", "result",
        "score","match_url","appearances","note"]

    for col in expected_cols:
        assert col in df.columns


def test_extract_last5_matches_invalid_player( client):
    with pytest.raises(ValueError):
        client.extract_last5_matches_current_year( LEAGUE, TEAM, "2025", "player_that_does_not_exist_123")


def test_extract_last5_matches_invalid_season_type( client):
    with pytest.raises(TypeError):
        client.extract_last5_matches_current_year( LEAGUE, TEAM, 2025, PLAYER )