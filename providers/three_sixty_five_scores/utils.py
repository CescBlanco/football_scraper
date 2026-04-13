import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Any

#----------------------------------------LEAGUE-------------------------------------------------------------------------------------------
def extract_season_standings(url: str, headers: Dict[str, str], season_selected: str = '2025/2026') -> pd.DataFrame:
    """
    Extract the standings for a given season from a 365Scores competition URL.

    Args:
        url (str): 365Scores competition URL.
        headers (Dict[str, str]): HTTP headers to use in the request.
        season_selected (str, optional): Season to extract (e.g., '2025/2026'). Defaults to '2025/2026'.

    Returns:
        pd.DataFrame: DataFrame with the season standings.
    """
    # Extract competition ID from URL
    id_competition = url.split('-')[-1]

    url_standings = f"https://webws.365scores.com/web/standings/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={id_competition}&live=false&withSeasonsFilter=true"


    try:
        # Make request
        response = requests.get(url_standings, headers=headers)
        response.raise_for_status()
        data: Dict[str, Any] = response.json()

        # Check if 'seasonsFilter' exists in response
        seasons_filter = data.get('seasonsFilter')
        if not seasons_filter:
            print(f"Warning: No seasonsFilter data available for competition {id_competition} and season {season_selected}.")
            return pd.DataFrame()

        # Normalize JSON to DataFrame
        df_standings = pd.json_normalize(seasons_filter)
        return df_standings

    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(
            f"Error retrieving data from API for competition {id_competition} and season {season_selected}: {e}") from e
    

#------------------------------------------------------------TEAMS-----------------------------------------------------------------------------
def get_competition_id(df_competitions: pd.DataFrame, competition_name: str, raise_error: bool = False) -> Optional[int]:
    """
    Retrieve the competition ID from a DataFrame given its name.

    Args:
        df_competitions (pd.DataFrame):
            DataFrame containing competition data. Must include 'name' and 'id' columns.

        competition_name (str):
            Name of the competition to search for.

        raise_error (bool, optional):
            If True, raises an error when the competition is not found.
            If False, returns None. Defaults to False.

    Returns:
        Optional[int]:
            Competition ID if found, otherwise None.

    Raises:
        ValueError:
            If required columns are missing or competition is not found (when raise_error=True).
    """

    # Validate required columns
    required_columns = {"name", "id"}
    if not required_columns.issubset(df_competitions.columns):
        raise ValueError(
            f"DataFrame must contain columns: {required_columns}"
        )

    # Filter row
    row = df_competitions[df_competitions["name"] == competition_name]

    if row.empty:
        if raise_error:
            raise ValueError(f"Competition '{competition_name}' not found.")
        return None

    return row["id"].iloc[0]

#------------------------------------------------------------PLAYER-----------------------------------------------------------------------------
def extract_row_data(url: str, headers: Dict[str, str] | None = None) -> Dict:
    """
    Retrieve raw player data from 365Scores API.

    Args:
        url (str): Player URL containing player ID.
        headers (Dict[str, str], optional): HTTP headers for request.

    Returns:
        Dict: Raw JSON response with player details.

    Raises:
        ValueError: If player ID is invalid.
        requests.exceptions.RequestException: If request fails.
    """
    id_player = url.split('-')[-1]
    if not id_player.isdigit():
        raise ValueError("Invalid player ID extracted from URL.")

    api_url =  f'https://webws.365scores.com/web/athletes/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&athletes={id_player}&fullDetails=true'

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Error retrieving player details: {e}") from e
    
def extract_stats_last_matches(stats: list) -> pd.Series:
    """
    Extract key stats from a list of athlete stats.

    Args:
        stats (list): List of stats dictionaries.

    Returns:
        pd.Series: Series containing minutes played, goals, rating value, and rating color.
    """
    minutes_played = None
    goals = None
    rating_value = None
    rating_color = None

    if isinstance(stats, list) and len(stats) > 0:
        # Safely extract values using try-except
        try:
            minutes_played = stats[0].get('value')
        except (IndexError, AttributeError):
            minutes_played = None

        try:
            goals = stats[1].get('value')
        except (IndexError, AttributeError):
            goals = None

        try:
            rating_value = stats[4].get('value')
            rating_color = stats[4].get('bgColor')
        except (IndexError, AttributeError):
            rating_value = None
            rating_color = None

    return pd.Series([minutes_played, goals, rating_value, rating_color],
                     index=['minutes_played', 'goals', 'rating_value', 'rating_color'])

def extract_data_penalties(url: str) -> dict:
    """
    Fetch raw penalty data for a player from 365Scores API.

    Args:
        url (str): Player URL containing the player ID.
        headers (Dict): HTTP headers for the API request.

    Returns:
        dict: Raw JSON response containing penalty chart events and games.
    """
    id_player = url.split('-')[-1]
    url_player_penalties = f"https://webws.365scores.com/web/athletes/chartEvents?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&athletes={id_player}"

    response = requests.get(url_player_penalties)
    response.raise_for_status()
    player_details = response.json()

    return player_details
