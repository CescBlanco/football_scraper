import pytest
import pandas as pd
from football_scraper.providers.transfermarkt.client import TransfermarktClient



@pytest.fixture
def client():
    return TransfermarktClient()

def test_extract_profile_info_returns_dataframe(client):
    df = client.player.extract_profile_info("https://www.transfermarkt.com/lamine-yamal/profil/spieler/937958")

    assert not df.empty
    assert "Name" in df.columns
    assert "age" in df.columns
    assert "current_club" in df.columns

def test_extract_stats_player_season_returns_dict(client):
    data = client.player.extract_stats_player_season("https://www.transfermarkt.com/lamine-yamal/leistungsdaten/spieler/937958/saison/2025/plus/1#gesamt")

    assert isinstance(data, dict)
    assert len(data) > 0

def test_extract_player_all_seasons_stats(client):
    df = client.player.extract_player_all_seasons_stats("https://www.transfermarkt.com/lamine-yamal/leistungsdatendetails/spieler/937958/saison//verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/plus/1")
    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "goals" in df.columns

def test_get_stats_by_club_returns_dict(client):
    url = "https://www.transfermarkt.com/lamine-yamal/leistungsdatenverein/spieler/937958"

    data = client.player.get_stats_by_club(url)

    assert isinstance(data, dict)
    assert "by_club" in data
    assert "by_competition" in data

def test_extract_stats_by_coach_returns_dataframe(client):
    url = "https://www.transfermarkt.com/lamine-yamal/leistungsdatentrainer/spieler/937958/plus/1"

    df = client.player.extract_stats_by_coach(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "coach" in df.columns
    assert "goals" in df.columns

def test_extract_record_against_returns_dataframe(client):
    url = "https://www.transfermarkt.com/lamine-yamal/bilanz/spieler/937958/plus/1?wettbewerb="

    df = client.player.extract_record_against(url)

    assert isinstance(df, pd.DataFrame)
    assert "team" in df.columns
    assert "appearances" in df.columns

def test_extract_penalty_goals_returns_two_dataframes(client):
    url = "https://www.transfermarkt.com/robert-lewandowski/elfmetertore/spieler/38253/saison_id//wettbewerb_id//plus/1"

    df_scored, df_missed = client.player.extract_penalty_goals(url)

    assert isinstance(df_scored, pd.DataFrame)
    assert isinstance(df_missed, pd.DataFrame)

def test_extract_all_goals(client):
    url = "https://www.transfermarkt.com/lamine-yamal/alletore/spieler/937958/saison//verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/minute/0/torart/0/plus/1"

    df = client.player.extract_all_goals(url)

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "competition" in df.columns
    assert "type_of_goal" in df.columns


def test_extract_goals_by_minute(client):
    url = "https://www.transfermarkt.com/lamine-yamal/torenachminute/spieler/937958/saison//verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/plus/1"

    df = client.player.extract_goals_by_minute(url)

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "total" in df.columns

def test_extract_player_absences(client):
    url = "https://www.transfermarkt.com/lamine-yamal/verletzungen/spieler/937958/plus/1"

    df1, df2 = client.player.extract_player_absences(url)

    assert isinstance(df1, pd.DataFrame)
    assert isinstance(df2, pd.DataFrame)

def test_extract_suspensions_absences(client):
    url = "https://www.transfermarkt.com/lamine-yamal/ausfaelle/spieler/937958"

    df = client.player.extract_suspensions_absences(url)

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "absence_type" in df.columns

def test_extract_mkt_value_overtime(client):
    url = "https://www.transfermarkt.com/lamine-yamal/marktwertverlauf/spieler/937958"

    df = client.player.extract_mkt_value_overtime(url)

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    assert "market_value" in df.columns
    assert "date" in df.columns
    assert "team" in df.columns
    assert "player" in df.columns

def test_extract_transfer_history(client):
    url = "https://www.transfermarkt.com/lamine-yamal/transfers/spieler/937958"

    df = client.player.extract_transfer_history(url)

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "left_team" in df.columns
    assert "joined_team" in df.columns
    assert "market_value" in df.columns
    assert "left_team_photo" in df.columns
    assert "joined_team_photo" in df.columns

def test_extract_national_team_stats(client):
    url = "https://www.transfermarkt.com/lamine-yamal/nationalmannschaft/spieler/937958/verein_id/3375/hauptwettbewerb//wettbewerb_id//start/2023-09-08/ende/2026-03-01/nurEinsatz/0/plus/1"

    df = client.player.extract_national_team_stats(url)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert "goals" in df.columns
        assert "appearances" in df.columns

def test_player_achievements(client):
    url = "https://www.transfermarkt.com/joan-garcia/erfolge/spieler/561613"

    df = client.player.extract_player_achievements(url)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "season" in df.columns
        assert "title" in df.columns
        assert "team" in df.columns

def test_debut_appearances(client):
    url ="https://www.transfermarkt.com/lamine-yamal/debuets/spieler/937958"

    df = client.player.extract_debut_appearances(url)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert "team" in df.columns
        assert "date" in df.columns

def test_scoring_debuts(client):
    url =  "https://www.transfermarkt.com/lamine-yamal/tordebuets/spieler/937958"

    df = client.player.extract_scoring_debuts(url)

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert "team" in df.columns
        assert "date" in df.columns

def test_extract_greatest_wins(client):
    df = client.player.extract_greatest_wins("https://www.transfermarkt.com/joan-garcia/siege/spieler/561613")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert "team" in df.columns
        assert "goals" in df.columns
        assert "assists" in df.columns
        assert "minutes_played" in df.columns

def test_extract_heaviest_losses(client):
    df = client.player.extract_heaviest_losses("https://www.transfermarkt.com/joan-garcia/niederlagen/spieler/561613")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert "team" in df.columns
        assert "minutes_played" in df.columns

def test_extract_most_goals_in_one_match(client):
    df = client.player.extract_most_goals_in_one_match("https://www.transfermarkt.com/lamine-yamal/meistetore/spieler/937958")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert "club" in df.columns
        assert "goals" in df.columns
        assert "assists" in df.columns
        assert "minutes_played" in df.columns

def test_extract_most_goalassists_in_one_match(client):
    url = "https://www.transfermarkt.com/lamine-yamal/leistungsdaten/spieler/937958"
    df = client.player.extract_most_goalassists_in_one_match("https://www.transfermarkt.com/lamine-yamal/meistetorbeteiligungen/spieler/937958")

    assert isinstance(df, pd.DataFrame)

    if not df.empty:
        assert "competition" in df.columns
        assert  "date" in df.columns
        assert "result" in df.columns
        assert "club_url" in df.columns
        assert "goals_assists" in df.columns

def test_extract_squad_number_history_and_national_team(client):
    url = "https://www.transfermarkt.com/joan-garcia/rueckennummern/spieler/561613"
    team_df, nt_df = client.player.extract_squad_number_history_and_national_team(url)

    assert isinstance(team_df, pd.DataFrame)
    assert isinstance(nt_df, pd.DataFrame)

def test_extract_games_played_together(client):
    url = "https://www.transfermarkt.com/joan-garcia/gemeinsameSpiele/spieler/561613/kriterium/2/wettbewerb//liga/0/verein/0/status/0/pos/0/gegner/0/plus/1"
    df = client.player.extract_games_played_together(url)

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "ppg" in df.columns
    assert "matches" in df.columns
    assert "joint_goal_participation" in df.columns

def test_extract_games_against_player(client):
    url = "https://www.transfermarkt.com/joan-garcia/spieleGegeneinander/spieler/561613/kriterium/2/wettbewerb//liga/0/verein/0/status/0/pos/0/gegner/0/plus/1"
    df = client.player.extract_games_against_player(url)

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "player_photo" in df.columns
    assert "position" in df.columns
    assert "highest_market_value" in df.columns
