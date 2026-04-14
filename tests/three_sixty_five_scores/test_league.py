import pytest
import pandas as pd

from providers.three_sixty_five_scores.constants import COMPETITIONS_URL
from providers.three_sixty_five_scores.client import Scores365Client
from providers.three_sixty_five_scores.league import Scores365LeagueScraper

@pytest.fixture
def client():
    client = Scores365Client()
    return Scores365LeagueScraper(session=client.session,competition_service=client.competition)

def test_extract_standings_general(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)
    df = client.extract_standings("LaLiga", season="2023/2024", type_standing="General")
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df) > 10

    expected_cols = ['team', 'pts', 'played', 'wins','draws', 'losses', 'goals_for', 'goals_against', 'goal_diff']
    for col in expected_cols:
        assert col in df.columns

    assert df['team'].dtype in ['object', 'string']
    assert df['pts'].dtype in ['int64', 'float64']
    assert df['pts'].max() > 0
    assert df['played'].min() >= 0
    assert isinstance(df.iloc[0]['recent_form'], list)

def test_extract_top_teams_stats(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)
    df = client.extract_top_teams_stats("Premier League")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ['id_team', 'team', 'value', 'name_stat']
    for col in expected_cols:
        assert col in df.columns

    assert pd.api.types.is_numeric_dtype(df['id_team'])
    assert pd.api.types.is_string_dtype(df['team'])
    assert pd.api.types.is_string_dtype(df['name_stat'])

    numeric_values = pd.to_numeric(df['value'], errors='coerce')
    assert numeric_values.notna().any()
    assert df['value'].dtype == object or pd.api.types.is_string_dtype(df['value'])

def test_extract_top_players_stats(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)
    df = client.extract_top_players_stats("Premier League")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ['id_player', 'player', 'name_for_url','positionName', 'value', 'name_stat']
    for col in expected_cols:
        assert col in df.columns

    assert pd.api.types.is_numeric_dtype(df['id_player'])
    assert pd.api.types.is_string_dtype(df['player'])
    assert pd.api.types.is_string_dtype(df['name_for_url'])
    assert pd.api.types.is_string_dtype(df['positionName'])
    assert pd.api.types.is_string_dtype(df['name_stat'])

    numeric_values = pd.to_numeric(df['value'], errors='coerce')
    assert numeric_values.notna().any()
    assert numeric_values.isna().any()

def test_extract_history_winners(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)
    df = client.extract_history_winners("LaLiga")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ['season', 'entity_id', 'team','symbolicName', 'team_image','W', 'D', 'L', 'Puntos']
    for col in expected_cols:
        assert col in df.columns

    assert pd.api.types.is_string_dtype(df['season'])
    assert pd.api.types.is_numeric_dtype(df['entity_id'])
    assert pd.api.types.is_string_dtype(df['team'])

    # 🔥 FIX: convertir antes de validar
    for col in ['W', 'D', 'L', 'Puntos']:
        numeric_col = pd.to_numeric(df[col], errors='coerce')
        assert numeric_col.notna().any()
        assert (numeric_col.dropna() >= 0).all()

def test_extract_actual_team_of_week(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)

    df, formation = client.extract_actual_team_of_week("Premier League")

    assert isinstance(df, pd.DataFrame)
    assert isinstance(formation, str)
    assert not df.empty
    assert len(df) >= 11 
    assert "-" in formation  # ej: 4-3-3

    expected_cols = ['athlete_id', 'player_id', 'name', 'short_name','position', 'formation', 'jersey_number','ranking', 'mvp', 'national_id','game_id',
                        'name_for_url','player_image', 'team', 'symbolicName', 'team_image']
    for col in expected_cols:
        assert col in df.columns

    assert pd.api.types.is_numeric_dtype(df['athlete_id'])
    assert pd.api.types.is_string_dtype(df['name'])
    assert df['name'].notna().all()
    assert df['team'].notna().all()
    assert df['mvp'].isin([True, False]).any()

    numeric_ranking = pd.to_numeric(df['ranking'], errors='coerce')
    assert numeric_ranking.notna().any()

def test_extract_transfers(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)

    df = client.extract_transfers("Premier League")


    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ['player_id', 'name', 'origin_team', 'target_team', 'nationality', 'post_start_date', 'contract_until_date', 'player_image']
    for col in expected_cols:
        assert col in df.columns

    assert pd.api.types.is_numeric_dtype(df['player_id'])
    assert pd.api.types.is_string_dtype(df['name'])
    assert df['name'].notna().any()
    assert df['origin_team'].notna().any()
    assert df['target_team'].notna().any()
    assert df['post_start_date'].str.len().ge(8).all()
    assert df['nationality'].notna().any()
    assert df['player_image'].notna().any()
    assert df.loc[df['player_image'].notna(), 'player_image'].str.contains("http").all()


def test_extract_info_teams(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)

    df = client.extract_info_teams("LaLiga")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ['competitor_id', 'team', 'name_for_url', 'symbolicName', 'color', 'awayColor', 'team_image', 'team_url']
    for col in expected_cols:
        assert col in df.columns

    assert pd.api.types.is_numeric_dtype(df['competitor_id'])
    assert pd.api.types.is_string_dtype(df['team'])
    assert pd.api.types.is_string_dtype(df['team_url'])
    assert df['team'].notna().any()
    assert df['team_url'].str.contains("365scores").all()

    valid_images = df['team_image'].dropna()
    assert valid_images.str.contains("imagecache").all()

def test_extract_next_matches(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)

    df = client.extract_next_matches("LaLiga")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    required_cols = ['id', 'roundNum', 'roundName', 'startDate', 'startTime']
    for col in required_cols:
        assert col in df.columns

    assert df['id'].notna().any()

def test_extract_results(client):
    client.competition_service.fetch_all(COMPETITIONS_URL)

    df = client.extract_results("LaLiga", season_year="2025")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert 'match_date' in df.columns
    assert 'match_time' in df.columns

    assert df['match_date'].notna().all()
    assert df['match_time'].notna().all()