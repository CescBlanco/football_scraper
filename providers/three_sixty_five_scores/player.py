import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np
from typing import List, Dict, Optional, Any, Tuple

from providers.three_sixty_five_scores.constants import DEFAULT_HEADERS, BASE_URL
from providers.three_sixty_five_scores.utils import extract_row_data, extract_stats_last_matches, extract_data_penalties

class Scores365PlayerScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_player_details(self, url_player: str)-> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract structured player data from raw API response.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: 
                - df_detailed: Player data including injuries.
                - df_cleaned: Player data with unnecessary columns removed.
        """
        player_details = extract_row_data(url_player, headers=self.headers)
        athletes = player_details.get('athletes', [])

        if not athletes:
            return pd.DataFrame(), pd.DataFrame()

        df = pd.DataFrame(athletes)

        # Position info
        df['position'] = df['position'].apply(lambda x: x.get('name', 'Staff') if isinstance(x, dict) else 'Staff')
        df['formationPosition'] = df['formationPosition'].apply(lambda x: x.get('name') if isinstance(x, dict) else None)

        df['date_of_birth'] = df['playerDetails'][0][0]['title']
        df['height'] = df['playerDetails'][0][1]['value']
        df['shirt_number'] = df['playerDetails'][0][2]['value']

        # Contract dates
        df['contract_until_date'] = df.get('contractUntil', '').str.split('T').str[0]
        df['contract_until_time'] = df.get('contractUntil', '').str.split('T').str[1].str.split('+').str[0]

        # Drop unnecessary columns
        cols_to_drop = ['contractUntil','playerDetails','hideOnCatalog','hideOnSearch','imageVersion','sportId']
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns], errors='ignore')

        # Injuries
        if 'injury' in df.columns and df['injury'].notna().any():
            df_injury = pd.json_normalize(df['injury'])
            df_injury['injury_start_date'] = df_injury['startDate'].str.split('T').str[0]
            df_injury['injury_start_time'] = df_injury['startDate'].str.split('T').str[1].str.split('+').str[0]
            df_injury = df_injury.drop(columns=['startDate'], errors='ignore')
            df_detailed = pd.concat([df.drop(columns=['injury']), df_injury], axis=1)
        else:
            df_detailed = df.copy()

        # Cleaned version
        extra_drop_cols = ['lastMatches','transfers','trophies','highlightStats','careerStats','HasPenaltiesShots','createdAt']
        df_cleaned = df_detailed.drop(columns=[c for c in extra_drop_cols if c in df_detailed.columns], errors='ignore')

        return df_detailed, df_cleaned
    
    def extract_stats_season_by_competition(self, url: str, competition: str)-> pd.DataFrame:
        """
        Extract seasonal statistics by competition for a player.

        Args:
            url (str): Player URL containing player ID.
            competition (str): Competition name to filter stats.

        Returns:
            pd.DataFrame: Filtered stats for the specified competition.
        """
        # Get player details
        df_row_player, _ = self.extract_player_details(url)

        # Check if 'highlightStats' exists and is not empty
        if 'highlightStats' not in df_row_player.columns or df_row_player['highlightStats'].isna().all():
            print("No highlight stats available for this player.")
            return pd.DataFrame()

        # Take the first row of highlightStats (usually a list of dictionaries)
        stats_list = df_row_player['highlightStats'].iloc[0]

        if not stats_list:
            print("No highlight stats found in the data.")
            return pd.DataFrame()

        df_stats = pd.DataFrame(stats_list)

        # Ensure the 'stats' field exists
        if 'stats' not in df_stats.columns:
            print("No 'stats' field found in highlight stats.")
            return pd.DataFrame()

        # Explode to have one row per stat
        df_exploded = df_stats.explode('stats').reset_index(drop=True)

        # Expand the 'stats' dictionary in each row
        stats_expanded = pd.json_normalize(df_exploded['stats']).add_prefix('stat_')
        df_final = pd.concat([df_exploded.drop(columns=['stats']).reset_index(drop=True),stats_expanded.reset_index(drop=True)], axis=1)

        # Drop unnecessary columns if they exist
        cols_to_drop = ['competitorId', 'name', 'stat_isTop', 'stat_type', 'stat_categoryId', 
                        'stat_shortName', 'stat_order', 'stat_imageId', 'stat_isExpanded']
        df_final = df_final.drop(columns=[c for c in cols_to_drop if c in df_final.columns], errors='ignore')

        # List of available competitions
        list_competition = df_final['competitionName'].unique().tolist()
        print(f"Available competitions: {list_competition}")

        # Filter by requested competition
        if competition in list_competition:
            return df_final[df_final['competitionName'] == competition].reset_index(drop=True)
        else:
            print("Invalid competition. Please choose one from the available competitions.")
            return pd.DataFrame()
    
    def extract_career_stats_last_season(self, url: str)-> pd.DataFrame:
        """
        Extract career statistics for the last season of a player.

        Args:
            url (str): Player URL containing player ID.

        Returns:
            pd.DataFrame: DataFrame containing last season career stats, 
                        organized by competition and stat categories.
        """
        # Get detailed player data
        df_row_player, _ = self.extract_player_details(url)

        # Check if 'careerStats' exists and has at least one season
        if 'careerStats' not in df_row_player.columns or df_row_player['careerStats'].isna().all():
            print("No career stats available for this player.")
            return pd.DataFrame()

        try:
            last_season = df_row_player['careerStats'].iloc[0]['seasons'][0]
        except (IndexError, KeyError, TypeError):
            print("Career stats structure is empty or invalid.")
            return pd.DataFrame()

        # Normalize season-level data
        df_season = pd.json_normalize(last_season)

        # Extract categories
        if 'stats.categories' in df_season.columns and df_season['stats.categories'].notna().any():
            df_categories = pd.json_normalize(df_season['stats.categories'].iloc[0])
            df_season = pd.concat([df_season.drop(columns=['stats.categories']), df_categories], axis=1)
        else:
            print("No stat categories found.")
            df_season['stats.categories'] = []

        # Extract tables (stats per competition)
        try:
            table = df_season['stats.tables'].iloc[0][0]
        except (KeyError, IndexError, TypeError):
            print("No stats tables found in career stats.")
            return df_season

        # Map column numbers to short names
        cols_map = {col['num']: col['shortName'] for col in table.get('columns', [])}

        # Build rows list
        rows_list = []
        for row in table.get('rows', []):
            stats = {cols_map.get(val['columnNum'], f"col_{val['columnNum']}"): val.get('value') for val in row.get('values', [])}
            row_dict = {'competition': row.get('title', 'Unknown'), **stats}
            rows_list.append(row_dict)

        df_comp_stats = pd.DataFrame(rows_list)

        # Repeat base columns for each competition
        base_cols = df_season.drop(columns=['stats.tables'], errors='ignore').iloc[[0]]
        base_cols = pd.concat([base_cols] * len(df_comp_stats), ignore_index=True)

        # Combine base columns and competition stats
        final_df = pd.concat([base_cols, df_comp_stats], axis=1)

        # Drop legend column if exists
        final_df = final_df.drop(columns=['stats.legend'], errors='ignore')

        return final_df.reset_index(drop=True)
    
    def extract_trophies(self, url_player: str) -> pd.DataFrame:
        """
        Extract trophies won by a player.

        Args:
            url_player (str): Player URL containing player ID.

        Returns:
            pd.DataFrame: DataFrame containing trophies information.
        """
        # Get detailed player data
        df_row_player, _ = self.extract_player_details(url_player)

        # Check if trophies exist
        if 'trophies' not in df_row_player.columns or df_row_player['trophies'].isna().all():
            print("No trophies data available for this player.")
            return pd.DataFrame()

        try:
            # Extract first category of trophies
            df_trophies = pd.DataFrame(df_row_player['trophies'].iloc[0]['categories'][0]['trophies'])
        except (IndexError, KeyError, TypeError):
            print("Trophies data structure is empty or invalid.")
            return pd.DataFrame()

        # Extract stats row safely
        stats_series = df_trophies['stats'].dropna()
        if stats_series.empty:
            print("No statistical data found in trophies.")
            return df_trophies

        stats = stats_series.iloc[0]

        # Map column numbers to names
        col_map = {col['num']: col['name'] for col in stats.get('columns', [])}

        # Extract row values safely
        row = stats.get('rows', [{}])[0]
        values = {col_map.get(val['columnNum'], f"col_{val['columnNum']}"): val.get('value') for val in row.get('values', [])}

        # Add extra information
        values['entityId'] = row.get('entityId')
        values['team'] = row.get('title')
        values['season'] = row.get('secondaryTitle')

        # DataFrame of stats
        df_stats = pd.DataFrame([values])

        # Combine with original trophies DataFrame (dropping 'stats' column)
        df_final = pd.concat([df_trophies.drop(columns='stats', errors='ignore'), df_stats], axis=1)

        return df_final.reset_index(drop=True)
    
    def extract_career_history(self, url_player: str) -> pd.DataFrame:
        """
        Extract a player's career history (transfers).

        Args:
            url_player (str): Player URL containing the player ID.
            headers (Dict): HTTP headers for the API request.

        Returns:
            pd.DataFrame: DataFrame containing the player's career history.
        """
        # Get detailed player data
        df_row_player, _ = self.extract_player_details(url_player)

        # Check if transfers exist
        if 'transfers' not in df_row_player.columns or df_row_player['transfers'].isna().all():
            print("No transfers data available for this player.")
            return pd.DataFrame()

        try:
            # Extract the first transfers list
            df = pd.DataFrame(df_row_player['transfers'].iloc[0])
        except (IndexError, KeyError, TypeError):
            print("Transfers data structure is empty or invalid.")
            return pd.DataFrame()

        # Parse dates safely
        if 'date' in df.columns:
            df['date'] = df['date'].str.split('T').str[0]

        if 'contractUntil' in df.columns:
            df['contract_until_date'] = df['contractUntil'].str.split(' ').str[0]

        # Drop unnecessary columns safely
        df = df.drop(columns=['contractUntil', 'transferType'], errors='ignore')

        return df.reset_index(drop=True)
    
    def extract_last_matches(self, url_player: str) -> pd.DataFrame:
        """
        Extract the last matches played by a player.

        Args:
            url_player (str): Player URL containing the player ID.

        Returns:
            pd.DataFrame: DataFrame containing last matches with player stats.
        """
        # Get detailed player data
        df_row_player, _ = self.extract_player_details(url_player)

        # Check if lastMatches exist
        if 'lastMatches' not in df_row_player.columns or df_row_player['lastMatches'].isna().all():
            print("No last matches data available for this player.")
            return pd.DataFrame()

        try:
            # Extract games from the first lastMatches entry
            df_last_matches = pd.DataFrame(df_row_player['lastMatches'].iloc[0]['games'])
        except (IndexError, KeyError, TypeError):
            print("Last matches data structure is empty or invalid.")
            return pd.DataFrame()

        # Normalize nested 'game' dictionaries
        if 'game' in df_last_matches.columns:
            game_expanded = pd.json_normalize(df_last_matches['game'])
            df1 = pd.concat([df_last_matches.drop(columns=['game']), game_expanded], axis=1)
        else:
            df1 = df_last_matches.copy()

        # Drop unnecessary columns safely
        drop_cols = [
            'sportId', 'hasStats', 'relatedCompetitor', 'roundName', 'statusGroup', 'shortStatusText',
            'gameTimeAndStatusDisplayType', 'hasPointByPoint', 'homeAwayTeamOrder', 'hasVideo',
            'homeCompetitor.sportId', 'homeCompetitor.type', 'homeCompetitor.popularityRank',
            'homeCompetitor.imageVersion', 'homeCompetitor.countryId', 'homeCompetitor.shortName',
            'homeCompetitor.hasSquad', 'homeCompetitor.hasTransfers', 'homeCompetitor.competitorNum',
            'homeCompetitor.hideOnSearch', 'homeCompetitor.hideOnCatalog', 'homeCompetitor.isWinner',
            'awayCompetitor.countryId', 'awayCompetitor.sportId', 'awayCompetitor.shortName',
            'awayCompetitor.isWinner', 'awayCompetitor.type', 'awayCompetitor.popularityRank',
            'awayCompetitor.imageVersion', 'awayCompetitor.hasSquad', 'awayCompetitor.hasTransfers',
            'awayCompetitor.competitorNum', 'awayCompetitor.hideOnSearch', 'awayCompetitor.hideOnCatalog',
            'groupNum', 'winner', 'scores',  'homeCompetitor.aggregatedScore',	'awayCompetitor.aggregatedScore'
        ]
        df1 = df1.drop(columns=drop_cols, errors='ignore')

        # Extract player stats
        if 'athleteStats' in df1.columns:
            df1[['minutes_played', 'goals', 'rating_value', 'rating_color']] = df1['athleteStats'].apply(extract_stats_last_matches)
        else:
            df1[['minutes_played', 'goals', 'rating_value', 'rating_color']] = None, None, None, None

        # Parse match date and time safely
        if 'startTime' in df1.columns:
            df1['match_date'] = df1['startTime'].str.split('T').str[0]
            df1['match_time'] = df1['startTime'].str.split('T').str[1].str.split('+').str[0]

        # Drop unnecessary columns
        df_final = df1.drop(columns=['athleteStats', 'startTime', 'seasonNum', 'stageNum'], errors='ignore')

        return df_final.reset_index(drop=True)
    
    def extract_penalty_shots(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract structured penalty information and match events for a player.

        Args:
            url (str): Player URL containing the player ID.
            headers (Dict): HTTP headers for the API request.

        Returns:
            tuple:
                - df_basic_info_penalties: DataFrame with summary info per penalty chart.
                - df_penalties_player: DataFrame with detailed penalty events merged with match info.
        """
        # Fetch raw data
        row_data_penalties = extract_data_penalties(url)

        # Normalize basic chart info
        df_info_penalties = pd.json_normalize(row_data_penalties.get('chartEvents', [{}])[0])
        df_basic_info_penalties = df_info_penalties.drop(columns=['events', 'eventTypes', 'statuses', 'eventSubTypes'], errors='ignore')
        # Handle mostCommonGoalZone safely
        df_basic_info_penalties['mostCommonGoalZone'] = df_basic_info_penalties['mostCommonGoalZone'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else x)

        # Normalize matches played
        df_matches = pd.json_normalize(row_data_penalties.get('games', []))
        if not df_matches.empty:
            df_matches['match_date'] = df_matches['startTime'].str.split('T').str[0]
            df_matches['match_time'] = df_matches['startTime'].str.split('T').str[1].str.split('+').str[0]

        # Drop unnecessary columns
        drop_cols_matches = ['sportId','scores' ,'statusGroup', 'startTime','statusText', 'shortStatusText',	'gameTimeAndStatusDisplayType', 'hasPointByPoint',  'hasVideo', 
                                    'homeCompetitor.hideOnSearch', 'homeCompetitor.hideOnCatalog','awayCompetitor.hideOnSearch',	'awayCompetitor.hideOnCatalog', 'homeCompetitor.shortName',
                                    'awayCompetitor.shortName', 'homeCompetitor.isWinner',   'awayCompetitor.isWinner','homeCompetitor.popularityRank',	'homeCompetitor.imageVersion' ,
                                    'awayCompetitor.popularityRank',	'awayCompetitor.imageVersion', 'homeCompetitor.hasSquad',	'homeCompetitor.hasTransfers',
                                    'awayCompetitor.hasSquad','awayCompetitor.hasTransfers', 'homeCompetitor.sportId','awayCompetitor.sportId',  'homeCompetitor.nameForURL', 'awayCompetitor.nameForURL',
                                    'awayCompetitor.color','awayCompetitor.awayColor', 'homeCompetitor.color', 'homeCompetitor.awayColor', 'homeCompetitor.countryId',  'awayCompetitor.countryId',
                                    'roundName', 	'groupNum' , 'homeAwayTeamOrder', 'homeCompetitor.type',  'awayCompetitor.type','homeCompetitor.competitorNum'	, 	'awayCompetitor.competitorNum']
        df_matches = df_matches.drop(columns=drop_cols_matches, errors='ignore')

        # Normalize competitions
        df_competitions = pd.json_normalize(row_data_penalties.get('competitions', []))
        df_matches = df_matches.merge(df_competitions, how='left', left_on='competitionId', right_on='id')
        df_matches = df_matches.drop(columns=['countryId', 'sportId', 'name', 'shortName', 'hasBrackets', 'popularityRank','imageVersion', 'currentStageType', 'color', 'competitorsType',
                                                'currentPhaseNum', 'currentSeasonNum', 'currentStageNum', 'hideOnCatalog','hideOnSearch', 'isInternational', 'id_y'], errors='ignore')
        df_matches = df_matches.rename(columns={'id_x': 'id_match'})

        # Normalize penalty events
        penalties_info_player = pd.json_normalize(df_info_penalties.get('events', [{}])[0])
        event_sub_type = pd.json_normalize(df_info_penalties.get('eventSubTypes', [{}])[0]).rename(columns={'id': 'id_subtype', 'value': 'subType', 'name': 'name_subtype'})
        info_half = pd.json_normalize(df_info_penalties.get('statuses', [{}])[0]).drop(columns=['name', 'sportTypeId', 'isExtraTime', 'isActive', 'isFinished', 'isNotStarted','isPenalties', 
                                                                                                    'isAbnormal', 'gameTimeForStatus', 'autonomicTime', 'hasEvents'], errors='ignore').rename(columns={'id': 'id_half',
                                                                                                                                                                                'symbolName': 'half_symbol', 'aliasName': 'half_name'})
        event_type = pd.json_normalize(df_info_penalties.get('eventTypes', [{}])[0]).rename(columns={'id': 'id_type', 'value': 'type', 'name': 'name_type'})

        # Merge all events info
        df_penalties = penalties_info_player.merge(info_half, how='left', left_on='status', right_on='id_half')
        df_penalties = df_penalties.merge(event_sub_type, how='left', left_on='subType', right_on='subType')
        df_penalties = df_penalties.merge(event_type, how='left', left_on='type', right_on='type')
        df_penalties = df_penalties.drop(columns=['status', 'type', 'subType', 'id_half', 'id_subtype', 'id_type', 'competitorNum'], errors='ignore')

        # Merge with match info
        df_penalties_player = df_penalties.merge(df_matches, how='left', left_on='gameId', right_on='id_match')

        return df_basic_info_penalties, df_penalties_player