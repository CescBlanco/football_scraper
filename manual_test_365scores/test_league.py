import requests
import pandas as pd

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

pd.set_option('display.max_columns', None)
from providers.three_sixty_five_scores.client import Scores365Client
from providers.three_sixty_five_scores.constants import BASE_URL, COMPETITIONS_URL, DEFAULT_HEADERS


# Inicializar cliente
client = Scores365Client()
client.competition.fetch_all(COMPETITIONS_URL)

# df_standings_general= client.league.extract_standings('LaLiga' ,season= '2025/2026', type_standing='General')
# print(df_standings_general)

# df_standings_home= client.league.extract_standings('LaLiga' ,season= '2025/2026', type_standing='Home')
# print(df_standings_home)

# df_standings_away= client.league.extract_standings('LaLiga' ,season= '2025/2026', type_standing='Away')
# print(df_standings_away)

# df_stats_team_league= client.league.extract_top_teams_stats('LaLiga')
# print(df_stats_team_league)

# df_top_players_stats= client.league.extract_top_players_stats('LaLiga')
# print(df_top_players_stats)

# df_history_league= client.league.extract_history_winners('LaLiga')
# print(df_history_league)

# df_team_of_week, formation=client.league.extract_actual_team_of_week('LaLiga')
# print(formation)
# print(df_team_of_week)

# df_transfers_league= client.league.extract_transfers('LaLiga')
# print(df_transfers_league)

# df_info_teams_league= client.league.extract_info_teams('LaLiga')
# print(df_info_teams_league)

# df_next_matches_league= client.league.extract_next_matches('LaLiga')
# print(df_next_matches_league)

# df_results_league= client.league.extract_results('LaLiga',season_year='2025')
# print(df_results_league)