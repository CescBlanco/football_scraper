import requests
import pandas as pd

pd.set_option('display.max_columns', None)
from providers.transfermarkt.client import TransfermarktClient

# Inicializar cliente
client = TransfermarktClient()


# url_porfile = "https://www.transfermarkt.com/lamine-yamal/profil/spieler/937958"
# df_player_profile_info = client.player.extract_profile_info(url_porfile)
# print(df_player_profile_info)


# url_current_season_player = "https://www.transfermarkt.com/lamine-yamal/leistungsdaten/spieler/937958/saison/2025/plus/1#gesamt"
# stats = client.player.extract_stats_player_season(url_current_season_player)
# print(stats['LaLiga'])

# url_stats_player_all_seasons = "https://www.transfermarkt.com/lamine-yamal/leistungsdatendetails/spieler/937958/saison//verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/plus/1"

# df = client.player.extract_player_all_seasons_stats(url_stats_player_all_seasons)

# print(df)


# url_stats_by_competition_player= "https://www.transfermarkt.com/lamine-yamal/detaillierteleistungsdaten/spieler/937958/plus/1"

# stats = client.player.get_stats_by_competition(url_stats_by_competition_player)

# for k, df in stats.items():
#     print(f"\n=== {k} ===")
#     print(df.head())


# url_stats_by_club_player= "https://www.transfermarkt.com/lamine-yamal/leistungsdatenverein/spieler/937958"
# stats = client.player.get_stats_by_club(url_stats_by_club_player)

# print("By club:")
# print(stats["by_club"])

# print("\nBy competition:")
# print(stats["by_competition"])

# url_stats_by_coach = "https://www.transfermarkt.com/lamine-yamal/leistungsdatentrainer/spieler/937958/plus/1"
# df_stats_by_coach_player = client.player.extract_stats_by_coach(url_stats_by_coach)

# print(df_stats_by_coach_player)



# url_record_against_player= "https://www.transfermarkt.com/lamine-yamal/bilanz/spieler/937958/plus/1?wettbewerb="
# df_record_against_player= client.player.extract_record_against(url_record_against_player)
# print(df_record_against_player)


# url_penalty_goals_player= "https://www.transfermarkt.com/robert-lewandowski/elfmetertore/spieler/38253/saison_id//wettbewerb_id//plus/1"
# url_penalty_goals_gk= "https://www.transfermarkt.com/mike-maignan/elfmeterstatistik/spieler/182906/saison_id//wettbewerb_id//plus/1"

# # Ejemplo para un portero
# df_penalties_saved, df_nonsaved_penalties= client.player.extract_penalty_goals(url_penalty_goals_gk, is_goalkeeper=True)

# # Ejemplo para un jugador de campo
# df_penalties_scored_player, df_penalties_missed_player =client.player.extract_penalty_goals(url_penalty_goals_player, is_goalkeeper=False)

# print(df_penalties_saved)
# print(df_nonsaved_penalties)
# print(df_penalties_scored_player)
# print(df_penalties_missed_player)


# url_all_goals_player= "https://www.transfermarkt.com/lamine-yamal/alletore/spieler/937958/saison//verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/minute/0/torart/0/plus/1"
# df_all_goals_player= client.player.extract_all_goals(url_all_goals_player)
# print(df_all_goals_player)

# url_goals_by_minute = "https://www.transfermarkt.com/lamine-yamal/torenachminute/spieler/937958/saison//verein/0/liga/0/wettbewerb//pos/0/trainer_id/0/plus/1"
# df_goals_by_minute = client.player.extract_goals_by_minute(url_goals_by_minute)
# print(df_goals_by_minute)

# url_history_absences = "https://www.transfermarkt.com/lamine-yamal/verletzungen/spieler/937958/plus/1"
# df_injury_history_player, df_total_injury_player = client.player.extract_player_absences(url_history_absences)
# print(df_injury_history_player)
# print(df_total_injury_player)

# url_suspensions_absences= "https://www.transfermarkt.com/lamine-yamal/ausfaelle/spieler/937958"
# df_suspensions = client.player.extract_suspensions_absences(url_suspensions_absences)
# print(df_suspensions)


# url_market_value_over_time= "https://www.transfermarkt.com/lamine-yamal/marktwertverlauf/spieler/937958"
# df_mkt_value_overtime_player= client.player.extract_mkt_value_overtime(url_market_value_over_time)
# print(df_mkt_value_overtime_player)


url_transfer_history= "https://www.transfermarkt.com/lamine-yamal/transfers/spieler/937958"
df_transfer_history_player = client.player.extract_transfer_history(url_transfer_history)
print(df_transfer_history_player)

#-----------------------HASTA AQUI TODO CORRECTO---------------------------------


# url_national_team_player= "https://www.transfermarkt.com/lamine-yamal/nationalmannschaft/spieler/937958/verein_id/3375/hauptwettbewerb//wettbewerb_id//start/2023-09-08/ende/2026-03-01/nurEinsatz/0/plus/1"
# df_national = client.player.extract_national_team_stats(url_national_team_player)

# print(df_national)

# url_player_archievements= "https://www.transfermarkt.com/joan-garcia/erfolge/spieler/561613"

# df_player_achievements= client.player.extract_player_achievements_transfermarkt(url_player_archievements)
# print(df_player_achievements)

# url_debuts_apearances = "https://www.transfermarkt.com/lamine-yamal/debuets/spieler/937958"

# df_debut_appearances_player= client.player.extract_debut_appearances(url_debuts_apearances)
# print(df_debut_appearances_player)

# url_scoring_debuts = "https://www.transfermarkt.com/lamine-yamal/tordebuets/spieler/937958"

# df_scoring_debuts = client.player.extract_scoring_debuts(url_scoring_debuts)
# print(df_scoring_debuts)

# url_greatests_wins= "https://www.transfermarkt.com/joan-garcia/siege/spieler/561613"
# df_greatest_wins_player= client.player.extract_greatest_wins(url_greatests_wins)
# print(df_greatest_wins_player)

# url_heaviest_losses= "https://www.transfermarkt.com/joan-garcia/niederlagen/spieler/561613"
# df_greatest_losses_player= client.player.extract_heaviest_losses(url_heaviest_losses)
# print(df_greatest_losses_player)

# url_most_goal_in_one_match= "https://www.transfermarkt.com/lamine-yamal/meistetore/spieler/937958"

# df_most_goals_in_one_match= client.player.extract_most_goals_in_one_match(url_most_goal_in_one_match)
# print(df_most_goals_in_one_match)

# url_most_goalassists_in_one_match = "https://www.transfermarkt.com/lamine-yamal/meistetorbeteiligungen/spieler/937958"
# df_most_goal_asisits_in_one_match= client.player.extract_most_goalassists_in_one_match(url_most_goalassists_in_one_match)
# print(df_most_goal_asisits_in_one_match)


# url_squad_number_player= "https://www.transfermarkt.com/joan-garcia/rueckennummern/spieler/561613"
# df_squad_number_team, df_squad_number_national_team = client.player.extract_squad_number_history_and_national_team(url_squad_number_player)
# print(df_squad_number_team)
# print(df_squad_number_national_team)


# url_games_player_together= "https://www.transfermarkt.com/joan-garcia/gemeinsameSpiele/spieler/561613/kriterium/2/wettbewerb//liga/0/verein/0/status/0/pos/0/gegner/0/plus/1"
# df_games_player_together= client.player.extract_games_played_together(url_games_player_together)
# print(df_games_player_together)

# url_games_against_player= "https://www.transfermarkt.com/joan-garcia/spieleGegeneinander/spieler/561613/kriterium/2/wettbewerb//liga/0/verein/0/status/0/pos/0/gegner/0/plus/1"
# df_games_against_player= client.player.extract_games_against_player(url_games_against_player)
# print(df_games_against_player)