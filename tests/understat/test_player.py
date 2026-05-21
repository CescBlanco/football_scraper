import pytest
import pandas as pd

from football_scraper.providers.understat.client import UnderstatClient
from football_scraper.providers.understat.team import UnderstatTeamScraper
from football_scraper.providers.understat.player import UnderstatPlayerScraper


@pytest.fixture
def client():

    client = UnderstatClient()
    team_service = UnderstatTeamScraper(session=client.session)

    return UnderstatPlayerScraper(session=client.session,team_service=team_service )

def test_extract_json_player(client):
    data = client.extract_json_player('Barcelona', 'Lamine Yamal','2025' )

    assert isinstance(data, dict)
    assert "groups" in data
    assert "season" in data["groups"]
    assert isinstance(data["groups"]["season"], list)

def test_extract_json_player_not_found(client):

    with pytest.raises(ValueError):
        client.extract_json_player('Barcelona', "THIS_PLAYER_DOES_NOT_EXIST_123",'2025')

def test_extract_stats_season(client):

    df = client.extract_stats_season( 'Barcelona', 'Lamine Yamal','2025')
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No season stats returned")

    expected_cols = [
        "season", "team", "position",
        "Apps", "Min", "G", "NPG", "A",
        "shots", "key pases",
        "xG", "xA", "NPxG",
        "xG90", "NPxG90", "xA90",
        "xG90 + xA90", "NPxG90 + xA90",
        "team_url"
    ]
    for col in expected_cols:
        assert col in df.columns

    assert df["season"].notna().all()
    assert df["team"].notna().all()
    assert pd.api.types.is_numeric_dtype(df["Min"])
    assert pd.api.types.is_numeric_dtype(df["xG"])

def test_extract_stats_position(client):
    df = client.extract_stats_position( 'Barcelona', 'Lamine Yamal','2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No position stats returned")

    assert "position" in df.columns
    assert "xG90 + xA90" in df.columns
    assert df["Min"].notna().all()

def test_extract_stats_situation(client):
    df = client.extract_stats_situation( 'Barcelona', 'Lamine Yamal','2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No situation stats returned")

    expected_cols = [
        "situation", "shots", "goals",
        "xG", "xA", "npxG",
        "xG90 + xA90"
    ]

    for col in expected_cols:
        assert col in df.columns

def test_extract_stats_situation(client):
    df = client.extract_stats_situation( 'Barcelona', 'Lamine Yamal','2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No situation stats returned")

    expected_cols = [
        "situation", "shots", "goals",
        "xG", "xA", "npxG",
        "xG90 + xA90"
    ]

    for col in expected_cols:
        assert col in df.columns

def test_extract_stats_shot_types(client):
    df = client.extract_stats_shot_types( 'Barcelona', 'Lamine Yamal','2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No shot types returned")

    assert "shot_type" in df.columns
    assert "xG/Sh" in df.columns

def test_extract_matches_played(client):
    df = client.extract_matches_played( 'Barcelona', 'Lamine Yamal','2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No matches played returned")

    expected_cols = [
        "id", "date", "season",
        "h_team", "a_team",
        "xG", "npxG", "xA",
        "match_url"
    ]

    for col in expected_cols:
        assert col in df.columns

def test_extract_shotmap(client):
    df = client.extract_shotmap( 'Barcelona', 'Lamine Yamal','2025')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        pytest.skip("No shotmap returned")

    assert "match_url" in df.columns
    assert "match_date" in df.columns
    assert "match_time" in df.columns