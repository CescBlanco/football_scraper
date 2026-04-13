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


# df_row_player, df_clean_player= client.player.extract_player_details('https://www.365scores.com/football/player/raphinha-39789')
# print(df_clean_player)

# df_stats_season_by_competition= client.player.extract_stats_season_by_competition('https://www.365scores.com/football/player/raphinha-39789', 'LaLiga')
# print(df_stats_season_by_competition)

# df_career_stats_last_season=  client.player.extract_career_stats_last_season('https://www.365scores.com/football/player/raphinha-39789')
# print(df_career_stats_last_season)

# df_trophies= client.player.extract_trophies('https://www.365scores.com/football/player/raphinha-39789')
# print(df_trophies)

# df_carrer_history= client.player.extract_career_history('https://www.365scores.com/football/player/raphinha-39789')
# print(df_carrer_history)

# df_last_matches= client.player.extract_last_matches('https://www.365scores.com/football/player/raphinha-39789')
# print(df_last_matches)

# df_basic_info_penalties, df_penalties_player= client.player.extract_penalty_shots('https://www.365scores.com/football/player/raphinha-39789')
# print(df_basic_info_penalties)
# print(df_penalties_player)