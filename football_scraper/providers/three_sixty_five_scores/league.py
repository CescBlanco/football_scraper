import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np
from typing import List, Dict, Optional, Any, Tuple

from football_scraper.providers.three_sixty_five_scores.constants import DEFAULT_HEADERS, BASE_URL
from football_scraper.providers.three_sixty_five_scores.utils import extract_season_standings

class Scores365LeagueScraper:
    def __init__(self, session, competition_service, headers=None):
        self.session = session
        self.competition_service = competition_service
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_standings(self, league: str,season: str = "2023/2024",type_standing: str = "General") -> pd.DataFrame:
        """
        Extract league standings from the 365Scores API.

        This function retrieves standings for a given competition and season,
        including team statistics, recent form, next opponent, and competition
        destinations (e.g., Champions League qualification).

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

            season (str, optional):
                Season name as provided by the API (e.g., "2023/2024").

            type_standing (str, optional):
                Type of standings table to retrieve.
                Options:
                    - "General"
                    - "Home"
                    - "Away"

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
        comp = self.competition_service.get_by_name(league)
        
        id_competition = str(comp['id'])
        slug_competition = comp['nameForURL']
        url_league= f'{BASE_URL}/football/league/{slug_competition}-{id_competition}'
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

    def extract_top_teams_stats(self, league: str) -> pd.DataFrame:
        """
        Extract top team statistics for a league from the 365Scores API.

        The function retrieves aggregated statistics (e.g., goals scored,
        clean sheets, etc.) for teams participating in a competition.

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            pd.DataFrame:
                DataFrame containing team statistics with the following fields:

                - id_team
                - team
                - value
                - name_stat

        Raises:
            ValueError:
                If the competition ID cannot be extracted from the URL.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected fields are missing in the API response.
        """

        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])
   
        try:
            response = requests.get(f'https://webws.365scores.com/web/stats/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}&competitors=&withSeasons=true', headers=self.headers)
            response.raise_for_status()
            stats= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving league statistics: {e}") from e
        
        # Validate JSON structure
        if "stats" not in stats or "competitorsStats" not in stats["stats"]:
            raise KeyError("Invalid API response: 'competitorsStats' not found.")
        
        all_data= []

        for stat in stats['stats']['competitorsStats']:
            stat_name = stat['name']

            for rank, row in enumerate(stat['rows'], start=1):
                    id_team = row['entity']['id']

                    team = row['entity']['name']


                    value = row['stats'][0]['value'] if row['stats'] else None
                    all_data.append({
                        'id_team': id_team,
                        'team': team,
                        'value': value,
                        'name_stat': stat_name,
                    })
        return pd.DataFrame(all_data)
    
    def extract_top_players_stats(self, league: str) -> pd.DataFrame:
        """
        Extract top player statistics for a league from the 365Scores API.

        This function retrieves aggregated statistics for players participating
        in a given competition (e.g., goals, assists, etc.) and returns them
        in a normalized pandas DataFrame.

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            pd.DataFrame:
                DataFrame containing player statistics with the following columns:

                - id_player
                - player
                - name_for_url
                - positionName
                - value
                - name_stat

        Raises:
            ValueError:
                If the competition ID cannot be extracted from the URL.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected JSON structure is not present in the API response.
        """
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])
        
        # Perform API request
        try:
            response = requests.get(f'https://webws.365scores.com/web/stats/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}&competitors=&withSeasons=true')
            response.raise_for_status()
            stats = response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving player statistics: {e}" ) from e

        # Validate JSON structure
        if "stats" not in stats or "athletesStats" not in stats["stats"]:
            raise KeyError("Invalid API response: 'athletesStats' not found.")
        

        all_data = []

        for stat in stats["stats"]["athletesStats"]:
            stat_name = stat['name']

            for rank, row in enumerate(stat['rows'], start=1):
                id_player = row['entity']['id']
                player = row['entity']['name']
                name_for_url= row['entity']['nameForURL']
                position_name = row['entity']['positionName']
                
                value = row['stats'][0]['value'] if row['stats'] else None

                all_data.append({
                    'id_player': id_player,
                    'player': player,
                    'name_for_url':name_for_url ,
                    'positionName': position_name,
                    'value': value,
                    'name_stat': stat_name,
                    })

        return pd.DataFrame(all_data)
    
    def extract_history_winners(self, league: str) -> pd.DataFrame:
        """
        Extract historical league winners and standings data from the 365Scores API.

        This function retrieves historical competition results including season,
        team information, and match statistics (wins, draws, losses, points).

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            pd.DataFrame:
                DataFrame containing historical league results with columns:

                - season
                - entity_id
                - team
                - symbolicName
                - team_image
                - W (wins)
                - D (draws)
                - L (losses)
                - Puntos

        Raises:
            ValueError:
                If the competition ID cannot be extracted from the URL.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected structure is not found in the API response.
        """

        # Extract competition ID
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])
        
        # API request
        try:
            url_history_league= f"https://webws.365scores.com/web/competitions/history/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}"
            response = requests.get(url_history_league, headers=self.headers)
            response.raise_for_status()
            history = response.json()
        except requests.exceptions.RequestException as e:
                raise requests.exceptions.RequestException(f"Error retrieving league history: {e}") from e

            # Validate JSON structure
        if "competitors" not in history or "table" not in history:
            raise KeyError("Invalid API response structure.")
        
        competitiors = history['competitors']

        competitiors_data = []

        for comp in competitiors:
            competitiors_data.append({
                'entity_id': comp['id'],
                'team': comp.get('longName', comp.get('name')),  # Si no hay longName, usar name
                'symbolicName': comp.get('symbolicName'),
                'team_image': f"https://imagecache.365scores.com/image/upload/f_png,w_40,h_40,c_limit,q_auto:eco,dpr_3,d_Competitors:default1.png/v3/Competitors/{comp['id']}",
                'countryId': comp.get('countryId')
            })

        df_competitors = pd.DataFrame(competitiors_data)

        rows = history['table']['rows']
        column_map = {1: 'W', 2: 'D', 3: 'L', 4: 'Puntos'} 

        rows_data = []

        for row in rows:
            season = row['title']  # '2024/2025'
            entity_id = row['entityId']  # ID del equipo/entidad
            values = row.get('values', [])
            
            row_dict = {'season': season, 'entity_id': entity_id}
            
            # Guardar cada columna en el diccionario usando columnNum como key
            for val in values:
                col_name = column_map.get(val['columnNum'], f"col_{val['columnNum']}")
                row_dict[f'{col_name}'] = val['value']
            
            rows_data.append(row_dict)

        df_history = pd.DataFrame(rows_data)

        df_full = df_history.merge(df_competitors, how='left', left_on='entity_id', right_on='entity_id')


        return df_full[['season', 'entity_id', 'team', 'symbolicName',  'team_image',  'W', 'D', 'L', 'Puntos']]
    
    def extract_actual_team_of_week(self, league: str) -> Tuple[pd.DataFrame, str]:
        """
        Extract the current Team of the Week from the 365Scores API.

        This function retrieves the Team of the Week lineup for a competition,
        including player information, team information, and formation.

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            Tuple[pd.DataFrame, str]:
                - DataFrame containing Team of the Week player information.
                - Formation used in the lineup (e.g., "4-3-3").

        Raises:
            ValueError:
                If the competition ID cannot be extracted from the URL.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected JSON structure is missing.
        """

        # Extract competition ID
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])
        
        url_tow= f"https://webws.365scores.com/web/competitions/teamoftheweek/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}"

        # Request API
        try:
            response = requests.get(url_tow, headers=self.headers)
            response.raise_for_status()
            tow= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving Team of the Week: {e}") from e
        
        # Validate JSON structure
        if "teamOfTheWeek" not in tow or "competitors" not in tow:
            raise KeyError("Invalid API response structure.")
        
        formation= tow['teamOfTheWeek']['lineup']['formation']

        competitiors= tow['competitors']
        competitiors_data= []
        for comp in competitiors:
                competitiors_data.append({
                    'competitor_id': comp['id'],
                    'team': comp.get('longName', comp.get('name')),  # Si no hay longName, usar name
                    'symbolicName': comp.get('symbolicName'),
                    'team_image': f"https://imagecache.365scores.com/image/upload/f_png,w_40,h_40,c_limit,q_auto:eco,dpr_3,d_Competitors:default1.png/v3/Competitors/{comp['id']}",
                })

        df_competitors = pd.DataFrame(competitiors_data)

        tow_data = []
        
        members= tow['teamOfTheWeek']['lineup']['members']
        for player in members:
            tow_data.append({
                'athlete_id': player.get('athleteId'),
                'player_id': player.get('id'),
                'name': player.get('name'),
                'short_name': player.get('shortName'),
                'position': player.get('position', {}).get('name'),
                'formation': player.get('formation', {}).get('name'),
                'jersey_number': player.get('jerseyNumber'),
                'ranking': player.get('ranking'),
                'mvp': player.get('hasHighestRanking'),
                'competitor_id': player.get('competitorId'),
                'national_id': player.get('nationalId'),
                'game_id': player.get('gameId'),
                'name_for_url': player.get('nameForURL'),
            })

        df_team_of_week = pd.DataFrame(tow_data)
        df_team_of_week['player_image'] = df_team_of_week['athlete_id'].apply(
            lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}"
        )
        df = df_team_of_week.merge(df_competitors, how='left', left_on='competitor_id', right_on='competitor_id')
        df= df.drop(columns=['competitor_id'])
        return df, formation
    
    def extract_transfers(self, league: str) -> pd.DataFrame:
        """
        Extract transfer data for a league from the 365Scores API.

        This function retrieves player transfers including player information,
        origin team, destination team, nationality, and contract dates.

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            pd.DataFrame:
                DataFrame containing transfer information including:

                - player information
                - origin team
                - target team
                - nationality
                - transfer date
                - contract expiration

        Raises:
            ValueError:
                If the competition ID cannot be extracted.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the API response structure is invalid.
        """

        # Extract competition ID
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])

        url_transfers = f'https://webws.365scores.com/web/transfers/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}'

        # Request API
        try:
            response = requests.get(url_transfers, headers=self.headers, timeout=10)
            response.raise_for_status()
            transfers= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving transfer data: {e}") from e

        required_keys = {"competitors", "countries", "athletes", "transfers"}
        if not required_keys.issubset(transfers):
            raise KeyError("Invalid API response structure.")

        # ------------------------
        # Teams
        # ------------------------
        df_teams = pd.json_normalize(transfers["competitors"])
        df_teams = df_teams.drop( columns=[  "sportId", "countryId", "type", "popularityRank","imageVersion", "hasSquad", "hasTransfers","hideOnSearch", "hideOnCatalog", "longName",
                                "shortName", "competitorNum", "competitions", "createdAt"],errors="ignore")
        df_teams = df_teams.rename(columns={"id": "team_id","name": "team_name","nameForURL": "team_name_for_url"})

        # ------------------------
        # Countries
        # ------------------------
        df_countries = pd.json_normalize(transfers["countries"])
        df_countries = df_countries.drop( columns=["sportTypes", "imageVersion", "isInternational"],errors="ignore" )
        df_countries = df_countries.rename( columns={ "id": "nationalityId", "name": "nationality", "nameForURL": "nationality_for_url"})

        # ------------------------
        # Players
        # ------------------------
        df_players = pd.json_normalize(transfers["athletes"])
        df_players = df_players.drop(columns=[ "age", "gender", "popularityRank", "shortName","sportId", "imageVersion", "createdAt"],errors="ignore")
        df_players = df_players.rename(columns={"id": "player_id"})
        df_players["player_image"] = df_players["player_id"].apply(lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}")
        df_players = df_players.merge(df_countries,how="left", on="nationalityId")

        # ------------------------
        # Transfers
        # ------------------------
        df_transfers = pd.json_normalize(transfers["transfers"])
        # Parse dates
        df_transfers["post_start_date"] = df_transfers["time"].str.split("T").str[0]
        df_transfers["post_start_time"] = df_transfers["time"].str.split("T").str[1].str.split("+").str[0]

        df_transfers["contract_until_date"] = df_transfers["contractUntil"].str.split("T").str[0]
        df_transfers["contract_until_time"] = df_transfers["contractUntil"].str.split("T").str[1].str.split("+").str[0]

        df_transfers = df_transfers.drop(columns=["ImageVersion", "statusId", "time", "type", "contractUntil", "positionId"],errors="ignore")

        # ------------------------
        # Merge origin team
        # ------------------------
        df_transfers = df_transfers.rename(columns={"origin": "team_id"})
        df_transfers = df_transfers.merge(   df_teams, how="left", on="team_id" )
        df_transfers = df_transfers.rename(columns={"team_name": "origin_team"})

        # ------------------------
        # Merge target team
        # ------------------------
        df_transfers = df_transfers.merge( df_teams,how="left",left_on="target",right_on="team_id",suffixes=("_origin", "_target"))
        df_transfers = df_transfers.rename( columns={ "team_name": "target_team"})
        df_transfers = df_transfers.drop(columns=["team_id_origin", "team_id_target", "target"], errors="ignore")

        # ------------------------
        # Merge player info
        # ------------------------
        df_final = df_transfers.merge(df_players, how="left", left_on="athleteId",  right_on="player_id")
        df_final = df_final.drop(columns=["athleteId"], errors="ignore")

        return df_final


    def extract_info_teams(self, league: str) -> pd.DataFrame:
        """
        Extract team information for a league from the 365Scores API.

        This function retrieves team metadata for all teams participating
        in a competition, including team name, colors, URLs, and images.

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            pd.DataFrame:
                DataFrame containing team information with columns:

                - competitor_id
                - team
                - name_for_url
                - symbolicName
                - color
                - awayColor
                - team_image
                - team_url

        Raises:
            ValueError:
                If the competition ID cannot be extracted from the URL.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the API response structure is invalid.
        """
        
        #Extract competition ID
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])
        
        url_results_actual=f'https://webws.365scores.com/web/games/fixtures/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitions={id_competition}&showOdds=true&includeTopBettingOpportunity=1'
        # API request
        try:
            response = requests.get(url_results_actual, headers=self.headers, timeout=10)
            response.raise_for_status()
            games= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving teams information: {e}") from e

        # Validate JSON structure
        if "competitors" not in games:
            raise KeyError("Invalid API response: 'competitors' field not found.")

        competitiors= games['competitors']

        competitors_data= []

        for comp in competitiors:
            competitor_id=  comp['id']
            name_for_url  = comp.get('nameForURL', comp.get('name'))

            competitors_data.append({
                'competitor_id': competitor_id,
                'team': comp.get('longName', comp.get('name')),  # Si no hay longName, usar name
                "name_for_url": name_for_url,
                'symbolicName': comp.get('symbolicName'),
                "color": comp.get('color'),
                "awayColor": comp.get('awayColor'),
                'team_image': f"https://imagecache.365scores.com/image/upload/f_png,w_40,h_40,c_limit,q_auto:eco,dpr_3,d_Competitors:default1.png/v3/Competitors/{comp['id']}",
                'team_url': f"https://www.365scores.com/football/team/{name_for_url}-{competitor_id}"
            })

        return  pd.DataFrame(competitors_data)
    
    def extract_next_matches(self, league: str) -> pd.DataFrame:
        """
        Extract upcoming matches for a league from the 365Scores API.

        This function retrieves all upcoming fixtures for a competition,
        iterating through paginated API results.

        Args:
            league (str):
                League name used to extract the competition slug and competition ID in the get_by_name function.

        Returns:
            pd.DataFrame:
                DataFrame containing upcoming matches with normalized
                team information.

        Raises:
            ValueError:
                If the competition ID cannot be extracted.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the API response structure is invalid.
        """

        # Extract competition ID
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])
        
        url_results_actual=f'https://webws.365scores.com/web/games/fixtures/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitions={id_competition}&showOdds=true&includeTopBettingOpportunity=1'

        all_games = []

        while url_results_actual:
            try:
                response = requests.get(url_results_actual, headers=self.headers )
                response.raise_for_status()
                data= response.json()
            except requests.exceptions.RequestException as e:
                raise requests.exceptions.RequestException(f"Error retrieving fixtures data: {e}") from e
            
            games = data.get('games', [])

            for game in games:
                all_games.append({
                    'id': game.get('id'),
                    'roundNum': game.get('roundNum'),
                    'roundName': game.get('roundName'),
                    'startDate': game.get('startTime').split('T')[0],
                    'startTime': game.get('startTime').split('T')[-1].split('+')[0],
                    'home_competitor': game.get('homeCompetitor', {}),
                    'away_competitor': game.get('awayCompetitor', {}),
                })

            # ir a la página anterior (partidos más antiguos)
            next_page = data.get('paging', {}).get('nextPage')

            if next_page:
                url_results_actual = BASE_URL+ next_page
            else:
                url_results_actual = None
        
        df_games= pd.json_normalize(all_games, sep='_')
        # Columns to remove
        drop_columns = ["home_competitor_sportId", "home_competitor_isQualified", "home_competitor_popularityRank", "home_competitor_imageVersion","home_competitor_countryId", "home_competitor_type",
            "home_competitor_toQualify", "home_competitor_isWinner","home_competitor_mainCompetitionId", "home_competitor_hasSquad", "home_competitor_hasTransfers", "home_competitor_competitorNum",
            "home_competitor_hideOnSearch", "home_competitor_hideOnCatalog","home_competitor_symbolicName", "home_competitor_nameForURL","home_competitor_longName", "home_competitor_shortName",
            "away_competitor_hideOnSearch", "away_competitor_hideOnCatalog","away_competitor_mainCompetitionId", "away_competitor_hasSquad","away_competitor_hasTransfers", "away_competitor_competitorNum",
            "away_competitor_countryId", "away_competitor_sportId","away_competitor_symbolicName", "away_competitor_isQualified","away_competitor_toQualify", "away_competitor_isWinner",
            "away_competitor_nameForURL", "away_competitor_type","away_competitor_popularityRank", "away_competitor_imageVersion", "away_competitor_shortName", "away_competitor_longName",
            ]
    
        return df_games.drop(columns=drop_columns, errors="ignore")
    
    def extract_results(self, league: str,season_year: str = "2025") -> pd.DataFrame:
        """
        Extract historical match results for a league from the 365Scores API.

        The function iterates through paginated API responses until all games
        from the specified season are retrieved.

        Args:
            League name used to extract the competition slug and competition ID in the get_by_name function.
            season_year (str, optional): Starting year of the season. Defaults to "2025".

        Returns:
            pd.DataFrame: DataFrame containing match results with cleaned columns.

        Raises:
            ValueError: If competition ID cannot be extracted.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If API response structure is invalid.
        """

        # Extract competition ID
        comp = self.competition_service.get_by_name(league)
        id_competition = str(comp['id'])

        url = f"https://webws.365scores.com/web/games/results/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitions={id_competition}&showOdds=true&includeTopBettingOpportunity=1"

        season_start = pd.Timestamp(f"{season_year}-08-01")
        all_games = []
        stop_loop = False

        # Pagination loop
        while url and not stop_loop:
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                raise requests.exceptions.RequestException(f"Error retrieving league results: {e}") from e

            games = data.get("games", [])

            for game in games:
                start_time = game.get("startTime")
                if not start_time:
                    continue  # skip if missing

                try:
                    match_date = pd.to_datetime(start_time.split("T")[0])
                except Exception:
                    continue  # skip if invalid date

                if match_date < season_start:
                    stop_loop = True
                    break

                all_games.append(game)

            # Pagination
            prev_page = data.get("paging", {}).get("previousPage")
            url = BASE_URL + prev_page if prev_page and not stop_loop else None

        # Normalize JSON to DataFrame
        df = pd.json_normalize(all_games)
        if df.empty:
            return df

        # Extract date and time safely
        df["match_date"] = df["startTime"].str.split("T").str[0]
        df["match_time"] = df["startTime"].str.split("T").str[1].str.split("+").str[0]

        # Drop unnecessary columns
        drop_columns = [
            'sportId', 'statusGroup', 'shortStatusText', 'gameTimeAndStatusDisplayType','homeAwayTeamOrder', 'groupNum', 'scores', 'startTime','hasPointByPoint', 'hasVideo',
            'homeCompetitor.sportId', 'homeCompetitor.isWinner', 'homeCompetitor.type','homeCompetitor.popularityRank', 'homeCompetitor.outcome', 'homeCompetitor.imageVersion',
            'homeCompetitor.hasSquad', 'homeCompetitor.hasTransfers', 'homeCompetitor.competitorNum','homeCompetitor.hideOnSearch', 'homeCompetitor.hideOnCatalog', 'homeCompetitor.countryId',
            'awayCompetitor.countryId', 'awayCompetitor.sportId', 'awayCompetitor.isWinner','awayCompetitor.type', 'awayCompetitor.popularityRank', 'awayCompetitor.outcome',
            'awayCompetitor.imageVersion', 'awayCompetitor.hasSquad', 'awayCompetitor.hasTransfers','awayCompetitor.competitorNum', 'awayCompetitor.hideOnSearch', 'awayCompetitor.hideOnCatalog',
            'homeCompetitor.aggregatedScore', 'awayCompetitor.aggregatedScore','justEnded', 'gameTimeDisplay', 'hasLineups', 'hasMissingPlayers', 'hasFieldPositions',
            'lineupsStatus', 'lineupsStatusText', 'hasTVNetworks', 'winDescription', 'isHomeAwayInverted','hasStats', 'hasStandings', 'standingsName', 'hasBrackets', 'hasPreviousMeetings',
            'hasRecentMatches', 'hasBets', 'hasPlayerBets', 'hasNews', 'homeCompetitor.redCards', 'awayCompetitor.redCards', 'homeCompetitor.isQualified', 'homeCompetitor.toQualify',
            'awayCompetitor.isQualified', 'awayCompetitor.toQualify', 'homeCompetitor.shortName','awayCompetitor.shortName', 'homeCompetitor.mainCompetitionId', 'awayCompetitor.mainCompetitionId',
            'hasBetsTeaser', 'stageNum', 'winner'
            ]

        return  df.drop(columns=drop_columns, errors="ignore")