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

from providers.sofascore.constants import DEFAULT_HEADERS, BASE_URL, BASE_URL_TEAM
from providers.sofascore.utils import sofascore_requests

class SofascoreLeagueService:
    def __init__(self, session: requests.Session, competition_service):
        self.session = session
        self.competition_service = competition_service
        self._leagues_cache = None 

    def get_all_leagues_from_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fetch all football leagues (unique tournaments) from SofaScore API
        for each country/category provided in the input DataFrame.

        This function iterates over a DataFrame of countries/categories,
        requests SofaScore's unique tournaments endpoint for each country,
        and aggregates all league data into a single DataFrame.

        Args:
            df (pd.DataFrame):
                DataFrame containing at least:
                    - id (int): country/category identifier
                    - name (str, optional): country name for logging/debugging

        Returns:
            pd.DataFrame:
                A combined DataFrame with all leagues found across countries.
                Columns:
                    - country_id (int)
                    - country_name (str)
                    - name (str): league name
                    - slug (str): league slug
                    - id (int): league id
                    - category.slug (str): category slug

        Raises:
            ValueError:
                If input DataFrame is empty or missing required columns.

            WebDriverException:
                If Selenium WebDriver fails to initialize or execute.

            Exception:
                Any unexpected runtime error during execution.
        """
        # 👇 SI YA EXISTE CACHE, NO SCRAPEAR
        if self._leagues_cache is not None:
            return self.leagues_cache
        
        if df is None or df.empty:
            raise ValueError("Input DataFrame is empty")

        if "id" not in df.columns:
            raise KeyError("Input DataFrame must contain an 'id' column")

        BASE_URL_TOURNAMENTS = "https://www.sofascore.com/api/v1/category/{}/unique-tournaments"

        driver = None
        all_leagues_data: List[pd.DataFrame] = []

        try:
            # =========================
            # Chrome configuration
            # =========================
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")

            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)

            # Load base page once to initialize session/cookies
            driver.get(BASE_URL)

            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # =========================
            # Iterate over countries
            # =========================
            for _, row in tqdm(df.iterrows(), total=len(df)):

                country_id = row["id"]
                country_name = row.get("name", "")

                url = BASE_URL_TOURNAMENTS.format(country_id)

                try:
                    driver.get(url)

                    # Wait for response body
                    body = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                    json_data = json.loads(body.text)

                    # Skip if structure is not valid
                    if ("groups" not in json_data or not json_data["groups"]):
                        continue

                    # Extract tournaments
                    df_leagues = pd.json_normalize(json_data["groups"][0]["uniqueTournaments"])

                    if df_leagues.empty:
                        continue

                    # Add metadata
                    df_leagues["country_id"] = country_id
                    df_leagues["country_name"] = country_name

                    # Select stable columns only
                    df_leagues = df_leagues[["country_id","country_name","name","slug","id","category.slug"]]

                    all_leagues_data.append(df_leagues)

                except (TimeoutException, json.JSONDecodeError) as e:
                    logging.warning(f"Skipping country {country_name} ({country_id}) due to parse/timeout error: {e}")
                    continue

                except Exception as e:
                    logging.error(f"Unexpected error for country {country_name} ({country_id}): {e}")
                    continue

        except WebDriverException as e:
            logging.error(f"WebDriver failed to initialize: {e}")
            raise

        finally:
            # Always close browser to avoid memory leaks
            if driver:
                driver.quit()

        # =========================
        # Merge results
        # =========================
        if all_leagues_data:
            df_final = pd.concat(all_leagues_data, ignore_index=True)
            self._leagues_cache = df_final 
            return df_final
        
        return pd.DataFrame()
    
    def extract_info_league(self, league_name: str, df_leagues_all: pd.DataFrame) -> str:
        """
        Extract the league information corresponding to a given league name.

        This function filters a DataFrame containing league data and retrieves
        the row that matches the provided league name.

        Args:
            league_name (str):
                Name of the league to search for.

            df_leagues_all (pd.DataFrame):
                DataFrame containing league data. It must include at least:
                    - name (str): league name
                    - id (int or str): league identifier

        Returns:
            pd.Series:
                A pandas Series representing the matched league row, including all
                available columns for that league.

        Raises:
            ValueError:
                If the DataFrame is empty or no league matches the provided name.

            KeyError:
                If required columns ('name', 'id') are missing.

        Example:
            league_info = extract_league("La Liga", df_leagues_all)
            league_id = league_info["id"]
        """

        # -------------------------
        # Validate input DataFrame
        # -------------------------
        if df_leagues_all is None or df_leagues_all.empty:
            raise ValueError("Leagues DataFrame is empty")

        required_cols = {"name", "id"}
        missing_cols = required_cols - set(df_leagues_all.columns)

        if missing_cols:
            raise KeyError(f"Missing required columns: {missing_cols}")

        # -------------------------
        # Filter league by name
        # -------------------------
        match = df_leagues_all[df_leagues_all["name"] == league_name]

        # -------------------------
        # Validate result
        # -------------------------
        if match.empty:
            raise ValueError(f"No league found with name: {league_name}")

        # Take first match safely


        return match

    def extract_id_from_league(self, league_name: str, df_leagues_all: pd.DataFrame) -> str:
        """
        Extract the SofaScore league ID for a given league name.

        This function retrieves league information using `extract_info_league`
        and extracts the unique SofaScore identifier from the resulting match.

        Args:
            league_name (str):
                Name of the league to search for.

            df_leagues_all (pd.DataFrame):
                DataFrame containing league data. It must include at least:
                    - name (str): league name
                    - id (int or str): league identifier

        Returns:
            str:
                The SofaScore league ID corresponding to the given league name.

        Raises:
            ValueError:
                If the DataFrame is empty or no league matches the provided name.

            KeyError:
                If required columns ('name', 'id') are missing.

        Example:
            league_id = extract_id_from_league("La Liga", df_leagues_all)
        """

        match= self.extract_info_league(league_name, df_leagues_all)

        # Take first match safely
        league_id = match["id"].iloc[0]

        return str(league_id)
    
    def extract_seasons_league(self, league_name: str,df_leagues_all: pd.DataFrame) -> pd.DataFrame:
        """
        Extract all seasons for a given football league from SofaScore API.

        This function retrieves the league ID from the provided DataFrame,
        queries the SofaScore API for available seasons of that league,
        and returns the data as a cleaned pandas DataFrame.

        Args:
            league_name (str):
                Name of the league to search for.

            df_leagues_all (pd.DataFrame):
                DataFrame containing all leagues. Must include at least:
                    - name (str): league name
                    - id (int/str): league identifier

        Returns:
            pd.DataFrame:
                DataFrame containing season information for the selected league,
                with irrelevant columns removed.

        Raises:
            ValueError:
                If no seasons are found or API response is invalid.

            KeyError:
                If expected keys ('seasons') are missing in API response.

            Exception:
                Propagates errors from underlying functions (API request or lookup).
        """

        # -----------------------------
        # Get league ID safely
        # -----------------------------
        league_id = self.extract_id_from_league(league_name, df_leagues_all)

        # -----------------------------
        # Build API endpoint
        # -----------------------------
        api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{league_id}/seasons"

        # -----------------------------
        # Fetch data from SofaScore API
        # -----------------------------
        json_data = sofascore_requests(api_url)

        # -----------------------------
        # Validate response structure
        # -----------------------------
        if not json_data or "seasons" not in json_data:
            raise KeyError("Missing 'seasons' key in SofaScore API response")

        seasons = json_data["seasons"]

        if not seasons:
            raise ValueError(f"No seasons found for league: {league_name}")

        # -----------------------------
        # Convert to DataFrame
        # -----------------------------
        df = pd.DataFrame(seasons)

        # -----------------------------
        # Clean unnecessary columns safely
        # -----------------------------
        columns_to_drop = ["editor", "seasonCoverageInfo"]
        df = df.drop(columns=[col for col in columns_to_drop if col in df.columns],errors="ignore")

        return df
    
    def extract_id_season_from_league(self, league_name: str,df_leagues_all: pd.DataFrame, season_selected: str = "25/26") -> str:
        """
        Extract the season ID for a given football league and season label.

        This function retrieves all seasons for a given league using the SofaScore API,
        filters them by the selected season (e.g. "25/26"), and returns the corresponding
        season ID.

        Args:
            league_name (str):
                Name of the league to search for.

            df_leagues_all (pd.DataFrame):
                DataFrame containing all leagues. Must include at least:
                    - name (str)
                    - id (int/str)

            season_selected (str, optional):
                Season label to filter by (e.g. "25/26"). Default is "25/26".

        Returns:
            str:
                The season ID corresponding to the selected league and season.

        Raises:
            ValueError:
                If no season matches the given criteria or if data is missing.

            KeyError:
                If required columns are missing in the seasons DataFrame.

            Exception:
                Propagates errors from underlying functions.
        """

        # ---------------------------------------
        # Get seasons for the selected league
        # ---------------------------------------
        df_seasons_league =self.extract_seasons_league(league_name, df_leagues_all)

        if df_seasons_league is None or df_seasons_league.empty:
            raise ValueError(f"No seasons found for league: {league_name}")

        # ---------------------------------------
        # Validate required column
        # ---------------------------------------
        if "year" not in df_seasons_league.columns:
            raise KeyError("Missing 'year' column in seasons DataFrame")

        # ---------------------------------------
        # Filter season safely
        # ---------------------------------------
        match = df_seasons_league[df_seasons_league["year"] == season_selected]

        if match.empty:
            raise ValueError(f"No season '{season_selected}' found for league '{league_name}'")

        # Take first match safely
        season_id = match["id"].iloc[0]

        return str(season_id)
    
    def extract_teams(self, id_league_selected: Union[str, int], id_season_selected: Union[str, int]) -> pd.DataFrame:
        """
        Extract teams participating in a specific league season from SofaScore API.

        This function retrieves the standings for a given league and season,
        extracts team information, and returns a cleaned pandas DataFrame
        enriched with team URLs and image URLs.

        Args:
            id_league_selected (str | int):
                Unique SofaScore identifier for the league.

            id_season_selected (str | int):
                Unique SofaScore identifier for the season.

        Returns:
            pd.DataFrame:
                DataFrame containing team information with columns:
                    - name
                    - slug
                    - shortName
                    - nameCode
                    - id
                    - country.alpha3
                    - country.name
                    - country.slug
                    - teamColors.primary
                    - teamColors.secondary
                    - teamColors.text
                    - url_team
                    - image_url

        Raises:
            KeyError:
                If expected keys ('standings', 'rows', 'team') are missing.

            ValueError:
                If API response is empty or malformed.

            Exception:
                Any error raised by the API request layer.
        """

        # -----------------------------
        # Build API endpoint
        # -----------------------------
        api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/standings/total"

        # -----------------------------
        # Fetch data from SofaScore API
        # -----------------------------
        json_data = sofascore_requests(api_url)

        # -----------------------------
        # Validate response structure
        # -----------------------------
        if not json_data or "standings" not in json_data or not json_data["standings"]:
            raise KeyError("Missing or invalid 'standings' data in API response")
        try:
            rows = json_data["standings"][0]["rows"]
        except (KeyError, IndexError, TypeError):
            raise KeyError("Invalid structure inside 'standings' response")

        # -----------------------------
        # Normalize team data
        # -----------------------------
        df = pd.json_normalize(pd.DataFrame(rows)["team"])

        if df.empty:
            raise ValueError("No team data found in standings response")

        # -----------------------------
        # Select relevant columns safely
        # -----------------------------
        expected_columns = [ "name","slug","shortName", "nameCode", "id","country.alpha3","country.name","country.slug",
            "teamColors.primary","teamColors.secondary","teamColors.text",]

        missing_cols = [col for col in expected_columns if col not in df.columns]
        if missing_cols:
            raise KeyError(f"Missing expected columns: {missing_cols}")

        df = df[expected_columns]

        # -----------------------------
        # Build derived fields
        # -----------------------------
        df["url_team"] = "https://www.sofascore.com/football/team/"+ df["slug"].astype(str)+ "/"+ df["id"].astype(str)

        df["image_url"] = BASE_URL_TEAM + df["id"].astype(str) + "/image/small"
        return df
    
    def extract_details(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int]) -> Tuple[pd.DataFrame, Union[pd.DataFrame, str], pd.DataFrame]:
        """
        Extract detailed information about a football league season from SofaScore API.

        This function retrieves general season statistics and information about
        promotion/relegation teams (upper and lower divisions) when available.

        Args:
            id_league_selected (str | int):
                Unique SofaScore identifier for the league.

            id_season_selected (str | int):
                Unique SofaScore identifier for the season.

        Returns:
            Tuple containing:
                - df_info (pd.DataFrame):
                    General season statistics (goals, wins, cards, etc.).

                - upper_division (pd.DataFrame | str):
                    Teams promoted to higher division, or a message if not applicable.

                - lower_division (pd.DataFrame):
                    Teams relegated to lower division.

        Raises:
            KeyError:
                If expected keys are missing in API response.

            ValueError:
                If API response is empty or malformed.

            Exception:
                Any error raised by the underlying request function.
        """

        # -----------------------------
        # Build API endpoint
        # -----------------------------
        api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/info"
        
        # -----------------------------
        # Fetch data
        # -----------------------------
        json_data = sofascore_requests(api_url)

        if not json_data or "info" not in json_data:
            raise KeyError("Missing 'info' key in SofaScore API response")

        info = json_data["info"]

        # -------------------------
        # MAIN INFO SAFE PARSING
        # -------------------------
        df_row = pd.json_normalize(info)

        expected_columns = ["id","season.name","season.year","season.id","numberOfCompetitors","goals","homeTeamWins","awayTeamWins","draws",
                            "yellowCards","redCards"]

        df_info = df_row[[c for c in expected_columns if c in df_row.columns]]

        # -------------------------
        # UPPER DIVISION (optional)
        # -------------------------
        upper_division = "This is the top-tier league (no upper division)."

        if info.get("newcomersUpperDivision"):
            upper_division = pd.json_normalize(info["newcomersUpperDivision"])

            # SAFE COLUMN SELECTION (NO CRASH EVER)
            cols_upper = ["name","slug","shortName","nameCode","id","teamColors"]

            upper_division = upper_division[[c for c in cols_upper if c in upper_division.columns]]

        # -------------------------
        # LOWER DIVISION (optional FIXED)
        # -------------------------
        lower_raw = info.get("newcomersLowerDivision", [])

        if not lower_raw:
            lower_division = pd.DataFrame()
        else:
            lower_division = pd.json_normalize(lower_raw)

            cols_lower = ["name","slug", "shortName", "nameCode", "id","teamColors"]

            # IMPORTANT FIX: avoid KeyError if teamColors missing
            lower_division = lower_division[[c for c in cols_lower if c in lower_division.columns]]

        return df_info, upper_division, lower_division
    
    def extract_team_of_the_week_by_tournament(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int]) -> pd.DataFrame:
        """
        Extract all 'Team of the Week' players for a given league and season
        from SofaScore API.

        This function:
            1. Retrieves all available periods (rounds).
            2. Iterates over each round.
            3. Extracts players and formation data.
            4. Returns a unified DataFrame with all players.

        Args:
            id_league_selected (str | int):
                SofaScore tournament ID.

            id_season_selected (str | int):
                SofaScore season ID.

        Returns:
            pd.DataFrame:
                DataFrame containing all players from Team of the Week,
                including round number and formation.

        Raises:
            WebDriverException:
                If Selenium fails to initialize.

            KeyError:
                If required keys are missing in API responses.

            Exception:
                Any unexpected runtime error.
        """

        driver = None
        all_players_data = []

        try:
            # -----------------------------
            # Chrome configuration
            # -----------------------------
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")

            driver = webdriver.Chrome( service=Service(ChromeDriverManager().install()), options=options )

            # -----------------------------
            # Initialize session
            # -----------------------------
            driver.get(BASE_URL)

            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # -----------------------------
            # Get periods (rounds)
            # -----------------------------
            api_periods = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/team-of-the-week/periods"
            

            driver.get(api_periods)

            body = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            json_periods = json.loads(body.text)

            if "periods" not in json_periods:
                logging.warning("No 'periods' found in response — returning empty DataFrame")
                return pd.DataFrame()

            rounds_df = pd.json_normalize(json_periods["periods"])

            if rounds_df.empty:
                return pd.DataFrame()

            rounds_df = rounds_df.rename(columns={"id": "period_id","round.round": "round_number"})

            rounds_df = rounds_df[[c for c in ["period_id", "round_number"] if c in rounds_df.columns]]

            # -----------------------------
            # Iterate rounds
            # -----------------------------
            for _, row in tqdm(rounds_df.iterrows(), total=len(rounds_df)):

                period_id = row.get("period_id")
                round_number = row.get("round_number")

                api_tow = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/team-of-the-week/{period_id}"

                try:
                    driver.get(api_tow)

                    body = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                    json_data = json.loads(body.text)

                    # -------------------------
                    # Extract players safely
                    # -------------------------
                    players = json_data.get("players", [])

                    if not players:
                        continue

                    players_df = pd.json_normalize(players)

                    players_df["round_number"] = round_number
                    players_df["formation_name"] = json_data.get("formation")

                    all_players_data.append(players_df)

                except (TimeoutException, json.JSONDecodeError) as e:
                    logging.warning(f"Skipping round {round_number} due to timeout/parse error: {e}")
                    continue

                except Exception as e:
                    logging.error(f"Unexpected error in round {round_number}: {e}")
                    continue

        except WebDriverException as e:
            logging.error(f"WebDriver initialization failed: {e}")
            raise

        finally:
            if driver:
                driver.quit()

        # -----------------------------
        # Merge results
        # -----------------------------
        if not all_players_data:
            return pd.DataFrame()

        df_players_all = pd.concat(all_players_data, ignore_index=True)

        # -----------------------------
        # Safe column selection (CRITICAL)
        # -----------------------------
        expected_cols = [
                'round_number', 'formation_name', 'order', 'id', 'player.name', 'player.slug', 'player.shortName', 'player.position', 'player.jerseyNumber', 'player.userCount', 'player.id', 'team.name', 'team.slug',
                'team.shortName', 'team.nameCode', 'team.id', 'event.status.description', 'event.winnerCode','event.homeTeam.name', 'event.homeTeam.slug', 'event.homeTeam.shortName', 'event.homeTeam.nameCode',
                'event.homeTeam.id', 'event.awayTeam.name', 'event.awayTeam.slug','event.awayTeam.shortName','event.awayTeam.nameCode', 'event.awayTeam.id', 'event.homeScore.current','event.homeScore.period1',
                'event.homeScore.period2','event.awayScore.current','event.awayScore.period1','event.awayScore.period2','event.id','event.slug'
                ]

        df_players_all = df_players_all[[c for c in expected_cols if c in df_players_all.columns]]

        return df_players_all
    
    def extract_standings_total_home_away(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int],type: str = "total") -> pd.DataFrame:
        """
        Extract standings (total, home, or away) for a given league season
        from SofaScore API.

        This function retrieves standings data and returns a structured
        DataFrame with team performance metrics.

        Args:
            id_league_selected (str | int):
                SofaScore league identifier.

            id_season_selected (str | int):
                SofaScore season identifier.

            type (str, optional):
                Type of standings to retrieve. Options:
                    - "total"
                    - "home"
                    - "away"
                Default is "total".

        Returns:
            pd.DataFrame:
                DataFrame containing standings data with columns such as:
                    - position
                    - team.name
                    - matches, wins, draws, losses
                    - goals scored/conceded
                    - points
                    - promotion.text (if available)
                    - image_url

        Raises:
            KeyError:
                If 'standings' or 'rows' is missing in API response.

            ValueError:
                If standings data is empty or invalid.

            Exception:
                Propagates errors from API request function.
        """

        # -----------------------------
        # Validate type input
        # -----------------------------
        valid_types = {"total", "home", "away"}
        if type not in valid_types:
            raise ValueError(f"type must be one of {valid_types}")

        # -----------------------------
        # Build API endpoint
        # -----------------------------
        api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/standings/{type}"

        # -----------------------------
        # Fetch data
        # -----------------------------
        json_data = sofascore_requests(api_url)

        if not json_data or "standings" not in json_data or not json_data["standings"]:
            raise KeyError("Missing 'standings' data in API response")

        try:
            rows = json_data["standings"][0]["rows"]
        except (KeyError, IndexError, TypeError):
            raise KeyError("Invalid structure inside 'standings'")
        if not rows:
            raise ValueError("No standings data found")

        # -----------------------------
        # Normalize data
        # -----------------------------
        df = pd.json_normalize(rows)

        if df.empty:
            raise ValueError("Empty DataFrame after normalization")

        # -----------------------------
        # Safe column selection (CRITICAL)
        # -----------------------------
        expected_columns = ["position","team.name","team.slug","team.shortName","team.nameCode","team.id","matches","wins",
                            "losses","draws","scoresFor","scoresAgainst","scoreDiffFormatted","points","promotion.text",]

        df = df[[col for col in expected_columns if col in df.columns]]

        # -----------------------------
        # Add derived fields safely
        # -----------------------------
        if "team.id" in df.columns:
            df["image_url"] =BASE_URL_TEAM+ df["team.id"].astype(str)+ "/image/small"

        return df
    
    # def extract_teams_performance(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int],df_teams_league: pd.DataFrame) -> pd.DataFrame:
    #     """
    #     Extract performance graph data for all teams in a league season.

    #     This function iterates over each team and retrieves time-series
    #     performance data (graphData) from SofaScore API, flattening nested
    #     event structures into a unified DataFrame.

    #     Args:
    #         id_league_selected (str | int):
    #             SofaScore league ID.

    #         id_season_selected (str | int):
    #             SofaScore season ID.

    #         df_teams_league (pd.DataFrame):
    #             DataFrame containing teams. Must include:
    #                 - id
    #                 - name

    #     Returns:
    #         pd.DataFrame:
    #             Combined DataFrame with performance data for all teams.
    #             Returns empty DataFrame if no data is available.

    #     Raises:
    #         ValueError:
    #             If input DataFrame is empty.

    #         KeyError:
    #             If required columns are missing.

    #         WebDriverException:
    #             If Selenium fails.
    #     """

    #     # -----------------------------
    #     # Validate input
    #     # -----------------------------
    #     if df_teams_league is None or df_teams_league.empty:
    #         raise ValueError("df_teams_league is empty")

    #     required_cols = {"id", "name"}
    #     missing = required_cols - set(df_teams_league.columns)

    #     if missing:
    #         raise KeyError(f"Missing required columns: {missing}")

    #     BASE_URL = "https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/team/{team_id}/team-performance-graph-data"
        

    #     driver = None
    #     all_teams_data = []

    #     try:
    #         # -----------------------------
    #         # Chrome setup
    #         # -----------------------------
    #         options = webdriver.ChromeOptions()
    #         options.add_argument("--headless=new")
    #         options.add_argument("--disable-blink-features=AutomationControlled")

    #         driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)

    #         # Initialize session
    #         driver.get(BASE_URL)

    #         WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    #         # -----------------------------
    #         # Loop teams
    #         # -----------------------------
    #         pbar = tqdm(df_teams_league.iterrows(), total=len(df_teams_league))

    #         for _, row in pbar:

    #             team_id = row["id"]
    #             team_name = row["name"]

    #             pbar.set_description(f"{team_name}")

    #             url = BASE_URL.format(id_league_selected=id_league_selected,id_season_selected=id_season_selected, team_id=team_id)

    #             try:
    #                 driver.get(url)

    #                 body = WebDriverWait(driver, 5).until( EC.presence_of_element_located((By.TAG_NAME, "body")) )

    #                 json_data = json.loads(body.text)

    #                 # -------------------------
    #                 # Validate graphData
    #                 # -------------------------
    #                 graph_data = json_data.get("graphData")

    #                 if not graph_data:
    #                     continue

    #                 df = pd.json_normalize(graph_data)

    #                 if df.empty or "events" not in df.columns:
    #                     continue
    #                 df = df[df["events"].apply(lambda x: isinstance(x, list))]
    #                 # -------------------------
    #                 # Explode events safely
    #                 # -------------------------
    #                 df = df.explode("events")
    #                 # convertir None/NaN en dict vacío
    #                 df["events"] = df["events"].apply( lambda x: x if isinstance(x, dict) else {})

    #                 events_df = pd.json_normalize(df["events"])

    #                 # -------------------------
    #                 # Merge base + events
    #                 # -------------------------
    #                 final_df = pd.concat([df.drop(columns=["events"], errors="ignore").reset_index(drop=True),events_df.reset_index(drop=True)],axis=1)

    #                 # Add metadata
    #                 final_df["team_id"] = team_id
    #                 final_df["team_name"] = team_name

    #                 all_teams_data.append(final_df)

    #             except (TimeoutException, json.JSONDecodeError) as e:
    #                 logging.warning(f"Skipping {team_name} due to timeout/parse error: {e}")
    #                 continue

    #             except Exception as e:
    #                 logging.error(f"Unexpected error with {team_name}: {e}")
    #                 continue

    #     except WebDriverException as e:
    #         logging.error(f"WebDriver failed: {e}")
    #         raise

    #     finally:
    #         if driver:
    #             driver.quit()

    #     # -----------------------------
    #     # Combine all teams
    #     # -----------------------------
    #     if not all_teams_data:
    #         return pd.DataFrame()

    #     final_df_all = pd.concat(all_teams_data, ignore_index=True)
    #     columns_to_drop = ["customId","finalResultOnly", "tournament.category.sport.name",	"tournament.category.sport.slug","tournament.category.flag",
    #                    "tournament.category.sport.id",	"tournament.category.priority","tournament.category.id", "tournament.category.sport.name",
    #                     "tournament.category.sport.slug","tournament.category.sport.id",	"tournament.category.priority",	"tournament.category.id", 
    #                     "tournament.category.alpha2","tournament.category.fieldTranslations.nameTranslation.ar",	
    #                     "tournament.category.fieldTranslations.nameTranslation.hi","tournament.category.fieldTranslations.nameTranslation.bn"	,
    #                     "tournament.category.fieldTranslations.nameTranslation.ru"	, "tournament.uniqueTournament.name"	,"tournament.uniqueTournament.slug"	,
    #                     "tournament.uniqueTournament.primaryColorHex"	,"tournament.uniqueTournament.secondaryColorHex"	,"tournament.uniqueTournament.category.name",
    #                     "tournament.uniqueTournament.category.slug","tournament.uniqueTournament.category.sport.name"	,"tournament.uniqueTournament.category.sport.slug"	,
    #                     "tournament.uniqueTournament.category.sport.id","tournament.uniqueTournament.category.priority"	,"tournament.uniqueTournament.category.id",
    #                     "tournament.uniqueTournament.category.flag"	, "tournament.uniqueTournament.category.alpha2"	,
    #                     "tournament.uniqueTournament.category.fieldTranslations.nameTranslation.ar"	,"tournament.uniqueTournament.category.fieldTranslations.nameTranslation.hi",
    #                     "tournament.uniqueTournament.category.fieldTranslations.nameTranslation.bn",
    #                 	"tournament.uniqueTournament.category.fieldTranslations.nameTranslation.ru"	,"tournament.uniqueTournament.userCount"	,"tournament.uniqueTournament.id",
    #                 	"tournament.uniqueTournament.displayInverseHomeAwayTeams",	"tournament.uniqueTournament.fieldTranslations.nameTranslation.ar",
    #                 	"tournament.uniqueTournament.fieldTranslations.nameTranslation.hi",	"tournament.uniqueTournament.fieldTranslations.nameTranslation.bn",
    #                 	"tournament.priority",	"tournament.isLive",	"tournament.id",	"tournament.fieldTranslations.nameTranslation.hi",
    #                 	"tournament.fieldTranslations.nameTranslation.ar",	"tournament.fieldTranslations.nameTranslation.bn",	"status.code",'homeTeam.gender',
    #                     'homeTeam.sport.name'	,'homeTeam.sport.slug',	'homeTeam.sport.id'	,'homeTeam.userCount','homeTeam.disabled','homeTeam.national'	,'homeTeam.type',
    #                     'homeTeam.teamColors.primary',	'homeTeam.teamColors.secondary',	'homeTeam.teamColors.text',	'homeTeam.fieldTranslations.nameTranslation.ar',
    #                     'homeTeam.fieldTranslations.nameTranslation.bn',	'homeTeam.fieldTranslations.nameTranslation.hi'	,'homeTeam.fieldTranslations.nameTranslation.ru',
    #                     'awayTeam.gender','awayTeam.sport.name'	,'awayTeam.sport.slug',	'awayTeam.sport.id'	,'awayTeam.userCount','awayTeam.disabled','awayTeam.national'	,
    #                     'awayTeam.type','awayTeam.teamColors.primary',	'awayTeam.teamColors.secondary',	'awayTeam.teamColors.text',	
    #                     'awayTeam.fieldTranslations.nameTranslation.ar','awayTeam.fieldTranslations.nameTranslation.bn',	'awayTeam.fieldTranslations.nameTranslation.hi'	,
    #                     'awayTeam.fieldTranslations.nameTranslation.ru','homeScore.display', 'homeScore.normaltime','awayScore.display', 'awayScore.normaltime',
    #                     'homeTeam.fieldTranslations.shortNameTranslation.ar','homeTeam.fieldTranslations.shortNameTranslation.bn',	
    #                     'homeTeam.fieldTranslations.shortNameTranslation.hi','awayTeam.fieldTranslations.shortNameTranslation.ar',	
    #                     'awayTeam.fieldTranslations.shortNameTranslation.bn',	'awayTeam.fieldTranslations.shortNameTranslation.hi','eventState.statusIndicator'  	] 
    #     df = final_df_all.drop(columns=[col for col in columns_to_drop if col in final_df_all.columns],errors="ignore")
    #     return df, valid, invalid

    
    # def extract_top_players_stat(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int],stat_type: str = "rating") -> pd.DataFrame:
    #     """
    #     Extract top players statistics for a given league and season
    #     from SofaScore API.

    #     This function retrieves all available top-player statistics,
    #     validates the requested stat_type, and returns a cleaned DataFrame
    #     with only relevant columns.

    #     Args:
    #         id_league_selected (str | int):
    #             SofaScore league ID.

    #         id_season_selected (str | int):
    #             SofaScore season ID.

    #         stat_type (str, optional):
    #             Statistic type to extract (e.g. "rating", "goals", "assists").
    #             Default is "rating".

    #     Returns:
    #         pd.DataFrame:
    #             DataFrame containing player statistics.

    #     Raises:
    #         KeyError:
    #             If 'topPlayers' is missing in API response.

    #         ValueError:
    #             If stat_type is not available.

    #         Exception:
    #             Propagates API request errors.
    #     """

    #     # -----------------------------
    #     # Build API endpoint
    #     # -----------------------------
    #     api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/top-players/overall"
        
    #     # -----------------------------
    #     # Fetch data
    #     # -----------------------------
    #     json_data = sofascore_requests(api_url)

    #     if not json_data or "topPlayers" not in json_data:
    #         raise KeyError("Missing 'topPlayers' in API response")

    #     top_players = json_data["topPlayers"]

    #     # -----------------------------
    #     # Validate stat_type
    #     # -----------------------------
    #     available_stats = list(top_players.keys())

    #     if stat_type not in available_stats:
    #         raise ValueError(f"Invalid stat_type '{stat_type}'. Available: {available_stats}")

    #     # -----------------------------
    #     # Normalize data
    #     # -----------------------------
    #     stats = pd.json_normalize(top_players[stat_type])

    #     if stats.empty:
    #         return pd.DataFrame()

    
    #     stats= stats.drop(columns=['playedEnough','statistics.id', 'statistics.type', 'statistics.statisticsType.sportSlug',	'statistics.statisticsType.statisticsType','player.fieldTranslations.nameTranslation.ar',	
    #                                 'player.userCount',	'player.gender','player.fieldTranslations.nameTranslation.bn',	'player.fieldTranslations.nameTranslation.hi',
    #                                 'player.fieldTranslations.shortNameTranslation.ar',	'player.fieldTranslations.shortNameTranslation.bn',	'player.fieldTranslations.shortNameTranslation.hi',
    #                                 'team.gender',	'team.sport.name',	'team.sport.slug',	'team.sport.id',	'team.userCount',	'team.national',	'team.type',
    #                                 'team.teamColors.primary',	'team.teamColors.secondary',	'team.teamColors.text',	'team.fieldTranslations.nameTranslation.ar',	
    #                                 'team.fieldTranslations.nameTranslation.bn','team.fieldTranslations.nameTranslation.hi',	'team.fieldTranslations.nameTranslation.ru'	,
    #                                 'team.fieldTranslations.shortNameTranslation.ar',	'team.parentTeam.name',	'team.parentTeam.slug',	'team.parentTeam.shortName',	'team.parentTeam.gender',
    #                                 'team.parentTeam.sport.name',	'team.parentTeam.sport.slug',	'team.parentTeam.sport.id',	'team.parentTeam.userCount',	'team.parentTeam.nameCode',
    #                                 'team.parentTeam.disabled',	'team.parentTeam.national',	'team.parentTeam.type',	'team.parentTeam.id',	'team.parentTeam.teamColors.primary',	
    #                                 'team.parentTeam.teamColors.secondary',	'team.parentTeam.teamColors.text',	'team.parentTeam.fieldTranslations.nameTranslation.ar',
    #                                 'team.fieldTranslations.shortNameTranslation.bn'	,'team.fieldTranslations.shortNameTranslation.hi',
    #                                 'team.parentTeam.fieldTranslations.nameTranslation.bn',	'team.parentTeam.fieldTranslations.nameTranslation.hi',	'team.parentTeam.fieldTranslations.nameTranslation.ru'], errors= 'ignore')

    #     return stats
    
    def extract_top_team_stat(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int],stat_type: str = "rating") -> pd.DataFrame:
        """
        Extract top team statistics for a given league and season
        from SofaScore API.

        This function retrieves available team statistics, validates
        the requested stat_type, and returns a cleaned DataFrame with
        relevant team performance metrics.

        Args:
            id_league_selected (str | int):
                SofaScore league ID.

            id_season_selected (str | int):
                SofaScore season ID.

            stat_type (str, optional):
                Statistic type to extract (e.g. "rating", "goals", "wins").
                Default is "rating".

        Returns:
            pd.DataFrame:
                DataFrame containing team statistics.

        Raises:
            KeyError:
                If 'topTeams' is missing in API response.

            ValueError:
                If stat_type is not available.

            Exception:
                Propagates API request errors.
        """

        # -----------------------------
        # Build API endpoint
        # -----------------------------
        api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/top-teams/overall"

        # -----------------------------
        # Fetch data
        # -----------------------------
        json_data = sofascore_requests(api_url)

        if not json_data or "topTeams" not in json_data:
            raise KeyError("Missing 'topTeams' in API response")

        top_teams = json_data["topTeams"]

        # -----------------------------
        # Validate stat_type
        # -----------------------------
        available_stats = list(top_teams.keys())

        if stat_type not in available_stats:
            raise ValueError( f"Invalid stat_type '{stat_type}'. Available: {available_stats}")

        # -----------------------------
        # Normalize data
        # -----------------------------
        stats = pd.json_normalize(top_teams[stat_type])

        if stats.empty:
            return pd.DataFrame()


        stats = stats.drop(columns=['team.gender',	'team.sport.name'	,'team.sport.slug',	'team.sport.id'	,'team.userCount',	'team.national',	'team.type',	'team.country.alpha2',
                                                                    'team.country.alpha3', 'team.teamColors.primary',	'team.teamColors.secondary',	'team.teamColors.text' ,'team.fieldTranslations.nameTranslation.ar',
                                                                    'team.fieldTranslations.nameTranslation.ru', 'team.fieldTranslations.shortNameTranslation.ar',	'team.parentTeam.name'	,'team.parentTeam.slug'	,
                                                                    'team.parentTeam.gender',	'team.parentTeam.sport.name',	'team.parentTeam.sport.slug',	'team.parentTeam.sport.id',	'team.parentTeam.userCount'	,
                                                                    'team.parentTeam.national',	'team.parentTeam.type',	'team.parentTeam.country.alpha2',	'team.parentTeam.country.alpha3',	'team.parentTeam.country.name',
                                                                    'team.parentTeam.country.slug',	'team.parentTeam.id',	'team.parentTeam.teamColors.primary',	'team.parentTeam.teamColors.secondary',
                                                                    'team.parentTeam.teamColors.text',	'team.parentTeam.fieldTranslations.nameTranslation.ar',	'team.parentTeam.fieldTranslations.nameTranslation.bn',
                                                                    'team.fieldTranslations.shortNameTranslation.bn'	,'team.fieldTranslations.shortNameTranslation.hi',
                                                                    'team.parentTeam.fieldTranslations.nameTranslation.hi',	'team.parentTeam.fieldTranslations.nameTranslation.ru',	'team.fieldTranslations.nameTranslation.bn',
                                                                    'team.fieldTranslations.nameTranslation.hi', 'statistics.awardedMatches', 'statistics.id'], errors= 'ignore')

        return stats
    
    def extract_player_of_season(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int],stat_type: str = "rating") -> pd.DataFrame:
        """
        Extract 'Player of the Season' race data from SofaScore API.

        This function retrieves the ranking of players competing for
        player of the season based on a selected statistic.

        Args:
            id_league_selected (str | int):
                SofaScore league ID.

            id_season_selected (str | int):
                SofaScore season ID.

            stat_type (str, optional):
                Statistic type (e.g. "rating", "goals", "assists").
                Default is "rating".

        Returns:
            pd.DataFrame:
                DataFrame containing player rankings and statistics.

        Raises:
            KeyError:
                If 'topPlayers' is missing in API response.

            ValueError:
                If stat_type is not available.

            Exception:
                Propagates API request errors.
        """

        # -----------------------------
        # Build API endpoint
        # -----------------------------
        api_url = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/player-of-the-season-race"

        # -----------------------------
        # Fetch data
        # -----------------------------
        json_data = sofascore_requests(api_url)

        if not json_data or "topPlayers" not in json_data:
            raise KeyError("Missing 'topPlayers' in API response")

        top_players = json_data["topPlayers"]

        # -----------------------------
        # Validate stat_type
        # -----------------------------
        available_stats = list(top_players.keys())

        if stat_type not in available_stats:
            raise ValueError( f"Invalid stat_type '{stat_type}'. Available: {available_stats}")

        # -----------------------------
        # Normalize data
        # -----------------------------
        df = pd.json_normalize(top_players[stat_type])

        if df.empty:
            return pd.DataFrame()

        df= df.drop(columns=['playedEnough', 'statistics.id', 'statistics.type', 'statistics.statisticsType.sportSlug',	'statistics.statisticsType.statisticsType',
                                        'player.userCount',	'player.gender','player.fieldTranslations.nameTranslation.ar',	'player.fieldTranslations.nameTranslation.bn',	'player.fieldTranslations.nameTranslation.hi',
                                        'player.fieldTranslations.shortNameTranslation.ar','player.fieldTranslations.shortNameTranslation.bn',	'player.fieldTranslations.shortNameTranslation.hi',
                                        'team.gender',	'team.sport.name',	'team.sport.slug',	'team.sport.id',	'team.userCount',	'team.national',	'team.type',
                                        'team.teamColors.primary',	'team.teamColors.secondary',	'team.teamColors.text',	'team.fieldTranslations.nameTranslation.ar',
                                        'team.fieldTranslations.nameTranslation.bn','team.fieldTranslations.nameTranslation.hi',	'team.fieldTranslations.nameTranslation.ru'])                     
                                            
        return df
    
    def extract_all_matches(self, id_league_selected: Union[str, int],id_season_selected: Union[str, int]) -> pd.DataFrame:
        """
        Extract all matches for a given league and season from SofaScore API.

        This function:
            1. Retrieves all rounds.
            2. Iterates through each round.
            3. Fetches match events.
            4. Flattens nested structures into a clean DataFrame.

        Args:
            id_league_selected (str | int):
                SofaScore league ID.

            id_season_selected (str | int):
                SofaScore season ID.

        Returns:
            pd.DataFrame:
                DataFrame containing all matches with structured fields.
                Returns empty DataFrame if no matches are found.

        Raises:
            WebDriverException:
                If Selenium fails to initialize.
        """

        driver = None
        all_events = []

        try:
            # -----------------------------
            # Chrome setup
            # -----------------------------
            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")

            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)

            # Initialize session
            driver.get(BASE_URL)

            # -----------------------------
            # Get rounds
            # -----------------------------
            api_rounds =f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/rounds"
            driver.get(api_rounds)

            body = WebDriverWait(driver, 5).until( EC.presence_of_element_located((By.TAG_NAME, "body")))
            json_data = json.loads(body.text)
            rounds = json_data.get("rounds", [])

            if not rounds:
                logging.warning("No rounds found")
                return pd.DataFrame()

            df_rounds = pd.DataFrame(rounds)

            if "round" not in df_rounds.columns:
                return pd.DataFrame()

            # -----------------------------
            # Loop rounds
            # -----------------------------
            pbar = tqdm(df_rounds["round"], total=len(df_rounds))

            for r in pbar:
                pbar.set_description(f"Round {r}")

                api_events = f"https://www.sofascore.com/api/v1/unique-tournament/{id_league_selected}/season/{id_season_selected}/events/round/{r}"
                

                try:
                    driver.get(api_events)

                    body = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                    json_data = json.loads(body.text)

                    events = json_data.get("events", [])

                    if not events:
                        continue

                    matches= pd.DataFrame(json_data['events'])

                    if matches.empty:
                        continue

                    # -------------------------
                    # Add match date
                    # -------------------------
                    if "startTimestamp" in matches.columns:
                        dt = pd.to_datetime(matches['startTimestamp'], unit='s', utc=True).dt.tz_convert('Europe/Madrid')
                        matches['match_date'] = dt.dt.date
                        matches['match_time'] = dt.dt.time

                    cols_initial= ['tournament', 'season', 'roundInfo', 'status'	,'homeTeam'	,'awayTeam',	'homeScore'	,'awayScore', 'id',	 'slug',	'winnerCode',	'match_date']
                    matches = matches.reindex(columns=cols_initial)


                    matches = pd.concat([
                                    matches.drop(['tournament', 'season', 'roundInfo', 'status', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore'], axis=1),
                                    matches['tournament'].apply(pd.Series).add_prefix('tournament_'),
                                    matches['season'].apply(pd.Series).add_prefix('season_'),
                                    matches['roundInfo'].apply(pd.Series).add_prefix('roundInfo_'),
                                    matches['homeTeam'].apply(pd.Series).add_prefix('homeTeam_'),
                                    matches['awayTeam'].apply(pd.Series).add_prefix('awayTeam_'),
                                    matches['homeScore'].apply(pd.Series).add_prefix('homeScore_'),
                                    matches['awayScore'].apply(pd.Series).add_prefix('awayScore_'),
                                ], axis=1)

                    # -------------------------
                    # Select final columns safely
                    # -------------------------
                    final_cols = ['id', 'slug', 'winnerCode', 'match_date', 'match_time',	'tournament_name',	'tournament_slug', 'roundInfo_round',	'homeTeam_name'	,'homeTeam_slug',	'homeTeam_shortName', 'homeTeam_nameCode' ,
                                        'homeTeam_id', 'awayTeam_name', 'awayTeam_slug',	'awayTeam_shortName',  'awayTeam_nameCode',	'awayTeam_id', 'homeScore_current' , 'homeScore_period1',	'homeScore_period2' ,
                                        'awayScore_current' ,'awayScore_period1','awayScore_period2']

                    matches = matches[[c for c in final_cols if c in matches.columns]]

                    all_events.append(matches)

                except (TimeoutException, json.JSONDecodeError) as e:
                    logging.warning(f"Skipping round {r}: {e}")
                    continue

                except Exception as e:
                    logging.error(f"Unexpected error in round {r}: {e}")
                    continue

        except WebDriverException as e:
            logging.error(f"WebDriver failed: {e}")
            raise

        finally:
            if driver:
                driver.quit()

        # -----------------------------
        # Combine all matches
        # -----------------------------
        if not all_events:
            return pd.DataFrame()

        return pd.concat(all_events, ignore_index=True)
