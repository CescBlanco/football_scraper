import pytest
import requests
import pandas as pd
from providers.scoresway.competitions import ScoreswayCompetitionScraper
from providers.scoresway.league import ScoreswayLeagueScraper
from providers.scoresway.team import ScoreswayTeamScraper

country_name = "Spain"
league_name = "Primera División"
team_name = "Barcelona"
team_name_squad='FC Barcelona'
season = "2025/2026"


@pytest.fixture
def session():
    return requests.Session()


@pytest.fixture
def competition_service(session):
    return ScoreswayCompetitionScraper(session=session)


@pytest.fixture
def league_service(session, competition_service):
    return ScoreswayLeagueScraper( session=session,competition_service=competition_service)

@pytest.fixture
def client(session, league_service):
    return ScoreswayTeamScraper( session=session,  league_service=league_service )

def test_extract_team_fixtures(client):
    df = client.extract_team_fixtures(country_name, league_name, team_name, season)

    assert isinstance(df, pd.DataFrame)
    if df.empty:
        return

    expected_cols = ["home_name", "away_name"]

    for col in expected_cols:
        assert col in df.columns

    assert (df["home_name"].eq(team_name).any()or df["away_name"].eq(team_name).any())

def test_extract_team_results(client):
    df = client.extract_team_results(country_name, league_name, team_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["home_name", "away_name"]
    for col in expected_cols:
        assert col in df.columns

    assert (df["home_name"].eq(team_name).any()or df["away_name"].eq(team_name).any())

def test_extract_squad(client):
    df = client.extract_squad(country_name, league_name, team_name_squad, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["contestantId","contestantName","competitionName","playerUrl","teamUrl","player_photo","team_photo",]
    for col in expected_cols:
        assert col in df.columns

    assert df["contestantName"].eq(team_name_squad).any()

def test_extract_team_fixtures_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_team_fixtures(123, league_name, team_name, season)

def test_extract_team_fixtures_empty_team(client):
    with pytest.raises(ValueError):
        client.extract_team_fixtures(country_name, league_name, "", season)

def test_extract_team_results_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_team_results(country_name, league_name, 123, season)

def test_extract_squad_invalid_season(client):
    with pytest.raises(RuntimeError):
        client.extract_squad(country_name, "LeagueThatDoesNotExist", team_name_squad, season)

def test_get_team_squad_cache_reuses_value(client):
    country = country_name
    league = league_name
    team = team_name_squad
    season_val = season

    # primera llamada → debería crear cache
    df1 = client._get_team_squad_cache(country, league, team, season_val)

    # segunda llamada → debería venir del cache
    df2 = client._get_team_squad_cache(country, league, team, season_val)

    assert isinstance(df1, pd.DataFrame)
    assert isinstance(df2, pd.DataFrame)

    # mismo objeto (cache real)
    assert df1 is df2

def test_get_team_squad_wrapper(client):
    df = client.get_team_squad(country_name, league_name, team_name_squad, season)

    assert isinstance(df, pd.DataFrame)

    # debería devolver algo válido (si hay datos)
    if df.empty:
        return

    assert "contestantName" in df.columns

def test_cache_isolated_by_key(client):
    df1 = client._get_team_squad_cache(country_name, league_name, "FC Barcelona", season)
    df2 = client._get_team_squad_cache(country_name, league_name, "Real Madrid CF", season)

    # pueden ser iguales o distintos, pero NO deben compartir cache
    assert df1 is not df2

def test_cache_is_stored(client):
    key = f"{country_name}_{league_name}_{team_name_squad}_{season}"

    client._team_squad_cache.clear()

    client._get_team_squad_cache(country_name, league_name, team_name_squad, season)

    assert key in client._team_squad_cache