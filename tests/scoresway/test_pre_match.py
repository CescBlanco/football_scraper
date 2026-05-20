import pytest
import pandas as pd
import requests

from providers.scoresway.pre_match import ScoreswayPreMatchScraper


url= "https://www.scoresway.com/en_GB/soccer/primera-divisi%C3%B3n-2025-2026/80zg2v1cuqcfhphn56u4qpyqc/match/view/3xq4alyjtlltd6j11gckoxvkk/match-preview"


@pytest.fixture
def client():
    session = requests.Session()
    return ScoreswayPreMatchScraper(session)


def test_extract_match_details(client):

    df = client.extract_match_details(url)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "id_match", "date", "id", "name", "position", "team_photo"]
    for col in expected_cols:
        assert col in df.columns


def test_extract_match_details_invalid_url_type(client):

    with pytest.raises(TypeError):
        client.extract_match_details(123)


def test_extract_match_details_empty_url(client):

    with pytest.raises(ValueError):
        client.extract_match_details("")

def test_extract_info_previous_meeting_mainleague(client):

    summary_df, matches_df, goals_df = client.extract_info_previous_meeting_mainleague(url)

    assert isinstance(summary_df, pd.DataFrame)
    assert isinstance(matches_df, pd.DataFrame)
    assert isinstance(goals_df, pd.DataFrame)

    if not matches_df.empty:
        assert "id_match" in matches_df.columns


def test_extract_info_previous_meeting_mainleague_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_info_previous_meeting_mainleague(123)

def test_extract_info_previous_meeting_anycomp(client):

    summary_df, matches_df, goals_df =  client.extract_info_previous_meeting_anycomp(url)


    assert isinstance(summary_df, pd.DataFrame)
    assert isinstance(matches_df, pd.DataFrame)
    assert isinstance(goals_df, pd.DataFrame)

    if not matches_df.empty:
        assert "id_match" in matches_df.columns


def test_extract_info_previous_meeting_anycomp_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_info_previous_meeting_anycomp(123)


# =========================================================
# LAST 6 FORM MAIN LEAGUE
# =========================================================

def test_extract_last6match_form_main_league(client):

    matches_df, goals_df =  client.extract_last6match_form_main_league(url)
    
    assert isinstance(matches_df, pd.DataFrame)
    assert isinstance(goals_df, pd.DataFrame)

    if not matches_df.empty:
        assert "side" in matches_df.columns


def test_extract_last6match_form_main_league_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_last6match_form_main_league(123)


def test_extract_last6match_form_anycomp(client):

    matches_df, goals_df = client.extract_last6match_form_anycomp(url)
    
    assert isinstance(matches_df, pd.DataFrame)
    assert isinstance(goals_df, pd.DataFrame)

    if not matches_df.empty:
        assert "side" in matches_df.columns


def test_extract_last6match_form_anycomp_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_last6match_form_anycomp(123)

def test_extract_win_probability(client):

    df = client.extract_win_probability(url)

    assert isinstance(df, pd.DataFrame)
    if df.empty:
        return

    assert len(df.columns) > 0


def test_extract_win_probability_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_win_probability(123)

def test_extract_extra_prematch_details(client):

    df_messages, df_form_guide, df_h2h, df_top_scorers, df_up_next_home, df_up_next_away = client.extract_extra_prematch_details(url)

    assert isinstance(df_messages, pd.DataFrame)
    assert isinstance(df_form_guide, pd.DataFrame)
    assert isinstance(df_h2h, pd.DataFrame)
    assert isinstance(df_top_scorers, pd.DataFrame)
    assert isinstance(df_up_next_home, pd.DataFrame)
    assert isinstance(df_up_next_away, pd.DataFrame)


def test_extract_extra_prematch_details_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_extra_prematch_details(123)


def test_extract_home_squad(client):

    df = client.extract_home_squad(url)

    assert isinstance(df, pd.DataFrame)
    if df.empty:
        return

    expected_cols = ["contestantId","contestantName","player_photo","nation_photo","team_photo"]

    for col in expected_cols:
        assert col in df.columns


def test_extract_home_squad_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_home_squad(123)

def test_extract_away_squad(client):

    df = client.extract_away_squad(url)

    assert isinstance(df, pd.DataFrame)
    if df.empty:
        return

    expected_cols = [ "contestantId", "contestantName", "player_photo", "nation_photo", "team_photo"]
    for col in expected_cols:
        assert col in df.columns


def test_extract_away_squad_invalid_url(client):

    with pytest.raises(TypeError):
        client.extract_away_squad(123)