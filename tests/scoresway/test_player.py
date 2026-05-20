import pytest
import pandas as pd
import requests

from providers.scoresway.player import ScoreswayPlayerScraper
from providers.scoresway.team import ScoreswayTeamScraper

url= 'https://www.scoresway.com/en_GB/soccer/primera-divisi%C3%B3n-2025-2026/80zg2v1cuqcfhphn56u4qpyqc/teams/view/agh9ifb2mw3ivjusgedj7c3fe/player/view/2wl6h1rlrfnn2mr65vuo3t815'


@pytest.fixture
def session():
    return requests.Session()


@pytest.fixture
def team_service(session):
    return ScoreswayTeamScraper(session=session, league_service=None)


@pytest.fixture
def client(session, team_service):
    return ScoreswayPlayerScraper(session=session, team_service=team_service)

def test_extract_bio(client):
    df = client.extract_bio(url)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["age", "player_photo", "nation_photo"]
    for col in expected_cols:
        assert col in df.columns

    assert df["id"].notna().all()


def test_extract_bio_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_bio(123)


def test_extract_bio_empty(client):
    with pytest.raises(ValueError):
        client.extract_bio("   ")


def test_extract_bio_invalid_url(client):
    with pytest.raises(ValueError):
        client.extract_bio("invalid-url")

def test_extract_career_teams(client):
    df = client.extract_career_teams(url)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["contestantId", "id"]
    for col in expected_cols:
        assert col in df.columns


def test_extract_career_teams_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_career_teams(None)


def test_extract_career_teams_empty(client):
    with pytest.raises(ValueError):
        client.extract_career_teams("")


def test_extract_career_teams_invalid_url(client):
    with pytest.raises(RuntimeError):
        client.extract_career_teams("https://badurl.com/player")

def test_extract_stats_season(client):
    df = client.extract_stats_season(url)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "id" in df.columns


def test_extract_stats_season_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_stats_season(999)


def test_extract_stats_season_empty(client):
    with pytest.raises(ValueError):
        client.extract_stats_season("")


def test_extract_stats_season_invalid_url(client):
    with pytest.raises(ValueError):
        client.extract_stats_season("https://short/url")

def test_extract_team_stats_season(client):
    df = client.extract_team_stats_season(url)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "id" in df.columns
    assert "name" in df.columns


def test_extract_team_stats_season_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_team_stats_season([])


def test_extract_team_stats_season_empty(client):
    with pytest.raises(ValueError):
        client.extract_team_stats_season("")


def test_extract_team_stats_season_invalid_url(client):
    with pytest.raises(ValueError):
        client.extract_team_stats_season("invalid")