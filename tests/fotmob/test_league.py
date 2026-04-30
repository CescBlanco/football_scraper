import pytest
import pandas as pd

from providers.fotmob.constants import BASE_URL
from providers.fotmob.client import FotmobClient
from providers.fotmob.competitions import FotmobCompetitionService
from providers.fotmob.league  import FotmobLeagueService

@pytest.fixture
def client():
    client = FotmobClient()
    competition_service = FotmobCompetitionService(session=client.session)
    return FotmobLeagueService(session=client.session,competition_service=competition_service)

def test_validate_season_success(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    result = client.validate_season_from_league(display_name, "2025/2026")

    assert isinstance(result, tuple)
    assert len(result) == 5

    valid, message, season_in, season_out, league_id = result

    assert isinstance(valid, bool)
    assert isinstance(message, str)

    if valid:
        assert season_in is not None
        assert season_out is not None
        assert league_id is not None

def test_extract_row_clean_data(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        raw_df, clean_df = client.extract_row_clean_data(display_name, "2025/2026")
    except ValueError:
        return  # season no disponible

    assert isinstance(raw_df, pd.DataFrame)
    assert isinstance(clean_df, pd.DataFrame)

    assert len(raw_df) >= len(clean_df)

def test_extract_teams(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        teams_df = client.extract_teams(display_name, "2025/2026")
    except ValueError:
        return

    assert isinstance(teams_df, pd.DataFrame)

    if teams_df.empty:
        return

    assert "id" in teams_df.columns
    assert "team_url" in teams_df.columns
    assert "team_photo" in teams_df.columns

def test_extract_team_of_week(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        df_totw = client.extract_team_of_week(display_name, "2025/2026", 'ESP', 10)
    except ValueError:
        return

    assert isinstance(df_totw, pd.DataFrame)

    if df_totw.empty:
        return

    assert "roundId" in df_totw.columns
    assert "player_photo" in df_totw.columns

def test_extract_teamofweek_by_round(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        df_totw = client.extract_team_of_week(display_name, "2025/2026", 'ESP', 10)
    except ValueError:
        return

    if df_totw.empty:
        return

    round_id = df_totw.iloc[0]["roundId"]

    result = client.extract_teamofweek_by_round(display_name, "2025/2026", "ESP", round_id)

    assert isinstance(result, pd.DataFrame)
    assert not result.empty

def test_extract_transfer(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        df_transfer = client.extract_transfer(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(df_transfer, pd.DataFrame)

    if df_transfer.empty:
        return

    assert "player_photo" in df_transfer.columns

def test_extract_all_matches(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        matches = client.extract_all_matches(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(matches, pd.DataFrame)

    if matches.empty:
        return

    assert "match_date" in matches.columns
    assert "match_time" in matches.columns

def test_extract_stats_players(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        stats = client.extract_stats_players(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(stats, pd.DataFrame)

def test_extract_stats_teams(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        stats = client.extract_stats_teams(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(stats, pd.DataFrame)

def test_extract_history_seasons(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        history = client.extract_history_seasons(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(history, pd.DataFrame)

    if history.empty:
        return

    assert "winner_id" in history.columns

def test_extract_standing_all_h_a_form(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        standings = client.extract_standing_all_h_a_form(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(standings, pd.DataFrame)

    if standings.empty:
        return

    assert "team_logo" in standings.columns

def test_extract_standing_xg(client):
    df = client.competition_service.extract_leagues_all()
    if df.empty:
        return

    display_name = "LaLiga - Spain"

    try:
        standings = client.extract_standing_xg(display_name, "2025/2026", "ESP")
    except ValueError:
        return

    assert isinstance(standings, pd.DataFrame)

    if standings.empty:
        return

    assert "xg" in standings.columns