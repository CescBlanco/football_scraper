import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np
from football_scraper.providers.transfermarkt.constants import DEFAULT_HEADERS
from football_scraper.providers.transfermarkt.utils import extract_text, extract_other_positions, get_img_src, parse_int, parse_minutes,parse_general_stats_player, parse_competition_match_stats_player, extract_all_player_stats, get_soup_selenium, extract_stats_by_competition, extract_stats_by_club, get_total_pages, extract_data_from_page, parse_squad_number_table

class TransfermarktPlayerScraper:
    def __init__(self, session, headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS
    
    
    def extract_profile_info(self, url:str)-> pd.DataFrame:

        """
        Extract detailed player profile information from Transfermarkt.

        This function scrapes the player's profile page on Transfermarkt and extracts 
        various details such as:
        - Full name
        - Date of birth
        - Age
        - Place of birth
        - Citizenship and citizenship photo
        - Height
        - Main and other positions
        - Preferred foot
        - Agent details and agent link
        - International career (caps/goals, current international status)
        - Market value and last update
        - Current club and club photo
        - Contract information (joined, expires, last extension)
        - Social media links (Instagram, TikTok)
        and more.

        Parameters
        ----------
        url : str
            URL of the player's profile page on Transfermarkt.
        headers : dict
            Dictionary of HTTP headers to use for the GET request, e.g., User-Agent.

        Returns
        -------
        pandas.DataFrame
            DataFrame containing the player's profile information, including:
                - Name
                - Full name
                - Player photo
                - Shirt number
                - Date of birth
                - Age
                - Place of birth
                - Citizenship
                - Citizenship photo
                - Height
                - Main position
                - Other positions
                - Foot preference
                - Agent name and link
                - Current international status (caps/goals)
                - Market value and last update
                - Current club name and photo
                - Contract details (joined, expires, last extension)
                - Social media (Instagram, TikTok)

        Raises
        ------
        requests.HTTPError
            If the HTTP request returned an unsuccessful status code (e.g., 404, 500).
        requests.RequestException
            For other network-related errors (e.g., connection issues).
        ValueError
            If the page structure is unexpected or an element is missing.
        """
       
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract date of birth and age from a specific text pattern
        dob_and_age = extract_text(soup, 'info-table__content info-table__content--bold', index=1)
        birth_date, age = re.match(r'(\d{2}/\d{2}/\d{4}) \((\d{1,2})\)', dob_and_age).groups()

        citizenship_span = soup.find_all('span', class_='info-table__content info-table__content--bold')[4]
        current_international_span = next((li.find('span', class_='data-header__content') for li in soup.find_all('li', class_='data-header__label') if 'Current international' in li.text), None)

        # Find the <span> containing agent information
        agent_span = soup.find('span', class_='info-table__content info-table__content--bold info-table__content--flex')


        # Caps/Goals information
        caps_goals_li = next((li for li in soup.find_all('li', class_='data-header__label') if 'Caps/Goals' in li.text), None)
        caps, goals = [tag.text.strip() for tag in caps_goals_li.find_all('a', class_='data-header__content data-header__content--highlight')] if caps_goals_li else ("0", "0")

        # Extract club, club photo and last market value updated
        club_div = soup.find('div', class_='data-header__box--big')
        club_image_tag = club_div.find('a', class_='data-header__box__club-link').find('img') if club_div else None
        last_update_full = soup.find('p', class_='data-header__last-update').text.strip()

        # Create a dictionary with all the player's profile data
        all_data = [{
            'Name': soup.find('strong').text,
            'full_name': extract_text(soup, 'info-table__content--bold'),
            'player_photo': soup.find('div', class_='data-header__profile-container').find('img', class_='data-header__profile-image')['src'],
            'shirt_number': soup.find('span', class_='data-header__shirt-number').text.strip().split("#")[-1],
            'date_of_birth': birth_date,
            'age': age,
            'place_of_birth': extract_text(soup, 'info-table__content info-table__content--bold', index=2),
            'citizenship': citizenship_span.text.strip(),
            'citizenship_photo': citizenship_span.find('img')['src'] if citizenship_span.find('img') else None,
            'height': extract_text(soup, 'info-table__content info-table__content--bold', index=3),
            'main_position': extract_text(soup, 'info-table__content info-table__content--bold', index=5),
            'other_positions': extract_other_positions(soup) ,
            'foot': extract_text(soup, 'info-table__content info-table__content--bold', index=6),
            'agent': soup.find('span', class_='info-table__content info-table__content--bold info-table__content--flex').find_next('a').text.strip(),
            'agent_link': f"https://www.transfermarkt.com{agent_span.find('a')['href']}",
            'current_international': current_international_span.find('a').text.strip() if current_international_span else None,
            'matches/goals_international': f"{caps}/{goals}",
            'market_value': ''.join([soup.find('span', class_='waehrung').text.strip(), soup.find('span', class_='waehrung').next_sibling.strip(),soup.find('span', class_='waehrung').find_next_sibling().text.strip()]),
            'last_mv_update': last_update_full.split(': ')[1],
            'current_club': club_image_tag['alt'] if club_image_tag else None,
            'current_club_photo': club_image_tag['srcset'].strip() if club_image_tag else None,
            'joined': extract_text(soup, 'info-table__content info-table__content--bold', index=7),
            'contract_expires': extract_text(soup, 'info-table__content info-table__content--bold', index=8),
            'last_contract_extension': extract_text(soup, 'info-table__content info-table__content--bold', index=9),
            'outfitter': extract_text(soup, 'info-table__content info-table__content--bold', index=10),
            'instagram': soup.find('a', {'title': 'Instagram'})['href'],
            'tiktok': soup.find('a', {'title': 'TikTok'})['href']
        }]


        return pd.DataFrame(all_data)

#--------------------------------------------------------------------------------------------     

    def extract_stats_player_season(self, url: str)->dict:
        """
        Extracts all available player statistics tables from a Transfermarkt season page.

        Parses both general competition statistics and match-by-match detailed statistics,
        returning them as a dictionary of DataFrames keyed by section title.

        Parameters
        ----------
        url : str
            URL of the player's season page on Transfermarkt.
        headers : dict, optional
            HTTP headers to use for the request. Default uses a common User-Agent.

        Returns
        -------
        dict
            Dictionary where:
            - Keys are section titles (e.g., "General Stats", "UEFA Champions League").
            - Values are pandas DataFrames with the respective statistics.

        Raises
        ------
        requests.HTTPError
            If the GET request fails (status code != 200).

        """
        with requests.Session() as session:
            response = session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            dfs = extract_all_player_stats(soup)
        return dfs

#-------------------------------------------------------------------------------------
    def extract_player_all_seasons_stats(self, url: str) -> pd.DataFrame:
        """
        Extract player statistics for all seasons from Transfermarkt.

        This function parses the table containing player stats per season and competition,
        extracting the following information:
        - season
        - competition
        - team
        - team_photo
        - squad
        - appearances
        - goals
        - assists
        - own_goals
        - yellow_cards
        - red_cards
        and more.

        Parameters
        ----------
        url : str
            URL of the player's all-seasons statistics page on Transfermarkt.
        headers : dict
            Dictionary of HTTP headers to use for the GET request, e.g., User-Agent.

        Returns
        -------
        pandas.DataFrame
            DataFrame containing one row per season/competition with columns:
                - season
                - competition
                - competition_photo
                - team
                - team_photo
                - squad
                - appearances
                - ppg
                - goals
                - assists
                - own_goals
                - subs_on
                - subs_off
                - yellow_cards
                - second_yellow_cards
                - red_cards
                - penalty_goals
                - minutes_per_goal
                - minutes_played

        Raises
        ------
        requests.HTTPError
            If the HTTP request returned an unsuccessful status code.
        requests.RequestException
            For other network-related errors.
        """

        try:
            
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Find the table containing the player's season stats
            table = soup.select_one("div.responsive-table table")
            rows = table.find("tbody").find_all("tr", recursive=False)

            all_data = []

            # Loop through each row in the table (one row per season/competition)
            for row in rows:
                cols = row.find_all("td", recursive=False)

                # Extract competition and team images
                comp_img_tag = cols[1].find("img")
                team_img_tag = cols[3].find("img")
                team_a_tag = cols[3].find("a")

                # Append the data for each row to the all_data list
                all_data.append({
                    "season": cols[0].get_text(strip=True),
                    "competition": cols[2].get_text(strip=True),
                    "competition_photo": comp_img_tag["src"] if comp_img_tag else "",
                    "team": team_a_tag["title"] if team_a_tag and team_a_tag.has_attr("title") else "",
                    "team_photo": team_img_tag["src"] if team_img_tag else "",
                    "squad": cols[4].get_text(strip=True),
                    "appearances": cols[5].get_text(strip=True),
                    "ppg": cols[6].get_text(strip=True),
                    "goals": cols[7].get_text(strip=True),
                    "assists": cols[8].get_text(strip=True),
                    "own_goals": cols[9].get_text(strip=True),
                    "subs_on": cols[10].get_text(strip=True),
                    "subs_off": cols[11].get_text(strip=True),
                    "yellow_cards": cols[12].get_text(strip=True),
                    "second_yellow_cards": cols[13].get_text(strip=True),
                    "red_cards": cols[14].get_text(strip=True),
                    "penalty_goals": cols[15].get_text(strip=True),
                    "minutes_per_goal": cols[16].get_text(strip=True),
                    "minutes_played": cols[17].get_text(strip=True),
                })

            # Convert the collected data into a pandas DataFrame
            return pd.DataFrame(all_data)

        except requests.HTTPError as http_err:
            print(f"[ERROR] HTTP error occurred while fetching data: {http_err}")
            return pd.DataFrame()  # Return an empty DataFrame on error

        except requests.RequestException as req_err:
            print(f"[ERROR] Request error occurred: {req_err}")
            return pd.DataFrame()  # Return an empty DataFrame on error

        except Exception as err:
            print(f"[ERROR] Unexpected error occurred: {err}")
            return pd.DataFrame()  # Return an empty DataFrame on error

#--------------------------------------------------------------------------------------
    def _get_soup(self, url: str):
        try:
            response = self.session.get(url, headers=DEFAULT_HEADERS)
            response.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Error fetching URL: {url}") from e

        return BeautifulSoup(response.text, "html.parser")
    
    def get_stats_by_competition(self, url: str, use_selenium: bool = False):
        """
        Get player stats grouped by competition type.
        """

        if use_selenium:
            soup = get_soup_selenium(url)
        else:
            soup = self._get_soup(url)

        return extract_stats_by_competition(soup)
    
#----------------------------------------------------------------------------------
    
    def get_stats_by_club(self, url: str, use_selenium: bool = False):
        """
        Get player stats by club and by competition per club.

        Parameters
        ----------
        url : str
            Transfermarkt URL of the player's page.
        use_selenium : bool
            Whether to use Selenium to render the page. Default False.

        Returns
        -------
        dict
            {
                "by_club": pd.DataFrame,
                "by_competition": pd.DataFrame
            }
        """
        if use_selenium:
            soup = get_soup_selenium(url)
        else:
            soup = self._get_soup(url)

        return extract_stats_by_club(soup)
    
#-----------------------------------------------------------------------------------------
    
    def extract_stats_by_coach(self,url: str) -> pd.DataFrame:
        """
        Extracts a player's statistics by coach from their Transfermarkt page.

        This function scrapes the player's statistics for each coach they have played under, such as 
        appearances, goals, assists, yellow/red cards, minutes played, etc.

        Parameters
        ----------
        url : str
            URL of the player's page on Transfermarkt that contains stats for different coaches.
        headers : dict
            HTTP headers to use for the GET request (e.g., User-Agent).

        Returns
        -------
        pd.DataFrame
            DataFrame with columns:
                - coach
                - appearances
                - goals
                - assists
                - own_goals
                - sub_on
                - sub_off
                - yellow_cards
                - second_yellow_cards
                - red_cards
                - penalty_goals
                - minutes_per_goals
                - minutes_played
        """
        all_data = []
        try:
        
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            if not table:
                return pd.DataFrame()  # No data

            rows = table.find("tbody").find_all("tr", recursive=False)

            for row in rows:
                cols = row.find_all("td", recursive=False)
                coach_a_tag = cols[0].find("a")

                all_data.append({
                    "coach": coach_a_tag["title"] if coach_a_tag else "",
                    "appearances": cols[1].get_text(strip=True),
                    "goals": cols[2].get_text(strip=True),
                    "assists": cols[3].get_text(strip=True),
                    "own_goals": cols[4].get_text(strip=True),
                    "sub_on": cols[5].get_text(strip=True),
                    "sub_off": cols[6].get_text(strip=True),
                    "yellow_cards": cols[7].get_text(strip=True),
                    "second_yellow_cards": cols[8].get_text(strip=True),
                    "red_cards": cols[9].get_text(strip=True),
                    "penalty_goals": cols[10].get_text(strip=True),
                    "minutes_per_goals": parse_minutes(cols[11].get_text(strip=True)),
                    "minutes_played": parse_minutes(cols[12].get_text(strip=True)),
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing the data for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------
    def extract_record_against(self, url: str) -> pd.DataFrame:
        """
        Extracts the record of a player against other teams from Transfermarkt.

        Returns a DataFrame with columns:
        - team, team_photo, appearances, w, d, l, points_scored, goal, assist,
        sub_on, sub_off, yellow_cards, second_yellow_cards, red_cards, own_goals,
        penalty_goals, minutes_played
        """
        all_data = []

        def _parse_int(text: str) -> int:
            """Converts text to int, handles '-', '.', ',' etc."""
            if not text or text.strip() in ("-", ""):
                return 0
            clean_text = text.strip().replace(".", "").replace(",", "").replace("'", "")
            try:
                return int(clean_text)
            except ValueError:
                return 0

        try:
           
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract pagination URLs
            pagination_links = soup.select("ul.tm-pagination a.tm-pagination__link")
            page_urls = set()
            for link in pagination_links:
                href = link.get("href")
                if href and ("/page/" in href or href.endswith("/plus/1")):
                    page_urls.add("https://www.transfermarkt.com" + href)

            def get_page_number(u):
                return int(u.split("/page/")[-1]) if "/page/" in u else 1

            page_urls = sorted(page_urls, key=get_page_number)

            for page_url in page_urls:
                response = self.session.get(page_url, headers=self.headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.select_one("div.responsive-table table")
                if not table:
                    continue

                rows = table.find("tbody").find_all("tr", recursive=False)
                for row in rows:
                    cols = row.find_all("td", recursive=False)
                    team_a_tag = cols[0].find("a")
                    team_img_tag = cols[0].find("img")

                    all_data.append({
                        "team": team_a_tag["title"] if team_a_tag else "",
                        "team_photo": team_img_tag["src"] if team_img_tag else "",
                        "appearances": _parse_int(cols[2].get_text(strip=True)),
                        "w": _parse_int(cols[3].get_text(strip=True)),
                        "d": _parse_int(cols[4].get_text(strip=True)),
                        "l": _parse_int(cols[5].get_text(strip=True)),
                        "points_scored": _parse_int(cols[6].get_text(strip=True)),
                        "goal": _parse_int(cols[7].get_text(strip=True)),
                        "assist": _parse_int(cols[8].get_text(strip=True)),
                        "sub_on": _parse_int(cols[9].get_text(strip=True)),
                        "sub_off": _parse_int(cols[10].get_text(strip=True)),
                        "yellow_cards": _parse_int(cols[11].get_text(strip=True)),
                        "second_yellow_cards": _parse_int(cols[12].get_text(strip=True)),
                        "red_cards": _parse_int(cols[13].get_text(strip=True)),
                        "own_goals": _parse_int(cols[14].get_text(strip=True)),
                        "penalty_goals": _parse_int(cols[15].get_text(strip=True)),
                        "minutes_played": _parse_int(cols[16].get_text(strip=True)),
                    })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error while processing {url} -> {e}")
            return pd.DataFrame()
        
#---------------------------------------------------------------------------------------------
   
    def extract_penalty_goals(self, url: str, is_goalkeeper=False)->tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extracts penalty goal data of a player from Transfermarkt.

        This scraping works on two tables: 'scored' (goals scored) and 'missed' (goals missed).
        It handles pagination for both tables, extracting data from all pages.

        Parameters:
        ----------
        url : str
            The URL of the player for extracting penalty goal data.
        headers : dict
            A dictionary of HTTP headers for the GET request (defaults to 'HEADERS').
        is_goalkeeper : bool
            A flag to indicate if the player is a goalkeeper (True) or not (False).

        Returns:
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            Two DataFrames:
            - df_scored: Data about scored penalty goals.
            - df_missed: Data about missed penalty goals.
        """
        all_data_scored = []
        all_data_missed = []

        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Get the total number of pages for 'scored' and 'missed' tables
                total_pages_scored = get_total_pages(soup, 0)
                total_pages_missed = get_total_pages(soup, 1)

                # Scraping for the 'scored' table
                for page in range(1, total_pages_scored + 1):
                    print(f"Extracting data from page {page} of 'scored'...")
                    scored_data = extract_data_from_page(url, page, 0, is_goalkeeper)
                    all_data_scored.extend(scored_data)

                # Scraping for the 'missed' table
                if total_pages_missed > 1:
                    for page in range(1, total_pages_missed + 1):
                        print(f"Extracting data from page {page} of 'missed'...")
                        missed_data = extract_data_from_page(url, page, 1, is_goalkeeper)
                        all_data_missed.extend(missed_data)
                else:
                    print("Extracting data from the first page of 'missed'...")
                    missed_data = extract_data_from_page(url, 1, 1)
                    all_data_missed.extend(missed_data)

                # Create DataFrames for both tables
                columns = ['season', 'competition', 'competition_photo', 'team', 'team_photo', 'date', 'home_team',
                            'home_team_photo', 'result', 'away_team', 'away_team_photo', 'minute', 'score_at_minute', 'player']

                # DataFrame for 'scored'
                df_scored = pd.DataFrame(all_data_scored, columns=columns)

                # DataFrame for 'missed'
                df_missed = pd.DataFrame(all_data_missed, columns=columns)

                return df_scored, df_missed

        except requests.RequestException as e:
            print(f"[ERROR] Error while making the GET request: {e}")
            return pd.DataFrame(), pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            return pd.DataFrame(), pd.DataFrame()

#---------------------------------------------------------------------------------------

    def extract_all_goals(self, url: str):
        """
        Extracts all goal data for a player from Transfermarkt, including match details, goal type,
        assists, and match outcomes.

        Parameters
        ----------
        url : str
            URL of the player's page on Transfermarkt containing goal data.

        Returns
        -------
        pd.DataFrame
            DataFrame with all goal details.
        """
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.find("div", class_="responsive-table").find("table")
            rows = table.find("tbody").find_all("tr")

            data = []
            current_season = None
            last_full_row = None

            for row in rows:
                cols = row.find_all("td")

                # Detect season row
                if len(cols) == 1 and "Season" in cols[0].get_text():
                    current_season = cols[0].get_text(strip=True)
                    continue

                if len(cols) < 4:
                    continue

                texts = [c.get_text(strip=True) for c in cols]

                # Main row with date
                if any("/" in t for t in texts):
                    season = current_season
                    competition = texts[1]
                    matchday = texts[2]
                    date = texts[3]
                    venue = texts[4]

                    imgs = row.find_all("img")
                    for_team = imgs[1]["title"] if len(imgs) > 1 else None
                    for_team_photo = imgs[1]["src"] if len(imgs) > 1 else None
                    opponent = imgs[2]["title"] if len(imgs) > 2 else None
                    opponent_photo = imgs[2]["src"] if len(imgs) > 2 else None

                    result = next((t for t in texts if ":" in t and "'" not in t), None)

                    position = texts[-5]
                    minute = texts[-4]
                    at_score = texts[-3]
                    type_of_goal = texts[-2]
                    goal_assist = texts[-1] if texts[-1] != type_of_goal else None

                    row_data = [
                        season, competition, matchday, date, venue,
                        for_team, for_team_photo, opponent, opponent_photo,
                        result, position, minute, at_score, type_of_goal, goal_assist
                    ]

                    last_full_row = row_data.copy()
                    data.append(row_data)

                # Secondary row (additional goal details)
                else:
                    if last_full_row:
                        new_row = last_full_row.copy()
                        tds = row.find_all("td")
                        goal_tds = [td for td in tds if not td.has_attr("colspan")]

                        minute = goal_tds[0].get_text(strip=True)
                        at_score = goal_tds[1].get_text(strip=True)
                        type_of_goal = goal_tds[2].get_text(strip=True)
                        goal_assist = (
                            goal_tds[3].get_text(strip=True)
                            if len(goal_tds) > 3 and goal_tds[3].get_text(strip=True) != ""
                            else None
                        )

                        new_row[11] = minute
                        new_row[12] = at_score
                        new_row[13] = type_of_goal
                        new_row[14] = goal_assist

                        data.append(new_row)

            columns = [
                "season", "competition", "matchday", "date", "venue",
                "for_team", "for_team_photo", "opponent", "opponent_photo",
                "result", "position", "minute", "at_score", "type_of_goal", "goal_assist"
            ]
            return pd.DataFrame(data, columns=columns)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing {url} -> {e}")
            return pd.DataFrame()

#-----------------------------------------------------------------------------------------------

    def extract_goals_by_minute(self, url: str):
        """
        Extracts the goal distribution by minute for a player from Transfermarkt.
        """
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Encuentra la tabla de distribución de goles
            table = soup.select_one("div.box div.responsive-table table.items")
            if not table:
                print(f"[INFO] Table not found for URL: {url}")
                return pd.DataFrame()

            rows = table.find("tbody").find_all("tr", recursive=False)
            all_data = []

            for row in rows:
                cols = row.find_all("td", recursive=False)
                if len(cols) < 13:
                    continue  # Saltar filas incompletas

                comp_img_tag = cols[1].find("img")
                team_img_tag = cols[3].find("img")
                team_a_tag = cols[3].find("a")

                all_data.append({
                    "season": cols[0].get_text(strip=True),
                    "competition": cols[2].get_text(strip=True),
                    "competition_photo": comp_img_tag["src"] if comp_img_tag else "",
                    "team": team_a_tag["title"] if team_a_tag and team_a_tag.has_attr("title") else "",
                    "team_photo": team_img_tag["src"] if team_img_tag else "",
                    "1-15": cols[4].get_text(strip=True),
                    "16-30": cols[5].get_text(strip=True),
                    "31-45": cols[6].get_text(strip=True),
                    "45+": cols[7].get_text(strip=True),
                    "46-60": cols[8].get_text(strip=True),
                    "61-75": cols[9].get_text(strip=True),
                    "76-90": cols[10].get_text(strip=True),
                    "90+": cols[11].get_text(strip=True),
                    "total": cols[12].get_text(strip=True),
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing the data for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------

    def extract_player_absences(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract a player's absences/history tables from a Transfermarkt page with two boxes.

        The page typically contains:
        - First box: Detailed injuries (season, injury, from, until, days, games missed)
        - Second box: Summary (season, days_total, injuries_total, games missed_total)

        Parameters
        ----------
        url : str
            URL of the player's absences/history page on Transfermarkt.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            Returns two DataFrames:
            - df_injury_history_player: DataFrame for the first box (detailed injuries)
            - df_total_injury_player: DataFrame for the second box (summary)
            Each DataFrame has the columns as described above.

        Raises
        ------
        requests.HTTPError
            If the HTTP request returned an unsuccessful status code.
        requests.RequestException
            For other network-related errors.
        Exception
            For any unexpected errors during the extraction or processing.
        """
        try:
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            boxes = soup.find_all("div", class_="box")

            # First box: detailed injuries
            df_injury_history_player = pd.DataFrame()
            if len(boxes) >= 1:
                table = boxes[0].select_one("div.responsive-table table")
                if table:
                    rows = table.find("tbody").find_all("tr", recursive=False)
                    all_data = []
                    for row in rows:
                        cols = row.find_all("td", recursive=False)
                        if len(cols) == 6:
                            all_data.append({
                                "season": cols[0].get_text(strip=True),
                                "injury": cols[1].get_text(strip=True),
                                "from": cols[2].get_text(strip=True),
                                "until": cols[3].get_text(strip=True),
                                "days": cols[4].get_text(strip=True),
                                "games_missed": cols[5].get_text(strip=True),
                            })
                    df_injury_history_player = pd.DataFrame(all_data)

            # Second box: summary injuries
            df_total_injury_player = pd.DataFrame()
            if len(boxes) >= 2:
                table = boxes[1].select_one("div.responsive-table table")
                if table:
                    rows = table.find("tbody").find_all("tr", recursive=False)
                    all_data = []
                    for row in rows:
                        cols = row.find_all("td", recursive=False)
                        if len(cols) == 4:
                            all_data.append({
                                "season": cols[0].get_text(strip=True),
                                "days_total": cols[1].get_text(strip=True),
                                "injuries_total": cols[2].get_text(strip=True),
                                "games_missed_total": cols[3].get_text(strip=True),
                            })
                    df_total_injury_player = pd.DataFrame(all_data)

            return df_injury_history_player, df_total_injury_player

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame(), pd.DataFrame()
        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing the data for {url} -> {e}")
            return pd.DataFrame(), pd.DataFrame()

#---------------------------------------------------------------------------------------------------------------------

    def extract_suspensions_absences(self, url: str)-> pd.DataFrame:
        """
        Extracts the 'Suspensions & Absences' table from a Transfermarkt player page.

        This function scrapes the 'Suspensions & Absences' data for a player from their Transfermarkt page
        and returns the relevant information about each absence, including the season, competition,
        duration, and number of games missed.

        Parameters
        ----------
        url : str
            URL of the player's suspensions/absences page on Transfermarkt.
        

        Returns
        -------
        pd.DataFrame
            DataFrame containing all rows of the 'Suspensions & Absences' table with the following columns:
            - season: The season the absence occurred in.
            - absence_type: Type of the absence (e.g., suspension, injury).
            - competition: Name of the competition the player was absent from.
            - competition_photo: URL to the competition's logo.
            - from_date: The start date of the absence.
            - until_date: The end date of the absence.
            - days: The number of days the player was absent.
            - games_missed: The number of games the player missed.

        Raises
        ------
        requests.HTTPError
            If the HTTP request returned an unsuccessful status code.
        requests.RequestException
            For other network-related errors (e.g., timeout, connection issues).
        Exception
            For unexpected errors during data extraction or parsing.
        """
        try:
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.box div.responsive-table table.items")
            if not table:
                print(f"[INFO] Table not found for URL: {url}")
                return pd.DataFrame()

            rows = table.find("tbody").find_all("tr", recursive=False)
            all_data = []

            for row in rows:
                cols = row.find_all("td", recursive=False)
                if len(cols) < 7:
                    continue  # Ignorar filas incompletas

                comp_img_tag = cols[2].find("img")

                all_data.append({
                    "season": cols[0].get_text(strip=True),
                    "absence_type": cols[1].get_text(strip=True),
                    "competition": comp_img_tag["title"] if comp_img_tag else "",
                    "competition_photo": comp_img_tag["src"] if comp_img_tag else "",
                    "from_date": cols[3].get_text(strip=True),
                    "until_date": cols[4].get_text(strip=True),
                    "days": cols[5].get_text(strip=True),
                    "games_missed": cols[6].get_text(strip=True),
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Network error occurred while fetching data for {url} -> {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing the data for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------
    
    def extract_mkt_value_overtime(self, url:str)-> pd.DataFrame:
        """
        Extract market value development over time for a player from Transfermarkt.

        This function scrapes the market value development data of a player over time from 
        Transfermarkt's API and processes it into a structured DataFrame.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page from which the player ID is extracted.
        

        Returns
        -------
        pd.DataFrame
            A DataFrame containing the player's market value development over time with the following columns:
            - 'date': The date of the market value.
            - 'market_value': The player's market value at the given date.
                - 'team': The team the player was with at the time.
                - 'team_photo': The team's logo.
                - 'player': The player's name.

            Raises
            ------
            requests.RequestException
                If there is an issue with the API request (e.g., network error, timeout).
            ValueError
                If the API response does not contain the expected data.
            Exception
                For any unexpected errors encountered during data extraction and processing.
            """
        try:
            player_id = url.split('/')[-1]
            response = requests.get(f'https://www.transfermarkt.com/ceapi/marketValueDevelopment/graph/{player_id}', headers=self.headers)
            response.raise_for_status()  # Ensure request was successful
            time.sleep(3)  # Respectful delay between requests

            # Parse the market value development data from the API response
            values = pd.DataFrame(response.json()['list'])

            # Fill missing team logos and handle empty values
            values['wappen'] = values['wappen'].apply(lambda x: np.nan if x == '' else x).ffill()

            # Extract player name from the URL
            player_name = response.json()['details_url'].split('/')[1].replace('-', ' ').title()
            values['player'] = player_name

            # Rename columns to match the desired output format
            mapeo = {'mw': 'market_value', 'datum_mw': "date", 'verein': "team", 'wappen': 'team_photo'}
            final_df = values.rename(columns=mapeo)

            return final_df

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except ValueError as e:
            print(f"[ERROR] Invalid data format received from the API for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing market value data for {url} -> {e}")
            return pd.DataFrame()

#-------------------------------------------------------------------------------------------------------------

    def extract_transfer_history(self, url: str)-> pd.DataFrame:
        """
        Extract the transfer history of a player from Transfermarkt.

        This function scrapes the transfer history of a player by calling the Transfermarkt API 
        and processes the data to return a structured DataFrame with transfer details.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page from which the player ID is extracted.
       
        Returns
        -------
        pd.DataFrame
            A DataFrame containing the player's transfer history with the following columns:
            - 'season': The season in which the transfer occurred.
            - 'market_value': The market value at the time of the transfer.
            - 'left_team': The club the player transferred from.
            - 'joined_team': The club the player transferred to.
            - 'left_team_photo': The logo of the club the player left.
            - 'joined_team_photo': The logo of the club the player joined.

        Raises
        ------
        requests.RequestException
            If there is an issue with the API request (e.g., network error, timeout).
        ValueError
            If the API response does not contain the expected data.
        Exception
            For any unexpected errors encountered during data extraction and processing.
        """
        try:
            player_id = url.split('/')[-1]
            response = requests.get(f'https://www.transfermarkt.com/ceapi/transferHistory/list/{player_id}', headers=self.headers)
            response.raise_for_status()  # Ensure request was successful
            time.sleep(3)  # Respectful delay between requests

            # Parse the transfer data from the API response
            transfer_df = pd.DataFrame(response.json()['transfers'])

            # Extract 'from' and 'to' club data
            df_from = transfer_df['from'].apply(pd.Series).rename(columns={'clubName': 'club_from'})['club_from']
            df_to = transfer_df['to'].apply(pd.Series).rename(columns={'clubName': 'club_to'})['club_to']

            # Concatenate the 'from' and 'to' data into the final dataframe
            final_df = pd.concat([transfer_df, df_from, df_to], axis=1)

            # Clean up the dataframe by extracting club logos and dropping unnecessary columns
            final_df['image_url_from'] = final_df['from'].apply(lambda x: x['clubEmblem-2x'] if isinstance(x, dict) else None)
            final_df['image_url_to'] = final_df['to'].apply(lambda x: x['clubEmblem-2x'] if isinstance(x, dict) else None)
            
            # Drop irrelevant columns
            columnas_eliminar = ['url', 'upcoming', 'to', 'from', 'showUpcomingHeader', 'showResetHeader', 'futureTransfer', 'dateUnformatted']
            final_df = final_df.drop(columns=columnas_eliminar)

            # Rename columns to match the desired output format
            mapeo = {'marketValue': 'market_value', 'club_from': "left_team", 'club_to': "joined_team", 
                    'image_url_from': 'left_team_photo', 'image_url_to': 'joined_team_photo'}
            final_df = final_df.rename(columns=mapeo)

            # Reorder columns to bring 'season' to the front
            final_df.insert(0, 'season', final_df.pop('season'))

            return final_df

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except ValueError as e:
            print(f"[ERROR] Invalid data format received from the API for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error occurred while processing transfer data for {url} -> {e}")
            return pd.DataFrame()

#-------------------------------------------------------------------------------------------------

    def extract_national_team_stats(self, url: str) -> pd.DataFrame:
        """
        Extract player statistics for national team appearances from Transfermarkt.

        This function scrapes a player's national team statistics from their Transfermarkt page, 
        including details about appearances, goals, assists, yellow/red cards, and more.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page containing the national team statistics.
        
        Returns
        -------
        pd.DataFrame
            A DataFrame containing the player's national team statistics, including:
            - Competition name and photo
            - Appearances, goals, assists, own goals
            - Substitutes in and out
            - Yellow cards, second yellow cards, red cards
            - Penalty goals, minutes per goal, and minutes played.
            Returns an empty DataFrame if no statistics are found.

        Raises
        ------
        requests.RequestException
            If there is an issue with the HTTP request (e.g., network error, timeout).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            table = soup.find('table', {'class': 'items'})
            if not table:
                print(f"[INFO] National team stats table not found for URL: {url}")
                return pd.DataFrame()

            all_data = []

            for row in table.find_all('tr')[1:]:  # Skip header
                cols = row.find_all('td')
                if len(cols) > 13:  # Ensure row has enough columns
                    comp_img = cols[0].find('img')
                    all_data.append({
                        "competition": cols[1].get_text(strip=True),
                        "competition_photo": comp_img['src'] if comp_img else "",
                        "appearances": cols[2].get_text(strip=True),
                        "goals": cols[3].get_text(strip=True),
                        "assists": cols[4].get_text(strip=True),
                        "own_goals": cols[5].get_text(strip=True),
                        "sub_on": cols[6].get_text(strip=True),
                        "sub_off": cols[7].get_text(strip=True),
                        "yellow_cards": cols[8].get_text(strip=True),
                        "second_yellow_cards": cols[9].get_text(strip=True),
                        "red_cards": cols[10].get_text(strip=True),
                        "penalty_goals": cols[11].get_text(strip=True),
                        "minutes_per_goal": cols[12].get_text(strip=True),
                        "minutes_played": cols[13].get_text(strip=True)
                    })

            df = pd.DataFrame(all_data)
            return df

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()
    
#------------------------------------------------------------------------------------------------------------------------

    def extract_player_achievements(self, url: str) -> pd.DataFrame:
        """
        Extract player achievements (titles) from the 'All titles' section of a Transfermarkt player page.

        This function scrapes the Transfermarkt player page to extract information about the player's 
        achievements, such as the season, title, team, and team logo.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page containing the 'All titles' section.
      
        Returns
        -------
        pd.DataFrame
            A DataFrame containing player achievements with the following columns:
            - 'season': The season in which the title was won.
            - 'title': The title or achievement name.
            - 'team': The team associated with the title.
            - 'team_logo': The URL of the team's logo image.
            Returns an empty DataFrame if no achievement data is found.

        Raises
        ------
        requests.RequestException
            If there is an issue with the HTTP request (e.g., network error, timeout).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
           
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Buscar el bloque correcto
            headline = soup.find("h2", string=lambda x: x and "All titles" in x)
            if not headline:
                print(f"[INFO] 'All titles' section not found: {url}")
                return pd.DataFrame()

            table = headline.find_next("table")
            tbody = table.find("tbody")

            records = []
            current_title = None

            for row in tbody.find_all("tr", recursive=False):

                # 🔹 Fila tipo categoría (bg_Sturm)
                if "bg_Sturm" in row.get("class", []):
                    title_cell = row.find("td")
                    current_title = title_cell.get_text(strip=True) if title_cell else None
                    continue

                # 🔹 Fila de temporada
                season_cell = row.find("td", class_="erfolg_table_saison")
                if not season_cell:
                    continue

                team_tag = row.find("td", class_="no-border-links")
                logo_tag = row.find("img")

                records.append({
                    "season": season_cell.get_text(strip=True),
                    "title": current_title,
                    "team": team_tag.get_text(strip=True) if team_tag else None,
                    "team_logo": logo_tag["src"] if logo_tag else None
                })

            # Filtrar registros que contienen "participant" en el título
            df = pd.DataFrame(records)
            df = df[~df["title"].str.contains("participant", case=False, na=False)]

            return df.reset_index(drop=True)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------

    def extract_debut_appearances(self, url: str) -> pd.DataFrame:
        """
        Extract debut appearance data for a player from Transfermarkt.

        Parameters
        ----------
        url : str
            Transfermarkt player debut appearance URL.
        headers : dict
            HTTP headers (User-Agent required).

        Returns
        -------
        pd.DataFrame
            Structured dataframe containing debut appearance data.
            Returns empty DataFrame if no debut appearance data is available.
        
        Raises
        ------
        requests.RequestException
            If there is an issue with the HTTP request (e.g., timeout, connection error).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
            
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            rows = table.select("tbody tr")

            all_data = []
            current_category = None

            for row in rows:
                # Detectar categoría (First Tier, Third Tier, etc.)
                if "bg_Sturm" in row.get("class", []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all("td")

                # Competition
                competition_link = cols[1].find("a")

                # Team
                club_link = cols[2].find("a")

                # Match
                match_cell = cols[4]
                match_links = match_cell.find_all("a")

                # Match result
                match_result_link = match_cell.find("a", class_="ergebnis-link")

                # Coach
                coach_link = cols[5].find("a")

                all_data.append({
                    "category": current_category,
                    "competition": competition_link.get_text(strip=True) if competition_link else None,
                    "competition_url": "https://www.transfermarkt.com" + competition_link["href"] if competition_link else None,
                    "team": club_link["title"] if club_link else None,
                    "team_url": "https://www.transfermarkt.com" + club_link["href"] if club_link else None,
                    "date": cols[3].get_text(strip=True),
                    "home_team": match_links[0]["title"] if len(match_links) > 0 else None,
                    "home_url": "https://www.transfermarkt.com" + match_links[0]["href"] if len(match_links) > 0 else None,
                    "result": match_result_link.get_text(strip=True) if match_result_link else None,
                    "away_team": match_links[-1]["title"] if len(match_links) > 1 else None,
                    "away_url": "https://www.transfermarkt.com" + match_links[-1]["href"] if len(match_links) > 1 else None,
                    "coach": coach_link.get_text(strip=True) if coach_link else None,
                    "age": cols[6].get_text(strip=True)
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()
    
#------------------------------------------------------------------------------------------------------------------------
 
    def extract_scoring_debuts(self, url: str) -> pd.DataFrame:
        """
        Extract scoring debut data for a player from Transfermarkt.

        Parameters
        ----------
        url : str
            Transfermarkt player scoring debut URL.

        Returns
        -------
        pd.DataFrame
            Structured dataframe containing scoring debut data.
            Returns empty DataFrame if no match data is available.
        """

        try:
            
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            if not table:
                print(f"[INFO] Table structure not found for URL: {url}")
                return pd.DataFrame()

            tbody = table.find("tbody")
            if not tbody:
                print(f"[INFO] Table body not found for URL: {url}")
                return pd.DataFrame()

            rows = tbody.find_all("tr")

            # Filter real data rows (exclude category rows)
            data_rows = [
                row for row in rows
                if "bg_Sturm" not in row.get("class", [])
            ]

            if not data_rows:
                print(f"[INFO] No scoring debut records found for player: {url}")
                return pd.DataFrame()

            all_data = []
            current_category = None

            for row in rows:

                # Category row
                if "bg_Sturm" in row.get("class", []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all("td")
                if len(cols) < 7:
                    continue

                # --- Competition ---
                competition_link = cols[1].find("a")

                # --- Team ---
                club_link = cols[2].find("a")

                # --- Match ---
                match_cell = cols[4]
                match_links = match_cell.find_all("a")
                match_result_link = match_cell.find("a", class_="ergebnis-link")

                all_data.append({
                    "category": current_category,
                    "competition": competition_link.get_text(strip=True) if competition_link else None,
                    "competition_url": "https://www.transfermarkt.com" + competition_link["href"]  if competition_link and competition_link.get("href") else None,
                    "team": club_link.get("title") if club_link else None,
                    "team_url": "https://www.transfermarkt.com" + club_link["href"]  if club_link and club_link.get("href") else None,
                    "date": cols[3].get_text(strip=True),
                    "home_team":  match_links[0].get("title") if len(match_links) > 0 else None,
                    "home_url": "https://www.transfermarkt.com" + match_links[0]["href"]  if len(match_links) > 0 and match_links[0].get("href") else None,
                    "result":  match_result_link.get_text(strip=True) if match_result_link else None,
                    "away_team": match_links[-1].get("title") if len(match_links) > 1 else None,
                    "away_url": "https://www.transfermarkt.com" + match_links[-1]["href"] if len(match_links) > 1 and match_links[-1].get("href") else None,
                    "goal_resulting_in": cols[5].get_text(strip=True),
                    "age_at_that_time": cols[6].get_text(strip=True)
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------

    def extract_greatest_wins(self, url: str) -> pd.DataFrame:
        """
        Extract scoring debut data for a player from Transfermarkt.

        Parameters
        ----------
        url : str
            Transfermarkt player scoring debut URL.
    
        Returns
        -------
        pd.DataFrame
            Structured dataframe containing scoring debut data.
            Returns empty DataFrame if no match data is available.
        """

        try:
            
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            if not table:
                print(f"[INFO] Table structure not found for URL: {url}")
                return pd.DataFrame()

            tbody = table.find("tbody")
            if not tbody:
                print(f"[INFO] Table body not found for URL: {url}")
                return pd.DataFrame()

            rows = tbody.find_all("tr")

            # Filter real data rows (exclude category rows)
            data_rows = [
                row for row in rows
                if "bg_Sturm" not in row.get("class", [])
            ]

            if not data_rows:
                print(f"[INFO] No scoring debut records found for player: {url}")
                return pd.DataFrame()

            all_data = []
            current_category = None

            for row in rows:

                # Category row
                if "bg_Sturm" in row.get("class", []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all("td")
                if len(cols) < 8:
                    continue

                # --- Competition ---
                competition_link = cols[1].find("a")

                # --- Team ---
                club_link = cols[2].find("a")

                # --- Match ---
                match_cell = cols[4]
                match_links = match_cell.find_all("a")
                match_result_link = match_cell.find("a", class_="ergebnis-link")

                all_data.append({
                    "category": current_category,
                    "competition": competition_link.get_text(strip=True) if competition_link else None,
                    "competition_url": "https://www.transfermarkt.com" + competition_link["href"]  if competition_link and competition_link.get("href") else None,
                    "team": club_link.get("title") if club_link else None,
                    "team_url": "https://www.transfermarkt.com" + club_link["href"]  if club_link and club_link.get("href") else None,
                    "date": cols[3].get_text(strip=True),
                    "home_team":  match_links[0].get("title") if len(match_links) > 0 else None,
                    "home_url": "https://www.transfermarkt.com" + match_links[0]["href"]  if len(match_links) > 0 and match_links[0].get("href") else None,
                    "result":  match_result_link.get_text(strip=True) if match_result_link else None,
                    "away_team": match_links[-1].get("title") if len(match_links) > 1 else None,
                    "away_url": "https://www.transfermarkt.com" + match_links[-1]["href"] if len(match_links) > 1 and match_links[-1].get("href") else None,
                    "goals":cols[5].get_text(strip=True),
                    "assists": cols[6].get_text(strip=True),
                    "minutes_played": cols[7].get_text(strip=True),

                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------

    def extract_heaviest_losses(self, url: str) -> pd.DataFrame:
        """
        Extract scoring debut data for a player from Transfermarkt.

        Parameters
        ----------
        url : str
            Transfermarkt player scoring debut URL.
        
        Returns
        -------
        pd.DataFrame
            Structured dataframe containing scoring debut data.
            Returns empty DataFrame if no match data is available.
        """

        try:
            
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            if not table:
                print(f"[INFO] Table structure not found for URL: {url}")
                return pd.DataFrame()

            tbody = table.find("tbody")
            if not tbody:
                print(f"[INFO] Table body not found for URL: {url}")
                return pd.DataFrame()

            rows = tbody.find_all("tr")

            # Filter real data rows (exclude category rows)
            data_rows = [
                row for row in rows
                if "bg_Sturm" not in row.get("class", [])
            ]

            if not data_rows:
                print(f"[INFO] No scoring debut records found for player: {url}")
                return pd.DataFrame()

            all_data = []
            current_category = None

            for row in rows:

                # Category row
                if "bg_Sturm" in row.get("class", []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all("td")
                if len(cols) < 6:
                    continue

                # --- Competition ---
                competition_link = cols[1].find("a")

                # --- Team ---
                club_link = cols[2].find("a")

                # --- Match ---
                match_cell = cols[4]
                match_links = match_cell.find_all("a")
                match_result_link = match_cell.find("a", class_="ergebnis-link")

                all_data.append({
                    "category": current_category,
                    "competition": competition_link.get_text(strip=True) if competition_link else None,
                    "competition_url": "https://www.transfermarkt.com" + competition_link["href"]  if competition_link and competition_link.get("href") else None,
                    "team": club_link.get("title") if club_link else None,
                    "team_url": "https://www.transfermarkt.com" + club_link["href"]  if club_link and club_link.get("href") else None,
                    "date": cols[3].get_text(strip=True),
                    "home_team":  match_links[0].get("title") if len(match_links) > 0 else None,
                    "home_url": "https://www.transfermarkt.com" + match_links[0]["href"]  if len(match_links) > 0 and match_links[0].get("href") else None,
                    "result":  match_result_link.get_text(strip=True) if match_result_link else None,
                    "away_team": match_links[-1].get("title") if len(match_links) > 1 else None,
                    "away_url": "https://www.transfermarkt.com" + match_links[-1]["href"] if len(match_links) > 1 and match_links[-1].get("href") else None,
                    "minutes_played": cols[5].get_text(strip=True),

                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------

    def extract_most_goals_in_one_match(self, url: str) -> pd.DataFrame:
        """
        Extract match contribution data (goals, assists, minutes played) for a player from Transfermarkt.

        This function scrapes a player's Transfermarkt page to extract data on their most goals, assists, 
        and minutes played in a single match. It returns a structured DataFrame containing relevant match statistics 
        such as competition, date, clubs involved, and goals and assists contributions.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page containing the match contribution data.

        Returns
        -------
        pd.DataFrame
            A DataFrame containing match contribution details such as:
            - Competition name and URL
            - Club names and URLs
            - Match date
            - Home and away teams
            - Match result
            - Goals, assists, and minutes played.
            Returns an empty DataFrame if no match records are found.

        Raises
        ------
        requests.RequestException
            If there is an issue with the HTTP request (e.g., network error, timeout).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
            
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            if not table:
                print(f"[INFO] Table not found: {url}")
                return pd.DataFrame()

            tbody = table.find("tbody")
            if not tbody:
                print(f"[INFO] Table body not found: {url}")
                return pd.DataFrame()

            rows = tbody.find_all("tr")

            # Exclude category rows
            data_rows = [row for row in rows if "bg_Sturm" not in row.get("class", [])]

            if not data_rows:
                print(f"[INFO] No match contribution records found: {url}")
                return pd.DataFrame()

            all_data = []
            current_category = None

            for row in rows:
                # Category row
                if "bg_Sturm" in row.get("class", []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all("td")
                if len(cols) < 8:
                    continue

                # Extract data for competition, club, match, and result
                competition_link = cols[1].find("a")
                club_link = cols[2].find("a")
                match_cell = cols[4]
                match_links = match_cell.find_all("a")
                result_link = match_cell.find("a", class_="ergebnis-link")

                all_data.append({
                    "category": current_category,
                    "competition": competition_link.get_text(strip=True) if competition_link else None,
                    "competition_url": "https://www.transfermarkt.com" + competition_link["href"] if competition_link and competition_link.get("href") else None,
                    "club": club_link.get("title") if club_link else None,
                    "club_url": "https://www.transfermarkt.com" + club_link["href"] if club_link and club_link.get("href") else None,
                    "date": cols[3].get_text(strip=True),
                    "home_team": match_links[0].get("title") if len(match_links) > 0 else None,
                    "home_url": "https://www.transfermarkt.com" + match_links[0]["href"] if len(match_links) > 0 and match_links[0].get("href") else None,
                    "result": result_link.get_text(strip=True) if result_link else None,
                    "away_team": match_links[-1].get("title") if len(match_links) > 1 else None,
                    "away_url": "https://www.transfermarkt.com" + match_links[-1]["href"] if len(match_links) > 1 and match_links[-1].get("href") else None,
                    "goals": cols[5].get_text(strip=True),
                    "assists": cols[6].get_text(strip=True),
                    "minutes_played": cols[7].get_text(strip=True)
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------

    def extract_most_goalassists_in_one_match(self, url: str) -> pd.DataFrame:
        """
        Extract match contribution data (goals, assists) for a player from Transfermarkt.

        This function scrapes a player's page on Transfermarkt to extract data on their 
        most goals and assists in a single match. It returns a structured DataFrame 
        containing relevant match statistics such as competition, date, clubs involved, 
        and the number of goals and assists.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page containing the match contribution data.

        Returns
        -------
        pd.DataFrame
            A DataFrame containing the match contribution details, such as:
            - Competition name and URL
            - Club names and URLs
            - Match date
            - Home and away teams
            - Match result
            - Goals, assists, and total goals+assists in the match.
            Returns an empty DataFrame if no match records are found.

        Raises
        ------
        requests.RequestException
            If there is an issue with the HTTP request (e.g., network error, timeout).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
            
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.select_one("div.responsive-table table")
            if not table:
                print(f"[INFO] Table not found: {url}")
                return pd.DataFrame()

            tbody = table.find("tbody")
            if not tbody:
                print(f"[INFO] Table body not found: {url}")
                return pd.DataFrame()

            rows = tbody.find_all("tr")

            # Exclude category rows
            data_rows = [row for row in rows if "bg_Sturm" not in row.get("class", [])]

            if not data_rows:
                print(f"[INFO] No match contribution records found: {url}")
                return pd.DataFrame()

            all_data = []
            current_category = None

            for row in rows:
                # Category row
                if "bg_Sturm" in row.get("class", []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all("td")
                if len(cols) < 8:
                    continue

                # Extract data for competition, club, match, and result
                competition_link = cols[1].find("a")
                club_link = cols[2].find("a")
                match_cell = cols[4]
                match_links = match_cell.find_all("a")
                result_link = match_cell.find("a", class_="ergebnis-link")

                all_data.append({
                    "category": current_category,
                    "competition": competition_link.get_text(strip=True) if competition_link else None,
                    "competition_url": "https://www.transfermarkt.com" + competition_link["href"] if competition_link and competition_link.get("href") else None,
                    "club": club_link.get("title") if club_link else None,
                    "club_url": "https://www.transfermarkt.com" + club_link["href"] if club_link and club_link.get("href") else None,
                    "date": cols[3].get_text(strip=True),
                    "home_team": match_links[0].get("title") if len(match_links) > 0 else None,
                    "home_url": "https://www.transfermarkt.com" + match_links[0]["href"] if len(match_links) > 0 and match_links[0].get("href") else None,
                    "result": result_link.get_text(strip=True) if result_link else None,
                    "away_team": match_links[-1].get("title") if len(match_links) > 1 else None,
                    "away_url": "https://www.transfermarkt.com" + match_links[-1]["href"] if len(match_links) > 1 and match_links[-1].get("href") else None,
                    "goals": cols[5].get_text(strip=True),
                    "assists": cols[6].get_text(strip=True),
                    "goals_assists": cols[7].get_text(strip=True)
                })

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return pd.DataFrame()

#------------------------------------------------------------------------------------------------------------------------

    def extract_squad_number_history_and_national_team(self, url: str):
        """
        Extract the squad number history and national team squad number data for a player from Transfermarkt.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page containing squad number history.

        Returns
        -------
        tuple
            A tuple containing two DataFrames:
            - df_squad_number_team: Squad number data for the player's club teams.
            - df_squad_number_national_team: Squad number data for the player's national team.

        Raises
        ------
        ValueError
            If the page does not contain at least two squad number tables.
        requests.RequestException
            If there is an issue with the HTTP request (e.g., network error, timeout).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
            
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            tables = soup.find_all("table", class_="items")

            if len(tables) < 2:
                raise ValueError("Expected at least 2 squad number tables")

            df_squad_number_team = parse_squad_number_table(tables[0])
            df_squad_number_national_team = parse_squad_number_table(tables[1])

            return df_squad_number_team, df_squad_number_national_team

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return None, None

        except ValueError as e:
            print(f"[ERROR] Value error: {e}")
            return None, None

        except Exception as e:
            print(f"[ERROR] Unexpected parsing error for {url} -> {e}")
            return None, None

#------------------------------------------------------------------------------------------------------------------------

    def extract_games_played_together(self, url:str)-> pd.DataFrame:
        """
            Extract data about games played together by a player from Transfermarkt.

            Parameters
            ----------
            url : str
                The URL of the Transfermarkt player page that contains the games played together data.

            Returns
            -------
            pd.DataFrame
                A DataFrame containing the player details for each game played together, including:
                player name, player URL, player photo, position, matches played, teams, PPG (points per game),
                wins, draws, losses, highest market value, joint goal participation, and minutes played.

            Raises
            ------
            requests.RequestException
                If there is an issue with the HTTP request (e.g., network error, timeout).
            Exception
                For any unexpected errors encountered during parsing or data extraction.
            """
        try:
           
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()  

            first_url = url + "/page/1"
            response = requests.get(first_url, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            pagination_links = soup.select("li.tm-pagination__list-item a.tm-pagination__link")
            page_numbers = []

            for link in pagination_links:
                href = link.get("href", "")
                match = re.search(r'page/(\d+)', href)
                if match:
                    page_numbers.append(int(match.group(1)))

            if page_numbers:
                total_pages = max(page_numbers)
            else:
                total_pages = 1

            print("Total pages:", total_pages)
            print(" ")

            all_data = []
            for page in range(1, total_pages + 1):
                    print("Scraping page...", page)

                    url_pagina = url + f"/page/{page}"
                    response = requests.get(url_pagina, headers=self.headers)
                    soup = BeautifulSoup(response.text, "html.parser")
                    table = soup.find("table", class_="items")
                    rows = table.find("tbody").find_all("tr", recursive=False)


                    for row in rows:
                        cells = row.find_all("td", recursive=False)

                        # Jugador y tabla anidada
                        player_table = cells[0].find("table", class_="inline-table")
                        player_tag = player_table.find("a")
                        

                        all_data.append({
                                    "player":  player_tag.text.strip(),
                                    "player_url": "https://www.transfermarkt.com" + player_tag["href"],
                                    "player_photo": player_table.find("img")["data-src"] if player_table.find("img") else None,
                                    "position":  player_table.find_all("tr")[1].find("td").text.strip(),
                                    "matches": cells[1].text.strip(),
                                    "teams": cells[2].text.strip(),
                                    "ppg": cells[3].text.strip(),
                                    "w": cells[4].text.strip(),
                                    "d": cells[5].text.strip(),
                                    "l": cells[6].text.strip(),
                                    "highest_market_value": cells[7].text.strip(),
                                    "joint_goal_participation":  cells[8].text.strip(),
                                    "minutes":  cells[9].text.strip()

                        })
                    print(f"✅ Page {page} scraped")
                    time.sleep(1)  

            return pd.DataFrame(all_data)
        
        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error during parsing or data extraction for {url} -> {e}")
            return pd.DataFrame()
    
#------------------------------------------------------------------------------------------------------------------------

    def extract_games_against_player(self,url: str) -> pd.DataFrame:
        """
        Extract data about games played against a player from Transfermarkt.

        Parameters
        ----------
        url : str
            The URL of the Transfermarkt player page containing the games played against data.

        Returns
        -------
        pd.DataFrame
            A DataFrame containing details about players played against, including:
            player name, player URL, player photo, position, matches played, teams,
            PPG (points per game), wins, draws, losses, highest market value, and minutes played.

        Raises
        ------
        requests.RequestException
            If there is an issue with the HTTP request (e.g., network error, timeout).
        Exception
            For any unexpected errors encountered during parsing or data extraction.
        """
        try:
            
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()  

            first_url = url + "/page/1"
            response = requests.get(first_url, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            pagination_links = soup.select("li.tm-pagination__list-item a.tm-pagination__link")
            page_numbers = []

            # Extract total number of pages
            for link in pagination_links:
                href = link.get("href", "")
                match = re.search(r'page/(\d+)', href)
                if match:
                    page_numbers.append(int(match.group(1)))

            if page_numbers:
                total_pages = max(page_numbers)
            else:
                total_pages = 1

            print("Total pages:", total_pages)
            print(" ")

            all_data = []
            for page in range(1, total_pages + 1):
                print(f"Scraping page {page}...")

                url_pagina = url + f"/page/{page}"
                response = requests.get(url_pagina, headers=self.headers)
                soup = BeautifulSoup(response.text, "html.parser")
                table = soup.find("table", class_="items")
                rows = table.find("tbody").find_all("tr", recursive=False)

                for row in rows:
                    cells = row.find_all("td", recursive=False)

                    # Extract player data from the nested player table
                    player_table = cells[0].find("table", class_="inline-table")
                    player_tag = player_table.find("a")

                    all_data.append({
                        "player": player_tag.text.strip(),
                        "player_url": "https://www.transfermarkt.com" + player_tag["href"],
                        "player_photo": player_table.find("img")["data-src"] if player_table.find("img") else None,
                        "position": player_table.find_all("tr")[1].find("td").text.strip(),
                        "matches": cells[1].text.strip(),
                        "teams": cells[2].text.strip(),
                        "ppg": cells[3].text.strip(),
                        "w": cells[4].text.strip(),
                        "d": cells[5].text.strip(),
                        "l": cells[6].text.strip(),
                        "highest_market_value": cells[7].text.strip(),
                        "minutes": cells[8].text.strip()
                    })

                print(f"✅ Page {page} scraped")
                time.sleep(1)  

            return pd.DataFrame(all_data)

        except requests.RequestException as e:
            print(f"[ERROR] Request failed for {url} -> {e}")
            return pd.DataFrame()

        except Exception as e:
            print(f"[ERROR] Unexpected error during parsing or data extraction for {url} -> {e}")
            return pd.DataFrame()