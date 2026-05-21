import requests
import pandas as pd
from typing import List, Dict, Any,Tuple, Optional

from football_scraper.providers.fotmob.constants import BASE_URL, BASE_URL_COMPETITIONS
from football_scraper.providers.fotmob.utils import flatten_leagues

class FotmobCompetitionService:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None
    
    def extract_leagues_all(self) -> pd.DataFrame:
        """
        Fetch and extract football league information from a FotMob API endpoint.

        The function retrieves JSON data from the given URL, parses both "countries"
        and "international" league sections, and returns a flattened pandas DataFrame
        containing league metadata.

        Returns:
            pd.DataFrame: A DataFrame containing the following columns:
                - country (str): Country or competition group name.
                - league_id (int | None): Unique identifier of the league.
                - league_name (str | None): Name of the league.
                - display_name (str): Combined league and country name.
                - localized_name (str | None): Localized name of the league.
                - pageUrl (str): Full URL to the league page.
                - logoURL (str): URL of the league logo image.

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
            ValueError: If the response content is not valid JSON or expected structure is missing.
            KeyError: If required keys are unexpectedly absent in the JSON structure.
        """
        try:
            response = requests.get(BASE_URL_COMPETITIONS)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException( f"Error fetching data from {BASE_URL_COMPETITIONS}: {e}")

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as e:
            raise ValueError(f"Invalid JSON response from {BASE_URL_COMPETITIONS}: {e}")

        countries: List[Dict[str, Any]] = data.get("countries", [])
        international: List[Dict[str, Any]] = data.get("international", [])

        

        all_leagues = flatten_leagues(countries) + flatten_leagues(international)
        df_final= pd.DataFrame(all_leagues)
        self._competitions_cache = df_final
        return df_final
    
    def find_leagues(self,league_name: str) -> pd.DataFrame:
        """
        Search for leagues whose names match a given query string.

        This function retrieves all leagues and performs a case-insensitive
        substring match on the "league_name" column.

        Args:
            league_name (str): The league name or partial name to search for.

        Returns:
            pd.DataFrame: A filtered DataFrame containing matching leagues with columns:
                - display_name (str): Combined league and country name.
                - league_id (int | None): Unique identifier of the league.
                - country (str): Country or competition group.

        Raises:
            ValueError: If no leagues match the provided name.
            TypeError: If league_name is not a string.
        """
        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        df = self.extract_leagues_all()
        league_name_clean = league_name.strip().lower()

        result = df[df["league_name"].str.lower().str.contains(league_name_clean, na=False)]

        if result.empty:
            raise ValueError(f"No leagues found matching: {league_name}")

        return result[["display_name", "league_id", "country"]]
    
    def extract_league_by_display_name(self, display_name: str) -> Dict[str, Any]:
        """
        Retrieve detailed information for a league based on its display name.

        This function performs an exact, case-insensitive match on the "display_name"
        field and returns the first matching league as a dictionary.

        Args:
            display_name (str): The exact display name of the league (case-insensitive).

        Returns:
            Dict[str, Any]: A dictionary containing league details:
                - country (str): Country or competition group name.
                - id (str): League identifier as a string.
                - name (str | None): League name.
                - localized_name (str | None): Localized league name.
                - url (str): Full URL to the league page.
                - logoURL (str): URL of the league logo.
                - name_slug (str): URL slug extracted from the league page URL.

        Raises:
            ValueError: If no league matches the provided display name.
            TypeError: If display_name is not a string.
        """
        if not isinstance(display_name, str):
            raise TypeError("display_name must be a string")

        df = self.extract_leagues_all()
        result = df[df["display_name"].str.lower() == display_name.strip().lower()]

        if result.empty:
            raise ValueError(f"No league found with name: {display_name}")

        league = result.iloc[0]

        return {
            "country": league["country"],
            "id": str(league["league_id"]),
            "name": league["league_name"],
            "localized_name": league["localized_name"],
            "url": league["pageUrl"],
            "logoURL": league["logoURL"],
            "name_slug": league["pageUrl"].split("/")[-1],
        }