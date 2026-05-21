import pytest
import pandas as pd
import requests

from football_scraper.providers.scoresway.events_match import ScoreswayEventsMatchScraper


url= "https://www.scoresway.com/en_GB/soccer/primera-divisi%C3%B3n-2025-2026/80zg2v1cuqcfhphn56u4qpyqc/match/view/3rpa9gg887sphjnou8h1uv6s4/match-summary"


@pytest.fixture
def client():
    session = requests.Session()
    return ScoreswayEventsMatchScraper(session=session)

def test_extract_and_build_events(client):

    df = client.extract_and_build_events(url)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ["id","eventId","event_type","periodId","timeMin","timeSec","contestantId","teamName","teamSide","playerId","playerName","outcome","x","y","qualifier"]
    for col in expected_cols:
        assert col in df.columns

    assert df["event_type"].notna().any()


def test_extract_and_build_events_invalid_url_type(client):

    with pytest.raises(TypeError):
        client.extract_and_build_events(123)


def test_extract_and_build_events_empty_url(client):

    with pytest.raises(ValueError):
        client.extract_and_build_events("")


# =========================================================
# expand_events
# =========================================================

def test_expand_events(client):

    events_df = client.extract_and_build_events(url)

    if events_df.empty:
        return

    available_events = events_df["event_type"].dropna().unique()

    if len(available_events) == 0:
        return

    event_type = available_events[0]

    df = client.expand_events(events_df, event_type)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "event_type" in df.columns
    assert "teamName" in df.columns


def test_expand_events_invalid_dataframe(client):

    with pytest.raises(TypeError):
        client.expand_events("not_a_dataframe", "pass")


def test_expand_events_invalid_event_type(client):

    events_df = client.extract_and_build_events(url)

    with pytest.raises(TypeError):
        client.expand_events(events_df, 123)


def test_expand_events_event_not_found(client):

    events_df = client.extract_and_build_events(url)

    with pytest.raises(RuntimeError):
        client.expand_events(events_df, "event_that_does_not_exist")