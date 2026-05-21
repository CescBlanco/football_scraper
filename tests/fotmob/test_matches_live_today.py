import pytest
import pandas as pd

from football_scraper.providers.fotmob.constants import BASE_URL
from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.fotmob.matches_live_today import FotmobMatchesTodayService

@pytest.fixture
def client():
    client = FotmobClient()
    return FotmobMatchesTodayService(session=client.session)

def test_extract_matches_live_full(client):
    df = client.extract_matches_live_full()

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [
        "ccode",
        "ccode_id",
        "parent_league_id",
        "league_name",
        "parent_league_name",
        "match_id",
        "tournament_stage",
        "home_team_id",
        "home_team_name",
        "home_team_long_name",
        "home_score",
        "away_team_id",
        "away_team_name",
        "away_team_long_name",
        "away_score",
        "status_id",
        "finished",
        "started",
        "cancelled",
        "awarded",
        "score_str",
        "global_score_str",
        "match_time_local",
        "period_length",
    ]

    for col in expected_cols:
        assert col in df.columns

    # checks de integridad básicos
    assert df["match_id"].notna().any()
    assert df["league_name"].notna().any()