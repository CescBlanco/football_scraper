import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Any, Tuple, Union
import re
import json
import logging

from providers.sofascore.constants import BASE_URL
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (WebDriverException, TimeoutException,NoSuchElementException)
from webdriver_manager.chrome import ChromeDriverManager


#-------------------------------------------SOFASCORE REQUESTS----------------------------------------------------------------------------
def sofascore_requests(url_api: str, timeout: int = 10) -> Dict:
    """
    Fetch JSON data from a SofaScore API endpoint using a headless Selenium browser.

    This function opens a real Chrome browser (headless mode) to bypass potential
    anti-bot protections or dynamic rendering issues. It loads a base SofaScore page
    first to establish session context, then navigates to the target API endpoint
    and extracts the JSON response from the page body.

    Args:
        url_api (str):
            Full URL of the SofaScore API endpoint to request.

        timeout (int, optional):
            Maximum time (in seconds) to wait for the page content to load.
            Default is 10 seconds.

    Returns:
        Dict:
            Parsed JSON response converted into a Python dictionary.

    Raises:
        ValueError:
            If the response body cannot be parsed as valid JSON.

        TimeoutException:
            If the page does not load within the specified timeout.

        NoSuchElementException:
            If the <body> element cannot be found.

        WebDriverException:
            If ChromeDriver fails to start or crashes during execution.

        Exception:
            Generic fallback for unexpected runtime errors.
    """

    driver = None

    try:
        # --- Chrome configuration (headless mode) ---
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")  # modern headless mode
        options.add_argument("--disable-blink-features=AutomationControlled")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)

        # --- Step 1: load base page to initialize cookies/session ---
        driver.get(BASE_URL)

        WebDriverWait(driver, timeout).until( lambda d: d.execute_script("return document.readyState") == "complete")

        # --- Step 2: request target API endpoint ---
        driver.get(url_api)

        # Wait until body is present
        body = WebDriverWait(driver, timeout).until( EC.presence_of_element_located((By.TAG_NAME, "body")) )

        # --- Extract raw response ---
        raw_text = body.text

        # --- Parse JSON safely ---
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from SofaScore API: {e}")

    except TimeoutException as e:
        logging.error("Timeout while loading SofaScore page or API")
        raise

    except NoSuchElementException as e:
        logging.error("Could not find expected HTML element in response")
        raise

    except WebDriverException as e:
        logging.error("WebDriver error occurred")
        raise

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise

    finally:
        # Always close browser to avoid memory leaks
        if driver:
            driver.quit()

#----------------------------------------PLAYER-------------------------------------------------------------------------------------------


def extract_tournament_season_available(id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract available tournaments and seasons for a player from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing in the API response.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - season info (id, name, year)
                - tournament info (name, slug, id)
                - category info
        """

        url = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/statistics/seasons"
        json_data = sofascore_requests(url)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "uniqueTournamentSeasons" not in json_data:
            raise KeyError("Missing 'uniqueTournamentSeasons' in API response")

        uts = json_data["uniqueTournamentSeasons"]

        if not isinstance(uts, list):
            raise ValueError("'uniqueTournamentSeasons' must be a list")

        if len(uts) == 0:
            return pd.DataFrame()

        # -----------------------------
        # Normalize
        # -----------------------------
        df = pd.DataFrame(uts)

        if "seasons" not in df.columns or "uniqueTournament" not in df.columns:
            raise KeyError("Missing required fields in tournament data")

        df = df.explode('seasons').reset_index(drop=True)

        # -----------------------------
        # Tournament info
        # -----------------------------
        tournament_df = pd.json_normalize(df['uniqueTournament'])

        required_tournament_cols = ['name', 'slug', 'id', 'category.name', 'category.slug', 'category.id']
        tournament_df = tournament_df.reindex(columns=required_tournament_cols)

        # -----------------------------
        # Season info
        # -----------------------------
        seasons_df = pd.json_normalize(df['seasons'])

        if 'id' not in seasons_df.columns:
            raise KeyError("Missing 'id' in seasons data")

        seasons_df = seasons_df.drop(columns=['editor', 'seasonCoverageInfo.editorCoverageLevel'],errors='ignore').rename(columns={'name': 'season_name', 'id': 'season_id'})

        # -----------------------------
        # Final merge
        # -----------------------------
        final_df = pd.concat([seasons_df, tournament_df], axis=1)

        return final_df              

def expand_coordinates(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    result = df.copy()
    for col in cols:
        if col in result.columns:
            expanded = result[col].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series).add_prefix(f"{col}_")
            result = pd.concat([result.drop(columns=[col]), expanded], axis=1)
    return result

#----------------------------------------GENERAL-------------------------------------------------------------------------------------------
def safe_expand(df: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
    if col in df.columns:
        return df[col].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series).add_prefix(prefix)
    return pd.DataFrame(index=df.index)
