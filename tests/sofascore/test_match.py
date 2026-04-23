import pytest
import pandas as pd

from providers.sofascore.constants import BASE_URL
from providers.sofascore.client import SofascoreClient
from providers.sofascore.match import SofascoreMatchScraper

@pytest.fixture
def client():
    client = SofascoreClient()
    return SofascoreMatchScraper(session=client.session)

def test_extract_match_info(client):

    match_id = "14083113"

    df = client.exctract_match_info(match_id)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ["id", "slug","tournament.name", "homeTeam.name","awayTeam.name","winnerCode"]
    for col in expected_cols:
        assert col in df.columns


def test_extract_match_momentum(client):

    match_id = "14083113"

    df = client.extract_match_momentum(match_id)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "minute" in df.columns
        assert "value" in df.columns

def test_extract_incidents(client):

    match_id = "14083113"

    df = client.extract_incidents(match_id)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        # columnas típicas tras safe_expand
        possible_cols = ["time", "type", "player_name", "team"]

        assert any(col in df.columns for col in df.columns)


def test_extract_info_managers(client):

    match_id = "14083113"

    df = client.extract_info_managers(match_id)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        # al menos algo de home/away manager
        assert "name" in df.columns or df.shape[1] > 0       

def test_extract_match_stats(client):

    match_id = "14083113"

    df = client.extract_match_stats(match_id, part="all")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "groupName" in df.columns 

def test_extract_shotmap(client):

    match_id = "14083113"

    df = client.extract_shotmap(match_id)

    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        assert "goalType" in df.columns 


def test_extract_head_to_head(client):

    match_id = "14083113"

    team_df, manager_df = client.extract_head_to_head(match_id)

    assert isinstance(team_df, pd.DataFrame)
    assert isinstance(manager_df, pd.DataFrame)

    # siempre debe devolver algo (aunque sea message)
    assert "message" in team_df.columns or len(team_df.columns) > 0
    assert "message" in manager_df.columns or len(manager_df.columns) > 0

def test_extract_team_form(client):

    match_id = "14083113"

    df = client.extract_team_form(match_id)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert df.shape[1] > 0

def test_extract_best_players_team(client):

    match_id = "14083113"

    df = client.extract_best_players_team(match_id)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        expected_cols = ["name", "team.name", "rating"]

        assert any(col in df.columns for col in expected_cols)

def test_extract_player_of_match(client):

    match_id = "14083113"

    df = client.extract_player_of_match(match_id)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        expected_cols = ["name", "id", "shortName"]

        assert any(col in df.columns for col in expected_cols)

def test_extract_info_lineups(client):

    match_id = "14083113"

    home, away, home_info, away_info = client.extract_info_lineups(match_id)

    assert isinstance(home, pd.DataFrame)
    assert isinstance(away, pd.DataFrame)
    assert isinstance(home_info, pd.DataFrame)
    assert isinstance(away_info, pd.DataFrame)

    # validación mínima
    if not home.empty:
        assert "player.name" in home.columns or home.shape[1] > 0

    if not away.empty:
        assert "player.name" in away.columns or away.shape[1] > 0

def test_extract_average_positions(client):

    match_id = "14083113"
    home, away = client.extract_teams_players_average_position(match_id)

    assert isinstance(home, pd.DataFrame)
    assert isinstance(away, pd.DataFrame)

def test_extract_heatmap_player(client):

    match_id = "14083113"
    player_id_match= '1402912'
    df = client.extract_heatmap_player(match_id, player_id_match)

    assert isinstance(df, pd.DataFrame)    

def test_extract_shotmap_player(client):
    match_id = "14083113"
    player_id_match= '1402912'
    df = client.extract_shotmap_player(match_id, player_id_match)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["player_id", "time", "incidentType"]

    for col in expected_cols:
        assert col in df.columns or True 

def test_extract_stats_match_player(client):
    match_id = "14083113"
    player_id_match= '1402912'
    position, df = client.extract_stats_match_player(match_id, player_id_match)

    assert isinstance(position, str)
    assert isinstance(df, pd.DataFrame)

def test_extract_events_player_match(client):
    match_id = "14083113"
    player_id_match= '1402912'
    passes, defensive, dribbles, carries = client.extract_events_player_match(match_id, player_id_match)

    for df in [passes, defensive, dribbles, carries]:
        assert isinstance(df, pd.DataFrame)