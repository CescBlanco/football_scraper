import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import logging
from typing import Dict, List, Union, Tuple ,Literal, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (WebDriverException, TimeoutException,NoSuchElementException)
from webdriver_manager.chrome import ChromeDriverManager
from tqdm import tqdm

from providers.sofascore.constants import DEFAULT_HEADERS, BASE_URL
from providers.sofascore.utils import sofascore_requests

class SofascoreCompetitionService:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None

    def extract_all_countries(self) -> pd.DataFrame:
        """
        Extract all football country categories from SofaScore API
        and return them as a structured pandas DataFrame.

        This function calls the SofaScore API endpoint that contains
        all football categories (countries/leagues structure), then
        extracts relevant fields and converts them into a DataFrame.

        Returns:
            pd.DataFrame:
                A DataFrame containing country/category information with
                the following columns:
                    - name (str): Name of the country/category
                    - slug (str): URL-friendly identifier
                    - id (int): Unique SofaScore identifier
                    - flag (str): URL or identifier of the country flag

        Raises:
            KeyError:
                If the expected 'categories' key is missing in the API response.

            ValueError:
                If the API response is empty or malformed.

            Exception:
                Any exception raised by the underlying API request function.
        """

        # --- Fetch raw JSON data from SofaScore API ---
        json_data = sofascore_requests("https://www.sofascore.com/api/v1/sport/football/categories/all")

        # --- Validate response structure ---
        if not json_data or "categories" not in json_data:
            raise KeyError("Missing 'categories' key in SofaScore API response")

        categories = json_data["categories"]

        if not isinstance(categories, list):
            raise ValueError("'categories' should be a list")

        # --- Convert to pandas DataFrame safely ---
        df = pd.DataFrame(categories)

        # --- Select only relevant columns (fail-safe) ---
        expected_columns = ["name", "slug", "id", "flag"]

        missing_cols = [col for col in expected_columns if col not in df.columns]
        if missing_cols:
            raise KeyError(f"Missing expected columns in data: {missing_cols}")
        df_final=df[expected_columns] 
        self._competitions_cache = df_final
        return df_final
    
    