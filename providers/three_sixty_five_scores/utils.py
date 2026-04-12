import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Any

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