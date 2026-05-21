from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


import pandas as pd
import re
import requests
import json
from bs4 import BeautifulSoup

from football_scraper.providers.scoresway.constants import DEFAULT_HEADERS

#----------------------------------------------DRIVE SELENIUM---------------------------------------------
def _create_driver():
    from webdriver_manager.chrome import ChromeDriverManager
    """
    Create and configure a Selenium Chrome WebDriver instance.

    This function initializes a Chrome browser in headless mode with
    anti-detection configurations commonly used for web scraping tasks.

    Returns
    -------
    webdriver.Chrome
        Configured Selenium Chrome WebDriver instance.

    Raises
    ------
    RuntimeError
        If the Chrome WebDriver cannot be initialized.
    """

    try:
        # Configure Chrome browser options
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")

        # Prevent Selenium detection by websites
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Set a realistic browser user-agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # Automatically install and configure ChromeDriver
        service = Service(ChromeDriverManager().install())

        # Create WebDriver instance
        driver = webdriver.Chrome(service=service, options=options)

        # Hide webdriver property from browser detection scripts
        driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """)

        return driver

    except Exception as e:
        raise RuntimeError(f"Failed to create Chrome WebDriver: {str(e)}")
    
#----------------------------------------------RESPONSE BEAUTIFUL---------------------------------------------
def _create_response(url_api: str):
    """
    Send a request to the PerformFeeds API and parse the JSONP response.

    This function performs an HTTP GET request to the provided API URL,
    extracts the JSON object from the JSONP wrapper, and converts it
    into a Python dictionary.

    Parameters
    ----------
    url_api : str
        Complete API endpoint URL.

    Returns
    -------
    dict
        Parsed JSON response as a Python dictionary.

    Raises
    ------
    TypeError
        If url_api is not a string.
    ValueError
        If:
        - url_api is empty.
        - the API response format is invalid.
        - JSON data cannot be extracted.
    RuntimeError
        If the HTTP request or JSON parsing fails.
    """

    try:
        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url_api, str):
            raise TypeError("url_api must be a string")

        if not url_api.strip():
            raise ValueError("url_api cannot be empty")

        # ------------------------
        # SEND API REQUEST
        # ------------------------
        r = requests.get(url_api, headers=DEFAULT_HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"API request failed with status code {r.status_code}")
        text = r.text

        # ------------------------
        # EXTRACT JSON FROM JSONP
        # ------------------------
        match = re.search(r'\((.*)\)', text)
        if not match:
            raise ValueError("Invalid JSONP response format")

        data = match.group(1)

        # ------------------------
        # PARSE JSON DATA
        # ------------------------
        json_data = json.loads(data)
        if not isinstance(json_data, dict):
            raise ValueError("Parsed response is not a valid JSON object")

        return json_data

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to decode JSON response: {str(e)}")

    except requests.RequestException as e:
        raise RuntimeError(f"HTTP request failed: {str(e)}")

    except Exception as e:
        raise RuntimeError( f"Failed to create API response: {str(e)}")
    
#----------------------------------------------POST MATCH---------------------------------------------
def extract_team_data(soup: BeautifulSoup,team_type: str) -> list[dict]:
    """
    Extract player statistics data for a specific team
    from a parsed match statistics page.

    This helper function parses HTML tables containing
    player statistics for either the home or away team,
    extracts player metrics, and returns a list of
    structured dictionaries.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed BeautifulSoup object containing the
        player statistics page HTML.
    team_type : str
        Team side identifier.

        Supported values:
        - "home"
        - "away"

    Returns
    -------
    list[dict]
        List of dictionaries containing:
        - player name
        - team side
        - player statistics

    Raises
    ------
    TypeError
        If:
        - soup is not a BeautifulSoup object.
        - team_type is not a string.
    ValueError
        If:
        - team_type is empty.
        - team_type is invalid.
        - no player statistics tables are found.
    RuntimeError
        If the extraction process fails.
    """

    try:
        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(soup, BeautifulSoup):
            raise TypeError("soup must be a BeautifulSoup object")

        if not isinstance(team_type, str):
            raise TypeError("team_type must be a string")

        if not team_type.strip():
            raise ValueError("team_type cannot be empty")

        valid_team_types = ["home", "away"]

        if team_type not in valid_team_types:
            raise ValueError(f"Invalid team_type '{team_type}'. Valid options are: {valid_team_types}")

        # ------------------------
        # INITIALIZE STORAGE
        # ------------------------
        players_dict = {}

        # ------------------------
        # SELECT TEAM TABLES
        # ------------------------
        selector = f"#mts_{team_type} div.Opta-js-data"
        tables = soup.select(selector)
        if not tables:
            raise ValueError(f"No player statistics tables were found for team '{team_type}'")

        # ------------------------
        # PARSE TABLES
        # ------------------------
        for table_block in tables:

            table = table_block.find("table")
            if not table:
                continue

            # ------------------------
            # EXTRACT TABLE HEADERS
            # ------------------------
            headers = [th.get("title")for th in table.select("thead th abbr")  if th.get("title")]

            # ------------------------
            # EXTRACT TABLE ROWS
            # ------------------------
            rows = table.select("tbody tr")

            for row in rows:

                player_tag = row.select_one("th")
                if not player_tag:
                    continue

                player = player_tag.text.strip()

                stats = [ td.text.strip() for td in row.select("td")]

                # ------------------------
                # INITIALIZE PLAYER DATA
                # ------------------------
                if player not in players_dict:

                    players_dict[player] = {
                        "player": player,
                        "team": team_type
                    }

                # ------------------------
                # MAP PLAYER STATISTICS
                # ------------------------
                for i, stat_name in enumerate(headers):

                    if i < len(stats):

                        players_dict[player][stat_name] = stats[i]

                    else:

                        players_dict[player][stat_name] = None

        # ------------------------
        # VALIDATE OUTPUT
        # ------------------------
        if not players_dict:
            raise ValueError(f"No player statistics were extracted for team '{team_type}'")

        return list(players_dict.values())

    except Exception as e:
        raise RuntimeError(f"Failed to extract player statistics for team '{team_type}': {str(e)}")

def extract_width(span) -> float | None:
    """
    Extract percentage width from style attribute.
    """

    if not span:
        return None

    style = span.get("style", "")

    for part in style.split(";"):

        if "width" in part:

            try:
                return float(
                    part.split(":")[1]
                    .replace("%", "")
                    .strip()
                )

            except Exception:
                return None

    return None

#----------------------------------------------EVENTS MATCH---------------------------------------------
def normalize_label(x: str) -> str:
    """
    Normalize a text label into a clean snake_case string.

    This function:
    - Converts text to lowercase
    - Replaces non-alphanumeric characters with underscores
    - Collapses multiple underscores
    - Strips leading/trailing underscores

    Parameters
    ----------
    x : str
        Input label to normalize.

    Returns
    -------
    str
        Normalized snake_case label. Returns empty string if input is invalid.
    """
    
    # ------------------------
    # VALIDATE INPUT
    # ------------------------
    if x is None:
        return ""

    # ------------------------
    # NORMALIZE
    # ------------------------
    if not isinstance(x, str):
        x = str(x)

    x = x.lower()

    x = re.sub(r"[^a-z0-9]+", "_", x)
    x = re.sub(r"_+", "_", x)

    return x.strip("_")

def build_qualifier_mapping(qualifiers_df: pd.DataFrame) -> dict:
    """
    Build a mapping from qualifier codes to normalized qualifier labels.

    This function transforms a qualifiers reference DataFrame into a
    dictionary that maps qualifier codes to cleaned, normalized names.

    Parameters
    ----------
    qualifiers_df : pd.DataFrame
        DataFrame containing:
        - Code
        - Qualifier

    Returns
    -------
    dict
        Dictionary mapping:
        {Code -> normalized qualifier label}

    Raises
    ------
    TypeError
        If qualifiers_df is not a DataFrame.
    ValueError
        If required columns are missing.
    """

    # ------------------------
    # VALIDATE INPUT
    # ------------------------
    if not isinstance(qualifiers_df, pd.DataFrame):
        raise TypeError("qualifiers_df must be a pandas DataFrame")

    required_cols = {"Code", "Qualifier"}
    missing_cols = required_cols - set(qualifiers_df.columns)

    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # ------------------------
    # CLEAN DATA
    # ------------------------
    codes = qualifiers_df["Code"]
    labels = qualifiers_df["Qualifier"].apply(normalize_label)

    # ------------------------
    # BUILD MAPPING
    # ------------------------
    return dict(zip(codes, labels))
