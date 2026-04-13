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

# df_squad = client.team.extract_squad_and_competition_available("https://www.365scores.com/football/team/fc-barcelona-132") 
# print(df_squad)

# df_competitions_available = client.team.extract_competition_available("https://www.365scores.com/football/team/fc-barcelona-132") 
# print(df_competitions_available)

# df_recent_form_team = client.team.extract_recent_form("https://www.365scores.com/football/team/fc-barcelona-132")
# print(df_recent_form_team)

# df_next_matches= client.team.extract_next_matches("https://www.365scores.com/football/team/fc-barcelona-132")
# print(df_next_matches)


# df_results_team= client.team.extract_results("https://www.365scores.com/football/team/fc-barcelona-132",season_year='2025')
# print(df_results_team)

# df_stats_one_team= client.team.extract_stats_team("https://www.365scores.com/football/team/fc-barcelona-132", 'LaLiga')
# print(df_stats_one_team)

# df_transfers = client.team.extract_transfers_rumors("https://www.365scores.com/football/team/fc-barcelona-132")
# print(df_transfers)
