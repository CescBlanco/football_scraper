import pytest
import pandas as pd

from football_scraper.providers.sofascore.constants import BASE_URL
from football_scraper.providers.sofascore.client import SofascoreClient
from football_scraper.providers.sofascore.manager import SofascoreManagerScraper

@pytest.fixture
def client():
    client = SofascoreClient()
    return SofascoreManagerScraper(session=client.session)

def test_extract_manager_details(client):
    df = client.extract_manager_details(id_manager_sofascore=793676)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return


    expected_cols = ['id','name','slug','shortName','birthdate','country_name','nationality','country_alpha2','preferredFormation','team_name','team_slug','team_shortName',
        'team_nameCode','team_id','performance_total','performance_wins','performance_draws','performance_losses','performance_goalsScored',
        'performance_goalsConceded','performance_totalPoints','manager_photo']

    for col in expected_cols:
        assert col in df.columns

    assert df['id'].notna().all()
    assert df['name'].notna().all()
    assert df['birthdate'].notna().all()

def test_extract_career_history_manager(client):
    df = client.extract_career_history_manager(id_manager_sofascore=793676)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ['team_name','team_slug','team_shortName','team_nameCode','team_id','team_ranking','performance_total','performance_wins','performance_draws',
                    'performance_losses','performance_totalPoints','start_period','end_period']

    for col in expected_cols:
        assert col in df.columns

    assert df['team_name'].notna().all()
    assert df['start_period'].notna().all()