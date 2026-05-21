import requests
import pandas as pd
import re
import time

from typing import Dict
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)

from football_scraper.providers.espn.utils import parse_footer, _create_driver

class ESPNLeagueScraper:
    def __init__(self, session: requests.Session, competition_service):
        self.session = session
        self.competition_service = competition_service
        self._league_teams_cache = {}

    def extract_teams(self, league_name: str) -> pd.DataFrame:
        """
        Extract all teams from a given league using ESPN Soccer.

        Parameters
        ----------
        league_name : str
            Name of the league to scrape (case-insensitive match).

        Returns
        -------
        pd.DataFrame
            DataFrame containing team information:
                - team (str)
                - team_id (Optional[str])
                - team_slug (Optional[str])
                - team_url (str)
                - team_photo (str)
                - team_fixtures_url (Optional[str])
                - team_stats_url (Optional[str])
                - slug_league (str)
                - slug_team_full (str)

        Raises
        ------
        TypeError
            If `league_name` is not a string.

        ValueError
            If the league does not exist or cannot be found.

        TimeoutException
            If the teams page fails to load within the expected time.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Uses headless Chrome scraping.
        - Extracts team metadata and related URLs.
        """

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        league = self.competition_service.get_league_by_name(league_name)
        if league is None or league.empty:
            raise ValueError(f"League not found: {league_name}")

        try:
            slug_league= league['competition_url'].iloc[0].split('/name/')[-1]

            url_teams = f'https://www.espn.com/soccer/teams/_/league/{slug_league}'
            
            driver= _create_driver()

            driver.get(url_teams)

            WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.TeamLinks")))

            teams = driver.find_elements(By.CSS_SELECTOR, "section.TeamLinks")

            rows = []

            for team in teams:

                try:
                    link_elem = team.find_element(By.CSS_SELECTOR, "a.AnchorLink")
                    href = link_elem.get_attribute("href")

                    path = urlparse(href).path

                    match = re.search(r"/id/(\d+)/([^/]+)", path)

                    team_id = match.group(1) if match else None
                    slug = match.group(2) if match else None

                    name = team.find_element(By.CSS_SELECTOR, "h2").text
                    photo = team.find_element(By.CSS_SELECTOR, "img").get_attribute("src")

                    fixtures = None
                    stats = None

                    links = team.find_elements(By.CSS_SELECTOR, "div.TeamLinks__Links a")

                    for l in links:

                        txt = l.text.lower()
                        h = l.get_attribute("href")

                        if "fixtures" in txt:
                            fixtures = h
                        elif "stats" in txt:
                            stats = h

                    rows.append({
                        "team": name,
                        "team_id": team_id,
                        "team_slug": slug,
                        "team_url": href,
                        "team_photo": photo,
                        "team_fixtures_url": fixtures,
                        "team_stats_url": stats,
                        "slug_league": slug_league.split(".")[0],
                        "slug_team_full": f"{slug_league.split('.')[0]}.{slug.replace('-', '_')}"
                    })

                except Exception:
                    continue

        except Exception as e:
            raise WebDriverException( f"Error while scraping league teams: {str(e)}" )

        finally:
            driver.quit()

        df_team= pd.DataFrame(rows)

        return df_team
    
    
    
    def _get_league_teams_cache(self, league_name: str) -> pd.DataFrame:
        """
        Return cached league teams data.
        Scrapes ESPN only if cache is empty.
        """

        if league_name not in self._league_teams_cache:

            self._league_teams_cache[league_name] = self.extract_teams(league_name)

        return self._league_teams_cache[league_name]
    
    def get_teams(self, league_name: str) -> pd.DataFrame:
     return self._get_league_teams_cache(league_name)
    
    def extract_standings(self, name_league: str, year: str = "2025") -> pd.DataFrame:
        """
        Extract league standings from ESPN Soccer.

        Parameters
        ----------
        name_league : str
            Name of the league (must exist in ESPN dataset).
        year : str, optional
            Season year, by default "2025".

        Returns
        -------
        pd.DataFrame
            League standings containing:
                - position (int)
                - team (str)
                - abbreviation (str)
                - team_url (str)
                - team_photo (str)
                - games_played (int)
                - wins (int)
                - draws (int)
                - losses (int)
                - goals_for (int)
                - goals_against (int)
                - goal_difference (int)
                - points (int)
                - competition_zone (Optional[str])

        Raises
        ------
        TypeError
            If `name_league` is not a string.

        ValueError
            If league is not found or invalid.

        TimeoutException
            If standings page fails to load.

        WebDriverException
            If Selenium WebDriver fails.

        Notes
        -----
        - Uses ESPN responsive standings table.
        - Combines fixed-left team table with stats table.
        - Adds competition zone using footer parsing.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        df_league = self.competition_service.get_league_by_name(name_league)
        if df_league is None or df_league.empty:
            raise ValueError(f"League not found: {name_league}")

        slug = df_league["competition_slug"].iloc[0]

        url= f"https://www.espn.com/soccer/standings/_/league/{slug}/season/{year}"

        driver= _create_driver()

        data = []

        try:
            driver.get(url)
            WebDriverWait(driver, 10).until( EC.presence_of_element_located((By.CSS_SELECTOR, "div.ResponsiveTable")))

            container = driver.find_element( By.CSS_SELECTOR, "div.ResponsiveTable")

            table_left = container.find_element( By.CSS_SELECTOR, "table.Table--fixed-left")
            team_rows = table_left.find_elements(By.CSS_SELECTOR, "tbody tr")

            table_right = container.find_element( By.CSS_SELECTOR, "div.Table__Scroller table.Table")
            stats_rows = table_right.find_elements(By.CSS_SELECTOR, "tbody tr")

            zone_map = parse_footer(driver)

            for team_row, stats_row in zip(team_rows, stats_rows):

                cell = team_row.find_element(By.CSS_SELECTOR, "td")

                position = int(cell.find_element(By.CSS_SELECTOR,  ".team-position").text.strip())
                team = cell.find_element(By.CSS_SELECTOR,".hide-mobile a").text.strip()
                
                img = cell.find_element(By.CSS_SELECTOR, "img")
                abbrev = (img.get_attribute("title")or img.get_attribute("alt"))
                logo = img.get_attribute("src")

                team_url = cell.find_element(By.CSS_SELECTOR,".TeamLink__Logo a").get_attribute("href")
                if team_url.startswith("/"):
                    team_url = "https://www.espn.com/" + team_url

                stats = stats_row.find_elements(By.CSS_SELECTOR, "td")

                data.append({
                    "position": position,
                    "team": team,
                    "abbreviation": abbrev,
                    "team_url": team_url,
                    "team_photo": logo,
                    "games_played": stats[0].text,
                    "wins": stats[1].text,
                    "draws": stats[2].text,
                    "losses": stats[3].text,
                    "goals_for": stats[4].text,
                    "goals_against": stats[5].text,
                    "goal_difference": stats[6].text,
                    "points": stats[7].text,
                    "competition_zone": zone_map.get(position)
                })

        except TimeoutException:
            raise TimeoutException("Standings page load timeout")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver error: {str(e)}")

        finally:
            driver.quit()

        return pd.DataFrame(data).sort_values("position").reset_index(drop=True)
    
    def extract_transfers(self, name_league: str,year: str = "2025") -> pd.DataFrame:
        """
        Extract transfer market data for a given league and season from ESPN.

        Parameters
        ----------
        name_league : str
            Name of the league (must exist in ESPN dataset).
        year : str, optional
            Season year, by default "2025".

        Returns
        -------
        pd.DataFrame
            DataFrame containing transfer information:
                - date (str)
                - player (Optional[str])
                - player_url (Optional[str])
                - team_from (Optional[str])
                - team_from_url (Optional[str])
                - team_from_photo (Optional[str])
                - team_to (Optional[str])
                - team_to_url (Optional[str])
                - team_to_photo (Optional[str])
                - fee (str)

        Raises
        ------
        TypeError
            If `name_league` is not a string.

        ValueError
            If league is not found or invalid.

        TimeoutException
            If the transfers page fails to load in time.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Uses infinite scroll simulation to load all transfers.
        - Handles cookie banner if present.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        league = self.competition_service.get_league_by_name(name_league)
        if league is None or league.empty:
            raise ValueError(f"League not found: {name_league}")

        slug = league["competition_slug"].iloc[0]
        url = f"https://www.espn.com/soccer/transfers/_/league/{slug}/season/{year}"

        driver= _create_driver()

        data = []

        try:
            driver.get(url)

            wait = WebDriverWait(driver, 10)

            # Cookies (optional)
            try:
                accept_cookies = wait.until(EC.element_to_be_clickable( (By.ID, "onetrust-accept-btn-handler")))
                accept_cookies.click()
                time.sleep(2)

            except TimeoutException:
                pass

            # Scroll to load dynamic content
            last_height = driver.execute_script( "return document.body.scrollHeight")

            while True:

                driver.execute_script("window.scrollBy(0, 800);")
                time.sleep(1.5)

                new_height = driver.execute_script( "return document.body.scrollHeight" )
                if new_height == last_height:
                    break

                last_height = new_height

            time.sleep(3)

            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

            for row in rows:

                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 6:
                    continue

                # Date
                date = cols[0].text.strip()

                # Player
                player = None
                player_url = None

                try:
                    player_tag = cols[1].find_element(By.TAG_NAME, "a")
                    player = player_tag.text.strip()
                    player_url = player_tag.get_attribute("href")

                except NoSuchElementException:
                    pass

                # From team
                team_from = team_from_url = team_from_photo = None

                try:
                    from_tag = cols[2].find_element(By.TAG_NAME, "a")
                    team_from = from_tag.text.strip()
                    team_from_url = from_tag.get_attribute("href")

                    img = cols[2].find_elements(By.TAG_NAME, "img")
                    if img:
                        team_from_photo = img[0].get_attribute("src")

                except NoSuchElementException:
                    pass

                # To team
                team_to = team_to_url = team_to_photo = None

                try:
                    to_tag = cols[4].find_element(By.TAG_NAME, "a")
                    team_to = to_tag.text.strip()
                    team_to_url = to_tag.get_attribute("href")

                    img = cols[4].find_elements(By.TAG_NAME, "img")
                    if img:
                        team_to_photo = img[0].get_attribute("src")

                except NoSuchElementException:
                    pass

                # Fee
                fee = cols[5].text.strip()

                data.append({
                    "date": date,
                    "player": player,
                    "player_url": player_url,
                    "team_from": team_from,
                    "team_from_url": team_from_url,
                    "team_from_photo": team_from_photo,
                    "team_to": team_to,
                    "team_to_url": team_to_url,
                    "team_to_photo": team_to_photo,
                    "fee": fee
                })

        except TimeoutException:
            raise TimeoutException("Transfers page load timeout")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver error: {str(e)}")

        finally:
            driver.quit()

        return pd.DataFrame(data)

    def extract_stats(self, name_league: str, year: str = "2025") -> Dict[str, Dict[str, pd.DataFrame]]:
        """
        Extract detailed league statistics tables from ESPN Soccer.

        This function scrapes multiple tabs (e.g., goals, assists, etc.)
        and returns a nested dictionary of DataFrames.

        Parameters
        ----------
        name_league : str
            Name of the league (must exist in ESPN dataset).
        year : str, optional
            Season year, by default "2025".

        Returns
        -------
        Dict[str, Dict[str, pd.DataFrame]]
            Nested dictionary structured as:
                {
                    tab_name: {
                        table_title: DataFrame
                    }
                }

        Raises
        ------
        TypeError
            If `name_league` is not a string.

        ValueError
            If league is not found or invalid.

        TimeoutException
            If page or tables fail to load in time.

        WebDriverException
            If Selenium WebDriver fails.

        Notes
        -----
        - Uses ESPN stats tab navigation (JS-driven).
        - Each tab may contain multiple statistic tables.
        - Cleans newline characters inside table cells.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        df_league = self.competition_service.get_league_by_name(name_league)
        if df_league is None or df_league.empty:
            raise ValueError(f"League not found: {name_league}")

        slug = df_league["competition_slug"].iloc[0]
        url =  f"https://www.espn.com/soccer/stats/_/league/{slug}/season/{year}"

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(options=options)

        driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """)

        wait = WebDriverWait(driver, 10)

        # ---------- Helper function ----------
        def parse_table(section):
            """
            Parse a single statistics table section into a DataFrame.

            Returns
            -------
            tuple[str, pd.DataFrame]
                (table_title, dataframe)
            """

            try:
                table_title = section.find_element(
                    By.CSS_SELECTOR,
                    "div.Table__Title"
                ).text.strip()

            except Exception:
                table_title = "Untitled"

            try:
                headers = section.find_elements(
                    By.CSS_SELECTOR,
                    "thead.Table__THEAD th"
                )
                columns = [h.text.strip() for h in headers]

            except Exception:
                columns = []

            rows = section.find_elements(
                By.CSS_SELECTOR,
                "tbody.Table__TBODY tr"
            )

            parsed_rows = []

            for row in rows:

                cols = row.find_elements(By.TAG_NAME, "td")
                parsed_rows.append([c.text.strip() for c in cols])

            df = (
                pd.DataFrame(parsed_rows, columns=columns)
                if columns else pd.DataFrame(parsed_rows)
            )

            # Clean newlines in text columns
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = (
                        df[col]
                        .str.replace("\n", " ", regex=False)
                        .str.strip()
                    )

            return table_title, df

        dfs: Dict[str, Dict[str, pd.DataFrame]] = {}

        try:
            driver.get(url)

            # Cookies (optional)
            try:
                accept = wait.until( EC.element_to_be_clickable( (By.ID, "onetrust-accept-btn-handler")))
                accept.click()
                time.sleep(1)

            except TimeoutException:
                pass

            tabs = wait.until( EC.presence_of_all_elements_located(  (By.CSS_SELECTOR, "nav.tabs__nav a.tabs__link")) )

            for i in range(len(tabs)):

                tabs = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "nav.tabs__nav a.tabs__link")))

                tab = tabs[i]
                tab_name = tab.text.strip()

                driver.execute_script( "arguments[0].scrollIntoView(true);",tab)

                driver.execute_script("arguments[0].click();", tab)

                time.sleep(1)

                try:
                    sections = wait.until(EC.presence_of_all_elements_located( (By.CSS_SELECTOR,  "section.statistics__table."  "InnerLayout__child--dividers" ) ))

                except TimeoutException:
                    continue

                dfs[tab_name] = {}

                for section in sections:

                    title, df_table = parse_table(section)
                    dfs[tab_name][title] = df_table

        except TimeoutException:
            raise TimeoutException("Stats page load timeout")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver error: {str(e)}")

        finally:
            driver.quit()

        return dfs