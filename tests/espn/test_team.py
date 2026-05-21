import pytest
import pandas as pd
import requests

from football_scraper.providers.espn.competitions import ESPNCompetitionScraper
from football_scraper.providers.espn.league import ESPNLeagueScraper
from football_scraper.providers.espn.team import ESPNTeamScraper

TEAM= 'FC Porto'
LEAGUE='Portuguese Primeira Liga'

@pytest.fixture
def competition_service():
    session = requests.Session()
    return ESPNCompetitionScraper(session=session)


@pytest.fixture
def league_service(competition_service):
    session = requests.Session()

    return ESPNLeagueScraper( session=session,  competition_service=competition_service)


@pytest.fixture
def client(league_service):
    session = requests.Session()

    return ESPNTeamScraper( session=session,league_service=league_service)



def test_extract_fixtures(client):
    df = client.extract_fixtures(TEAM,LEAGUE)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["section","date","match_url","team_home","team_home_url","team_home_photo","team_away",
        "team_away_url","team_away_photo","time","competition","tv"]
    for col in expected_cols:
        assert col in df.columns

    assert df["team_home"].notna().all()
    assert df["team_away"].notna().all()


def test_extract_fixtures_invalid_team_type(client):
    with pytest.raises(TypeError):
        client.extract_fixtures(123, LEAGUE)


def test_extract_fixtures_invalid_league_type(client):
    with pytest.raises(TypeError):
        client.extract_fixtures(TEAM, 123)


def test_extract_fixtures_invalid_team(client):
    with pytest.raises(ValueError):
        client.extract_fixtures("team_that_does_not_exist_123",LEAGUE)


def test_extract_results(client):
    df = client.extract_results(TEAM,LEAGUE)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "section", "date", "team_home", "team_away", "team_home_url", "team_away_url", "team_home_photo",
        "team_away_photo", "score", "result", "competition", "match_url", "game_note"]
    for col in expected_cols:
        assert col in df.columns

    assert df["score"].notna().all()


def test_extract_results_invalid_team_type(client):
    with pytest.raises(TypeError):
        client.extract_results(123, LEAGUE)


def test_extract_results_invalid_league_type(client):
    with pytest.raises(TypeError):
        client.extract_results(TEAM, 123)


def test_extract_results_invalid_team(client):
    with pytest.raises(ValueError):
        client.extract_results( "team_that_does_not_exist_123", LEAGUE)


def test_extract_transfers(client):
    df = client.extract_transfers( TEAM, LEAGUE )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "date", "player", "player_url", "team_from_or_to",
        "team_from_or_to_url", "team_from_or_to_photo","fee","type",]
    for col in expected_cols:
        assert col in df.columns

    assert df["player"].notna().all()


def test_extract_transfers_invalid_team_type(client):
    with pytest.raises(TypeError):
        client.extract_transfers(123, LEAGUE)


def test_extract_transfers_invalid_league_type(client):
    with pytest.raises(TypeError):
        client.extract_transfers(TEAM, 123)


def test_extract_transfers_invalid_team(client):
    with pytest.raises(ValueError):
        client.extract_transfers( "team_that_does_not_exist_123", LEAGUE )


def test_extract_avaiable_competitions( client):
    team_id, df = client.extract_avaiable_competitions( LEAGUE, TEAM)

    assert isinstance(team_id, str)
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [  "name",  "value",]
    for col in expected_cols:
        assert col in df.columns


def test_extract_stats_by_competition(client):
    stats = client.extract_stats_by_competition( LEAGUE, TEAM, "2025")

    assert isinstance(stats, dict)

    if len(stats) == 0:
        return

    for tab_name, tables in stats.items():

        assert isinstance(tab_name, str)
        assert isinstance(tables, dict)

        for table_name, df in tables.items():

            assert isinstance(table_name, str)
            assert isinstance(df, pd.DataFrame)


def test_extract_squad_by_competition(client):
    df = client.extract_squad_by_competition( LEAGUE, TEAM, "2025")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert len(df.columns) > 0


def test_get_team_squad(client):
    df = client.get_team_squad( LEAGUE, TEAM, "2025")

    assert isinstance(df, pd.DataFrame)
    assert LEAGUE in client._team_squad_cache


def test_get_team_squad_cache(client):
    df = client._get_team_squad_cache( LEAGUE, TEAM, "2025")

    assert isinstance(df, pd.DataFrame)
    assert LEAGUE in client._team_squad_cache