import pytest
import pandas as pd
import requests

from football_scraper.providers.scoresway.competitions import ScoreswayCompetitionScraper


country_name= 'Spain'
league_name= 'Primera División'

@pytest.fixture
def client():
    session = requests.Session()
    return ScoreswayCompetitionScraper(session=session)

def test_extract_competitions(client):
    df = client.extract_competitions()

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["continent", "country", "country_photo", "league", "league_url"]
    for col in expected_cols:
        assert col in df.columns

    assert df["continent"].notna().all()
    assert df["country"].notna().all()


def test_get_competitions_cache(client):
    df = client._get_competitions_cache()

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert client._competitions_cache is not None


def test_list_countries_available(client):
    countries = client.list_countries_available()

    assert isinstance(countries, list)

    if len(countries) == 0:
        return

    assert all(isinstance(c, str) for c in countries)
    
def test_list_competitions_available(client):
    competitions = client.list_competitions_available()

    assert isinstance(competitions, list)

    if len(competitions) == 0:
        return

    assert all(isinstance(c, str) for c in competitions)

def test_get_league_by_country_and_name_success(client):
    competitions = client.list_competitions_available()

    if len(competitions) == 0:
        return

    df = client.get_league_by_country_and_name(country_name, league_name)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["continent","country","country_photo","league","league_url"]
    for col in expected_cols:
        assert col in df.columns

def test_get_league_by_country_and_name_not_found(client):
    result = client.get_league_by_country_and_name(country_name,"league_that_does_not_exist_123")

    assert result is None


def test_get_league_by_country_and_name_invalid_type(client):
    with pytest.raises(TypeError):
        client.get_league_by_country_and_name(123, league_name)
