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

competitions= client.competition.fetch_all(COMPETITIONS_URL)
print(competitions)

list_competitions= client.competition.list_all()
print(list_competitions)

competition_name= client.competition.get_by_name( 'LaLiga')
print(competition_name)


