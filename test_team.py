import requests
import pandas as pd

pd.set_option('display.max_columns', None)


from providers.transfermarkt.client import TransfermarktClient
from providers.transfermarkt.constants import COMPETITIONS_URL

client = TransfermarktClient()
client.competition.fetch_all(COMPETITIONS_URL)

# usar el MISMO objeto
# leagues = client.competition.list_all()
# print(leagues)

# df_teams_league_season = client.team.extract_teams_league("LaLiga - Spain (ES1)", 2025)
# print(df_teams_league_season)

# url_full_squad_details = "https://www.transfermarkt.com/fc-barcelona/kader/verein/131/plus/1/galerie/0?saison_id=2025"
# df_full_squad_details = client.team.extract_full_squad_details(url_full_squad_details, "LaLiga - Spain", 2025)
# print(df_full_squad_details)

# url_agent_contracts = "https://www.transfermarkt.com/fc-barcelona/berateruebersicht/verein/131/plus/1"
# df_agent_contracts = client.team.extract_agent_and_contracts(url_agent_contracts)
# print(df_agent_contracts)

# url_suspension_injuries= "https://www.transfermarkt.com/fc-barcelona/sperrenundverletzungen/verein/131/plus/1"
# df_injuries_team, df_suspension_team =  client.team.extract_suspensions_and_injuries(url_suspension_injuries)
# print(df_injuries_team)
# print(df_suspension_team)

# url_internationals_players= "https://www.transfermarkt.com/fc-barcelona/nationalspieler/verein/131/plus/1#anationalspieler"
# df_national_team_players= client.team.extract_national_team_players(url_internationals_players)
# print(df_national_team_players)

# url_foreigners_team = "https://www.transfermarkt.com/131tm/legionaere/verein/131/plus/1"
# df_foreigners_details = client.team.extract_foreigners_team(url_foreigners_team)
# print(df_foreigners_details)

# url_experience = "https://www.transfermarkt.com/fc-barcelona/erfahrung/verein/131/wettbewerbAuswahl/ES1/plus/1"
# df_experience_team= client.team.extract_experience_team(url_experience)
# print(df_experience_team)

# url_end_of_contract= "https://www.transfermarkt.com/fc-barcelona/vertragsende/verein/131/vertragsendeJahr/2026/plus/1"
# df_end_of_contract_team = client.team.extract_end_of_contract_team(url_end_of_contract)
# print(df_end_of_contract_team)

# url_club_debutants = "https://www.transfermarkt.com/fc-barcelona/debuetanten/verein/131/wettbewerb_id/ES1/plus/1"
# df_club_debutants= client.team.extract_club_debutants(url_club_debutants)
# print(df_club_debutants)

# url_penalty_takers= "https://www.transfermarkt.com/fc-barcelona/elfmeterschuetzen/verein/131"
# df_penalty_takers_team= client.team.extract_penalty_takers_team(url_penalty_takers)
# print(df_penalty_takers_team)

# url_market_value_analysis= "https://www.transfermarkt.com/131tm/marktwertanalyse/verein/131/plus/"
# df_market_value_analysis_team= client.team.extract_market_value_analysis_team(url_market_value_analysis)
# print(df_market_value_analysis_team)

# url_market_value_debut= "https://www.transfermarkt.com/131tm/marktwertbeimdebuet/verein/131/plus/1"
# df_market_value_at_debut= client.team.extract_market_value_at_debut(url_market_value_debut)
# print(df_market_value_at_debut)

# url_record_fixtures= "https://www.transfermarkt.com/fc-barcelona/spielplan/verein/131/saison_id/2025"
# df_fixtures_by_competition = client.team.extract_season_record_team(url_record_fixtures)
# print(df_fixtures_by_competition)

# url_fixtures_by_date = "https://www.transfermarkt.com/fc-barcelona/spielplandatum/verein/131/saison_id/2025/wettbewerb_id//datum_von/0000-00-00/datum_bis/0000-00-00/day/0/plus/1"
# df_matches_by_date = client.team.extract_fixtures_by_date_team(url_fixtures_by_date)
# print(df_matches_by_date)

# url_general =  "https://www.transfermarkt.com/laliga/tabelle/wettbewerb/ES1/saison_id/2025"
# url_home    =  "https://www.transfermarkt.com/laliga/heimtabelle/wettbewerb/ES1/saison_id/2025"
# url_away    =  "https://www.transfermarkt.com/laliga/gasttabelle/wettbewerb/ES1/saison_id/2025"

# df_general, df_home, df_away = client.team.extract_league_tables(url_general, url_home, url_away, "LaLiga", "2025/26")
# print(df_general)
# print(df_home)
# print(df_away)

# url_fixtures_last_matches= "https://www.transfermarkt.com/fc-barcelona/spielplan/verein/131/plus/0?saison_id=2025"
# last_fixtures = client.team.extract_last_games(url_fixtures_last_matches)
# print(last_fixtures)


# url_all_time_standings= "https://www.transfermarkt.com/laliga/ewigeTabelle/wettbewerb/ES1/saison_id_von/1999/saison_id_bis/2025/tabllenart//plus/1"
# df_all_time_standings = client.team.extract_all_time_standings(url_all_time_standings)
# print(df_all_time_standings)

# url_results_grid = "https://www.transfermarkt.com/laliga/kreuztabelle/wettbewerb/ES1/saison_id/2025"
# df_results_grid= client.team.extract_league_grid(url_results_grid)
# print(df_results_grid)


# url_current_season_transfers="https://www.transfermarkt.com/fc-barcelona/transfers/verein/131/saison_id/2025/pos//detailpos/0/w_s//plus/1#zugaenge"
# df_transfer_record, df_arrivals, df_arrivals_summary, df_departures,  df_departures_summary= client.team.extract_current_season_transfer_team(url_current_season_transfers)
# print(df_transfer_record)
# print(df_arrivals)
# print(df_arrivals_summary)
# print(df_departures)
# print(df_departures_summary)


# url_transfers_flows_arrivals= "https://www.transfermarkt.com/fc-barcelona/transferstroeme/verein/131/plus/1?saisonIdVon=1899&saisonIdBis=2025&zuab=zu&verein_id="
# df_transfers_flow_arrivals = client.team.extract_transfers_flows_arrivals(url_transfers_flows_arrivals)
# print(df_transfers_flow_arrivals)


# url_transfers_flows_departures= 'https://www.transfermarkt.com/fc-barcelona/transferstroeme/verein/131/plus/1?saisonIdVon=1899&saisonIdBis=2025&zuab=ab&verein_id='
# df_transfers_flow_departures = client.team.extract_transfers_flows_departures(url_transfers_flows_departures)
# print(df_transfers_flow_departures)

# url_loan_from = "https://www.transfermarkt.com/fc-barcelona/leihspielerhistorie/verein/131/plus/1?saison_id=2025&leihe=war"
# df_loan_from_history = client.team.extract_loan_from_history(url_loan_from)
# print(df_loan_from_history)

# url_loan_out = "https://www.transfermarkt.com/fc-barcelona/leihspielerhistorie/verein/131/plus/1?saison_id=2025&leihe=ist"
# df_loan_out_history = client.team.extract_loan_out_history(url_loan_out)
# print(df_loan_out_history)

# url_record_arrivals = "https://www.transfermarkt.com/fc-barcelona/transferrekorde/verein/131/saison_id//pos//detailpos/0/w_s//altersklasse//plus/1"
# df_record_arrivals = client.team.extract_record_arrivals(url_record_arrivals)
# print(df_record_arrivals)

# url_record_departures="https://www.transfermarkt.com/fc-barcelona/rekordabgaenge/verein/131/saison_id//pos//detailpos/0/w_s//plus/1"
# df_record_departures = client.team.extract_record_departures(url_record_departures)
# print(df_record_departures)

# url_most_value_arrivals= "https://www.transfermarkt.com/fc-barcelona/wertvollstezugaenge/verein/131/saison_id//pos//detailpos/0/w_s//plus/1"
# df_most_v_arrivals = client.team.extract_most_valuable_arrivals(url_most_value_arrivals)
# print(df_most_v_arrivals)

# url_most_value_departures = "https://www.transfermarkt.com/fc-barcelona/wertvollsteabgaenge/verein/131/saison_id//pos//detailpos/0/w_s//plus/1"
# df_most_v_departures = client.team.extract_most_valuable_departures(url_most_value_departures)
# print(df_most_v_departures)

# url_rumors_arrivals= "https://www.transfermarkt.com/fc-barcelona/geruechte/verein/131/plus/1"
# df_rumors_arrivals= client.team.extract_rumors_about_arrivals(url_rumors_arrivals)
# print(df_rumors_arrivals)


# url_rumors_departures= "https://www.transfermarkt.com/fc-barcelona/geruechteabgaenge/verein/131/plus/1"
# df_rumors_departures= client.team.extract_rumors_about_departures(url_rumors_departures)
# print(df_rumors_departures)


# url_achievements = "https://www.transfermarkt.com/fc-barcelona/erfolge/verein/131"
# df_archievements = client.team.extract_achievements(url_achievements)
# print(df_archievements)

# url_attendance = "https://www.transfermarkt.com/fc-barcelona/besucherzahlenentwicklung/verein/131"
# df_attendance = client.team.extract_attendance_team(url_attendance)
# print(df_attendance)

