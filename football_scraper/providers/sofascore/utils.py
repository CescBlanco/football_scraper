import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict, Optional, Any, Tuple, Union, Literal
import re
import json
import logging

from football_scraper.providers.sofascore.constants import BASE_URL
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (WebDriverException, TimeoutException,NoSuchElementException)
from webdriver_manager.chrome import ChromeDriverManager

from concurrent.futures import ThreadPoolExecutor


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

#----------------------------------------TEAM-------------------------------------------------------------------------------------------

def clear_data_transfers(json_data: Dict[str, Any],type_transfer: Literal['in', 'out'] = 'in') -> pd.DataFrame:
    """
    Clean and transform transfer data (inbound or outbound) from SofaScore API.

    Args:
        json_data (Dict[str, Any]):
            Raw JSON response from SofaScore transfers endpoint.
        type_transfer (Literal['in', 'out'], optional):
            Type of transfers to extract:
            - 'in'  -> transfersIn
            - 'out' -> transfersOut
            Defaults to 'in'.

    Raises:
        ValueError:
            If input JSON is empty or invalid.
        KeyError:
            If required keys are missing in the JSON structure.

    Returns:
        pd.DataFrame:
            Cleaned and flattened DataFrame containing transfer data, including:
            - player info
            - origin and destination teams
            - transfer fee description
            - transfer date
    """

    # -----------------------------
    # Validate input JSON
    # -----------------------------
    if not json_data:
        raise ValueError("Empty or invalid JSON data")

    key = 'transfersIn' if type_transfer == 'in' else 'transfersOut'

    if key not in json_data:
        raise KeyError(f"Missing '{key}' in JSON data")

    transfers = json_data[key]

    if not isinstance(transfers, list):
        raise ValueError(f"'{key}' must be a list")

    if len(transfers) == 0:
        return pd.DataFrame()  # válido: sin transfers

    df = pd.DataFrame(transfers)

    # -----------------------------
    # Required columns validation
    # -----------------------------
    required_cols = ['player', 'transferFrom', 'transferTo','transferFeeDescription', 'transferDateTimestamp' ]

    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise KeyError(f"Missing columns in transfers data: {missing_cols}")

    df = df[required_cols]

    # -----------------------------
    # Flatten nested fields
    # -----------------------------
    df = pd.concat([
            df.drop(['player', 'transferFrom', 'transferTo'], axis=1),
            df['player'].apply(pd.Series).add_prefix('player_'),
            df['transferFrom'].apply(pd.Series).add_prefix('transferFrom_'),
            df['transferTo'].apply(pd.Series).add_prefix('transferTo_'),
        ], axis=1)

    # -----------------------------
    # Date transformation
    # -----------------------------
    df['transfer_date'] = pd.to_datetime( df['transferDateTimestamp'],unit='s',errors='coerce').dt.date

    # -----------------------------
    # Final column selection
    # -----------------------------
    final_cols = ['player_name',	'player_slug',	'player_shortName'	,'player_position',	'player_jerseyNumber',	'player_id',	'transferFrom_name'	,'transferFrom_slug',	'transferFrom_shortName',	
                                'transferFrom_nameCode'	, 'transferFrom_id',	'transferTo_name'	,'transferTo_slug'	,'transferTo_shortName',	'transferTo_nameCode'	,'transferTo_id',	'transferFeeDescription',	
                                'transfer_date']

    missing_final_cols = [col for col in final_cols if col not in df.columns]
    if missing_final_cols:
        raise KeyError(f"Missing expected columns after transformation: {missing_final_cols}")

    df = df[final_cols]

    return df

def extract_start_year(year: Union[str, int, None]) -> Optional[int]:
    """
    Extract starting year from season format.

    Args:
        year (Union[str, int, None]):
            Season representation. Examples:
            - '25/26' → 2025
            - '2025'  → 2025

    Raises:
        ValueError:
            If the input format is invalid or cannot be parsed.

    Returns:
        Optional[int]:
            Starting year as integer, or None if input is None.
    """

    if year is None:
        return None

    # -----------------------------
    # String formats
    # -----------------------------
    if isinstance(year, str):
        if '/' in year:
            try:
                return int(year[:2]) + 2000
            except Exception:
                raise ValueError(f"Invalid season format: {year}")
        else:
            try:
                return int(year)
            except Exception:
                raise ValueError(f"Invalid year format: {year}")

    # -----------------------------
    # Integer format
    # -----------------------------
    if isinstance(year, int):
        return year

    # -----------------------------
    # Unsupported type
    # -----------------------------
    raise ValueError(f"Unsupported type for year: {type(year)}")

def fetch_page(id_team: Union[str, int], page: int) -> Dict[str, Any]:
    api = f"https://www.sofascore.com/api/v1/team/{id_team}/events/next/{page}"
    data = sofascore_requests(api)

    if data is None:
        raise ValueError(f"Empty response for page={page}, team={id_team}")

    return data

def get_all_next_events_fast(id_team: Union[str, int]) -> List[Dict[str, Any]]:
    first = fetch_page(id_team, 0)

    if "events" not in first:
        raise KeyError("Missing 'events' in API response")

    all_events = first.get('events', [])

    if not isinstance(all_events, list):
        raise ValueError("'events' must be a list")

    if not first.get('hasNextPage'):
        return all_events

    pages = list(range(1, 10))

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(lambda p: fetch_page(id_team, p), pages)

        for res in results:
            if not res:
                continue

            if "events" not in res:
                raise KeyError("Missing 'events' in paginated response")

            all_events.extend(res.get('events', []))

            if not res.get('hasNextPage'):
                break

    return all_events

def clean_events(events_list: List[Dict[str, Any]]) -> pd.DataFrame:

    if not isinstance(events_list, list):
        raise ValueError("events_list must be a list")

    if len(events_list) == 0:
        return pd.DataFrame()

    df = pd.json_normalize(events_list, errors='ignore')

    # -----------------------------
    # Datetime transformation
    # -----------------------------
    dt = pd.to_datetime(df['startTimestamp'], unit='s',utc=True).dt.tz_convert('Europe/Madrid')
    df['match_date'] = dt.dt.date
    df['match_time'] = dt.dt.time

    # -----------------------------
    # Select & rename
    # -----------------------------
    expected_cols = [
        'id','slug', 'match_date', 'match_time', 'tournament.name','tournament.slug', 'roundInfo.round','roundInfo.name', 'roundInfo.slug', 'roundInfo.cupRoundType','status.description','homeTeam.name','homeTeam.slug',
        'homeTeam.shortName','homeTeam.nameCode','homeTeam.id','awayTeam.name', 'awayTeam.slug', 'awayTeam.shortName', 'awayTeam.nameCode', 'awayTeam.id', 'previousLegEventId']

    df = df.reindex(columns=expected_cols)
    df.columns = ['id', 'slug', 'match_date', 'match_time', 'tournament_name', 'tournament_slug', 'round', 'round_name', 'round_slug', 'round_cupRoundType',
        'status_description','homeTeam_name', 'homeTeam_slug', 'homeTeam_shortName', 'homeTeam_nameCode', 'homeTeam_id','awayTeam_name', 'awayTeam_slug', 'awayTeam_shortName', 'awayTeam_nameCode', 'awayTeam_id','previousLegEventId']
    return df

def process_players(df_raw: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Process and normalize player data from SofaScore API.

    Args:
        df_raw (List[Dict[str, Any]]):
            Raw list of player data dictionaries.

    Raises:
        ValueError:
            If input data is invalid or not a list.

    Returns:
        pd.DataFrame:
            Cleaned and flattened DataFrame containing player information:
            - personal info
            - position data
            - country
            - injury status
            - contract and suspension info
    """

    # -----------------------------
    # Validate input
    # -----------------------------
    if not isinstance(df_raw, list):
        raise ValueError("df_raw must be a list of dictionaries")

    if len(df_raw) == 0:
        return pd.DataFrame()

    df = pd.DataFrame(df_raw)

    # -----------------------------
    # SAFE EXPAND
    # -----------------------------
    def safe_expand(df: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
        if col in df.columns:
            return (df[col].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series).add_prefix(prefix))
        return pd.DataFrame(index=df.index)

    # -----------------------------
    # EXPAND PLAYER
    # -----------------------------
    df = pd.concat([ df.drop(['player'], axis=1, errors='ignore'),safe_expand(df, 'player', 'player_'),], axis=1)

    # -----------------------------
    # BASE COLUMNS
    # -----------------------------
    base_cols = ['player_name','player_slug','player_shortName','player_position','player_positionsDetailed','player_jerseyNumber','player_height', 'player_dateOfBirth','player_preferredFoot','player_country',
                'player_id','player_proposedMarketValue','player_contractUntilTimestamp','player_injury','player_activeSeasonSuspensions']

    df = df.reindex(columns=base_cols)

    # -----------------------------
    # EXPAND NESTED
    # -----------------------------
    df = pd.concat([
            df.drop(['player_country','player_injury','player_activeSeasonSuspensions'], axis=1, errors='ignore'),
            safe_expand(df, 'player_country', 'player_country_'),
            safe_expand(df, 'player_injury', 'player_injury_'),
            safe_expand(df, 'player_activeSeasonSuspensions', 'player_activeSeasonSuspensions_'),
        ], axis=1)

    # -----------------------------
    # CLEANING
    # -----------------------------
    if 'player_positionsDetailed' in df.columns:
        df['player_positionsDetailed'] = df['player_positionsDetailed'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)

    if 'player_dateOfBirth' in df.columns:
        df['player_dateOfBirth'] = pd.to_datetime(df['player_dateOfBirth'], errors='coerce').dt.date

    # -----------------------------
    # TIMESTAMPS
    # -----------------------------
    timestamp_cols = ['player_contractUntilTimestamp','player_injury_startDateTimestamp','player_injury_updateDateTimestamp','player_injury_endDateTimestamp']

    for col in timestamp_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col],unit='s', errors='coerce').dt.date

    # -----------------------------
    # FINAL CLEANUP
    # -----------------------------
    df = df.drop(columns=['player_country_alpha2', 'player_injury_0', 'player_injury_status'],errors='ignore')

    return df

def extract_top_players_stats_available(id_team_sofascore: Union[str, int], id_league_selected: Union[str, int],id_season_selected: Union[str, int]) -> Tuple[List[str], Dict[str, Any]]:
    """
    Get available top player statistics categories for a team in a given competition season.

    Args:
        id_team_sofascore (Union[str, int]):
            Team identifier in SofaScore.
        id_league_selected (Union[str, int]):
            League identifier.
        id_season_selected (Union[str, int]):
            Season identifier.

    Raises:
        ValueError:
            If API response is empty or invalid.
        KeyError:
            If 'topPlayers' is missing in API response.

    Returns:
        Tuple[List[str], Dict[str, Any]]:
            - List of available statistic names
            - Raw JSON response from API
    """

    api =f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/unique-tournament/{id_league_selected}/season/{id_season_selected}/top-players/overall"
 

    json_data = sofascore_requests(api)

    # -----------------------------
    # Hard failure: API response
    # -----------------------------
    if not json_data:
        raise ValueError("Empty API response")

    if "topPlayers" not in json_data:
        raise KeyError("Missing 'topPlayers' in API response")

    # -----------------------------
    # Normalize stats
    # -----------------------------
    top_players_row = pd.json_normalize(json_data['topPlayers']).transpose()
    top_players_row = top_players_row.rename(columns={0: 'dict_stats'}).reset_index().rename(columns={'index': 'stat_name'})
    

    stat_names = top_players_row['stat_name'].tolist()

    return stat_names, json_data
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


#----------------------------------------MATCH-------------------------------------------------------------------------------------------
def safe_expand(df: pd.DataFrame, col: str, prefix: str) -> pd.DataFrame:
        """
        Safely expands nested player-like columns into flat structure.
        """
        if col not in df.columns:
            return pd.DataFrame(index=df.index)

        expanded = df[col].apply(
            lambda x: {} if not isinstance(x, dict) else x).apply(pd.Series)

        # Select only expected columns if they exist
        cols = ["name", "slug", "shortName", "position", "jerseyNumber", "id"]
        expanded = expanded[[c for c in cols if c in expanded.columns]]

        return expanded.add_prefix(f"{prefix}_")

def safe_manager(manager, prefix: str) -> pd.DataFrame:
            """
            Safely converts manager dict into flat DataFrame.
            """
            if not isinstance(manager, dict):
                return pd.DataFrame(
                    [{f"{prefix}_name": None,
                    f"{prefix}_slug": None,
                    f"{prefix}_short_name": None,
                    f"{prefix}_manager_id": None}]
                )

            return pd.DataFrame([manager])[["name", "slug", "shortName", "id"]].rename(
                columns={
                    "name": f"{prefix}_name",
                    "slug": f"{prefix}_slug",
                    "shortName": f"{prefix}_short_name",
                    "id": f"{prefix}_manager_id"
                }
            )

def safe_extract_players(players, team_label: str) -> pd.DataFrame:
        """
        Safely extracts player list into flat DataFrame.
        """

        if not players:
            return pd.DataFrame()
        df = pd.DataFrame(players)

        if df.empty or "player" not in df.columns:
            return pd.DataFrame()

        player_df = df["player"].apply(lambda x: {} if not isinstance(x, dict) else x).apply(pd.Series)

        cols = [ "name", "slug", "shortName","position", "jerseyNumber","height", "id","dateOfBirthTimestamp" ]

        player_df = player_df[[c for c in cols if c in player_df.columns]]

        if "dateOfBirthTimestamp" in player_df.columns:
            player_df["dateOfBirthTimestamp"] = pd.to_datetime(player_df["dateOfBirthTimestamp"], unit="s",errors="coerce" )

        player_df["team"] = team_label

        return player_df

def process_team(data: list) -> pd.DataFrame:
        df = pd.DataFrame(data)

        if df.empty or "player" not in df.columns:
            return pd.DataFrame()

        player = df["player"].apply( lambda x: {} if not isinstance(x, dict) else x).apply(pd.Series)

        player = player.drop(columns=["userCount","gender","fieldTranslations","firstName","lastName","sofascoreId"],errors="ignore")

        return pd.concat( [player, df.drop(columns=["player"], errors="ignore")],axis=1 )

#----------------------------------------MATCH ONE PLAYER-------------------------------------------------------------------------------------------

def safe_expand_one_player(df, col, prefix):
    if col in df.columns:
        return df[col].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series).add_prefix(prefix)
    return pd.DataFrame(index=df.index)
