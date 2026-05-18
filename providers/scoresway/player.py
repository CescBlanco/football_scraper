import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)

from providers.scoresway.utils import _create_response

class ScoreswayPlayerScraper:
    def __init__(self, session: requests.Session, team_service):
        self.session = session
        self.team_service = team_service

    def extract_bio(self, url_player: str) -> pd.DataFrame:
        """
        Extract detailed biography information for a football player.

        This function retrieves player bio data from the PerformFeeds API,
        calculates the player's age, generates player and nationality
        image URLs, and returns the information as a structured DataFrame.

        Parameters
        ----------
        url_player : str
            Full Scoresway player URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - player personal information
            - nationality information
            - calculated age
            - player image URL
            - nationality flag image URL

        Raises
        ------
        TypeError
            If url_player is not a string.
        ValueError
            If:
            - url_player is empty.
            - player identifier cannot be extracted.
            - player bio data is unavailable.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUT
            # ------------------------
            if not isinstance(url_player, str):
                raise TypeError("url_player must be a string")

            if not url_player.strip():
                raise ValueError("url_player cannot be empty")

            # ------------------------
            # EXTRACT PLAYER ID
            # ------------------------
            url_parts = url_player.split('/')

            if len(url_parts) < 2:
                raise ValueError("Invalid player URL format" )

            player_id = url_parts[-1]
            if not player_id:
                raise ValueError("Player ID could not be extracted from the URL")

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f"https://api.performfeeds.com/soccerdata/nlgdynamicplayerbio/ft1tiv1inq7v1sk3y9tv12yh5?prsn={player_id}&_rt=c&_fmt=jsonp&_lcl=en-gb&_clbk=W3bbb0359296b3ad807f91546f5d58db1b72e38e79"

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "person" not in json_data:
                raise ValueError("Player bio data was not found in API response" )

            # ------------------------
            # NORMALIZE PLAYER DATA
            # ------------------------
            df= pd.DataFrame(json_data['person']).drop(columns= ['membership', 'messages', 'lastUpdated'])
            if df.empty:
                raise ValueError("No player bio information was found" )

            # ------------------------
            # CALCULATE PLAYER AGE
            # ------------------------
            df['dateOfBirth'] = pd.to_datetime(df['dateOfBirth'])
            today = pd.Timestamp.today()

            # Accurate age calculation based on birthday
            df['age'] = today.year - df['dateOfBirth'].dt.year- ( (today.month < df['dateOfBirth'].dt.month) | ( (today.month == df['dateOfBirth'].dt.month) &(today.day < df['dateOfBirth'].dt.day)))
            # ------------------------
            # BUILD PLAYER IMAGE URL
            # ------------------------
            if len(url_parts) < 4:
                raise ValueError("Unable to extract team identifier from player URL")

            team_id = url_parts[-4]
            df['player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + team_id + '&dimensions=103x155&id=' + df['id']
            # ------------------------
            # BUILD NATION FLAG URL
            # ------------------------
            df['nation_photo']=  "https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=flags&description=countries&dimensions=21x21&id=" + df['nationalityId']

            return df

        except Exception as e:
            raise RuntimeError(f"Failed to extract player bio from URL '{url_player}': {str(e)}")
        
    def extract_career_teams(self, url_player: str) -> pd.DataFrame:
        """
        Extract historical team membership information for a football player.

        This function retrieves player membership history from the
        PerformFeeds API, expands statistical information associated
        with each team membership, and returns a structured DataFrame.

        Parameters
        ----------
        url_player : str
            Full Scoresway player URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - team membership history
            - start and end dates
            - competition information
            - player statistics per team

        Raises
        ------
        TypeError
            If url_player is not a string.
        ValueError
            If:
            - url_player is empty.
            - player identifier cannot be extracted.
            - membership information is unavailable.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUT
            # ------------------------
            if not isinstance(url_player, str):
                raise TypeError("url_player must be a string")

            if not url_player.strip():
                raise ValueError("url_player cannot be empty")

            # ------------------------
            # EXTRACT PLAYER ID
            # ------------------------
            url_parts = url_player.split('/')
            if len(url_parts) < 2:
                raise ValueError("Invalid player URL format" )

            player_id = url_parts[-1]
            if not player_id:
                raise ValueError("Player ID could not be extracted")

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/nlgdynamicplayerbio/ft1tiv1inq7v1sk3y9tv12yh5?prsn={player_id}&_rt=c&_fmt=jsonp&_lcl=en-gb&_clbk=W3bbb0359296b3ad807f91546f5d58db1b72e38e79'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "person" not in json_data:
                raise ValueError("Player information was not found in API response")

            membership_data = json_data['person'][0].get('membership')
            if not membership_data:
                raise ValueError("No membership history was found")

            # ------------------------
            # NORMALIZE MEMBERSHIP DATA
            # ------------------------
            teams_player = pd.DataFrame( membership_data)

            # Remove trailing Z from datetime strings
            teams_player['startDate'] = teams_player['startDate'].str.replace('Z', '', regex=False)
            teams_player['endDate'] = teams_player['endDate'].str.replace('Z', '', regex=False)

            # Sort memberships by most recent
            teams_player = teams_player.sort_values(by='startDate', ascending= False).reset_index(drop=True)

            # ------------------------
            # EXPAND STATISTICS
            # ------------------------
            teams_player_expanded = teams_player.explode('stat').reset_index(drop=True)

            # Convert stat dictionaries into columns
            stats_df = pd.json_normalize(teams_player_expanded['stat'])
            # Merge membership and stat data
            final_df= pd.concat([teams_player_expanded.drop(columns=['stat']), stats_df],axis=1)

            return final_df

        except Exception as e:
            raise RuntimeError(f"Failed to extract player team history from URL '{url_player}': {str(e)}")
        
    def extract_stats_season(self, url_player: str) -> pd.DataFrame:
        """
        Extract season statistics for a specific football player.

        This function retrieves season player statistics from the
        PerformFeeds API using information extracted from a player URL,
        expands player statistical metrics into columns, and returns
        a structured DataFrame.

        Parameters
        ----------
        url_player : str
            Full Scoresway player URL containing competition,
            team, and player identifiers.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - player identifiers
            - player information
            - season statistics
            - statistical metrics as columns

        Raises
        ------
        TypeError
            If url_player is not a string.
        ValueError
            If:
            - url_player is empty.
            - required identifiers cannot be extracted.
            - player statistics are unavailable.
            - player is not found.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUT
            # ------------------------
            if not isinstance(url_player, str):
                raise TypeError("url_player must be a string")

            if not url_player.strip():
                raise ValueError("url_player cannot be empty")

            # ------------------------
            # EXTRACT URL IDENTIFIERS
            # ------------------------
            url_parts = url_player.split('/')

            if len(url_parts) < 7:
                raise ValueError( "Invalid player URL format")

            tournament_id = url_parts[-7]
            contestant_id = url_parts[-4]
            player_id = url_parts[-1]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f"https://api.performfeeds.com/soccerdata/seasonstats/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={tournament_id}&ctst={contestant_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W343661dd22d45ad571f67328ca253d9c5c31b6ff9"

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "player" not in json_data:
                raise ValueError("Player statistics were not found in API response")

            # ------------------------
            # NORMALIZE PLAYER DATA
            # ------------------------
            data_player_team = pd.DataFrame(json_data['player'])
            if data_player_team.empty:
                raise ValueError("No player statistics were found")

            # Filter selected player
            stats_player = data_player_team[ data_player_team['id'] == player_id]
            if stats_player.empty:
                raise ValueError(f"Player with ID '{player_id}' was not found")

            # ------------------------
            # EXPAND PLAYER STATS
            # ------------------------
            team_stats_dict = stats_player['stat'].apply(lambda x: {d['name']: d['value'] for d in x})

            # Convert stats dictionary into columns
            df2 = pd.json_normalize(team_stats_dict)

            # Merge base information with stats
            final_df = pd.concat( [stats_player.drop(columns=['stat']).reset_index(drop=True), df2.reset_index(drop=True)],axis=1)

            return final_df

        except Exception as e:
            raise RuntimeError(f"Failed to extract player season statistics from URL '{url_player}': {str(e)}" )
        
    def extract_team_stats_season(self, url_player: str) -> pd.DataFrame:
        """
        Extract season statistics for all teams in a competition.

        This function retrieves season team statistics from the
        PerformFeeds API using information extracted from a player URL,
        pivots statistical values into columns, and returns a
        structured DataFrame.

        Parameters
        ----------
        url_player : str
            Full Scoresway player URL containing competition
            and team identifiers.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - team identifiers
            - team names
            - season statistics
            - statistical metrics as columns

        Raises
        ------
        TypeError
            If url_player is not a string.
        ValueError
            If:
            - url_player is empty.
            - required identifiers cannot be extracted.
            - team statistics are unavailable.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUT
            # ------------------------
            if not isinstance(url_player, str):
                raise TypeError("url_player must be a string")

            if not url_player.strip():
                raise ValueError("url_player cannot be empty")

            # ------------------------
            # EXTRACT URL IDENTIFIERS
            # ------------------------
            url_parts = url_player.split('/')
            if len(url_parts) < 7:
                raise ValueError("Invalid player URL format" )

            tournament_id = url_parts[-7]
            contestant_id = url_parts[-4]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f"https://api.performfeeds.com/soccerdata/seasonstats/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={tournament_id}&ctst={contestant_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W343661dd22d45ad571f67328ca253d9c5c31b6ff9"

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "contestant" not in json_data:
                raise ValueError("Team statistics were not found in API response")

            # ------------------------
            # NORMALIZE TEAM DATA
            # ------------------------
            df = pd.DataFrame( json_data['contestant'])
            if df.empty:
                raise ValueError("No team statistics were found")

            # ------------------------
            # EXTRACT STAT VALUES
            # ------------------------
            df['stat_name'] = df['stat'].apply(lambda x: x['name'])
            df['stat_value'] = df['stat'].apply(lambda x: x['value'])

            # ------------------------
            # PIVOT STATISTICS
            # ------------------------
            final_df = df.pivot_table(index=['id', 'name'], columns='stat_name', values='stat_value', aggfunc='first').reset_index()

            # Remove hierarchical column name
            final_df.columns.name = None

            return final_df

        except Exception as e:
            raise RuntimeError( f"Failed to extract season team statistics from URL '{url_player}': {str(e)}")