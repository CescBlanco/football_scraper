import pytest
import pandas as pd

from football_scraper.providers.fotmob.constants import BASE_URL
from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.fotmob.competitions import FotmobCompetitionService

@pytest.fixture
def client():
    client = FotmobClient()
    return FotmobCompetitionService(session=client.session)

def test_extract_leagues_all(client):
    df = client.extract_leagues_all()
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["country", "league_id", "league_name","display_name",
        "localized_name","pageUrl","logoURL", ]
    for col in expected_cols:
        assert col in df.columns

    assert df["display_name"].notna().all()
    assert df["country"].notna().all()

def test_find_leagues_success(client):
    df = client.find_leagues("Premier League")
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["display_name", "league_id", "country"]
    for col in expected_cols:
        assert col in df.columns

def test_extract_league_by_display_name_success(client):
    df = client.extract_leagues_all()
    if df.empty:
        return

    display_name = df.iloc[0]["display_name"]

    result = client.extract_league_by_display_name(display_name)

    assert isinstance(result, dict)

    expected_keys = [ "country","id","name", "localized_name", "url","logoURL","name_slug",]

    for key in expected_keys:
        assert key in result

    assert result["id"] is not None
    assert isinstance(result["id"], str)