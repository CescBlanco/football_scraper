import pytest

from providers.understat.constants import BASE_URL
from providers.understat.client import UnderstatClient
from providers.understat.competitions import UnderstatCompetitionScraper

@pytest.fixture
def client():
    client = UnderstatClient()
    return UnderstatCompetitionScraper(session=client.session)

def test_build_competitions_dict(client):
    result = client.build_competitions_dict(BASE_URL)

    assert isinstance(result, dict)

    if not result:
        pytest.skip("No competitions returned from Understat")

    # checks básicos
    for name, url in result.items():
        assert isinstance(name, str)
        assert isinstance(url, str)
        assert name != ""
        assert url.startswith("https://")

def test_list_competitions(client):
    # primero llenamos cache real
    client.build_competitions_dict(BASE_URL)

    result = client.list_competitions()

    assert isinstance(result, list)

    if not result:
        pytest.skip("No competitions available")

    for name in result:
        assert isinstance(name, str)
        assert name != ""

def test_get_competition_found(client):
    competitions = client.build_competitions_dict(BASE_URL)

    if not competitions:
        pytest.skip("No competitions available")

    # coger uno real
    name = list(competitions.keys())[0]

    result = client.get_competition(name)

    assert isinstance(result, dict)
    assert result["name"] == name
    assert result["url"] == competitions[name]

def test_get_competition_case_insensitive(client):
    competitions = client.build_competitions_dict(BASE_URL)

    if not competitions:
        pytest.skip("No competitions available")

    name = list(competitions.keys())[0]

    result = client.get_competition(name.upper())

    assert result["name"] == name


def test_get_competition_not_found(client):
    client.build_competitions_dict(BASE_URL)

    with pytest.raises(ValueError):
        client.get_competition("THIS_DOES_NOT_EXIST_123")

