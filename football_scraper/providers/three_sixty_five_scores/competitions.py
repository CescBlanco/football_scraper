import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Any

from football_scraper.providers.three_sixty_five_scores.constants import BASE_URL, COMPETITIONS_URL, DEFAULT_HEADERS 

class Scores365CompetitionService:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None
    
    def fetch_all(self, url: str, name_id: str = "Football") -> pd.DataFrame:
        """
        Extract available leagues and cups from the 365Scores API response.

        This function retrieves sports competition data from the provided URL,
        filters competitions belonging to the selected sport, and merges them
        with country information.

        Args:
            url (str):
                API endpoint containing sports, competitions, and countries data.

            name_id (str, optional):
                Name of the sport to filter competitions. Defaults to "Football".

            headers (Dict[str, str] | None, optional):
                HTTP headers used for the API request.

        Returns:
            pd.DataFrame:
                DataFrame containing competition information merged with country data.

        Raises:
            requests.exceptions.RequestException:
                If the HTTP request fails.

            ValueError:
                If the selected sport name is not found in the API response.

            KeyError:
                If expected fields are missing in the API response.
        """

        try:
            response = requests.get(url)
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException( f"Error retrieving data from API: {e}") from e

        # Validate required keys
        required_keys = {"sports", "competitions", "countries"}
        if not required_keys.issubset(data.keys()):
            missing = required_keys - data.keys()
            raise KeyError(f"Missing keys in API response: {missing}")

        # Extract sports
        df_sports = pd.json_normalize(data["sports"])

        sport_match = df_sports[df_sports["name"] == name_id]

        if sport_match.empty:
            raise ValueError(f"Sport '{name_id}' not found in API response.")

        sport_id = sport_match["id"].iloc[0]

        # Extract competitions
        df_competitions = pd.DataFrame(data["competitions"])
        df_competitions = df_competitions[df_competitions["sportId"] == sport_id]

        df_competitions = df_competitions[["id", "name","countryId","sportId","nameForURL","currentSeasonNum","currentStageNum","color", "isActive","shortName","longName" ]]

        # Extract countries
        df_countries = pd.json_normalize(data["countries"])
        df_countries = df_countries.drop(columns=["sportTypes", "imageVersion", "isInternational"], errors="ignore",)

        df_countries = df_countries.rename(columns={  "id": "id_country","name": "name_country","nameForURL": "country_for_url"})
        # Merge datasets
        df_final = (df_competitions.merge(df_countries, how="left",left_on="countryId",right_on="id_country",).drop(columns=["countryId", "sportId", "shortName"], errors="ignore"))
        
        self._competitions_cache = df_final

        return df_final

    def get_by_name(self, name: str):
        """Search competition by name (case-insensitive)."""

        if self._competitions_cache is None:
            raise RuntimeError("Competitions not loaded. Call fetch_all() first.")

        name = name.lower().strip()

        df = self._competitions_cache

        match = df[df["name"].str.lower().str.strip() == name]

        if match.empty:
            raise ValueError(f"Competition not found: {name}")

        return match.iloc[0].to_dict()
    
    def list_all(self):
        """Return list of all competition names."""

        if self._competitions_cache is None:
            raise RuntimeError("Competitions not loaded. Call fetch_all() first.")

        return (self._competitions_cache["name"].dropna().unique().tolist())