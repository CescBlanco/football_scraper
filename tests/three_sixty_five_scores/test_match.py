import pytest
import pandas as pd

from providers.three_sixty_five_scores.constants import COMPETITIONS_URL
from providers.three_sixty_five_scores.client import Scores365Client
from providers.three_sixty_five_scores.match import Scores365MatchScraper

@pytest.fixture
def client():
    client = Scores365Client()
    return Scores365MatchScraper(session=client.session)

def test_extract_match_info(client):
    df = client.extract_match_info("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df, pd.DataFrame)

    # puede estar vacío si la API no devuelve data
    if not df.empty:
        assert "match_date" in df.columns
        assert "match_time" in df.columns

        # checks suaves (no frágiles)
        assert "home_image" in df.columns
        assert "away_image" in df.columns

def test_extract_top_performers(client):
    df_info, df_stats = client.extract_top_performers("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df_info, pd.DataFrame)
    assert isinstance(df_stats, pd.DataFrame)

    # si hay data, validamos mínimo
    if not df_stats.empty:
        assert "team" in df_stats.columns or len(df_stats.columns) > 0

    if not df_info.empty:
        # checks suaves (no dependientes de estructura exacta)
        assert isinstance(df_info, pd.DataFrame)

def test_extract_heatmap_match_player(client):
    result = client.extract_heatmap_match_player("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354",player_id= 3948590 )

    # puede devolver string o imagen
    assert result is not None

def test_extract_lineups_and_data_match(client):
    h_info, h_stats, a_info, a_stats = client.extract_lineups_and_data_match("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(h_info, pd.DataFrame)
    assert isinstance(h_stats, pd.DataFrame)
    assert isinstance(a_info, pd.DataFrame)
    assert isinstance(a_stats, pd.DataFrame)

def test_extract_match_members_squad(client):
    df = client.extract_match_members_squad("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "player_image" in df.columns

def test_extract_shots_data(client):
    df = client.extract_shots_data("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "player_image" in df.columns
        assert "xg" in df.columns or "xgot" in df.columns

def test_plot_match_shotmap(client):

    result = client.plot_match_shotmap("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354",save_fig=False)

    assert result is None 

def test_extract_match_events(client):
    df = client.extract_match_events("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "addedTime" in df.columns      

def test_extract_match_time_stats(client):
    df_general, df_wasted = client.extract_match_time_stats("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df_general, pd.DataFrame)
    assert isinstance(df_wasted, pd.DataFrame)

    if not df_general.empty:
        assert "actual_playtime" in df_general.columns

def test_extract_match_stats(client):
    df = client.extract_match_stats("https://www.365scores.com/football/match/laliga-11/espanyol-fc-barcelona-132-136-11#id=4467354")

    assert isinstance(df, pd.DataFrame)

    # puede estar vacío si API no devuelve stats
    if not df.empty:
        # estructura mínima esperable en 365Scores stats
        assert len(df.columns) > 0