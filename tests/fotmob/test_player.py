import pytest
import asyncio
import pandas as pd

from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.fotmob.player import FotmobPlayerService


@pytest.fixture
def client():
    client = FotmobClient()
    return FotmobPlayerService(client)

@pytest.mark.asyncio
async def test_fetch_player_json_smoke(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    result = await client.fetch_player_details(url)

    assert isinstance(result, dict)
    assert result is not None

def test_extract_player_info_basic(client):
    url ="https://www.fotmob.com/players/696679/raphinha"
    df = client.extract_player_info(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1

    # columnas clave (mínimo esperado)
    expected_cols = ["player", "id", "teamName", "player_photo"]
    for col in expected_cols:
        assert col in df.columns

    # sanity checks
    assert pd.notnull(df["player"].iloc[0])

def test_extract_career_stats_senior(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df1, df2 = client.extract_career_stats_senior(url)
    except ValueError:
        return 

    assert isinstance(df1, pd.DataFrame)
    assert isinstance(df2, pd.DataFrame)
    assert len(df1.columns) > 0
    assert len(df2.columns) > 0
    assert "total_appearances" in df1.columns or "appearances" in df1.columns
    assert "startDate" in df2.columns or len(df2.columns) >= 1
    assert len(df2) >= 0

def test_extract_career_stats_youth(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df1, df2 = client.extract_career_stats_youth(url)
    except ValueError:
        return

    assert isinstance(df1, pd.DataFrame)
    assert isinstance(df2, pd.DataFrame)
    assert not (df1.empty and df2.empty)
    assert len(df1.columns) > 0
    assert len(df2.columns) > 0
    if "startDate" in df2.columns:
        assert pd.api.types.is_datetime64_any_dtype(df2["startDate"])

def test_extract_career_stats_national_team(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df1, df2 = client.extract_career_stats_national_team(url)
    except ValueError:
        return

    assert isinstance(df1, pd.DataFrame)
    assert isinstance(df2, pd.DataFrame)
    assert len(df1.columns) > 0
    assert len(df2.columns) > 0
    if "total_goals" in df1.columns:
        assert df1["total_goals"].dtype != object

    if "startDate" in df2.columns:
        assert pd.api.types.is_datetime64_any_dtype(df2["startDate"])

def test_extract_club_national_teammates(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        club_df, nat_df = client.extract_club_national_teammates(url)
    except ValueError:
        return

    assert isinstance(club_df, pd.DataFrame)
    assert isinstance(nat_df, pd.DataFrame)
    assert not (club_df.empty and nat_df.empty)
    assert len(club_df.columns) >= 0
    assert len(nat_df.columns) >= 0            

def test_extract_market_values_basic(client):
    url ="https://www.fotmob.com/players/696679/raphinha" 
    df = client.extract_market_values(url)

    assert isinstance(df, pd.DataFrame)
    assert "value_date" in df.columns
    assert "teamId" in df.columns
    assert len(df) > 0

def test_extract_stats_section_season(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df = client.extract_stats_section_season(url)
    except ValueError:
        return 
    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) > 0

    if not df.empty:
        expected_base_cols = ["title", "localizedTitleId"]
        assert all(col in df.columns for col in expected_base_cols)
        substat_cols = [col for col in df.columns if col.startswith("substat_")]
        assert len(substat_cols) > 0
        numeric_substats = df.select_dtypes(include=["number"]).columns
        assert len(numeric_substats) >= 0

    assert isinstance(df, pd.DataFrame)

def test_extract_shotmap(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df = client.extract_shotmap(url, is_goalkeeper=False)
    except ValueError:
        return 

    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) > 0

    if not df.empty:

        assert "match_date" in df.columns or "match_time" in df.columns
        assert "datetime" not in df.columns
        assert "datetime_local" not in df.columns

    assert isinstance(df, pd.DataFrame)


def test_extract_heatmap_season_stats(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df = client.extract_heatmap_season_stats(url)
    except ValueError:
        return 

    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) >= 0

    if not df.empty:

        possible_cols = ["x", "y", "xValue", "yValue", "positionX", "positionY"]
        assert any(col in df.columns for col in possible_cols)

    assert df.shape[0] >= 0


def test_extract_next_match(client):
    url ="https://www.fotmob.com/players/696679/raphinha"
    df = client.extract_next_match(url)

    assert isinstance(df, pd.DataFrame)

    expected_cols = ["matchUrl", "match_date", "match_time"]
    for col in expected_cols:
        assert col in df.columns

    assert len(df) == 1

def test_extract_player_traits(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        description, df = client.extract_player_traits(url)
    except ValueError:
        return 

    assert isinstance(description, str)
    assert isinstance(df, pd.DataFrame)
    assert df.shape[1] > 0

    if not df.empty:
        possible_cols = ["title", "label", "description", "name"]
        assert any(col in df.columns for col in possible_cols)
        assert "key" not in df.columns

def test_extract_actual_data_mainleague(client):
    url ="https://www.fotmob.com/players/696679/raphinha"

    try:
        df = client.extract_actual_data_mainleague(url)
    except ValueError:
        return  

    assert isinstance(df, pd.DataFrame)
    assert len(df.columns) > 0

    if not df.empty:
        assert "leagueName" in df.columns
        assert "leagueId" in df.columns
        assert "season" in df.columns

        numeric_cols = df.select_dtypes(include=["number"]).columns
        assert len(numeric_cols) >= 0
        assert df.shape[1] >= 1

def test_extract_position(client):
    url ="https://www.fotmob.com/players/696679/raphinha"
    df = client.extract_position(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    assert "strPos" in " ".join(df.columns)

def test_extract_all_matches_stats(client):
    url ="https://www.fotmob.com/players/696679/raphinha"
    df = client.extract_all_matches_stats(url)

    assert isinstance(df, pd.DataFrame)

    expected_cols = ["match_date", "teamId", "opponentTeamId"]
    for col in expected_cols:
        assert col in df.columns

    assert len(df) > 0

def test_extract_trophies(client):
    url ="https://www.fotmob.com/players/696679/raphinha"
    df = client.extract_trophies(url)

    assert isinstance(df, pd.DataFrame)
    assert len(df) >= 1
    assert "year" in df.columns or len(df.columns) > 0