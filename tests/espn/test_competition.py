import pytest
import pandas as pd
import requests

from football_scraper.providers.espn.competitions import ESPNCompetitionScraper

@pytest.fixture
def client():
    session = requests.Session()
    return ESPNCompetitionScraper(session=session)


def test_extract_all_competitions(client):
    df = client.extract_all_competitions()

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["country", "competition", "competition_url", "competition_photo", "competition_url_fixtures",
        "competition_url_teams", "competition_url_stats", "competition_slug",]
    for col in expected_cols:
        assert col in df.columns

    assert df["competition"].notna().all()
    assert df["country"].notna().all()
    assert "Top Competitions" not in df["country"].values


def test_get_competitions_cache(client):
    df = client._get_competitions_cache()

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert client._competitions_cache is not None


def test_list_competitions_available(client):
    competitions = client.list_competitions_available()

    assert isinstance(competitions, list)

    if len(competitions) == 0:
        return

    assert all(isinstance(c, str) for c in competitions)


def test_get_league_by_name_success(client):
    competitions = client.list_competitions_available()

    if len(competitions) == 0:
        return

    league_name = competitions[0]

    df = client.get_league_by_name(league_name)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["country","competition","competition_url","competition_photo","competition_url_fixtures",
        "competition_url_teams", "competition_url_stats", "competition_slug",]
    for col in expected_cols:
        assert col in df.columns

def test_get_league_by_name_not_found(client):
    result = client.get_league_by_name("league_that_does_not_exist_123")

    assert result is None


def test_get_league_by_name_invalid_type(client):
    with pytest.raises(TypeError):
        client.get_league_by_name(123)