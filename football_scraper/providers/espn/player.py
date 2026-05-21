import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)

from football_scraper.providers.espn.utils import _create_driver

class ESPNPlayerScraper:
    def __init__(self, session: requests.Session, team_service):
        self.session = session
        self.team_service = team_service

    def extract_bio(self, name_league: str, name_team: str, season: str, player_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract player biography information and career history
        from ESPN Soccer.

        Parameters
        ----------
        name_league : str
            League or competition name.

        name_team : str
            Team name.

        season : str
            Season year.

        player_name : str
            Player full name.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            Tuple containing:

            1. Player bio DataFrame:
                - Name
                - Number
                - Position
                - HT
                - WT
                - Birthdate
                - Age
                - Nationality
                - Additional ESPN bio fields

            2. Career history DataFrame:
                - team
                - team_url
                - team_photo
                - seasons

        Raises
        ------
        TypeError
            If input parameters are not strings.

        ValueError
            If the player cannot be found in the squad.

        TimeoutException
            If ESPN page elements fail to load.

        WebDriverException
            If Selenium execution fails.

        Notes
        -----
        - Uses squad extraction to locate the player profile URL.
        - Automatically parses height and weight fields.
        - Extracts player career history from ESPN profile pages.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        if not isinstance(name_team, str):
            raise TypeError("name_team must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not isinstance(player_name, str):
            raise TypeError("player_name must be a string")

        df_squad= self.team_service.get_team_squad(name_league, name_team, season)
        if df_squad.empty:
            raise ValueError( f"No squad data found for team '{name_team}'")

        player_df = df_squad[df_squad["player_name"] == player_name]
        if player_df.empty:
            raise ValueError(f"Player '{player_name}' not found in team '{name_team}'")

        url_player = player_df["player_url"].iloc[0]

        player_id = url_player.split("/")[-2]
        player_slug = url_player.split("/")[-1]

        url = f"https://www.espn.com/soccer/player/bio/_/id/{player_id}/{player_slug}"
        
        driver=  _create_driver()
        wait = WebDriverWait(driver, 10)

        history = []

        try:
            driver.get(url)

            time.sleep(3)

            # Accept cookies if displayed
            try:
                accept_cookies = wait.until(EC.element_to_be_clickable(( By.ID, "onetrust-accept-btn-handler")))
                accept_cookies.click()
                time.sleep(1)

            except TimeoutException:
                pass

            wait.until( EC.presence_of_element_located(( By.CSS_SELECTOR, ".Bio__Item")))

            # ---------------- BIO DATA ----------------

            bio_items = driver.find_elements(By.CSS_SELECTOR,".Bio__Item")

            data = {}

            for item in bio_items:

                try:
                    label = item.find_element( By.CSS_SELECTOR, ".Bio__Label").text.strip()

                    spans = item.find_elements( By.TAG_NAME, "span")
                    value = spans[-1].text.strip()
                    data[label] = value

                except NoSuchElementException:
                    continue

            bio_stats = pd.DataFrame([data])

            # Split height and weight
            if "HT/WT" in bio_stats.columns:

                bio_stats[["HT", "WT"]] = bio_stats["HT/WT"] .str.split(",", expand=True)
                bio_stats["HT"] =  bio_stats["HT"].str.strip()
                bio_stats["WT"] =  bio_stats["WT"].str.strip()
                bio_stats = bio_stats.drop( columns=["HT/WT"])

            # Extract birthdate and age
            if "BIRTHDATE" in bio_stats.columns:

                bio_stats[["BIRTHDATE", "AGE"]] = bio_stats["BIRTHDATE"].str.extract(    r"(.+?)\s*\((\d+)\)")
                

            # Normalize column names
            bio_stats.columns = [col if col in ["HT", "WT"] else col.capitalize() for col in bio_stats.columns]

            # ---------------- CAREER HISTORY ----------------

            teams = driver.find_elements( By.CSS_SELECTOR, ".Career__History__Item" )

            for team in teams:

                try:
                    name = team.find_element( By.CSS_SELECTOR, ".clr-black").text.strip()

                    seasons = team.find_element( By.CSS_SELECTOR, ".clr-gray-05").text.strip()

                    team_url = team.get_attribute("href")

                    photo = team.find_element( By.TAG_NAME,  "img").get_attribute("src")

                    history.append({
                        "team": name,
                        "team_url": team_url,
                        "team_photo": photo,
                        "seasons": seasons
                    })

                except NoSuchElementException:
                    continue

        except TimeoutException:
            raise TimeoutException("Player bio page failed to load" )

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver execution failed: {str(e)}")

        finally:
            driver.quit()

        return bio_stats, pd.DataFrame(history)
    
    def extract_stats_current_year(self, name_league: str,name_team: str,season: str, player_name: str) -> pd.DataFrame:
        """
        Extract current season statistics for a football player
        from ESPN Soccer across all available competitions.

        Parameters
        ----------
        name_league : str
            League or competition name.

        name_team : str
            Team name.

        season : str
            Season year.

        player_name : str
            Player full name.

        Returns
        -------
        pd.DataFrame
            DataFrame containing player statistics grouped by competition.

            Columns include:
            - competition: competition name
            - dynamic statistical fields extracted from ESPN tables
            (e.g., goals, assists, matches played, minutes, etc.)

        Raises
        ------
        TypeError
            If any input parameter is not a string.

        ValueError
            If no squad data is found for the team or
            if the player is not found in the squad.

        TimeoutException
            If the ESPN stats page or required elements
            fail to load within the expected time.

        NoSuchElementException
            If expected DOM elements cannot be located
            during scraping.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Navigates through ESPN player stats page.
        - Iterates over all available competition dropdown options.
        - Re-extracts table data dynamically after each selection.
        - Handles DOM refresh issues by re-locating elements inside loops.
        - Returns an empty DataFrame if no valid stats are found.
        - Uses Selenium with headless Chrome for scraping.
        """

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        if not isinstance(name_team, str):
            raise TypeError("name_team must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not isinstance(player_name, str):
            raise TypeError("player_name must be a string")

        df_squad= self.team_service.get_team_squad(name_league, name_team, season)
        if df_squad.empty:
            raise ValueError(f"No squad data found for team '{name_team}'")

        player_df = df_squad[df_squad["player_name"] == player_name]
        if player_df.empty:
            raise ValueError(f"Player '{player_name}' not found in team '{name_team}'")

        url_player = player_df["player_url"].iloc[0]

        player_id = url_player.split("/")[-2]
        player_slug = url_player.split("/")[-1]

        url_player = f"https://www.espn.com/soccer/player/_/id/{player_id}/{player_slug}"

        driver= _create_driver()

        wait = WebDriverWait(driver, 15)
        all_rows = []

        try:
            driver.get(url_player)

            # Wait for stats section to load
            wait.until(EC.presence_of_element_located( (By.CSS_SELECTOR, "section.Card.PlayerStats")))

            # Locate competition dropdown
            select_element = wait.until(EC.presence_of_element_located( (By.CSS_SELECTOR, "section.Card.PlayerStats select.dropdown__select")))
            select = Select(select_element)

            options_list = [{"value": opt.get_attribute("value"), "text": opt.text.strip()} for opt in select.options]

            for competition in options_list:
                comp_value = competition["value"]
                comp_name = competition["text"]

                # Re-locate dropdown (DOM refresh issue)
                select_element = wait.until(EC.presence_of_element_located(    (By.CSS_SELECTOR, "section.Card.PlayerStats select.dropdown__select")))
                select = Select(select_element)
                select.select_by_value(comp_value)

                # Wait for competition update
                try:
                    wait.until(EC.text_to_be_present_in_element(( By.CSS_SELECTOR, "section.Card.PlayerStats .PlayerStats__subtitle"),    comp_name) )
                except TimeoutException:
                    time.sleep(1.5)

                stats_section = driver.find_element(By.CSS_SELECTOR,"section.Card.PlayerStats")

                table = stats_section.find_element(By.CSS_SELECTOR,".Table__Scroller table")

                headers = table.find_elements(By.CSS_SELECTOR, "thead th")
                col_names = [th.get_attribute("title") or th.text.strip() for th in headers]

                data_cells = table.find_elements(By.CSS_SELECTOR, "tbody tr td")
                values = [td.text.strip() for td in data_cells]

                if not col_names or not values:
                    continue

                row = {"competition": comp_name}
                for col, val in zip(col_names, values):
                    row[col] = val

                all_rows.append(row)

        except TimeoutException as e:
            raise TimeoutException(f"Timeout waiting for stats page elements: {e}")

        except NoSuchElementException as e:
            raise NoSuchElementException(f"DOM element not found: {e}")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver execution failed: {str(e)}")

        finally:
            driver.quit()

        if not all_rows:
            return pd.DataFrame()

        df = pd.DataFrame(all_rows)

        cols = ["competition"] + [c for c in df.columns if c != "competition"]
        return df[cols]
    
    def extract_last5_matches_current_year(self,name_league: str, name_team: str,  season: str, player_name: str) -> pd.DataFrame:
        """
        Extract the last 5 matches played by a football player
        in the current season from ESPN Soccer.

        Parameters
        ----------
        name_league : str
            League or competition name.

        name_team : str
            Team name.

        season : str
            Season year.

        player_name : str
            Player full name.

        Returns
        -------
        pd.DataFrame
            DataFrame containing the last 5 matches of the player.

            Columns include:
            - team_tricode
            - team_name
            - team_url
            - team_logo
            - date
            - venue (home/away)
            - opponent
            - opponent_full_name
            - opponent_url
            - opponent_logo
            - competition
            - result
            - score
            - match_url
            - appearances
            - note (if available)
            - additional match statistics (dynamic columns such as goals, assists, shots, cards, etc.)

        Raises
        ------
        TypeError
            If any input parameter is not a string.

        ValueError
            If no squad data is found for the team or
            if the player is not found in the squad.

        TimeoutException
            If the player page or match log section
            fails to load within the expected time.

        NoSuchElementException
            If required DOM elements cannot be found during scraping.

        WebDriverException
            If Selenium WebDriver fails during execution.

        Notes
        -----
        - Uses ESPN gamelog widget to extract match history.
        - Scrapes HTML after page rendering using Selenium + BeautifulSoup.
        - Handles home/away detection based on match text ("vs" / "@").
        - Dynamically extracts statistical columns from table headers.
        - Converts numeric stats when possible.
        - Returns an empty DataFrame if no valid match data is found.
        - Focuses on the last 5 matches shown in ESPN widget.
        """

        # INPUT VALIDATION

        if not isinstance(name_league, str):
            raise TypeError("name_league must be a string")

        if not isinstance(name_team, str):
            raise TypeError("name_team must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not isinstance(player_name, str):
            raise TypeError("player_name must be a string")

        # FETCH PLAYER FROM SQUAD

        df_squad= self.team_service.get_team_squad(name_league, name_team, season)
        if df_squad.empty:
            raise ValueError(f"No squad data found for team '{name_team}'")

        player_df = df_squad[df_squad["player_name"] == player_name]
        if player_df.empty:
            raise ValueError(f"Player '{player_name}' not found in team '{name_team}'")

        # BUILD PLAYER URL
        url_player = player_df["player_url"].iloc[0]

        player_id = url_player.split("/")[-2]
        player_slug = url_player.split("/")[-1]

        url_player = f"https://www.espn.com/soccer/player/_/id/{player_id}/{player_slug}"

        driver= _create_driver()

        wait = WebDriverWait(driver, 15)

        try:

            # LOAD PLAYER PAGE
            driver.get(url_player)

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "section.gamelogWidget--soccer") ) )

            html = driver.page_source

        except TimeoutException as e:
            raise TimeoutException(f"Timeout loading last matches page: {e}")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver execution failed: {str(e)}")

        finally:
            driver.quit()

        soup = BeautifulSoup(html, "html.parser")

        # LOCATE MATCHES SECTION
        section = soup.select_one("section.Card.gamelogWidget.gamelogWidget--soccer")
        if not section:
            return pd.DataFrame()

        table = section.select_one("table")

        if not table:
            return pd.DataFrame()

        # EXTRACT HEADERS

        # Prefer "title" attribute, fallback to visible text
        headers = []
        for th in table.select("thead th"):
            title_attr = th.get("title", "").strip()
            text = th.get_text(strip=True)
            headers.append(title_attr if title_attr else text)

        # PARSE MATCH ROWS
        all_matches = []
        rows = table.select("tbody tr")

        for row in rows:

            # Skip note rows but attach note to previous match
            if "note-row" in row.get("class", []):
                if all_matches:
                    note_text = row.get_text(strip=True)
                    all_matches[-1]["note"] = note_text
                continue

            cols = row.find_all("td")

            # Ensure minimum structure (team, date, opponent, etc.)
            if len(cols) < 5:
                continue

            team_td = cols[0]
            team_img = team_td.select_one("img")
            team_link = team_td.select_one("a[data-clubhouse-uid]")

            team_tricode = team_img.get("alt", "").strip() if team_img else None
            team_name = team_link.get_text(strip=True) if team_link else None
            team_url = team_link.get("href") if team_link else None

            if team_url and team_url.startswith("/"):
                team_url = "https://www.espn.com" + team_url

            # Team logo (clean data URLs if needed)
            team_logo = None
            if team_img:
                team_logo = ( team_img.get("data-default-src") or team_img.get("data-src") or team_img.get("src"))
                if team_logo and team_logo.startswith("data:image"):
                    team_logo = None

            # MATCH DATE (column 1)
            date = cols[1].get_text(strip=True)

            # OPPONENT INFO (column 2)
            opp_td = cols[2]
            text = opp_td.get_text(" ", strip=True)

            # Determine match venue
            venue = "home" if "vs" in text else "away" if "@" in text else None

            links = opp_td.select("a[data-clubhouse-uid]")

            opponent = None
            opponent_full_name = None
            opponent_url = None

            if links:
                team_link = links[-1]
                opponent = team_link.get_text(strip=True)

                title_attr = team_link.get("title", "")
                if "Team - " in title_attr:
                    opponent_full_name = title_attr.replace(
                        "Team - ", ""
                    ).strip()

                opponent_url = team_link.get("href")
                if opponent_url and opponent_url.startswith("/"):
                    opponent_url = "https://www.espn.com" + opponent_url

            # Fallback if structured link is missing
            if not opponent:
                fallback = opp_td.find_all("a")
                if fallback:
                    opponent = fallback[-1].get_text(strip=True)

            # Opponent logo
            opponent_logo = None
            logo_img = opp_td.select_one("span.TeamLink__Logo img")
            if logo_img:
                opponent_logo = ( logo_img.get("data-default-src") or logo_img.get("data-src") or logo_img.get("src"))
                if opponent_logo and opponent_logo.startswith("data:image"):
                    opponent_logo = None


            # COMPETITION (column 3)
            comp_td = cols[3]
            comp_span = comp_td.select_one("span[title]")
            competition = (comp_span.get("title", "").strip()if comp_span else comp_td.get_text(strip=True))

            # RESULT & SCORE (column 4)
            result_td = cols[4]
            result_cell = result_td.select_one(".ResultCell")
            result = result_cell.get_text(strip=True) if result_cell else None

            all_spans = result_td.find_all("span")
            score = ( all_spans[-1].get_text(strip=True) if all_spans else None)

            match_link = result_td.find("a")
            match_url = match_link.get("href") if match_link else None

            if match_url and match_url.startswith("/"):
                match_url = "https://www.espn.com" + match_url

            # APPEARANCES (column 5)
            appearances = (cols[5].get_text(strip=True) if len(cols) > 5 else None )

            # DYNAMIC STATS COLUMNS (6+)
            stats = {}
            for idx in range(6, len(cols)):
                if idx >= len(headers):
                    break

                col_name = headers[idx]
                value = cols[idx].get_text(strip=True)

                # Convert numeric values when possible
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    pass

                stats[col_name] = value

            # BUILD FINAL MATCH OBJECT
            match_data = {
                "team_tricode": team_tricode,
                "team_name": team_name,
                "team_url": team_url,
                "team_logo": team_logo,
                "date": date,
                "venue": venue,
                "opponent": opponent,
                "opponent_full_name": opponent_full_name,
                "opponent_url": opponent_url,
                "opponent_logo": opponent_logo,
                "competition": competition,
                "result": result,
                "score": score,
                "match_url": match_url,
                "appearances": appearances,
                "note": None,
            }

            match_data.update(stats)
            all_matches.append(match_data)

        return pd.DataFrame(all_matches)