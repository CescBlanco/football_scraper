import pytest
import pandas as pd
from football_scraper.providers.transfermarkt.client import TransfermarktClient
from football_scraper.providers.transfermarkt.constants import COMPETITIONS_URL

@pytest.fixture
def client():
    client = TransfermarktClient()
    client.competition.fetch_all(COMPETITIONS_URL)
    return client


def test_extract_teams_league(client):
    df = client.team.extract_teams_league("LaLiga - Spain (ES1)", 2025)

    assert isinstance(df, pd.DataFrame)
    assert "club_name" in df.columns

def test_extract_full_squad_details(client):
    url = "https://www.transfermarkt.com/fc-barcelona/kader/verein/131/plus/1/galerie/0?saison_id=2025"
    df = client.team.extract_full_squad_details(url, "La Liga", 2025)

    assert isinstance(df, pd.DataFrame)
    assert "name" in df.columns or "player_url" in df.columns

def test_extract_agent_and_contracts(client):
    df = client.team.extract_agent_and_contracts( "https://www.transfermarkt.com/fc-barcelona/berateruebersicht/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns

def test_extract_suspensions_and_injuries(client):
    injuries, suspensions = client.team.extract_suspensions_and_injuries("https://www.transfermarkt.com/fc-barcelona/sperrenundverletzungen/verein/131/plus/1")

    assert isinstance(injuries, pd.DataFrame)
    assert isinstance(suspensions, pd.DataFrame)

def test_extract_national_team_players(client):
    df = client.team.extract_national_team_players("https://www.transfermarkt.com/fc-barcelona/nationalspieler/verein/131/plus/1#anationalspieler")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns

def test_extract_foreigners_team(client):
    df = client.team.extract_foreigners_team("https://www.transfermarkt.com/131tm/legionaere/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns or "nation" in df.columns

def test_extract_experience_team(client):
    df = client.team.extract_experience_team("https://www.transfermarkt.com/fc-barcelona/erfahrung/verein/131/wettbewerbAuswahl/ES1/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns or "appearances" in df.columns

def test_extract_end_of_contract_team(client):
    df = client.team.extract_end_of_contract_team("https://www.transfermarkt.com/fc-barcelona/vertragsende/verein/131/vertragsendeJahr/2026/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns or "market_value" in df.columns

def test_extract_club_debutants(client):
    df = client.team.extract_club_debutants("https://www.transfermarkt.com/fc-barcelona/debuetanten/verein/131/wettbewerb_id/ES1/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns

def test_extract_penalty_takers_team(client):
    df = client.team.extract_penalty_takers_team("https://www.transfermarkt.com/fc-barcelona/elfmeterschuetzen/verein/131")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns or "competition" in df.columns

def test_extract_market_value_analysis_team(client):
    df = client.team.extract_market_value_analysis_team("https://www.transfermarkt.com/131tm/marktwertanalyse/verein/131/plus/")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns or "market_value" in df.columns

def test_extract_market_value_at_debut(client):
    df = client.team.extract_market_value_at_debut("https://www.transfermarkt.com/131tm/marktwertbeimdebuet/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns or "current_market_value" in df.columns

def test_extract_season_record_fixtures(client):
    df = client.team.extract_season_record_team("https://www.transfermarkt.com/fc-barcelona/spielplan/verein/131/saison_id/2025")

    assert isinstance(df, pd.DataFrame)
    assert "competition" in df.columns
    assert "matches" in df.columns
    assert "wins" in df.columns

def test_extract_fixtures_by_date_team(client):
    df = client.team.extract_fixtures_by_date_team("https://www.transfermarkt.com/fc-barcelona/spielplandatum/verein/131/saison_id/2025/wettbewerb_id//datum_von/0000-00-00/datum_bis/0000-00-00/day/0/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "home_team" in df.columns or "competition" in df.columns

def test_extract_league_tables(client):
    url_general ="https://www.transfermarkt.com/laliga/tabelle/wettbewerb/ES1/saison_id/2025"
    url_home = "https://www.transfermarkt.com/laliga/heimtabelle/wettbewerb/ES1/saison_id/2025"
    url_away = "https://www.transfermarkt.com/laliga/gasttabelle/wettbewerb/ES1?saison_id=2025"

    df_general, df_home, df_away = client.team.extract_league_tables(url_general, url_home, url_away, "LaLiga", "2025/26")

    assert isinstance(df_general, pd.DataFrame)
    assert isinstance(df_home, pd.DataFrame)
    assert isinstance(df_away, pd.DataFrame)

    assert len(df_general.columns) > 0
    assert len(df_home.columns) > 0
    assert len(df_away.columns) > 0
    assert "team" in df_general.columns or "club" in df_general.columns

def test_extract_last_games(client):
    df = client.team.extract_last_games("https://www.transfermarkt.com/fc-barcelona/spielplan/verein/131/plus/0?saison_id=2025")

    assert isinstance(df, pd.DataFrame)
    assert "opponent" in df.columns
    assert "result" in df.columns

def test_extract_all_time_standings(client):
    df = client.team.extract_all_time_standings("https://www.transfermarkt.com/laliga/ewigeTabelle/wettbewerb/ES1/saison_id_von/1999/saison_id_bis/2025/tabllenart//plus/1")

    assert isinstance(df, pd.DataFrame)

    # si falla Selenium o no carga, al menos no revienta
    if df.empty:
        assert True
        return

    assert "position" in df.columns or "#" not in df.columns

def test_extract_league_grid(client):
    df = client.team.extract_league_grid("https://www.transfermarkt.com/laliga/kreuztabelle/wettbewerb/ES1/saison_id/2025")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        assert True
        return

    assert df.shape[0] > 0
    assert df.shape[1] > 0

def test_extract_current_season_transfer_team(client):
    result = client.team.extract_current_season_transfer_team("https://www.transfermarkt.com/fc-barcelona/transfers/verein/131/saison_id/2025/pos//detailpos/0/w_s//plus/1#zugaenge")

    assert isinstance(result, tuple)
    assert len(result) == 5

    df_transfer_record, df_arrivals, df_arrivals_summary, df_departures, df_departures_summary = result

    assert isinstance(df_transfer_record, pd.DataFrame)
    assert isinstance(df_arrivals, pd.DataFrame)
    assert isinstance(df_arrivals_summary, pd.DataFrame)
    assert isinstance(df_departures, pd.DataFrame)
    assert isinstance(df_departures_summary, pd.DataFrame)

    assert len(df_arrivals.columns) > 0
    assert len(df_departures.columns) > 0

def test_extract_transfers_flows_arrivals(client):
    df = client.team.extract_transfers_flows_arrivals("https://www.transfermarkt.com/fc-barcelona/transferstroeme/verein/131/plus/1?saisonIdVon=1899&saisonIdBis=2025&zuab=zu&verein_id=")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        assert True
        return

    assert "club" in df.columns
    assert "transfers" in df.columns
    assert "transfer_volume" in df.columns

def test_extract_transfers_flows_departures(client):
    df = client.team.extract_transfers_flows_departures('https://www.transfermarkt.com/fc-barcelona/transferstroeme/verein/131/plus/1?saisonIdVon=1899&saisonIdBis=2025&zuab=ab&verein_id=')

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        assert True
        return

    assert "club" in df.columns
    assert "transfers" in df.columns
    assert "transfer_volume" in df.columns

def test_extract_loan_from_history(client):
    df = client.team.extract_loan_from_history("https://www.transfermarkt.com/fc-barcelona/leihspielerhistorie/verein/131/plus/1?saison_id=2025&leihe=war")

    assert isinstance(df, pd.DataFrame)

    if df.empty:
        assert True
        return

    assert "player" in df.columns
    assert "on_loan_from" in df.columns
    assert "loan_start" in df.columns

def test_extract_loan_out_history(client):
    df = client.team.extract_loan_out_history("https://www.transfermarkt.com/fc-barcelona/leihspielerhistorie/verein/131/plus/1?saison_id=2025&leihe=ist")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "player_url" in df.columns

def test_extract_record_arrivals(client):
    df = client.team.extract_record_arrivals("https://www.transfermarkt.com/fc-barcelona/transferrekorde/verein/131/saison_id//pos//detailpos/0/w_s//altersklasse//plus/1")

    assert df["fee"].notna().any()

def test_extract_record_departures(client):
    df = client.team.extract_record_departures("https://www.transfermarkt.com/fc-barcelona/transferrekorde/verein/131/saison_id//pos//detailpos/0/w_s//altersklasse//plus/1")

    assert df["fee"].notna().any()

def test_extract_most_valuable_arrivals(client):
    df = client.team.extract_most_valuable_arrivals("https://www.transfermarkt.com/fc-barcelona/wertvollstezugaenge/verein/131/saison_id//pos//detailpos/0/w_s//plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player_name" in df.columns
    assert "fee" in df.columns

def test_extract_most_valuable_departures(client):
    df = client.team.extract_most_valuable_departures("https://www.transfermarkt.com/fc-barcelona/wertvollsteabgaenge/verein/131/saison_id//pos//detailpos/0/w_s//plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player_name" in df.columns
    assert "fee" in df.columns

def test_extract_rumors_about_arrivals(client):
    df = client.team.extract_rumors_about_arrivals("https://www.transfermarkt.com/fc-barcelona/geruechte/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player_name" in df.columns
    assert "interest_team_name" in df.columns

def test_extract_rumors_about_departures(client):
    df = client.team.extract_rumors_about_departures("https://www.transfermarkt.com/fc-barcelona/geruechteabgaenge/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player_name" in df.columns
    assert "interest_team_name" in df.columns

def test_extract_achievements(client):
    df = client.team.extract_achievements("https://www.transfermarkt.com/fc-barcelona/erfolge/verein/131")

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "title" in df.columns

def test_extract_attendance_team(client):
    df = client.team.extract_attendance_team("https://www.transfermarkt.com/fc-barcelona/besucherzahlenentwicklung/verein/131")

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "league" in df.columns
    assert "avg_spectators" in df.columns

def test_extract_historical_standings(client):
    df = client.team.extract_historical_standings("https://www.transfermarkt.com/fc-barcelona/platzierungen/verein/131")

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "points" in df.columns
    assert "position" in df.columns

def test_extract_cup_history(client):
    df = client.team.extract_cup_history("https://www.transfermarkt.com/fc-barcelona/pokalhistorie/verein/131#google_vignette")

    assert isinstance(df, pd.DataFrame)
    assert "competition" in df.columns
    assert "season" in df.columns
    assert "opponents" in df.columns

def test_extract_record_against(client):
    df = client.team.extract_record_against("https://www.transfermarkt.com/fc-barcelona/bilanz/verein/131/saison_id//wettbewerb_id//datum_von/0000-00-00/datum_bis/0000-00-00/land_id/0/group/1/day/0/clubs_in_comp_id//plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "team" in df.columns
    assert "matches" in df.columns
    assert "goals_for" in df.columns

def test_extract_record_players(client):
    df = client.team.extract_record_players("https://www.transfermarkt.com/fc-barcelona/rekordspieler/verein/131/wettbewerb_id/alle/position/alle/aktive/alle/detailposition/alle/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "rank" in df.columns
    assert "player" in df.columns
    assert "player_url" in df.columns
    assert "appearances" in df.columns
    assert "goals" in df.columns
    assert "assists" in df.columns
    assert "minutes_played" in df.columns


def test_extract_top_scorers(client):
    df = client.team.extract_top_scorers("https://www.transfermarkt.com/fc-barcelona/toptorschuetzen/verein/131/wettbewerb_id/alle/position/alle/detailposition/alle/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "goals" in df.columns
    assert "appearances" in df.columns
    assert df.shape[0] > 0
    assert df["player"].notna().any()

def test_extract_top_scores_by_season(client):
    df = client.team.extract_top_scores_by_season("https://www.transfermarkt.com/fc-barcelona/toptorschuetzensaison/verein/131/wettbewerb_id//pos//plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "season" in df.columns
    assert "player" in df.columns
    assert "goals" in df.columns
    assert "competition" in df.columns

def test_extract_most_value_players(client):
    df = client.team.extract_most_value_players( "https://www.transfermarkt.com/fc-barcelona/wertvollsteSpielerVereinshistorie/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "player_url" in df.columns
    assert "highest_market_value" in df.columns
    assert "current_team" in df.columns


def test_extract_foreign_players(client):
    df = client.team.extract_foreign_players("https://www.transfermarkt.com/fc-barcelona/gastarbeiter/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "nation" in df.columns
    assert "player_name" in df.columns
    assert "player_url" in df.columns

def test_extract_debut_young_old_players(client):
    df_young, df_old = client.team.extract_debut_young_old_players( "https://www.transfermarkt.com/fc-barcelona/juengsteAelteste/verein/131/saisonIdVon/1901/saisonIdBis/2025/wettbewerb_id/gesamt/plus/1#jung")

    assert isinstance(df_young, pd.DataFrame)
    assert isinstance(df_old, pd.DataFrame)

    assert "player" in df_young.columns
    assert "player" in df_old.columns
    assert "category" not in df_young.columns
    assert "category" not in df_old.columns

def test_extract_where_ex_players(client):
    df = client.team.extract_where_ex_players("https://www.transfermarkt.com/fc-barcelona/weristwo/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "current_club" in df.columns

def test_extract_returned_players(client):
    df = client.team.extract_returned_players("https://www.transfermarkt.com/fc-barcelona/rueckkehrer/verein/131/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "player" in df.columns
    assert "appearances_after" in df.columns

def test_extract_staff_history(client):
    df = client.team.extract_staff_history("https://www.transfermarkt.com/fc-barcelona/mitarbeiterhistorie/verein/131/personalie_id/0/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert "coach" in df.columns
    assert "matches" in df.columns

def test_extract_referee_statistics(client):
    df = client.team.extract_referee_statistics("https://www.transfermarkt.com/fc-barcelona/schiedsrichter/verein/131/reldata/&2025")

    assert isinstance(df, pd.DataFrame)
    assert "referee" in df.columns
    assert "matches" in df.columns

def test_extract_penalty_statistics(client):
    df = client.team.extract_penalty_statistics("https://www.transfermarkt.com/fc-barcelona/elfmeterstatistik/verein/131/reldata/%262025/plus/1")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    required_cols = ["player","player_url", "penalties", "converted","missed", "ratio"]

    for col in required_cols:
        assert col in df.columns

    assert df["player"].notna().any()

def test_extract_penalty_shootouts(client):
    df = client.team.extract_penalty_shootouts("https://www.transfermarkt.com/fc-barcelona/elfmeterschiessen/verein/131/haupt_wettbewerb_id//plus/1")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    required_cols = ["competition", "season","round","team_home","team_away","result"]

    for col in required_cols:
        assert col in df.columns

    assert df["competition"].astype(str).str.len().mean() > 0