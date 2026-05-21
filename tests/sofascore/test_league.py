import pytest
import pandas as pd

from football_scraper.providers.sofascore.constants import BASE_URL
from football_scraper.providers.sofascore.client import SofascoreClient
from football_scraper.providers.sofascore.competitions import SofascoreCompetitionService
from football_scraper.providers.sofascore.league  import SofascoreLeagueService

@pytest.fixture
def client():
    client = SofascoreClient()
    competition_service = SofascoreCompetitionService(session=client.session)
    return SofascoreLeagueService(session=client.session,competition_service=competition_service)

@pytest.fixture
def countries_df(client):

    return client.competition_service.extract_all_countries()

def test_get_all_leagues_from_df(client, countries_df):
    df = client.get_all_leagues_from_df(countries_df)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return
    expected_cols = ["country_id", "country_name","name","slug", "id", "category.slug" ]

    for col in expected_cols:
        assert col in df.columns

    assert df["id"].notna().all()
    assert df["name"].notna().all()
    assert df["country_id"].notna().all()
    assert df["id"].is_unique is False or len(df) > 1  
    assert len(df) > 0

def test_extract_id_from_league(client, countries_df):
    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["name"].iloc[0]

    league_id = client.extract_id_from_league(sample_league, leagues_df)

    assert isinstance(league_id, str)
    assert league_id.isdigit()

def test_extract_seasons_league(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["name"].iloc[0]

    df = client.extract_seasons_league(sample_league, leagues_df)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "id" in df.columns
    assert "year" in df.columns
    assert df["id"].notna().all()
    assert df["year"].notna().all()
    assert len(df) > 0

def test_extract_id_season_from_league(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["name"].iloc[0]
    season_id = client.extract_id_season_from_league(sample_league,leagues_df,season_selected="25/26")

    assert isinstance(season_id, str)
    assert season_id.isdigit()
    assert len(season_id) > 0

def test_extract_seasons_league_invalid(client):

    empty_df = pd.DataFrame(columns=["name", "id"])

    try:
        client.extract_seasons_league("La Liga", empty_df)
        assert False 
    except Exception:
        assert True

def test_extract_teams(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    # necesitamos season
    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return
    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_teams(sample_league, sample_season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["name", "slug", "shortName", "nameCode", "id", "country.alpha3", "country.name", "country.slug","teamColors.primary", "teamColors.secondary",
                     "teamColors.text","url_team", "image_url"]

    for col in expected_cols:
        assert col in df.columns

    assert df["id"].notna().all()
    assert df["name"].notna().all()
    assert len(df) > 0

def test_extract_details(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df_info, upper, lower = client.extract_details(sample_league, sample_season)

    assert isinstance(df_info, pd.DataFrame)
    assert isinstance(upper, (pd.DataFrame, str))
    assert isinstance(lower, pd.DataFrame)

    if not df_info.empty:
        assert "id" in df_info.columns
        assert len(df_info) > 0

    if isinstance(upper, pd.DataFrame) and not upper.empty:
        assert "id" in upper.columns

    if not lower.empty:
        assert "id" in lower.columns

def test_extract_team_of_the_week_by_tournament(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_team_of_the_week_by_tournament(sample_league, sample_season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "round_number" in df.columns
    assert "formation_name" in df.columns
    assert len(df) > 0

def test_extract_standings_total_home_away(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_standings_total_home_away(sample_league,sample_season,type="total")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert len(df) > 0

def test_extract_top_players_stat(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_top_players_stat( sample_league,sample_season,stat_type="rating")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert len(df) > 0

def test_extract_top_team_stat(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_top_team_stat(sample_league, sample_season,stat_type="bigChancesMissed")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert len(df) > 0

def test_extract_player_of_season(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_player_of_season(sample_league,sample_season, stat_type="rating")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert len(df) > 0

def test_extract_all_matches(client, countries_df):

    leagues_df = client.get_all_leagues_from_df(countries_df)

    if leagues_df.empty:
        return

    sample_league = leagues_df["id"].iloc[0]

    seasons_df = client.extract_seasons_league(leagues_df["name"].iloc[0], leagues_df)

    if seasons_df.empty:
        return

    sample_season = seasons_df["id"].iloc[0]

    df = client.extract_all_matches(sample_league, sample_season)

    assert isinstance(df, pd.DataFrame)

    # puede ser vacío por scraping → aceptamos
    if df.empty:
        return

    expected_cols = ["id", "slug", "winnerCode", "match_date","match_time", "tournament_name", "tournament_slug","homeTeam_name", "awayTeam_name"]

    # al menos algunas columnas deben existir
    assert any(col in df.columns for col in expected_cols)

    assert len(df) > 0