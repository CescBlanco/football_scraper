import re
import pandas as pd
import time 

from typing import List, Dict, Optional, Any, Tuple,Union

from selenium import webdriver

from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)
from webdriver_manager.chrome import ChromeDriverManager
from providers.espn.utils import parse_game_info, get_team_name, get_record_points_by_uid, extract_events

class ESPNMatchScraper:
    def __init__(self, session):
        self.session = session

    def extract_basic_info(self, url: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract match information and goal events from an ESPN soccer match page.

        Parameters
        ----------
        url : str
            ESPN match URL.

        Returns
        -------
        Tuple[pd.DataFrame, pd.DataFrame]
            First DataFrame:
                Match-level information.

            Second DataFrame:
                Goal event information.

        Raises
        ------
        ValueError
            If the match ID cannot be extracted from the URL.

        TimeoutException
            If the page does not load required elements in time.

        WebDriverException
            If Selenium WebDriver fails.

        Notes
        -----
        - Uses Selenium in headless Chrome mode.
        - Automatically closes the browser session.
        """

        match_id_match = re.search(r"gameId/(\d+)", url)

        if not match_id_match:
            raise ValueError("Invalid match URL. Match ID not found.")

        match_id = match_id_match.group(1)

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        try:
            driver.get(url)

            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='prism-picture']")) )

            # Competition and season
            comp_candidates = driver.find_elements(By.CSS_SELECTOR, "span")

            competition = ""
            season = ""

            for span in comp_candidates:

                text = span.text.strip()
                match = re.match(r"^(\d{4}-\d{2})\s+(.+)$", text)

                if match:
                    season = match.group(1)
                    competition = match.group(2)
                    break

            # Team links
            team_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/soccer/team/_/id/']")

            seen_hrefs = set()
            teams = []

            for link in team_links:

                href = link.get_attribute("href")

                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    teams.append(link)

            if len(teams) < 2:
                raise ValueError("Unable to identify both teams.")

            home_team_el = teams[0]
            away_team_el = teams[1]

            home_team_url = home_team_el.get_attribute("href")
            away_team_url = away_team_el.get_attribute("href")

            home_team = get_team_name(home_team_el)
            away_team = get_team_name(away_team_el)

            # Team logos
            pictures = driver.find_elements( By.CSS_SELECTOR,"[data-testid='prism-picture']")

            home_logo = (pictures[0].find_element(By.TAG_NAME, "img").get_attribute("src"))
            away_logo = (pictures[1].find_element(By.TAG_NAME, "img").get_attribute("src"))

            # Scores
            gamestrip = driver.find_element(By.CSS_SELECTOR,"[class*='Gamestrip']")
            all_divs = gamestrip.find_elements(By.TAG_NAME, "div")

            scores = []

            for div in all_divs:

                text = div.text.strip()

                if re.fullmatch(r"\d+", text):
                    scores.append(text)

                    if len(scores) == 2:
                        break

            home_score = int(scores[0]) if scores else None
            away_score = int(scores[1]) if len(scores) > 1 else None

            # Match status
            status = "unknown"

            status_patterns = re.compile( r"^(FT|HT|Final|Postponed|\d+'|\d+:\d+)$",re.IGNORECASE)

            for span in comp_candidates:
                text = span.text.strip()
                if status_patterns.match(text):
                    status = text
                    break

            # Match winner
            winner = None

            if home_score is not None and away_score is not None:

                if home_score > away_score:
                    winner = home_team

                elif away_score > home_score:
                    winner = away_team

                else:
                    winner = "draw"

            # Team records and points
            record_pattern = re.compile(r"^(\d+)-(\d+)-(\d+)$")
            points_pattern = re.compile(r"(\d+)\s*PTS")

            home_uid = home_team_el.get_attribute("data-clubhouse-uid")
            away_uid = away_team_el.get_attribute("data-clubhouse-uid")

            home_record, home_points = get_record_points_by_uid(driver, gamestrip,record_pattern,points_pattern, home_uid)

            away_record, away_points = get_record_points_by_uid(driver, gamestrip,record_pattern,points_pattern,away_uid)

            game_info = parse_game_info(driver)

            match_time, match_date = ( game_info["datetime"].split(", ", 1)if game_info["datetime"]else (None, None))

            # Match DataFrame
            df_match = pd.DataFrame([{
                "match_id": match_id,
                "home_team": home_team,
                "home_score": home_score,
                "home_team_url": home_team_url,
                "home_photo": home_logo,
                "home_record": home_record,
                "home_points": home_points,
                "away_team": away_team,
                "away_score": away_score,
                "away_team_url": away_team_url,
                "away_photo": away_logo,
                "away_record": away_record,
                "away_points": away_points,
                "winner": winner,
                "competition": competition,
                "season": season,
                "status": status,
                "stadium": game_info["stadium"],
                "match_date": match_date,
                "match_time": match_time,
                "coverage": game_info["coverage"],
                "city": game_info["city"].split(",")[0] if game_info["city"] else None,
                "country": game_info["city"].split(",")[-1].strip() if game_info["city"] else None,
                "attendance": game_info["attendance"],
                "referees": game_info["referees"]
            }])

            # Goal events extraction
            goal_containers = driver.find_elements( By.XPATH,"//div[div[contains(@class,'XKrIt')]]")
            pattern = re.compile(r"(.+?)\s-\s(\d+)'")

            events = []
            seen_events = set()

            for parent in goal_containers:

                children = parent.find_elements(By.XPATH, "./div")

                if len(children) < 3:
                    continue

                home_block = children[0]
                away_block = children[2]

                for block, team in [(home_block, home_team),(away_block, away_team)]:

                    text = block.text.strip()
                    if not text:
                        continue

                    matches = pattern.findall(text)

                    for player, minute in matches:

                        key = (player.strip(), minute)
                        if key in seen_events:
                            continue

                        seen_events.add(key)

                        events.append({
                            "match_id": match_id,
                            "team": team,
                            "player": player.strip(),
                            "minute": int(minute),
                            "event_type": "goal"
                        })

            df_events = pd.DataFrame(events) if events else pd.DataFrame(columns=[ "match_id","team","player","minute","event_type"])

            return df_match, df_events

        finally:
            driver.quit()

    def extract_match_stats(self, url: str) -> pd.DataFrame:
        """
        Extract match statistics from the ESPN match stats page.

        Parameters
        ----------
        url : str
            ESPN match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
                - stat (str): Statistic name.
                - home (Optional[int | float]): Home team value.
                - away (Optional[int | float]): Away team value.

        Raises
        ------
        ValueError
            If the match ID cannot be extracted from the URL.

        TimeoutException
            If the stats page fails to load.

        WebDriverException
            If Selenium WebDriver fails.

        Notes
        -----
        - Possession values are stored as float percentages.
        - Other statistics are stored as integers.
        """

        match_id = url.split("/")[-2]

        if not match_id.isdigit():
            raise ValueError("Invalid match URL. Match ID not found.")

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        url_stats = f"https://www.espn.com/soccer/matchstats/_/gameId/{match_id}"

        stats: Dict[str, Optional[float]] = {}

        try:
            driver.get(url_stats)

            WebDriverWait(driver, 15).until( EC.presence_of_element_located( (By.CSS_SELECTOR, "[data-testid='prism-LayoutCard']")) )

            stat_cards = driver.find_elements( By.CSS_SELECTOR, "[data-testid='prism-LayoutCard']")

            match_stats_card = None

            for card in stat_cards:

                try:
                    header = card.find_element(By.TAG_NAME, "header").text

                    if "Match Stats" in header:
                        match_stats_card = card
                        break

                except NoSuchElementException:
                    continue

            if not match_stats_card:
                return pd.DataFrame(columns=["stat", "home", "away"])

            # Possession stats
            try:
                home_poss = match_stats_card.find_element( By.CSS_SELECTOR,"span.uHRs").text.replace("%", "").strip()
                away_poss = match_stats_card.find_element(By.CSS_SELECTOR, "span.nljvg").text.replace("%", "").strip()

                stats["home_Possession"] = float(home_poss)
                stats["away_Possession"] = float(away_poss)

            except (NoSuchElementException, ValueError):
                pass

            # Remaining statistics
            stat_rows = match_stats_card.find_elements( By.CSS_SELECTOR,"div.LOSQp")
            for row in stat_rows:

                try:
                    label = row.find_element( By.CSS_SELECTOR,"span.OkRBU").text.strip()
                except NoSuchElementException:
                    continue

                if not label or label == "Possession":
                    continue

                progressbars = row.find_elements( By.CSS_SELECTOR, "[role='progressbar']")
                if len(progressbars) < 2:
                    continue

                home_val = progressbars[0].get_attribute("aria-valuenow")
                away_val = progressbars[1].get_attribute("aria-valuenow")

                key = label

                stats[f"home_{key}"] = int(home_val) if home_val is not None else None
                stats[f"away_{key}"] = int(away_val) if away_val is not None else None
        
        finally:
            driver.quit()

        rows = []

        for key, value in stats.items():

            if key.startswith("home_"):

                stat_name = key[5:]
                rows.append({
                    "stat": stat_name,
                    "home": value,
                    "away": stats.get(f"away_{stat_name}")
                })

        return  pd.DataFrame(rows) if rows else pd.DataFrame(columns=["stat", "home", "away"])

    def extract_teams_form_pre_match(self, url: str) -> pd.DataFrame:
        """
        Extract both teams' recent form before the match.

        Parameters
        ----------
        url : str
            ESPN match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
                - match_id (str)
                - team (Optional[str])
                - result (str)
                - team_home (str)
                - team_home_url (str)
                - team_home_photo (str)
                - score_team_home (Optional[int])
                - score_team_away (Optional[int])
                - team_away (str)
                - team_away_url (str)
                - team_away_photo (str)
                - match_url (str)
                - date (str)
                - competition (str)

        Raises
        ------
        ValueError
            If the match ID cannot be extracted.

        WebDriverException
            If Selenium WebDriver fails.
        """

        match_id = url.split("/")[-2]

        if not match_id.isdigit():
            raise ValueError("Invalid match URL. Match ID not found.")

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        url_stats = f"https://www.espn.com/soccer/matchstats/_/gameId/{match_id}"

        rows: List[Dict[str, Optional[str]]] = []

        try:
            driver.get(url_stats)

            WebDriverWait(driver, 15).until(EC.presence_of_element_located( (By.CSS_SELECTOR, "section.MatchFormTable") ))

            form_tables = driver.find_elements(By.CSS_SELECTOR, "section.MatchFormTable" )
            for table in form_tables:

                try:
                    team = table.find_element( By.CSS_SELECTOR, ".Card__Header__Title__Logo__Wrapper img" ).get_attribute("title")
                except NoSuchElementException:
                    team = None

                tr_rows = table.find_elements(By.CSS_SELECTOR,"tr.MatchFormTable--table_row")
                for tr in tr_rows:

                    cells = tr.find_elements(By.CSS_SELECTOR,"td.MatchFormTable--table_cell")
                    if len(cells) < 8:
                        continue

                    try:
                        result =  cells[0].find_element(By.CSS_SELECTOR,"span.MatchFormTable--results" ).text.strip()
                        team_home_name = cells[1].text.strip()
                        team_home_url = cells[1].find_element(By.TAG_NAME, "a").get_attribute("href")
                        team_home_photo =  cells[2].find_element(By.TAG_NAME, "img").get_attribute("src")
            

                        score_el = cells[3].find_element(By.TAG_NAME, "a")
                        score = score_el.text.strip()

                        match_url = score_el.get_attribute("href")

                        score_parts = score.split(" - ")
                        score_team_home =  int(score_parts[0]) if len(score_parts) == 2 else None
                        score_team_away = int(score_parts[1]) if len(score_parts) == 2 else None

                        team_away_photo =  cells[4].find_element(By.TAG_NAME, "img").get_attribute("src")
                        team_away_url =  cells[4].find_element(By.TAG_NAME, "a").get_attribute("href")
                        
                        team_away_name = cells[5].text.strip()

                        date = cells[6].text.strip()

                        competition = cells[7].text.strip()

                        rows.append({
                            "match_id": match_id,
                            "team": team,
                            "result": result,
                            "team_home": team_home_name,
                            "team_home_url": team_home_url,
                            "team_home_photo": team_home_photo,
                            "score_team_home": score_team_home,
                            "score_team_away": score_team_away,
                            "team_away": team_away_name,
                            "team_away_url": team_away_url,
                            "team_away_photo": team_away_photo,
                            "match_url": match_url,
                            "date": date,
                            "competition": competition
                        })

                    except (
                        NoSuchElementException,
                        ValueError,
                        IndexError
                    ):
                        continue

        finally:
            driver.quit()

        return  pd.DataFrame(rows) if rows else pd.DataFrame(columns=["match_id","team","result","team_home", "team_home_url","team_home_photo","score_team_home","score_team_away","team_away",
                                                                        "team_away_url","team_away_photo","match_url","date","competition"])
        
    def extract_head_to_head(self, url: str) -> pd.DataFrame:
        """
        Extract historical head-to-head matches between both teams.

        Parameters
        ----------
        url : str
            ESPN match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
                - match_id (str)
                - team_home (str)
                - team_home_url (str)
                - team_home_photo (str)
                - score_team_home (Optional[int])
                - score_team_away (Optional[int])
                - team_away (str)
                - team_away_url (str)
                - team_away_photo (str)
                - winner (Optional[str])
                - match_url (str)
                - date (str)
                - competition (str)

        Raises
        ------
        ValueError
            If the match ID is invalid.

        TimeoutException
            If page loading times out.

        WebDriverException
            If Selenium WebDriver fails.
        """

        match_id = url.split("/")[-2]

        if not match_id.isdigit():
            raise ValueError("Invalid match URL. Match ID not found.")

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        url_stats = f"https://www.espn.com/soccer/matchstats/_/gameId/{match_id}"

        rows = []

        try:
            driver.get(url_stats)

            WebDriverWait(driver, 15).until( EC.presence_of_element_located((By.CSS_SELECTOR, "section.MatchFormTable")))

            sections = driver.find_elements(By.CSS_SELECTOR,"section.MatchFormTable")

            h2h_section = None
            for section in sections:

                try:
                    h3 = section.find_element(By.TAG_NAME, "h3")
                    if "Head To Head" in h3.text:
                        h2h_section = section
                        break

                except NoSuchElementException:
                    continue

            if not h2h_section:
                return pd.DataFrame(columns=[
                    "match_id","team_home","team_home_url","team_home_photo","score_team_home","score_team_away",
                    "team_away","team_away_url","team_away_photo","winner","match_url","date","competition" ])

            tr_rows = h2h_section.find_elements( By.CSS_SELECTOR,"tr.MatchFormTable--table_row")

            for tr in tr_rows:

                cells = tr.find_elements(By.CSS_SELECTOR,"td.MatchFormTable--table_cell")
                if len(cells) < 7:
                    continue

                try:
                    team_home_name = cells[0].text.strip()

                    team_home_url = cells[0].find_element(By.TAG_NAME, "a").get_attribute("href")
                    

                    team_home_photo = cells[1].find_element(By.TAG_NAME, "img").get_attribute("src")
                    

                    score_el = cells[2].find_element(By.TAG_NAME, "a")
                    score = score_el.text.strip()

                    match_url = score_el.get_attribute("href")

                    score_parts = score.split(" - ")
                    score_team_home =  int(score_parts[0]) if len(score_parts) == 2 else None
                    score_team_away =  int(score_parts[1]) if len(score_parts) == 2 else None
                    

                    team_away_photo =  cells[3].find_element(By.TAG_NAME, "img") .get_attribute("src")
                    team_away_url =  cells[3].find_element(By.TAG_NAME, "a") .get_attribute("href")
                    team_away_name = cells[4].text.strip()

                    date = cells[5].text.strip()

                    competition = cells[6].text.strip()

                    winner = None

                    if score_team_home is not None and score_team_away is not None:

                        if score_team_home > score_team_away:
                            winner = team_home_name

                        elif score_team_away > score_team_home:
                            winner = team_away_name

                        else:
                            winner = "Draw"

                    rows.append({
                        "match_id": match_id,
                        "team_home": team_home_name,
                        "team_home_url": team_home_url,
                        "team_home_photo": team_home_photo,
                        "score_team_home": score_team_home,
                        "score_team_away": score_team_away,
                        "team_away": team_away_name,
                        "team_away_url": team_away_url,
                        "team_away_photo": team_away_photo,
                        "winner": winner,
                        "match_url": match_url,
                        "date": date,
                        "competition": competition
                    })

                except (NoSuchElementException, ValueError,IndexError):
                    continue

        finally:
            driver.quit()

        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["match_id","team_home","team_home_url","team_home_photo","score_team_home","score_team_away",
                                                                        "team_away","team_away_url","team_away_photo","winner","match_url","date","competition"])

    def extract_lineups(self, url: str) -> pd.DataFrame:
        """
        Extract match lineups including starters, substitutions,
        and unused substitutes.

        Parameters
        ----------
        url : str
            ESPN match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
                - match_id (str)
                - team (Optional[str])
                - formation (Optional[str])
                - type (str)
                - number (Optional[str])
                - name (Optional[str])
                - player_url (Optional[str])
                - events (Optional[str])

        Raises
        ------
        ValueError
            If the match ID is invalid.

        TimeoutException
            If lineup content fails to load.

        WebDriverException
            If Selenium WebDriver fails.

        Notes
        -----
        Player type values:
            - starter
            - substitute_in
            - unused_substitute
        """

        match_id = url.split("/")[-2]

        if not match_id.isdigit():
            raise ValueError("Invalid match URL. Match ID not found.")

        options = webdriver.ChromeOptions()

        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.add_argument(
            "user-agent=Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)

        url_lineups = f"https://www.espn.com/soccer/lineups/_/gameId/{match_id}"

        rows = []

        try:
            driver.get(url_lineups)

            WebDriverWait(driver, 15).until( EC.presence_of_element_located((By.CSS_SELECTOR, ".LineUps__BothTeams") ))

            # Scroll until all dynamic content is loaded
            last_height = driver.execute_script("return document.body.scrollHeight")
            
            while True:

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                time.sleep(2)

                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break

                last_height = new_height

            both_teams_div = driver.find_element(By.CSS_SELECTOR,".LineUps__BothTeams")

            sections = both_teams_div.find_elements(By.CSS_SELECTOR, "section.Card" )

            for section in sections:

                try:
                    team = section.find_element(By.CSS_SELECTOR,".LineUps__BothTeams__Header img" ).get_attribute("alt")
                except NoSuchElementException:
                    team = None

                try:
                    formation = section.find_element(By.CSS_SELECTOR,".LineUps__TabsHeader__Title" ).text.strip()
                    

                except NoSuchElementException:
                    formation = None

                # Starting lineup
                try:
                    player_rows = section.find_elements(By.CSS_SELECTOR, ".LineUps__PlayersTable tr.LineUps__TableRow")

                    for tr in player_rows:

                        players = tr.find_elements(By.CSS_SELECTOR,".SoccerLineUpPlayer")
                        
                        for player_div in players:
                            try:
                                header_div = player_div.find_element( By.CSS_SELECTOR,".SoccerLineUpPlayer__Header")

                                is_sub_in = "subbedIn" in (header_div.get_attribute("class") or "")

                            except NoSuchElementException:
                                is_sub_in = False

                            try:
                                number = player_div.find_element(By.CSS_SELECTOR, ".SoccerLineUpPlayer__Header__Number").text.strip()
                                

                            except NoSuchElementException:
                                number = None

                            try:
                                name_el = player_div.find_element( By.CSS_SELECTOR,".SoccerLineUpPlayer__Header__Name")
                                name = name_el.text.strip()

                                player_url = name_el.get_attribute("href")

                            except NoSuchElementException:
                                name = None
                                player_url = None

                            events = []

                            try:
                                icon_svgs = player_div.find_elements(By.CSS_SELECTOR,".SoccerLineUpPlayer__Header__IconWrapper svg[aria-hidden='false']" )
                                for svg in icon_svgs:

                                    label = svg.get_attribute("aria-label") or ""

                                    if label:
                                        events.append(label)

                            except Exception:
                                pass

                            rows.append({
                                "match_id": match_id,
                                "team": team,
                                "formation": formation,
                                "type": "substitute_in" if is_sub_in else "starter",
                                "number": number,
                                "name": name,
                                "player_url": player_url,
                                "events": ", ".join(events) if events else None     
                            })

                except Exception:
                    pass

                # Unused substitutes
                try:
                    sub_rows = section.find_elements(By.CSS_SELECTOR,".LineUps__SubstitutesTable tr.LineUps__TableRow")

                    for tr in sub_rows:

                        try:
                            number = tr.find_element(By.CSS_SELECTOR, ".SoccerLineUpPlayer__Header__Number").text.strip()
                            
                        except NoSuchElementException:
                            number = None

                        try:
                            name_el = tr.find_element( By.CSS_SELECTOR, ".SoccerLineUpPlayer__Header__Name")
                            name = name_el.text.strip()

                            player_url = name_el.get_attribute("href")

                        except NoSuchElementException:
                            name = None
                            player_url = None

                        rows.append({
                            "match_id": match_id,
                            "team": team,
                            "formation": formation,
                            "type": "unused_substitute",
                            "number": number,
                            "name": name,
                            "player_url": player_url,
                            "events": None
                        })

                except Exception:
                    pass

        finally:
            driver.quit()

        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["match_id","team","formation","type","number","name","player_url","events"])
    
    def extract_match_commentary(self, url):
        # -------------------------
        # CONFIG CHROME
        # -------------------------
        options = Options()

        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=options)
        wait = WebDriverWait(driver, 20)


        url_commentary= f'https://www.espn.com/soccer/commentary/_/gameId/{url.split("/")[-2]}'

        # -------------------------
        # ABRIR WEB
        # -------------------------
        driver.get(url_commentary)

        # esperar tabla
        wait.until(EC.presence_of_element_located( (By.CSS_SELECTOR, "tbody.Table__TBODY")))

        # -------------------------
        # ALL COMMENTARY
        # -------------------------
        return extract_events(driver)
    
    def extract_match_timeline(self, url):
        # -------------------------
        # CONFIG CHROME
        # -------------------------
        options = Options()

        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")

        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 20)

        # -------------------------
        # ABRIR WEB
        # -------------------------
        url_commentary= f'https://www.espn.com/soccer/commentary/_/gameId/{url.split("/")[-2]}'

        # -------------------------
        # ABRIR WEB
        # -------------------------
        driver.get(url_commentary)

        boton_key_events = wait.until( EC.element_to_be_clickable( (By.XPATH,"//button[contains(., 'Key Events')]" )))
        driver.execute_script("arguments[0].click();", boton_key_events)

        # esperar a que cambie el contenido
        time.sleep(2)

        # -------------------------
        # EXTRAER KEY EVENTS
        # -------------------------
        return  extract_events(driver)