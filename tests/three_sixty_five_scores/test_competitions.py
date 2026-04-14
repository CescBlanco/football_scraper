import pytest
import pandas as pd
from providers.three_sixty_five_scores.client import Scores365Client
from providers.three_sixty_five_scores.constants import COMPETITIONS_URL

@pytest.fixture
def client():
    return Scores365Client()

def test_fetch_all_returns_data(client):
    data = client.competition.fetch_all(COMPETITIONS_URL)

    assert isinstance(data,  pd.DataFrame)
    assert len(data) > 0
    assert "isActive" in data.columns


def test_list_all_returns_list(client):
    client.competition.fetch_all(COMPETITIONS_URL)

    result = client.competition.list_all()

    assert isinstance(result, list)
    assert len(result) > 10
    assert any("LaLiga" in c for c in result)

def test_get_by_name_returns_competition(client):
    client.competition.fetch_all(COMPETITIONS_URL)

    comp = client.competition.get_by_name('Premier League')

    assert comp["name"] == 'Premier League'
    assert comp["name_country"] == 'England'
    assert "country_for_url" in comp