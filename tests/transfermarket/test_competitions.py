import pytest
from football_scraper.providers.transfermarkt.client import TransfermarktClient
from football_scraper.providers.transfermarkt.constants import COMPETITIONS_URL


@pytest.fixture
def client():
    return TransfermarktClient()


def test_fetch_all_returns_data(client):
    data = client.competition.fetch_all(COMPETITIONS_URL)

    assert isinstance(data, dict)
    assert len(data) > 0
    assert "Top competitions" in data


def test_list_all_returns_list(client):
    client.competition.fetch_all(COMPETITIONS_URL)

    result = client.competition.list_all()

    assert isinstance(result, list)
    assert len(result) > 10
    assert any("LaLiga" in c for c in result)


def test_get_by_name_returns_competition(client):
    client.competition.fetch_all(COMPETITIONS_URL)

    comp = client.competition.get_by_name("LaLiga - Spain (ES1)")

    assert comp["name"] == "LaLiga"
    assert comp["nation"] == "Spain"
    assert "url" in comp