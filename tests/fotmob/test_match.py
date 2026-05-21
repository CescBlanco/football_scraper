import pytest
import asyncio
import pandas as pd

from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.fotmob.match import FotmobMatchService


@pytest.fixture
def client():
    client = FotmobClient()
    return FotmobMatchService(client)

@pytest.mark.asyncio
async def test_fetch_match_json_smoke(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    result = await client.fetch_match_json(url)

    assert isinstance(result, dict)
    assert result is not None

def test_extract_match_details(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    df = client.extract_match_details(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) >= 1

    expected_cols = [
        "home_team_score",
        "away_team_score",
        "match_date",
        "match_time"
    ]

    for col in expected_cols:
        assert col in df.columns

    assert pd.notnull(df["match_date"].iloc[0])

def test_extract_head_to_head(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    summary, df = client.extract_head_to_head(url)

    assert isinstance(summary, pd.DataFrame)
    assert "match_home_wins" in summary.columns
    assert isinstance(df, pd.DataFrame)
    assert "matchUrl" in df.columns
    assert len(summary) == 1

def test_extract_info_lineups(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    data = client.extract_info_lineups(url)

    assert isinstance(data, tuple)
    assert len(data) == 6

    home_info, away_info, home_lineup, away_lineup, home_unavail, away_unavail = data

    assert isinstance(home_lineup, pd.DataFrame)
    assert isinstance(away_lineup, pd.DataFrame)

    assert len(home_lineup) > 0
    assert len(away_lineup) > 0

def test_extract_events(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    df = client.extract_events(url)

    assert isinstance(df, pd.DataFrame)

    expected_cols = ["profileUrl", "assistProfileUrl"]
    for col in expected_cols:
        assert col in df.columns

def test_extract_player_of_the_match(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    df, df_clean = client.extract_player_of_the_match(url)

    assert isinstance(df, pd.DataFrame)
    assert isinstance(df_clean, pd.DataFrame)
    assert len(df) >= 1
    assert "player_photo" in df.columns

def test_extract_shotmap_player_of_the_match(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    result = client.extract_shotmap_player_of_the_match(url, player_id= '1083323')

    assert isinstance(result, (pd.DataFrame, str))

def test_extract_home_away_form(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    home, away = client.extract_home_away_form(url)

    assert isinstance(home, pd.DataFrame)
    assert isinstance(away, pd.DataFrame)
    assert "match_date" in home.columns

def test_extract_top_players_home_away(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    home, away = client.extract_top_players_home_away(url)

    assert isinstance(home, pd.DataFrame)
    assert isinstance(away, pd.DataFrame)
    assert "player_photo" in home.columns

def test_extract_top_scores_home_away(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    home, away = client.extract_top_scores_home_away(url)

    assert isinstance(home, pd.DataFrame)
    assert isinstance(away, pd.DataFrame)

def test_extract_match_momentum(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    df = client.extract_match_momentum(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0

def test_extract_player_stats(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    clean, stats = client.extract_player_stats(url)

    assert isinstance(clean, pd.DataFrame)
    assert isinstance(stats, pd.DataFrame)

    assert "player_id" in stats.columns

def test_extract_shot_map_player(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    result = client.extract_shot_map_player(url, player_id= '614834')

    assert isinstance(result, (pd.DataFrame, str))

def test_extract_shots_map_all(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    df = client.extract_shots_map_all(url)

    assert isinstance(df, pd.DataFrame)

def test_extract_match_stats(client):
    url = "https://www.fotmob.com/matches/getafe-vs-barcelona/2dfbe4#4837426"
    df = client.extract_match_stats(url)

    assert isinstance(df, pd.DataFrame)

    assert "period" in df.columns
    assert "stat_home" in df.columns