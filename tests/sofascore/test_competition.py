import pytest
import pandas as pd

from providers.sofascore.constants import BASE_URL
from providers.sofascore.client import SofascoreClient
from providers.sofascore.competitions import SofascoreCompetitionService

@pytest.fixture
def client():
    client = SofascoreClient()
    return SofascoreCompetitionService(session=client.session)

def test_extract_all_countries(client):
    df = client.extract_all_countries()

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["name", "slug", "id", "flag"]

    for col in expected_cols:
        assert col in df.columns

   
    assert df["id"].notna().all()
    assert df["name"].notna().all()
    assert df["slug"].notna().all()
