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

url_league= 'https://www.365scores.com/football/league/laliga-11'
df_standings_general= client.league.extract_standings_league(url_league,season= '2025/2026', type_standing='General')
print(df_standings_general)

df_standings_home= client.league.extract_standings_league(url_league,season= '2025/2026', type_standing='Home')
print(df_standings_home)

df_standings_away= client.league.extract_standings_league(url_league,season= '2025/2026', type_standing='Away')
print(df_standings_away)