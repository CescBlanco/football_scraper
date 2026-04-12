import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np

from providers.three_sixty_five_scores.constants import DEFAULT_HEADERS
from providers.three_sixty_five_scores.utils import extract_season_standings

class Scores365LeagueScraper:
    def __init__(self, session, competition_service, headers=None):
        self.session = session
        self.competition_service = competition_service
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_standings_league(self, url_league: str,season: str = "2023/2024",type_standing: str = "General") -> pd.DataFrame:
        """
        Extract league standings from the 365Scores API.

        This function retrieves standings for a given competition and season,
        including team statistics, recent form, next opponent, and competition
        destinations (e.g., Champions League qualification).

        Args:
            url_league (str):
                League URL containing the competition ID at the end.

            season (str, optional):
                Season name as provided by the API (e.g., "2023/2024").

            type_standing (str, optional):
                Type of standings table to retrieve.
                Options:
                    - "General"
                    - "Home"
                    - "Away"

            headers (Dict[str, str] | None, optional):
                HTTP headers used in the API request.

        Returns:
            pd.DataFrame:
                DataFrame containing team standings with the following fields:
        Raises:
            ValueError:
                If the season or standings type is invalid.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected structure is not found in the API response.
        """
        id_competition = url_league.split('-')[-1]
        seasons_avaiables= extract_season_standings(url_league, headers= self.headers)
        season_selected = str(seasons_avaiables[seasons_avaiables['seasonName']==season]['seasonNum'].iloc[0])

        if type_standing == 'General':
            url_standings = f"https://webws.365scores.com/web/standings/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}&live=false&seasonNum={season_selected}&withSeasonsFilter=true"

        elif type_standing == 'Home': 
            url_standings = f"https://webws.365scores.com/web/standings/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitions={id_competition}&type=2&live=false&stageNum=1&seasonNum={season_selected}&withSeasonsFilter=true"
        else:
            url_standings = f"https://webws.365scores.com/web/standings/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitions={id_competition}&type=3&live=false&stageNum=1&seasonNum={season_selected}&withSeasonsFilter=true"

        response = requests.get(url_standings, headers=self.headers)
        data = response.json()

        destinations = data['standings'][0].get('destinations', [])
        destination_map = {d['num']: d for d in destinations}

        form_map = {0: 'Lost', 1: 'Win', 2: 'Draw'}

        rows = data['standings'][0].get('rows', [])
        all_data = []

        for row in rows:

            team_name = row['competitor'].get('longName', row['competitor'].get('name', 'Unknown'))

            recent_form = row.get('recentForm', [])
            next_match = row.get('nextMatch')

            opponent = None

            if next_match:
                home = next_match['homeCompetitor'].get('longName', next_match['homeCompetitor'].get('name'))
                away = next_match['awayCompetitor'].get('longName', next_match['awayCompetitor'].get('name'))
                opponent = away if team_name == home else home

            all_data.append({
                'id_team': row['competitor'].get('id'),
                'team': team_name,
                'name_for_url': row['competitor'].get('nameForURL', ''),
                'home_color': row['competitor'].get('color', ''),
                'away_color': row['competitor'].get('awayColor', ''),
                'played': row.get('gamePlayed', 0),
                'wins': row.get('gamesWon', 0),
                'draws': row.get('gamesEven', 0),
                'losses': row.get('gamesLost', 0),
                'goals_for': row.get('for', 0),
                'goals_against': row.get('against', 0),
                'goal_diff': row.get('ratio', 0),
                'pts': row.get('points', 0),
                'recent_form': [form_map.get(i) for i in recent_form],
                'destinationNum': row.get('destinationNum'),
                'next_match': opponent,
            })

            df = pd.DataFrame(all_data)

            if destinations:
                df['destination_name'] = df['destinationNum'].map(lambda x: destination_map.get(x, {}).get('name')).fillna('-')
                df['destination_color'] = df['destinationNum'].map(lambda x: destination_map.get(x, {}).get('color'))
        
                df = df.drop(columns=['destinationNum'])
            
            else:
                df = df.drop(columns=['destinationNum'])
        return df

