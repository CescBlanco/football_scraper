import requests
from bs4 import BeautifulSoup
from io import StringIO
import pandas as pd
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)


from providers.espn.utils import _create_driver, clean_text, parse_match_cell, parse_squad

class ESPNTeamScraper:
    def __init__(self, session: requests.Session, league_service):
        self.session = session
        self.league_service = league_service
        self._team_squad_cache = {}
    
    def extract_fixtures(self, team_name: str, league_name: str) -> pd.DataFrame:
        """
        Extract upcoming fixtures for a specific team from ESPN Soccer.

        Parameters
        ----------
        team_name : str
            Team name as listed in the league teams dataset.

        league_name : str
            League name used to retrieve the team information.

        Returns
        -------
        pd.DataFrame
            DataFrame containing fixture information:
                - section (str)
                - date (str)
                - match_url (str)
                - team_home (str)
                - team_home_url (str)
                - team_home_photo (Optional[str])
                - team_away (str)
                - team_away_url (str)
                - team_away_photo (Optional[str])
                - time (str)
                - competition (str)
                - tv (Optional[str])

        Raises
        ------
        TypeError
            If `team_name` or `league_name` are not strings.

        ValueError
            If the league or team cannot be found.

        TimeoutException
            If fixtures page fails to load.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Uses dynamic scrolling to load additional fixtures.
        - Extracts monthly grouped fixtures tables.
        """

        if not isinstance(team_name, str):
            raise TypeError("team_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        df = self.league_service.get_teams(league_name)

        team_df = df[df["team"] == team_name]
        if team_df.empty:
            raise ValueError( f"Team '{team_name}' not found in league '{league_name}'")

        team_id = team_df["team_id"].iloc[0]

        url =   f"https://www.espn.com/soccer/team/fixtures/_/id/{team_id}"

        driver= _create_driver()

        wait = WebDriverWait(driver, 10)

        data = []

        try:
            driver.get(url)

            time.sleep(5)

            for _ in range(5):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            tables = wait.until(EC.presence_of_all_elements_located( (By.CLASS_NAME, "ResponsiveTable")))

            for table in tables:

                try:
                    section = table.find_element( By.CLASS_NAME, "Table__Title").text

                    rows = table.find_elements( By.CSS_SELECTOR, "tbody.Table__TBODY tr")

                    for row in rows:

                        try:
                            date = row.find_element( By.CSS_SELECTOR, '[data-testid="date"]').text
                            match_link = row.find_element( By.CSS_SELECTOR, '[data-testid="score"] a[href*="gameId"]')
                            match_url = match_link.get_attribute("href")
                            team_home = row.find_element( By.CSS_SELECTOR, '[data-testid="localTeam"]').text
                            team_away = row.find_element( By.CSS_SELECTOR, '[data-testid="awayTeam"]').text
                            home_elem = row.find_element( By.CSS_SELECTOR, '[data-testid="localTeam"] a')
                            away_elem = row.find_element( By.CSS_SELECTOR, '[data-testid="awayTeam"] a')

                            team_home_url = home_elem.get_attribute("href")
                            team_away_url = away_elem.get_attribute("href")

                            imgs = row.find_elements(By.CSS_SELECTOR,'[data-testid="score"] img')
                            team_home_photo = imgs[0].get_attribute("src")if len(imgs) > 0 else None
                            team_away_photo = imgs[1].get_attribute("src")if len(imgs) > 1 else None
                            

                            tds = row.find_elements(By.CSS_SELECTOR, "td")

                            time_match = tds[4].text
                            competition = tds[5].text

                            tv_elem = row.find_elements(By.CSS_SELECTOR,'[data-testid="tv"]')
                            tv = tv_elem[0].text if tv_elem else None

                            data.append({
                                "section": section,
                                "date": date,
                                "match_url": match_url,
                                "team_home": team_home,
                                "team_home_url": team_home_url,
                                "team_home_photo": team_home_photo,
                                "team_away": team_away,
                                "team_away_url": team_away_url,
                                "team_away_photo": team_away_photo,
                                "time": time_match,
                                "competition": competition,
                                "tv": tv
                            })

                        except NoSuchElementException:
                            continue

                except NoSuchElementException:
                    continue

        except TimeoutException:
            raise TimeoutException("Fixtures page load timeout")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver error: {str(e)}")

        finally:
            driver.quit()

        return pd.DataFrame(data)
    
    def extract_results(self, team_name: str,league_name: str,season: str = "2025") -> pd.DataFrame:
        """
        Extract match results for a specific team from ESPN Soccer.

        Parameters
        ----------
        team_name : str
            Team name as listed in the league teams dataset.

        league_name : str
            League name used to retrieve the team information.

        season : str, optional
            Season year, by default "2025".

        Returns
        -------
        pd.DataFrame
            DataFrame containing historical match results:
                - section (str)
                - date (str)
                - team_home (str)
                - team_away (str)
                - team_home_url (str)
                - team_away_url (str)
                - team_home_photo (Optional[str])
                - team_away_photo (Optional[str])
                - score (str)
                - result (Optional[str])
                - competition (str)
                - match_url (str)
                - game_note (Optional[str])

        Raises
        ------
        TypeError
            If parameters are invalid types.

        ValueError
            If the team or league cannot be found.

        TimeoutException
            If results page fails to load.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Uses infinite scrolling to load all historical matches.
        - Extracts grouped monthly result tables.
        """

        if not isinstance(team_name, str):
            raise TypeError("team_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        df = self.league_service.get_teams(league_name)

        team_df = df[df["team"] == team_name]

        if team_df.empty:
            raise ValueError( f"Team '{team_name}' not found in league '{league_name}'")

        team_id = team_df["team_id"].iloc[0]

        url = f"https://www.espn.com/soccer/team/results/_/id/{team_id}/season/{season}"

        driver= _create_driver()

        wait = WebDriverWait(driver, 10)

        data = []

        try:
            driver.get(url)

            time.sleep(5)

            last_height = driver.execute_script("return document.body.scrollHeight")

            while True:

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);" )

                time.sleep(2)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break

                last_height = new_height

            tables = wait.until(EC.presence_of_all_elements_located( (By.CLASS_NAME, "ResponsiveTable")))

            for table in tables:

                try:
                    section = table.find_element(By.CLASS_NAME,"Table__Title").text

                    rows = table.find_elements(By.CSS_SELECTOR,"tbody.Table__TBODY tr")

                    for row in rows:

                        try:
                            date = row.find_element( By.CSS_SELECTOR, '[data-testid="date"]').text

                            local_elem = row.find_element( By.CSS_SELECTOR, '[data-testid="localTeam"] a')

                            away_elem = row.find_element( By.CSS_SELECTOR, '[data-testid="awayTeam"] a')
                            team_home = local_elem.text
                            team_away = away_elem.text

                            team_home_url = local_elem.get_attribute("href")
                            team_away_url = away_elem.get_attribute("href")

                            tds = row.find_elements(By.CSS_SELECTOR, "td")

                            competition = tds[-1].text

                            match_link = row.find_element(By.CSS_SELECTOR,'a[href*="gameId"]')

                            match_url = match_link.get_attribute("href")

                            imgs = row.find_elements(By.CSS_SELECTOR,'[data-testid="score"] img')
                            team_home_photo = imgs[0].get_attribute("src")if len(imgs) > 0 else None
                            team_away_photo = imgs[1].get_attribute("src")if len(imgs) > 1 else None
                        

                            score = row.find_element(By.CSS_SELECTOR,'[data-testid="score"]').text.strip()

                            try:
                                result = row.find_element(By.CSS_SELECTOR,'[data-testid="result"]').text

                            except NoSuchElementException:
                                result = None

                            try:
                                game_note = row.find_element(By.CSS_SELECTOR,".gameNote").text

                            except NoSuchElementException:
                                game_note = None

                            data.append({
                                "section": section,
                                "date": date,
                                "team_home": team_home,
                                "team_away": team_away,
                                "team_home_url": team_home_url,
                                "team_away_url": team_away_url,
                                "team_home_photo": team_home_photo,
                                "team_away_photo": team_away_photo,
                                "score": score,
                                "result": result,
                                "competition": competition,
                                "match_url": match_url,
                                "game_note": game_note
                            })

                        except NoSuchElementException:
                            continue

                except NoSuchElementException:
                    continue

        except TimeoutException:
            raise TimeoutException("Results page load timeout")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver error: {str(e)}")

        finally:
            driver.quit()

        return pd.DataFrame(data)
    
    def extract_transfers(self, team_name: str, league_name: str,season: str = "2025") -> pd.DataFrame:
        """
        Extract transfer activity for a specific team from ESPN Soccer.

        Parameters
        ----------
        team_name : str
            Team name as listed in the league teams dataset.

        league_name : str
            League name used to retrieve the team information.

        season : str, optional
            Season year, by default "2025".

        Returns
        -------
        pd.DataFrame
            DataFrame containing transfer information:
                - date (str)
                - player (str)
                - player_url (str)
                - team_from_or_to (str)
                - team_from_or_to_url (str)
                - team_from_or_to_photo (Optional[str])
                - fee (str)
                - type (Optional[str])

        Raises
        ------
        TypeError
            If parameters are not strings.

        ValueError
            If the team or league cannot be found.

        TimeoutException
            If the transfers page fails to load.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Uses dynamic scrolling to load all transfer records.
        - Supports both incoming and outgoing transfers.
        - Transfer type is normalized as:
            - "in"
            - "out"
        """

        if not isinstance(team_name, str):
            raise TypeError("team_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        df_teams = self.league_service.get_teams(league_name)

        team_df = df_teams[df_teams["team"] == team_name]

        if team_df.empty:
            raise ValueError(f"Team '{team_name}' not found in league '{league_name}'")

        team_id = team_df["team_id"].iloc[0]

        url = f"https://www.espn.com/soccer/team/transfers/_/id/{team_id}/year/{season}"

        driver= _create_driver()
        wait = WebDriverWait(driver, 10)

        data = []

        try:
            driver.get(url)

            time.sleep(5)

            # Dynamic scroll
            last_height = driver.execute_script( "return document.body.scrollHeight")

            while True:

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                time.sleep(2)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break

                last_height = new_height

            transfer_tables = wait.until( EC.presence_of_all_elements_located((By.CSS_SELECTOR, '[data-testid="singleTransferTable"]') ))

            for table in transfer_tables:

                try:
                    title = table.find_element(By.TAG_NAME,"h3").text.strip()

                    if "In" in title:transfer_type = "in"

                    elif "Out" in title:transfer_type = "out"

                    else:transfer_type = None

                    rows = table.find_elements(By.CSS_SELECTOR,"tbody.Table__TBODY tr")

                    for row in rows:

                        try:
                            tds = row.find_elements( By.CSS_SELECTOR, "td")

                            date = tds[0].text.strip()

                            # Player
                            player_elem = tds[1].find_element( By.TAG_NAME, "a")
                            player = player_elem.text
                            player_url = player_elem.get_attribute( "href")

                            # Club
                            club_elem = tds[2].find_element( By.TAG_NAME, "a")
                            team_from_or_to = club_elem.text
                            team_from_or_to_url = club_elem.get_attribute("href")
                            

                            # Club logo
                            try:
                                club_img = tds[2].find_element(By.TAG_NAME,"img")
                                team_from_or_to_photo = club_img.get_attribute("src")
                                

                            except NoSuchElementException:
                                team_from_or_to_photo = None

                            # Fee
                            fee = tds[3].text.strip()

                            data.append({
                                "date": date,
                                "player": player,
                                "player_url": player_url,
                                "team_from_or_to": team_from_or_to,
                                "team_from_or_to_url": team_from_or_to_url,
                                "team_from_or_to_photo": team_from_or_to_photo,
                                "fee": fee,
                                "type": transfer_type
                            })

                        except ( NoSuchElementException, IndexError ):
                            continue

                except NoSuchElementException:
                    continue

        except TimeoutException:
            raise TimeoutException( "Transfers page load timeout")

        except WebDriverException as e:
            raise WebDriverException( f"WebDriver error: {str(e)}")

        finally:
            driver.quit()

        return pd.DataFrame(data)


    def extract_avaiable_competitions(self, name_league: str, team_name: str) -> tuple[str, pd.DataFrame]:
        """
        Extract available competitions for a specific team from ESPN.

        Parameters
        ----------
        name_league : str
            League name used to retrieve the team information.

        team_name : str
            Team name to search within the league.

        Returns
        -------
        tuple[str, pd.DataFrame]
            Tuple containing:
                - Team ID (str)
                - DataFrame with available competitions:
                    - name (str)
                    - value (str)

        Raises
        ------
        TypeError
            If input parameters are not strings.

        ValueError
            If the league or team cannot be found.

        requests.RequestException
            If the HTTP request fails.

        Notes
        -----
        - Uses the ESPN team stats page to extract competition options.
        - Only competition dropdown values are parsed.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        if not isinstance(team_name, str):
            raise TypeError("team_name must be a string")

        df_teams = self.league_service.get_teams(name_league)
        if df_teams.empty:
            raise ValueError( f"No teams found for league '{name_league}'" )

        filtered_team = df_teams[df_teams["team"] == team_name]
        if filtered_team.empty:
            raise ValueError( f"Team '{team_name}' not found in league '{name_league}'")

        id_team = filtered_team["team_id"].iloc[0]
        url = f"https://www.espn.com/soccer/team/stats/_/id/{id_team}"

        headers = { "User-Agent": "Mozilla/5.0"}

        try:
            response = requests.get(url,headers=headers, timeout=15)
            response.raise_for_status()

        except requests.RequestException as e:
            raise requests.RequestException(f"Failed to retrieve competitions page: {str(e)}" )

        soup = BeautifulSoup(response.text, "html.parser")

        competitions = []

        select = soup.select_one("div.dropdown__select--competitions select")

        if select:

            for opt in select.select("option[data-url]"):

                competitions.append({
                    "name": opt.text.strip(),
                    "value": opt.get("value")
                })

        df_competitions = pd.DataFrame(competitions)

        return id_team, df_competitions
    
    def extract_stats_by_competition(self,name_league: str,name_team: str,season: str) -> dict[str, dict[str, pd.DataFrame]]:
        """
        Extract team statistics grouped by competition tabs and tables.

        Parameters
        ----------
        name_league : str
            League name.

        name_team : str
            Team name.

        season : str
            Season year.

        Returns
        -------
        dict[str, dict[str, pd.DataFrame]]
            Nested dictionary structure:
                {
                    "Tab Name": {
                        "Table Title": DataFrame
                    }
                }

        Raises
        ------
        TypeError
            If parameters are not strings.

        ValueError
            If the competition or team cannot be found.

        TimeoutException
            If page elements fail to load.

        WebDriverException
            If Selenium fails during execution.

        Notes
        -----
        - Dynamically parses all available statistic tabs.
        - Uses DOM correction for MATCH columns.
        - Cleans text formatting automatically.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        if not isinstance(name_team, str):
            raise TypeError("name_team must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        id_team, df_competitions = (self.extract_avaiable_competitions( name_league, name_team  ))

        competition_df = df_competitions[ df_competitions["name"] == name_league ]
        if competition_df.empty:
            raise ValueError( f"Competition '{name_league}' not available for team '{name_team}'")

        competition_value = competition_df["value"].iloc[0]

        url = f"https://www.espn.com/soccer/team/stats/_/id/{id_team}/league/{competition_value}/season/{season}"

        options = Options()

        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )

        options.add_argument(
            "user-agent=Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(options=options)

        driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """)
        wait = WebDriverWait(driver, 10)

        data = {}

        try:
            driver.get(url)

            # Accept cookies if present
            try:
                accept_cookies = wait.until(EC.element_to_be_clickable(    (By.ID, "onetrust-accept-btn-handler")))
                accept_cookies.click()

                time.sleep(1)

            except TimeoutException:
                pass

            tabs = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR,  "nav.tabs__nav a.tabs__link")))

            for idx in range(len(tabs)):

                tabs = wait.until(
                    EC.presence_of_all_elements_located((  By.CSS_SELECTOR, "nav.tabs__nav a.tabs__link")))

                tab = tabs[idx]
                tab_name = tab.get_attribute("textContent").strip()

                driver.execute_script("arguments[0].scrollIntoView(true);",tab)
                driver.execute_script("arguments[0].click();",tab)

                time.sleep(1.5)

                try:
                    sections = wait.until(EC.presence_of_all_elements_located( (  By.CSS_SELECTOR,  "section.statistics__table"  )))
                except TimeoutException:
                    continue

                tab_tables = {}

                for section in sections:

                    try:
                        table_title = section.find_element(By.CSS_SELECTOR,"div.Table__Title").get_attribute("textContent").strip()

                    except NoSuchElementException:
                        table_title = "Untitled"

                    try:
                        html = section.get_attribute("outerHTML")

                        df = pd.read_html(StringIO(html))[0]

                        # Smart text cleaning
                        for col in df.columns:

                            col_upper = str(col).upper()

                            if col_upper == "MATCH":

                                df[col] = df[col].apply(lambda x:clean_text(x) if isinstance(x, str) else x)

                            else:
                                df[col] = df[col].apply( clean_text )

                        # DOM override for MATCH column
                        try:
                            rows = section.find_elements( By.CSS_SELECTOR, "tbody.Table__TBODY tr" )

                            match_col_idx = None

                            for col_idx, column in enumerate(df.columns):

                                if str(column).upper() == "MATCH":
                                    match_col_idx = col_idx
                                    break

                            if match_col_idx is not None:

                                for row_idx, row in enumerate(rows):

                                    cols = row.find_elements(By.TAG_NAME,"td")

                                    if match_col_idx < len(cols):

                                        df.iat[ row_idx, match_col_idx ] = parse_match_cell( cols[match_col_idx])

                        except Exception:
                            pass

                    except Exception:
                        df = pd.DataFrame()

                    tab_tables[table_title] = df

                data[tab_name] = tab_tables

        except TimeoutException:
            raise TimeoutException( "Timeout while loading team statistics")

        except WebDriverException as e:
            raise WebDriverException( f"WebDriver execution failed: {str(e)}" )

        finally:
            driver.quit()

        return data
    
    def extract_squad_by_competition(self, name_league: str, name_team: str, season: str) -> pd.DataFrame:
        """
        Extract squad statistics for a team in a specific competition.

        Parameters
        ----------
        name_league : str
            League or competition name.
        name_team : str
            Team name.
        season : str
            Season year.
            
        Returns
        -------
        pd.DataFrame
            DataFrame containing squad statistics.

        Raises
        ------
        TypeError
            If parameters are not strings.

        ValueError
            If the competition or team cannot be found.

        TimeoutException
            If squad tables fail to load.

        WebDriverException
            If Selenium fails during execution.

        Notes
        -----
        - Extracts all squad sections dynamically.
        - Includes both goalkeeper and outfield player stats.
        - Uses ESPN squad pages.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        if not isinstance(name_team, str):
            raise TypeError("name_team must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        id_team, df_comp= self.extract_avaiable_competitions(name_league, name_team)

        competition_df = df_comp[df_comp["name"] == name_league]
        if competition_df.empty:
            raise ValueError( f"Competition '{name_league}' not available for team '{name_team}'")

        competition_value = competition_df["value"].iloc[0]

        url_team = f"https://www.espn.com/soccer/team/squad/_/id/{id_team}/league/{competition_value}/season/{season}"
    
        driver= _create_driver()

        wait = WebDriverWait(driver, 10)

        try:
            driver.get(url_team)

            time.sleep(3)

            # Accept cookies if displayed
            try:
                accept_cookies = wait.until(EC.element_to_be_clickable(( By.ID, "onetrust-accept-btn-handler")))
                accept_cookies.click()
                time.sleep(1)

            except TimeoutException:
                pass

            wait.until(
                EC.presence_of_element_located(( By.CSS_SELECTOR,  ".Roster__MixedTable table")))

            squad = parse_squad(driver)

        except TimeoutException:
            raise TimeoutException( "Squad tables failed to load" )

        except WebDriverException as e:
            raise WebDriverException( f"WebDriver execution failed: {str(e)}")
        
        finally:
            driver.quit()

        return pd.DataFrame(squad)
    
    def _get_team_squad_cache(self, team_league: str, name_team: str, season: str) -> pd.DataFrame:
        """
        Return cached league teams data.
        Scrapes ESPN only if cache is empty.
        """

        if team_league not in self._team_squad_cache:

            self._team_squad_cache[team_league] = self.extract_squad_by_competition(team_league, name_team, season)

        return self._team_squad_cache[team_league]
    
    def get_team_squad(self, team_league: str,name_team: str, season: str) -> pd.DataFrame:
     return self._get_team_squad_cache(team_league, name_team, season)
    
