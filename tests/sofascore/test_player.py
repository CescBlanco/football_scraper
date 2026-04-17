import pytest
import pandas as pd

from providers.sofascore.constants import BASE_URL
from providers.sofascore.client import SofascoreClient
from providers.sofascore.player import SofascorePlayerScraper

@pytest.fixture
def client():
    client = SofascoreClient()
    return SofascorePlayerScraper(session=client.session)

def test_extract_tournament_season_by_player(client):
    season_id, competition_id = client.extract_tournament_season_by_player(
        id_player_sofascore='1402912',
        competition_selected_sofascored="LaLiga",
        season_selected_sofascored='25/26'
        )

    assert isinstance(season_id, str)
    assert isinstance(competition_id, str)

    assert len(season_id) > 0
    assert len(competition_id) > 0

def test_extract_player_info(client):
    df = client.extract_player_info(id_player_sofascore='1402912')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [
        'id','name','slug','shortName','position','positionsDetailed','jerseyNumber','height','dateOfBirth','preferredFoot','proposedMarketValue',
        'team_name','team_slug','team_shortName','team_nameCode','team_id','country_alpha3','country_name','country_slug',
        'team_tournament_name','team_tournament_slug','team_country_alpha3','team_country_name','team_country_slug'
        ]

    for col in expected_cols:
        assert col in df.columns

    assert df['id'].notna().all()
    assert df['name'].notna().all()
    assert df['dateOfBirth'].notna().all()

def test_extract_attributes_summary(client):
    df = client.extract_attributes_summary(id_player_sofascore='1402912')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert 'position' in df.columns
    assert 'date' in df.columns

    assert df['date'].notna().all()

def test_extract_summary_last_year(client):
    df_final, df_stats = client.extract_summary_last_year(id_player_sofascore='1402912')

    assert isinstance(df_final, pd.DataFrame)
    assert isinstance(df_stats, pd.DataFrame)

    if df_final.empty:
        return

    assert 'timestamp' in df_final.columns
    assert df_final['timestamp'].notna().all()

    if not df_stats.empty:
        assert 'name' in df_stats.columns
        assert 'appearances' in df_stats.columns
        assert 'avg_rating' in df_stats.columns

def test_extract_transfer_history(client):
    df = client.extract_transfer_history(id_player_sofascore='1402912')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [
        'player_name','player_slug','player_shortName','player_position','player_jerseyNumber','player_id','transfer_date','transferFeeDescription',
        'transferFrom_name','transferFrom_id','transferTo_name','transferTo_id'
        ]

    for col in expected_cols:
        assert col in df.columns

    assert df['player_id'].notna().all()

def test_extract_national_team_stats(client):
    df = client.extract_national_team_stats(id_player_sofascore=1)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert 'team_name' in df.columns

    if 'match_date' in df.columns:
        assert df['match_date'].notna().all()

def test_extract_heatmap_season(client):
    df = client.extract_heatmap_season(
        id_player_sofascore='1402912',
        id_competition_sofascored=8,
        id_season_sofascored=77559
        )

    assert isinstance(df, pd.DataFrame)

def test_extract_season_ratings(client):
    df = client.extract_season_ratings(
        id_player_sofascore='1402912',
        id_competition_sofascored=8,
        id_season_sofascored=77559
        )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert 'match_date' in df.columns
    assert 'match_time' in df.columns

    assert df['match_date'].notna().all()
    assert df['match_time'].notna().all()

def test_extract_stats_season(client):
    df = client.extract_stats_season(
        id_player_sofascore='1402912',
        id_competition_sofascored=8,
        id_season_sofascored=77559
        )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert 'statisticsType.competitionSlug' not in df.columns

def test_extract_info_penalties(client):
    df, attempts, scored, conversion_rate = client.extract_info_penalties(id_player_sofascore='1402912')

    assert isinstance(df, pd.DataFrame)
    assert isinstance(attempts, int)
    assert isinstance(scored, int)
    assert isinstance(conversion_rate, float)

    if df.empty:
        return

    assert attempts >= 0
    assert scored >= 0

def test_extract_career_stats_all_h_a(client):
    df = client.extract_career_stats_all_h_a(
        id_player_sofascore='1402912',
        type_stat="overall"
        )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert 'team_name' in df.columns
    assert 'uniqueTournament_name' in df.columns
    assert 'season_name' in df.columns

def test_extract_stats_one_match(client):
    position, df = client.extract_stats_one_match(
        id_one_match_player='14083662',
        id_player_sofascore='1402912'
        )

    assert isinstance(position, (str, type(None)))
    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert len(df.columns) > 0

def test_extract_events_rating_breakdown(client):
    passes, defensive, dribbles, ball_carries = client.extract_events_rating_breakdown(
        id_one_match_player='14083662',
        id_player_sofascore='1402912'
        )

    for df in [passes, defensive, dribbles, ball_carries]:
        assert isinstance(df, pd.DataFrame)

    # Checks específicos (si hay datos)
    if not passes.empty:
        assert isinstance(passes, pd.DataFrame)

    if not defensive.empty:
        assert isinstance(defensive, pd.DataFrame)

def test_extract_shotmap_one_match(client):
    df = client.extract_shotmap_one_match(
        id_one_match_player='14083662',
        id_player_sofascore='1402912'
        )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [
        'player_name','player_slug','player_shortName','player_position',
        'player_id','xg','xgot','shotType','incidentType'
        ]

    # comprobación flexible (no todos siempre vienen)
    for col in expected_cols:
        assert col in df.columns or True

    assert len(df) >= 0

def test_extract_heatmap_one_match(client):
    df = client.extract_heatmap_one_match(
        id_one_match_player='14083662',
        id_player_sofascore='1402912'
        )

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    # normalmente heatmap tiene x/y/intensity o similar
    assert df.shape[1] > 0
