import pytest
import pandas as pd
import requests

from providers.espn.competitions import ESPNCompetitionScraper
from providers.espn.league import ESPNLeagueScraper

LEAGUE='Portuguese Primeira Liga'

@pytest.fixture
def competition_service():
    session = requests.Session()
    return ESPNCompetitionScraper(session=session)


@pytest.fixture
def client(competition_service):
    session = requests.Session()
    return ESPNLeagueScraper( session=session, competition_service=competition_service)


def test_extract_teams(client):
    df = client.extract_teams(LEAGUE)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "team", "team_id", "team_slug", "team_url", "team_photo",
        "team_fixtures_url", "team_stats_url", "slug_league", "slug_team_full", ]
    for col in expected_cols:
        assert col in df.columns

    assert df["team"].notna().all()


def test_extract_teams_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_teams(123)


def test_extract_teams_invalid_league(client):
    with pytest.raises(ValueError):
        client.extract_teams("league_that_does_not_exist_123")


def test_get_league_teams_cache(client):
    df = client._get_league_teams_cache(LEAGUE)

    assert isinstance(df, pd.DataFrame)

    assert LEAGUE in client._league_teams_cache


def test_get_teams(client):
    df = client.get_teams(LEAGUE)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "team" in df.columns


def test_extract_standings(client):
    df = client.extract_standings(LEAGUE)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["position","team","abbreviation","team_url","team_photo","games_played","wins",
        "draws", "losses", "goals_for", "goals_against", "goal_difference", "points", "competition_zone"]
    for col in expected_cols:
        assert col in df.columns

    assert df["team"].notna().all()


def test_extract_standings_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_standings(123)


def test_extract_standings_invalid_league(client):
    with pytest.raises(ValueError):
        client.extract_standings("league_that_does_not_exist_123")


def test_extract_transfers(client):
    df = client.extract_transfers(LEAGUE)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "date", "player", "player_url", "team_from", "team_from_url", "team_from_photo", "team_to", "team_to_url", "team_to_photo", "fee"]
    for col in expected_cols:
        assert col in df.columns

    assert df["date"].notna().all()


def test_extract_transfers_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_transfers(123)


def test_extract_transfers_invalid_league(client):
    with pytest.raises(ValueError):
        client.extract_transfers("league_that_does_not_exist_123")


def test_extract_stats(client):
    stats = client.extract_stats(LEAGUE)

    assert isinstance(stats, dict)

    if len(stats) == 0:
        return

    for tab_name, tables in stats.items():

        assert isinstance(tab_name, str)
        assert isinstance(tables, dict)

        for table_name, df in tables.items():

            assert isinstance(table_name, str)
            assert isinstance(df, pd.DataFrame)


def test_extract_stats_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_stats(123)


def test_extract_stats_invalid_league(client):
    with pytest.raises(ValueError):
        client.extract_stats("league_that_does_not_exist_123")