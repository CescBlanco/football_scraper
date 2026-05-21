import pytest
import pandas as pd
import requests

from football_scraper.providers.scoresway.competitions import ScoreswayCompetitionScraper
from football_scraper.providers.scoresway.league import ScoreswayLeagueScraper

country_name= 'Spain'
league_name= 'Primera División'
team_name= 'Barcelona'
season= '2025/2026'

@pytest.fixture
def competition_service():
    session = requests.Session()
    return ScoreswayCompetitionScraper(session=session)


@pytest.fixture
def client(competition_service):
    session = requests.Session()
    return ScoreswayLeagueScraper( session=session, competition_service=competition_service)

def test_extract_season_league_available(client):
    df = client.extract_season_league_available(country_name, league_name)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [ "season", "id_season", "season_url"]
    for col in expected_cols:
        assert col in df.columns

    assert df["season"].notna().all()


def test_extract_fixtures(client):
    df = client.extract_fixtures(country_name, league_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ['matchInfo.id', 'matchInfo.localDate', 'matchInfo.localTime','matchInfo.week', 'matchInfo.description', 'matchInfo.competition.id',
       'matchInfo.competition.name', 'matchInfo.competition.knownName','matchInfo.competition.competitionFormat','matchInfo.competition.country.id',
       'matchInfo.competition.country.name', 'matchInfo.tournamentCalendar.id','matchInfo.tournamentCalendar.name', 'matchInfo.venue.id',
       'matchInfo.venue.neutral', 'matchInfo.venue.longName','matchInfo.venue.shortName', 'matchInfo.venue.latitude','matchInfo.venue.longitude', 
       'liveData.matchDetails.matchStatus','liveData.matchDetailsExtra.matchOfficial', 'home_id', 'home_name','home_shortName', 'home_officialName', 'home_code', 
       'home_position','home_country.id', 'home_country.name', 'away_id', 'away_name','away_shortName', 'away_officialName', 'away_code', 'away_position',
       'away_country.id', 'away_country.name', 'home_photo', 'away_photo','match_url'] 
    for col in expected_cols:
        assert col in df.columns

    assert df["matchInfo.description"].notna().all()

def test_extract_results(client):
    df = client.extract_results(country_name, league_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols =  ['matchInfo.id', 'matchInfo.localDate', 'matchInfo.localTime','matchInfo.week', 'matchInfo.description', 'matchInfo.competition.id',
       'matchInfo.competition.name', 'matchInfo.competition.knownName','matchInfo.competition.competitionFormat', 'matchInfo.competition.country.id',
       'matchInfo.competition.country.name', 'matchInfo.tournamentCalendar.id','matchInfo.tournamentCalendar.name', 'matchInfo.venue.id',
       'matchInfo.venue.neutral', 'matchInfo.venue.longName','matchInfo.venue.shortName', 'matchInfo.venue.latitude','matchInfo.venue.longitude',
        'liveData.matchDetails.matchStatus','liveData.matchDetailsExtra.matchOfficial', 'liveData.matchDetails.winner', 'liveData.matchDetails.period',
         'liveData.matchDetails.scores.ht.home','liveData.matchDetails.scores.ht.away', 'liveData.matchDetails.scores.ft.home','liveData.matchDetails.scores.ft.away',
       'liveData.matchDetails.scores.total.home','liveData.matchDetails.scores.total.away', 'liveData.goal','liveData.substitute', 'liveData.matchDetailsExtra.attendance',
       'liveData.card', 'liveData.missedPen', 'liveData.VAR', 'home_id','home_name', 'home_shortName', 'home_officialName', 'home_code','home_position', 'home_country.id',
        'home_country.name', 'away_id','away_name', 'away_shortName', 'away_officialName', 'away_code','away_position', 'away_country.id', 'away_country.name', 'home_photo',
       'away_photo', 'match_url' ]
    for col in expected_cols:
        assert col in df.columns

    assert df["matchInfo.description"].notna().all()

def test_extract_squads_info(client):
    df = client.extract_squads_info(country_name, league_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = ['contestantId', 'contestantName', 'contestantShortName',
       'contestantClubName', 'contestantCode', 'tournamentCalendarId',
       'tournamentCalendarStartDate', 'tournamentCalendarEndDate',
       'competitionName', 'competitionId', 'venueName', 'venueId',
       'slugContestantName', 'competition_slug', 'teamUrl', 'teamPhoto']
    
    for col in expected_cols:
        assert col in df.columns

    assert df["contestantId"].notna().all()

def test_extract_squads_info_invalid_type(client):
    with pytest.raises(TypeError):
        client.extract_squads_info(123, league_name, season )


def test_extract_squads_info_invalid_league(client):
    with pytest.raises(RuntimeError):
        client.extract_squads_info( country_name,  "league_that_does_not_exist_123", season )


def test_get_league_teams_cache(client):
    df = client.get_teams(country_name, league_name, season)

    assert isinstance(df, pd.DataFrame)

    assert league_name in client._league_teams_cache


def test_get_teams(client):
    df = client.get_teams(country_name, league_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "contestantId" in df.columns

def test_extract_team_kits(client):
    df = client.extract_team_kits( country_name,league_name, team_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "shirtColour1" in df.columns
    assert "type" in df.columns

def test_extract_teams_stats(client):
    df = client.extract_teams_stats( country_name,league_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "team" in df.columns
    assert "id_team" in df.columns

def test_extract_players_stats(client):
    df = client.extract_players_stats( country_name,league_name, season)

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "team" in df.columns
    assert "id_team" in df.columns
    assert "player_name" in df.columns
    assert "id" in df.columns

def test_extract_standings_total(client):

    df = client.extract_standings_by_type(country_name, league_name, season, "total")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    expected_cols = [  "rank", "contestantName","points","matchesPlayed","goalsFor","goalsAgainst","team_photo"]
    for col in expected_cols:
        assert col in df.columns


def test_extract_standings_home(client):

    df = client.extract_standings_by_type( country_name,league_name, season, "home")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "rank" in df.columns
    assert "points" in df.columns

def test_extract_standings_home(client):

    df = client.extract_standings_by_type( country_name,league_name, season, "attendance")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        return

    assert "venueName" in df.columns
    assert "venueId" in df.columns


def test_extract_standings_invalid_type_table(client):

    with pytest.raises(RuntimeError):
        client.extract_standings_by_type(country_name, league_name, season,"fake_table")


def test_extract_standings_invalid_country_type(client):

    with pytest.raises(TypeError):
        client.extract_standings_by_type( 123, league_name, season,"total")


def test_extract_standings_invalid_season(client):

    with pytest.raises(RuntimeError):
        client.extract_standings_by_type( country_name, league_name,"1900/1901","total")
