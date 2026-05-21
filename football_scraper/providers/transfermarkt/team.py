import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from football_scraper.providers.transfermarkt.constants import DEFAULT_HEADERS
from football_scraper.providers.transfermarkt.utils import  extract_signed_from, extract_qualification_legend, parse_general_table, parse_home_away_table, extract_transfer_record_current_next_sesion_transfers, extract_players_table_current_next_sesion_transfers, extract_summary_current_next_sesion_transfers, safe_int,parse_group_stage_opponents, parse_knockout_opponents, extract_legs_from_row_with_url 

class TransfermarktTeamScraper:
    def __init__(self, session, competition_service, headers=None):
        self.session = session
        self.competition_service = competition_service
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_teams_league(self, league: str, season: int) -> pd.DataFrame:
        """
        Extract teams and their data for a given league and season from Transfermarkt.

        Args:
            league (str): The display name of the league.
            season (int): The season year.

        Returns:
            pd.DataFrame: DataFrame containing teams with squad size, age, foreigners, market values, etc.
        """
        comp = self.competition_service.get_by_name(league)
        url = f"{comp['url']}/plus/?saison_id={season}"

        all_data = []

        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.find("table", class_="items")
        if not table:
            return pd.DataFrame()

        rows = table.select("tbody tr.odd, tbody tr.even")

        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 7:
                continue

            club_link = tds[1].find("a")
            if not club_link:
                continue

            logo_img = tds[0].find("img", class_="tiny_wappen")

            all_data.append({
                "club_id": club_link["href"].split("/verein/")[1].split("/")[0],
                "club_name": club_link.text.strip(),
                "club_url": f"https://www.transfermarkt.com{club_link['href']}",
                "logo": logo_img["src"] if logo_img else None,
                "squad_size": tds[2].text.strip(),
                "avg_age": tds[3].text.strip(),
                "foreigners": tds[4].text.strip(),
                "avg_market_value": tds[5].text.strip(),
                "total_market_value": tds[6].text.strip(),
                "season": season,
                "league": league.split('(')[0].strip()
            })

        return pd.DataFrame(all_data)
    
#--------------------------------------------------------------------------------------------     

    def extract_full_squad_details(self, team_url: str, league: str, season: int) -> pd.DataFrame:
        """
        Extract detailed squad information for a given team, league, and season from Transfermarkt.

        Args:
            team_url (str): URL of the team page on Transfermarkt.
            league (str): League display name.
            season (int): Season year.


        Returns:
            pd.DataFrame: DataFrame containing detailed player information including
                        personal info, club info, and market values.
        """
        all_data = []

       
        response = self.session.get(team_url, headers=self.headers)
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("tbody tr.odd, tbody tr.even") or soup.select("tbody tr")

        # Detect if it is a past season (affects table structure)
        is_past_season = False
        if rows and len(rows[0].find_all("td")) >= 8:
            td7_img = rows[0].find_all("td")[7].find("img")
            is_past_season = td7_img and "wappen" in td7_img.get("src", "")

        for row in rows:
            tds = row.find_all("td")
            if len(tds) < 13:
                continue

            try:
                # Shirt number
                shirt_div = tds[0].find("div", class_="rn_nummer")
                shirt_number = shirt_div.text.strip() if shirt_div else None

                # Player info
                player_table = tds[1].find("table", class_="inline-table")
                if player_table:
                    player_link = player_table.find("a", href=lambda x: x and "/profil/spieler/" in x)
                    name = player_link.text.strip() if player_link else None
                    player_url = f"https://www.transfermarkt.com{player_link['href']}" if player_link else None

                    img_tag = player_table.find("img", class_="bilderrahmen-fixed")
                    player_image_url = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

                    rows_in_table = player_table.find_all("tr")
                    position = rows_in_table[1].find("td").text.strip() if len(rows_in_table) > 1 else None
                else:
                    name = player_url = player_image_url = position = None

                # Date of birth and age
                dob_text = tds[5].text.strip()
                date_of_birth = re.search(r'(\d{2}/\d{2}/\d{4})', dob_text)
                age = re.search(r'\((\d+)\)', dob_text)

                # Nationality
                flag_img = tds[6].find("img", class_="flaggenrahmen")

                offset = 1 if is_past_season else 0

                # Current club (past season only)
                if is_past_season:
                    current_club_img = tds[7].find("img")
                    current_club = current_club_img.get("alt") if current_club_img else None
                    current_club_logo = current_club_img.get("src") if current_club_img else None
                else:
                    current_club = current_club_logo = None

                # Height
                height_text = tds[7 + offset].text.strip()
                height = None
                if height_text:
                    height_match = re.search(r'(\d+[,.]?\d*)', height_text)
                    height = height_match.group(1).replace(',', '.') if height_match else None

                # Club signed from
                club_img = tds[10 + offset].find("img")

                # Market value
                mv_link = tds[12].find("a")

                all_data.append({
                    "shirt_number": shirt_number,
                    "name": name,
                    "player_url": player_url,
                    "player_image_url": player_image_url,
                    "position": position,
                    "date_of_birth": date_of_birth.group(1) if date_of_birth else None,
                    "age": int(age.group(1)) if age else None,
                    "nation": flag_img.get("title") if flag_img else None,
                    "nation_photo": flag_img.get("src") if flag_img else None,
                    "current_club": current_club,
                    "current_club_logo": current_club_logo,
                    "height": height,
                    "foot":  tds[8 + offset].text.strip() or None,
                    "joined": tds[9 + offset].text.strip() or None,
                    "signed_from": club_img.get("alt") if club_img else tds[10 + offset].text.strip() or None,
                    "signed_from_logo": club_img.get("src") if club_img else None,
                    "contract_until": None if is_past_season else (tds[11].text.strip() or None),
                    "market_value": mv_link.text.strip() if mv_link else tds[12].text.strip(),
                    "league": league,
                    "season": season
                })

            except Exception as e:
                print(f"Error processing row: {e}")
                continue

        return pd.DataFrame(all_data)

#--------------------------------------------------------------------------------------------     

    def extract_agent_and_contracts(self, url: str) -> pd.DataFrame:
        """
        Extract player contract and agent information from a Transfermarkt team page.

        Args:
            url (str): URL of the team squad/contract page.
 
        Returns:
            pd.DataFrame: DataFrame containing player info, contract details, and agent info.
        """

        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.select_one("table.items")
        if not table:
            raise ValueError("Table not found on the page")

        all_data = []
        rows = table.select("tbody tr.odd, tbody tr.even")
        
        for row in rows:
            cols = row.find_all("td")

            # Player URL
            player_link = cols[3].select_one("td.hauptlink a")

            # Player photo
            img_tag = cols[2].find("img")

            # Nationality and flag
            flag_img = cols[6].find("img")

            # Agent info
            agent_link = cols[11].find("a", href=True)

            all_data.append({
                "shirt_number": cols[0].text.strip(),
                "player": cols[3].text.strip(),
                "player_photo": img_tag.get("src") if img_tag else None,
                "player_url": f"https://www.transfermarkt.com{player_link['href']}" if player_link else None,
                "position": cols[4].text.strip(),
                "age": cols[5].text.strip(),
                "nation": flag_img.get("title") if flag_img else None,
                "nation_photo": flag_img.get("src") if flag_img else None,
                "joined": cols[7].text.strip(),
                "contract_expires":  cols[8].text.strip(),
                "contract_option": cols[9].text.strip(),
                "latest_extension": cols[10].text.strip(),
                "agent": agent_link.text.strip() if agent_link else None,
                "agent_url": f"https://www.transfermarkt.com{agent_link['href']}" if agent_link else None
            })

        return pd.DataFrame(all_data)

#--------------------------------------------------------------------------------------------     

    def extract_suspensions_and_injuries(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract player injuries and suspensions from a Transfermarkt page.

        Args:
            url (str): URL of the injuries/suspensions page.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]: Two DataFrames: (injuries, suspensions)
        """
    
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        boxes = soup.find_all("div", class_="box")

        if len(boxes) < 2:
            raise ValueError("Expected at least two boxes for injuries and suspensions")

        # ---------- 1️⃣ Injuries ----------
        injuries_table = boxes[0].find("table", class_="items")
        data_injuries = []

        for row in injuries_table.select("tbody tr.odd, tbody tr.even"):
            cols = row.find_all("td")
            link_tag = row.find("a", href=True)

            img_tag = row.find("img")

            data_injuries.append({
                "player": link_tag.get_text(strip=True) if link_tag else "-",
                "player_url": f"https://www.transfermarkt.com{link_tag['href']}" if link_tag else None,
                "player_photo": img_tag.get("data-src") if img_tag else None,
                "position": row.find("table", class_="inline-table").find_all("tr")[1].get_text(strip=True) if row.find("table", class_="inline-table") else None,
                "age": cols[4].get_text(strip=True) if len(cols) > 4 else None,
                "reason": cols[5].get_text(strip=True) if len(cols) > 5 else None,
                "since": cols[6].get_text(strip=True) if len(cols) > 6 else None,
                "expected_return": cols[7].get_text(strip=True) if len(cols) > 7 else None,
                "games_missed": cols[8].get_text(strip=True) if len(cols) > 8 else None,
                "days": cols[9].get_text(strip=True) if len(cols) > 9 else None,
                "market_value": cols[10].get_text(strip=True) if len(cols) > 10 else None,
            })

        # ---------- 2️⃣ Suspensions ----------
        suspension_table = boxes[1].find("table", class_="items")
        data_suspension = []

        for row in suspension_table.select("tbody tr.odd, tbody tr.even"):
            cols = row.find_all("td")
            link_tag = row.find("a", href=True)

            img_tag = row.find("img")

            data_suspension.append({
                "player": link_tag.get_text(strip=True) if link_tag else "-",
                "player_url":  f"https://www.transfermarkt.com{link_tag['href']}" if link_tag else None,
                "player_photo": img_tag.get("data-src") if img_tag else None,
                "position": row.find("table", class_="inline-table").find_all("tr")[1].get_text(strip=True) if row.find("table", class_="inline-table") else None,
                "age": cols[4].get_text(strip=True) if len(cols) > 4 else None,
                "yellow_cards": cols[5].get_text(strip=True) if len(cols) > 5 else None,
                "appearances": cols[6].get_text(strip=True) if len(cols) > 6 else None,
                "cards_per_match": cols[7].get_text(strip=True) if len(cols) > 7 else None,
                "market_value": cols[8].get_text(strip=True) if len(cols) > 8 else None,
            })

        return pd.DataFrame(data_injuries), pd.DataFrame(data_suspension)
    

    def extract_national_team_players(self, url: str) -> pd.DataFrame:
        """
        Extract national team player information from a Transfermarkt page.

        Args:
            url (str): URL of the national team squad page.

        Returns:
            pd.DataFrame: DataFrame containing player info, appearances, goals, debut, and market value.
        """
        all_data = []
       
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for row in soup.select("tbody > tr"):
            name_tag = row.select_one("td.hauptlink a[title]")

            # Position
            position_tag = row.select_one("table.inline-table tr:nth-of-type(2) td")

            # Age
            age_tag = row.select("td.zentriert")

            # Nationality (second td.hauptlink)
            td_nat = row.select("td.hauptlink")
            nationality = nationality_link = None
            if len(td_nat) > 1:
                a_tags = td_nat[1].find_all("a")
                if a_tags:
                    nationality = a_tags[-1].text.strip()
                    nationality_link = "https://www.transfermarkt.com" + a_tags[-1]["href"]

            # Appearances, goals, debut
            caps = goals = debut = None
            zentriert_links = row.select("td.zentriert a")
            if len(zentriert_links) >= 2:
                caps = zentriert_links[0].text.strip()
                goals = zentriert_links[1].text.strip()
            if len(age_tag) > 3:
                debut = age_tag[3].text.strip()

            # Market value
            mv_tag = row.select_one("td.rechts.hauptlink")

            all_data.append({
                "player": name_tag.text.strip(),
                "position": position_tag.text.strip() if position_tag else None,
                "age": age_tag[0].text.strip() if len(age_tag) > 0 else None,
                "nationality": nationality,
                "nationality_flag": nationality_link,
                "appearances": caps,
                "goals": goals,
                "debut": debut,
                "market_value": mv_tag.text.strip() if mv_tag else None
            })

        return pd.DataFrame(all_data)

    def extract_foreigners_team(self, team_url: str) -> pd.DataFrame:
        """
        Extract information about foreign players in a team from Transfermarkt.

        Args:
            team_url (str): URL of the team's squad page.

        Returns:
            pd.DataFrame: DataFrame containing player info, nationality, height, and previous club.
        """       
        response = self.session.get(team_url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("tbody tr.odd, tbody tr.even") or soup.select("tbody tr")

        all_data = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 13:
                continue

            # Player block
            player_block = cols[1]
            player_link = player_block.find("a", href=True, title=True)

            player_photo_tag = player_block.find("img", class_="bilderrahmen")

            dob_text = cols[5].text.strip()
            date_of_birth_match = re.search(r'(\d{2}/\d{2}/\d{4})', dob_text)
            age_match = re.search(r'\((\d+)\)', dob_text)

            # Nationality
            flag_img = cols[6].find("img")

            # Height
            height_text = cols[7].text.strip()
            height_match = re.search(r'(\d+[,.]?\d*)', height_text)

            # Signed from
            signed_data = extract_signed_from(cols[11])

            all_data.append({
                "shirt_number": cols[0].get_text(strip=True),
                "player": player_link.get_text(strip=True) if player_link else None,
                "player_url":  f"https://www.transfermarkt.com{player_link['href']}" if player_link else None,
                "player_photo": player_photo_tag.get("src") if player_photo_tag else None,
                "position": cols[4].text.strip(),
                "date_of_birth": date_of_birth_match.group(1) if date_of_birth_match else None,
                "age":  int(age_match.group(1)) if age_match else None,
                "nation": flag_img.get("title") if flag_img else None,
                "nation_photo": flag_img.get("src") if flag_img else None,
                "height": height_match.group(1).replace(',', '.') if height_match else None,
                "foot": cols[8].get_text(strip=True),
                "joined": cols[9].get_text(strip=True),
                "contract_expires": cols[10].get_text(strip=True),
                "signed_from_name": signed_data["signed_from"],
                "signed_from_url": signed_data["signed_from_url"],
                "signed_from_logo": signed_data["signed_from_logo"],
                "market_value": cols[12].get_text(strip=True)
            })

        return pd.DataFrame(all_data)

    def extract_experience_team(self, url: str) -> pd.DataFrame:
        """
        Extract player experience data for a team from Transfermarkt.

        Args:
            url (str): URL of the team's experience/appearances page.


        Returns:
            pd.DataFrame: DataFrame containing player experience: appearances, goals, minutes, and clubs.
        """
        all_data = []


        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        rows = soup.select("tbody tr.odd, tbody tr.even")

        for row in rows:
            cols = row.find_all("td")

            # Nationality
            nation_img = cols[4].find("img")

            # Player info
            name_tag = cols[2].find("a")
            name_photo_tag = cols[1].find("img")

            all_data.append({
                "player": name_tag.text.strip() if name_tag else None,
                "player_url": f"https://www.transfermarkt.com{name_tag['href']}" if name_tag else None,
                "player_photo": name_photo_tag.get("data-src") if name_photo_tag else None,
                "position": cols[3].text.strip(),
                "nation": nation_img.get("title") if nation_img else None,
                "nation_flag": nation_img.get("src") if nation_img else None,
                "season": cols[5].text.strip(),
                "appearances": cols[6].text.strip(),
                "goals": cols[7].text.strip(),
                "clubs": cols[8].text.strip(),
                "minutes_played": cols[9].text.strip()
            })

        return pd.DataFrame(all_data)
    
    def extract_end_of_contract_team(self, url: str) -> pd.DataFrame:
        """
        Extract end-of-contract player information for a team from Transfermarkt.

        Args:
            url (str): URL of the team's end-of-contract page.
    

        Returns:
            pd.DataFrame: DataFrame containing player info, contract end date, market value, and agent.
        """
        all_data = []


        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Select table rows
        tabla = soup.select_one("table.items > tbody")
        if not tabla:
            return pd.DataFrame()
        
        rows = tabla.find_all("tr", recursive=False)

        for row in rows:
            cols = row.find_all("td", recursive=False)

            # Player info
            player_table = cols[0].find("table", class_="inline-table")
            if player_table:
                player_link = player_table.find("a", href=lambda x: x and "/profil/spieler/" in x)
                name = player_link.text.strip() if player_link else None
                player_url = f"https://www.transfermarkt.com{player_link['href']}" if player_link else None

                img_tag = player_table.find("img", class_="bilderrahmen-fixed")
                player_image_url = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

                tr_list = player_table.find_all("tr")
                position = tr_list[1].find("td").text.strip() if len(tr_list) > 1 else None
            else:
                name = player_url = player_image_url = position = None

            # Date of birth & age
            dob_text = cols[1].text.strip()
            date_of_birth_match = re.search(r'(\d{2}/\d{2}/\d{4})', dob_text)
            age_match = re.search(r'\((\d+)\)', dob_text)

            # Nationality
            flag_img = cols[2].find("img")

            all_data.append({
                "player": name,
                "player_link": player_url,
                "player_photo": player_image_url,
                "position": position,
                "date_of_birth": date_of_birth_match.group(1) if date_of_birth_match else None,
                "age": int(age_match.group(1)) if age_match else None,
                "nation": flag_img.get("title") if flag_img else None,
                "nation_photo": flag_img.get("src") if flag_img else None,
                "end_of_contract": cols[3].text.strip(),
                "contract_option": cols[4].text.strip(),
                "market_value": cols[5].text.strip(),
                "fee_paid": cols[6].text.strip(),
                "agent": cols[7].text.strip()

            })

        return pd.DataFrame(all_data)
    
    def extract_club_debutants(self, url: str) -> pd.DataFrame:
        """
        Extract debutant player data for a club from Transfermarkt across all pages.

        Args:
            url (str): URL of the club debutants page.


        Returns:
            pd.DataFrame: DataFrame containing debutant info, match details, and age.
        """
        all_data = []

    
        # 1️⃣ Get first page
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # 🔎 Detect last page
        last_page_link = soup.select_one(
            "li.tm-pagination__list-item--icon-last-page a.tm-pagination__link"
        )
        if last_page_link:
            match = re.search(r'/page/(\d+)', last_page_link["href"])
            total_pages = int(match.group(1)) if match else 1
        else:
            total_pages = 1

        print(f"Total pages detected: {total_pages}")

        # 2️⃣ Iterate through all pages
        for page_num in range(1, total_pages + 1):
            print(f"Scraping page {page_num}...")
            page_url = url if page_num == 1 else re.sub(r'/page/\d+', '', url) + f"/page/{page_num}"

            response = self.session.get(page_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Select all rows with inline-table (players)
            rows = soup.select("tr:has(table.inline-table)")
            for row in rows:
                # -------------------------
                # Player info
                # -------------------------
                player_link = row.find("a", href=lambda x: x and "/profil/spieler/" in x)
                photo_tag = row.find("img", class_="bilderrahmen-fixed")
                inline_table = row.find("table", class_="inline-table")

                # -------------------------
                # Nationality
                # -------------------------
                flag_img = row.find("img", class_="flaggenrahmen")

                # -------------------------
                # Matches & manager
                # -------------------------
                matches_tag = row.find("a", href=lambda x: x and "leistungsdatendetails" in x)
                manager_tag = row.find("a", href=lambda x: x and "/profil/trainer/" in x)
                debut_tag = row.find("a", href=lambda x: x and "spielbericht" in x)

                # -------------------------
                # Local team
                # -------------------------
                local_td = row.find("td", class_="zentriert no-border-rechts")
                match_team_local = match_team_local_escudo = None
                if local_td:
                    img_local = local_td.find("img")
                    if img_local:
                        match_team_local = img_local.get("alt")
                        match_team_local_escudo = img_local.get("src")

                # -------------------------
                # Away team
                # -------------------------
                away_td = row.find("td", class_="zentriert no-border-links")
                match_team_away = match_team_away_escudo = None
                if away_td:
                    img_away = away_td.find("img")
                    if img_away:
                        match_team_away = img_away.get("alt")
                        match_team_away_escudo = img_away.get("src")

                # -------------------------
                # Result & age
                # -------------------------
                result_tag = row.find("a", class_="ergebnis-link")
                age_tag = row.find("td", class_="rechts hauptlink")
        
                # Append to list
                all_data.append({
                    "player": player_link.text.strip() if player_link else None,
                    "player_url": f"https://www.transfermarkt.com{player_link['href']}" if player_link else None,
                    "player_photo": photo_tag.get("data-src") if photo_tag else None,
                    "position": inline_table.find_all("tr")[1].text.strip() if inline_table else None,
                    "age": age_tag.text.strip() if age_tag else None,
                    "nation": flag_img.get("title") if flag_img else None,
                    "nation_photo": flag_img.get("src") if flag_img else None,
                    "matches": matches_tag.text.strip() if matches_tag else None,
                    "manager": manager_tag.text.strip() if manager_tag else None,
                    "debut": debut_tag.text.strip() if debut_tag else None,
                    "match_team_local": match_team_local,
                    "match_team_local_escudo": match_team_local_escudo,
                    "match_result": result_tag.text.strip() if result_tag else None,
                    "match_team_away": match_team_away,
                    "match_team_away_escudo": match_team_away_escudo,
                })

            print(f"✅ Page {page_num} scraped")
            time.sleep(1)  # polite delay

        # Convert to DataFrame
        return pd.DataFrame(all_data)

    def extract_penalty_takers_team(self,url: str) -> pd.DataFrame:
        """
        Extract penalty taker data for a team from Transfermarkt, including match info and outcome.

        Args:
            url (str): URL of the team's penalty takers page.

        Returns:
            pd.DataFrame: DataFrame with penalty takers, match info, player nationality, and result.
        """
        data = []
        current_competition = None

        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for row in soup.select("tbody tr"):
            # -------------------------
            # Detect competition header row
            # -------------------------
            comp_cell = row.find("td", class_=lambda x: x and "extrarow" in x)
            if comp_cell:
                current_competition = comp_cell.get_text(strip=True)
                continue

            # -------------------------
            # Detect match row (odd/even)
            # -------------------------
            if row.get("class") and any(c in ["odd", "even"] for c in row.get("class")):
                cols = row.find_all("td")

                # Player info
                player_cell = row.find("td", class_="links")
                if player_cell:
                    player_tag = player_cell.select_one("td.hauptlink a")
                    player_img_tag = player_cell.select_one("img")
                    player = player_tag.get_text(strip=True) if player_tag else None
                    player_url = f"https://www.transfermarkt.com{player_tag['href']}" if player_tag else None
                    player_photo = player_img_tag.get("data-src") if player_img_tag else None
                else:
                    player = player_url = player_photo = None

                # Player nationality (can be multiple, we pick the first)
                flags = cols[5].find_all("img") if len(cols) > 5 else []

                # -------------------------
                # Home team info
                # -------------------------
                team_home_cell = row.find("td", class_="zentriert no-border-rechts")
                if team_home_cell:
                    home_a = team_home_cell.find("a")
                    home_img = team_home_cell.find("img")
                    team_home = home_a.get("title") if home_a else None
                    team_home_link = f"https://www.transfermarkt.com{home_a['href']}" if home_a else None
                    team_home_photo = home_img.get("src") if home_img else None
                else:
                    team_home = team_home_link = team_home_photo = None

                # -------------------------
                # Away team info
                # -------------------------
                team_away_cell = row.find("td", class_="zentriert no-border-links")
                if team_away_cell:
                    away_a = team_away_cell.find("a")
                    away_img = team_away_cell.find("img")
                    team_away = away_a.get("title") if away_a else None
                    team_away_link = f"https://www.transfermarkt.com{away_a['href']}" if away_a else None
                    team_away_photo = away_img.get("src") if away_img else None
                else:
                    team_away = team_away_link = team_away_photo = None

                # -------------------------
                # Append data
                # -------------------------
                data.append({
                    "competition": current_competition,
                    "date": cols[0].get_text(strip=True) if len(cols) > 0 else None,
                    "player": player,
                    "player_url": player_url,
                    "player_photo": player_photo,
                    "position": cols[4].get_text(strip=True) if len(cols) > 4 else None,
                    "nation": flags[0].get("title") if flags else None,
                    "nation_flag": flags[0].get("src") if flags else None,
                    "team_home": team_home,
                    "team_home_link": team_home_link,
                    "team_home_photo": team_home_photo,
                    "resultado": cols[7].get_text(strip=True) if len(cols) > 7 else None,
                    "team_away": team_away,
                    "team_away_link": team_away_link,
                    "team_away_photo": team_away_photo,
                    "outcome_type": cols[9].get_text(strip=True) if len(cols) > 9 else None,
                    "minute": cols[10].get_text(strip=True) if len(cols) > 10 else None,
                    "penalty_moment_result": cols[11].get_text(strip=True) if len(cols) > 11 else None
                })

        return pd.DataFrame(data)
    
    def extract_market_value_analysis_team(self, url: str) -> pd.DataFrame:
        """
        Extract market value data for a team's players from Transfermarkt.

        This function scrapes a Transfermarkt page that lists player details along with
        their market value, contract expiry, nationality, age, position, and other info.

        Args:
            url (str): URL of the team's market value page.

        Returns:
            pd.DataFrame: DataFrame containing player info with market value analysis.
        """
        all_data = []

        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Locate the main table
        table = soup.select_one("table.items")
        if not table:
            raise ValueError("Table not found on the page.")

        rows = table.select("tbody tr.odd, tbody tr.even")
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 11:
                continue  # skip malformed rows

            # Player link
            player_link_tag = cols[3].select_one("td.hauptlink a")
            player_url = f"https://www.transfermarkt.com{player_link_tag['href']}" if player_link_tag else None

            # Player photo
            img_tag = cols[2].find("img")

            # Nationality (flag)
            flag_img = cols[6].find("img")
        
            all_data.append({
                "shirt_number": cols[0].text.strip(),
                "player": cols[3].text.strip(),
                "player_photo": img_tag["src"] if img_tag else None,
                "player_url": player_url,
                "position": cols[4].text.strip(),
                "age": cols[5].text.strip(),
                "nation": flag_img.get("title") if flag_img else None,
                "country_img": flag_img.get("src") if flag_img else None,
                "contract_expires": cols[7].text.strip(),
                "market_value": cols[10].text.strip()
            })

        return pd.DataFrame(all_data)
    
    def extract_market_value_at_debut(self, url: str) -> pd.DataFrame:
        """
        Extract players' market value data at the time of their club debut from Transfermarkt.

        This function scrapes a Transfermarkt table that shows each player's market value 
        at debut, current market value, difference, debut date, position, and age at debut.

        Args:
            url (str): URL of the team's debut market value page.

        Returns:
            pd.DataFrame: DataFrame containing players with debut market value info.
        """
        all_data = []
     
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Locate the main table
        table = soup.select_one("table.items")
        if not table:
            raise ValueError("Table not found on the page.")

        rows = table.select("tbody tr.odd, tbody tr.even")
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 9:
                continue  # skip incomplete rows

            # Player link and photo
            player_link_tag = cols[0].select_one("td.hauptlink a")
            img_tag = cols[0].find("img")

            all_data.append({
                "player": cols[2].text.strip(),
                "player_photo": img_tag["src"] if img_tag else None,
                "player_url": f"https://www.transfermarkt.com{player_link_tag['href']}" if player_link_tag else None,
                "position": cols[3].text.strip(),
                "date_debut": cols[4].text.strip(),
                "age_at_debut": cols[5].text.strip(),
                "market_value_prior_to_debut": cols[6].text.strip(),
                "current_market_value": cols[7].text.strip(),
                "difference": cols[8].text.strip()
            })

        return pd.DataFrame(all_data)
    
    def extract_season_record_team(self, url: str) -> pd.DataFrame:
        """
        Extract a team's season record from Transfermarkt.

        This function scrapes the season performance table of a team, extracting
        results for each competition, including wins, draws, losses, goals, points, 
        and average spectators.

        Args:
            url (str): URL of the team's season record page.
    

        Returns:
            pd.DataFrame: DataFrame containing season records per competition.
        """

        # Fetch the page
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.select_one("div.responsive-table table")
        if table is None:
            raise ValueError("Table not found on the page.")

        def zero_if_dash(x):
            """Convert '-' to 0, otherwise return the stripped string."""
            x = x.strip()
            return 0 if x == "-" else x

        rows = []

        # Skip the first thead (often table header) and iterate the rest
        theads = table.find_all("thead")[1:]

        for thead in theads:
            th = thead.select_one("th[colspan='8'] a")  # Competition name & link
            if not th:
                continue

            tbody = thead.find_next_sibling("tbody")
            if not tbody:
                continue

            for tr in tbody.find_all("tr", recursive=False):
                tds = tr.find_all("td", recursive=False)
                if len(tds) != 8:
                    continue

                goals_for, goals_against = map(int, tds[6].get_text(strip=True).split(":"))

                rows.append({
                    "competition": th.get_text(strip=True),
                    "competition_url": f"https://www.transfermarkt.com{th['href']}",
                    "record_type": tds[0].get_text(strip=True),
                    "matches": int(zero_if_dash(tds[1].get_text(strip=True))),
                    "wins": int(zero_if_dash(tds[2].get_text(strip=True))),
                    "draws": int(zero_if_dash(tds[3].get_text(strip=True))),
                    "losses": int(zero_if_dash(tds[4].get_text(strip=True))),
                    "avg_points": float(zero_if_dash(tds[5].get_text(strip=True))),
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "avg_spectators": int(zero_if_dash(tds[7].get_text(strip=True)).replace(".", ""))
                })

        return pd.DataFrame(rows)

    def extract_fixtures_by_date_team(self, url: str) -> pd.DataFrame:
        """
        Scrape match fixtures for a team from a Transfermarkt page.

        The function extracts structured match information grouped by competition,
        including matchday, date, time, teams, tactical system, coach, attendance,
        result, match status (preview or played), and match report URL.

        Args:
            url (str): Transfermarkt URL containing the fixtures table.


        Returns:
            pd.DataFrame: DataFrame containing structured fixture data.
        """
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        

        rows = []

        for table in soup.find_all("table"):
            tbody = table.find("tbody")
            if not tbody:
                continue

            current_competition = None
            current_competition_url = None

            for tr in tbody.find_all("tr", recursive=True):

                # 🟦 FILA DE COMPETICIÓN
                comp_td = tr.find("td", class_="extrarow")
                if comp_td and comp_td.has_attr("colspan"):
                    link = comp_td.find("a")
                    if link:
                        current_competition = link.get_text(strip=True)
                        current_competition_url = (
                            "https://www.transfermarkt.com" + link["href"]
                        )
                    continue

                tds = tr.find_all("td", recursive=False)
                if len(tds) < 11 or current_competition is None:
                    continue

                # 🟨 Match report / preview
                result_td = tds[10]
                result_link = result_td.find("a")

                match_report_url = None
                match_status = "unknown"
                result = None

                if result_link:
                    match_report_url = (
                        "https://www.transfermarkt.com" + result_link["href"]
                    )
                    title = result_link.get("title", "").lower()
                    text = result_link.get_text(strip=True)

                    if "preview" in title or text == "-:-":
                        match_status = "preview"
                        result = "-:-"
                    elif "report" in title:
                        match_status = "played"
                        result = text

                rows.append({
                    "competition": current_competition,
                    "competition_url": current_competition_url,
                    "matchday": tds[0].get_text(strip=True),
                    "date": tds[1].get_text(strip=True),
                    "time": tds[2].get_text(strip=True),
                    "home_team": tds[4].get_text(strip=True),
                    "away_team": tds[6].get_text(strip=True),
                    "system": tds[7].get_text(strip=True),
                    "coach": tds[8].get_text(strip=True),
                    "attendance": tds[9].get_text(strip=True).replace(".", ""),
                    "match_status": match_status,
                    "result": result,
                    "match_report_url": match_report_url,
                })

        return pd.DataFrame(rows)
    
    def extract_league_tables(self,url_general, url_home, url_away, league, season):
    
        # Tabla general
        session = requests.Session()
        response_general = session.get(url_general, headers=self.headers)
        soup_general = BeautifulSoup(response_general.text, "html.parser")
        table_general = soup_general.select_one("table.items")
        legend = extract_qualification_legend(soup_general)
        df_general = parse_general_table(table_general, league, season, legend)

        # Tabla local
        session = requests.Session()
        response_home = requests.get(url_home, headers=self.headers)
        soup_home = BeautifulSoup(response_home.text, "html.parser")
        table_home = soup_home.select_one("table.items")
        df_home = parse_home_away_table(table_home, league, season, legend)

        # Tabla visitante
        session = requests.Session()
        response_away = session.get(url_away, headers=self.headers)
        soup_away = BeautifulSoup(response_away.text, "html.parser")
        table_away = soup_away.select_one("table.items")
        df_away = parse_home_away_table(table_away, league, season, legend)

        return df_general, df_home, df_away
    
    def extract_last_games(self, url: str) -> pd.DataFrame:
        """
        Extract a team's last games from Transfermarkt.

        This function scrapes the "Last Games" box of a team on Transfermarkt, 
        recording the result type (Win, Draw, Loss), opponent, match location, 
        opponent logo, and match URL.

        Args:
            url (str): URL of the team's page containing last games (current season).
 
        Returns:
            pd.DataFrame: DataFrame containing the last games with opponent and results.
        """
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for the "Last games" box
        last_games_box = soup.select_one("div.box.letzte_spiele")
        if not last_games_box:
            raise ValueError("Error: the URL must belong to the current season.")

        table_body = last_games_box.select_one("table tbody")
        if not table_body:
            raise ValueError("Error: last games table not found.")

        games = []

        # Each row represents a result type: Win (W), Draw (D), Loss (L)
        for row in table_body.find_all("tr"):
            result_cell = row.select_one("td.hauptlink")
            if not result_cell:
                continue

            result_type = result_cell.get_text(strip=True)  # W / D / L

            # Iterate over all match cells in the row
            for cell in row.select("td")[1:]:
                home_away = cell.select_one("span")   # H (home) or A (away)
                link = cell.select_one("a")           # match link
                img = cell.select_one("img")          # opponent logo

                if not link:
                    continue  # skip empty cells

                games.append({
                    "result": result_type,  # W / D / L
                    "home_away": home_away.get_text(strip=True) if home_away else None,
                    "opponent": img["title"] if img and img.has_attr("title") else None,
                    "opponent_logo": img["src"] if img and img.has_attr("src") else None,
                    "match_url": "https://www.transfermarkt.com" + link["href"]
                })

        return pd.DataFrame(games)
    
    def extract_all_time_standings(self, url: str) -> pd.DataFrame:
        """
        Scrape standings table data from a dynamically rendered Transfermarkt page.

        This function uses Selenium (headless Chrome) to render JavaScript content,
        extracts the standings table, cleans and normalizes column names, and
        separates goal statistics into structured columns.

        Args:
            url (str): Transfermarkt URL containing the standings table.

        Returns:
            pd.DataFrame: Cleaned standings DataFrame.
                        Returns an empty DataFrame if no table is found.
        """
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")

        with webdriver.Chrome(options=options) as driver:
            driver.get(url)
            
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.items"))
            )
            soup = BeautifulSoup(driver.page_source, "html.parser")

            table = soup.find("table", {"class": "items"})
            if table is None:
                return pd.DataFrame()  # Devuelve vacío si no encuentra la tabla

            # Encabezados
            columns = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]

            # Filas
            data = [
                [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                for tr in table.find("tbody").find_all("tr")
            ]

            df = pd.DataFrame(data, columns=columns)
            
            # Limpiar y renombrar columnas
            df.drop(columns=["wappen"], inplace=True, errors="ignore")
            df.rename(columns={"#": "position", "Points per annum": "points_per_year", "GD": "goals_diff"}, inplace=True)

            # Separar Goals en dos columnas antes de Goals Diff
            # Split "Goals" column into structured fields
            if "Goals" in df.columns:
                goals_split = df["Goals"].str.split(":", expand=True)
                if goals_split.shape[1] == 2:
                    df["goals_for"] = goals_split[0]
                    df["goals_against"] = goals_split[1]

                    df.drop(columns=["Goals"], inplace=True)

                    if "goals_diff" in df.columns:
                        idx = df.columns.get_loc("goals_diff")
                        df.insert(idx, "goals_for", df.pop("goals_for"))
                        df.insert(idx + 1, "goals_against", df.pop("goals_against"))
        return df
    
    def extract_league_grid(self, url: str) -> pd.DataFrame:
        """
        Extracts the league grid (cross-table) from Transfermarkt.

        This function scrapes the 'kreuztabelle' (cross-table) for a league, 
        which shows results between all teams: each row is a team, and each column 
        is the opponent team, with match results in the cells.

        Args:
            url (str): URL of the league's Kreuztabelle page.

        Returns:
            pd.DataFrame: DataFrame representing the league grid with teams as both 
                        row indices and columns, and results in the cells.
        """
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.select_one("table.kreuztabelle")
        if table is None:
            raise ValueError("No 'kreuztabelle' table found.")

        rows = table.find_all("tr")

        # Extract column teams from the first row (opponent teams)
        column_teams = [img["title"] for img in rows[0].find_all("img")]

        # Extract row teams and the results matrix
        matrix = []
        index = []

        for row in rows[1:]:
            tds = row.find_all("td")
            img = tds[0].find("img")
            if not img:
                continue

            # Row team name
            index.append(img["title"])

            # Results against other teams
            resultados = [
                (col.find("a").get_text(strip=True) if col.find("a") else col.get_text(strip=True))
                for col in tds[1:-1]
            ]

            matrix.append(resultados)

        return pd.DataFrame(matrix, index=index, columns=column_teams)


    def extract_current_season_transfer_team(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Scrapes a Transfermarkt team transfer page and extracts all relevant data:
        transfer record, arrivals, departures, and their summaries.

        Parameters
        ----------
        url : str
            URL of the Transfermarkt team transfer page.
    
        Returns
        -------
        tuple of pd.DataFrame
            - df_transfer_record: transfer summary (income, expenditure, balance)
            - df_arrivals: detailed arrivals information
            - df_arrivals_summary: summary of arrivals
            - df_departures: detailed departures information
            - df_departures_summary: summary of departures
        """
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table", class_="items")

        arrivals_table = tables[0]
        departures_table = tables[1]

        df_transfer_record = extract_transfer_record_current_next_sesion_transfers(soup)

        df_arrivals = extract_players_table_current_next_sesion_transfers(arrivals_table, arrivals=True)
        df_departures = extract_players_table_current_next_sesion_transfers(departures_table, arrivals=False)

        df_arrivals_summary = extract_summary_current_next_sesion_transfers(arrivals_table)
        df_departures_summary = extract_summary_current_next_sesion_transfers(departures_table)

        return (df_transfer_record, df_arrivals, df_arrivals_summary, df_departures,  df_departures_summary)
    
    #FALTA UNOOOOO

    def extract_transfers_flows_arrivals(self, url: str) -> pd.DataFrame:
        """
        Extracts incoming transfers (arrivals) for a club or league from Transfermarkt.

        Scrapes the arrivals page, including all paginated pages, to collect club, country,
        league, number of transfers, loans, and transfer volume.

        Args:
            url (str): URL of the arrivals/transfer flows page on Transfermarkt.
 
        Returns:
            pd.DataFrame: DataFrame containing arrivals with columns:
                - club
                - club_url
                - country
                - league
                - transfers
                - loans
                - transfer_volume
        """
        all_data = []

        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

  
        pagination_links = soup.select("ul.tm-pagination li.tm-pagination__list-item a.tm-pagination__link")
        page_urls = ["https://www.transfermarkt.com" + a["href"] for a in pagination_links if a.text.isdigit()]
        page_urls = sorted(list(set(page_urls)), key=lambda x: int(re.search(r'/page/(\d+)', x).group(1)) if re.search(r'/page/(\d+)', x) else 1)

        if not page_urls:
            page_urls = [url] 

        print(f"Total pages detected: {len(page_urls)}\n")

        for page_num, page_url in enumerate(page_urls, start=1):
            print(f"Scraping page {page_num}...")
            response = self.session.get(page_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            rows = soup.select("tbody tr.odd, tbody tr.even")
            for row in rows:
                cols = row.find_all("td")

          
                country_img = cols[3].find("img")
                
                all_data.append({
                    "club": cols[2].text.strip(),
                    "club_url": "https://www.transfermarkt.com" + cols[2].find("a")["href"],
                    "country": country_img["title"] if country_img else "",
                    "league": cols[3].find("a").text.strip(),
                    "transfers": cols[4].text.strip(),
                    "loans": cols[5].text.strip(),
                    "transfer_volume": cols[6].text.strip()
                })

            print(f"✅ Page {page_num} scraped")
            time.sleep(1)  

        return  pd.DataFrame(all_data)
    
    def extract_transfers_flows_departures(self,url: str) -> pd.DataFrame:
        """
        Extracts outgoing transfers (departures) for a club or league from Transfermarkt.

        This function scrapes the departures page, including paginated pages, 
        to collect the club, country, league, number of transfers, loans, and transfer volume.

        Args:
            url (str): URL of the departures/transfer flows page on Transfermarkt.

        Returns:
            pd.DataFrame: DataFrame containing all departures with columns:
                - club
                - club_url
                - country
                - league
                - transfers
                - loans
                - transfer_volume
        """
        all_data = []


        # 1️⃣ First page
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # 2️⃣ Detect pagination URLs
        pagination_links = soup.select("ul.tm-pagination li.tm-pagination__list-item a.tm-pagination__link")
        page_urls = ["https://www.transfermarkt.com" + a["href"] for a in pagination_links if a.text.isdigit()]
        # Sort pages numerically
        page_urls = sorted(list(set(page_urls)), key=lambda x: int(re.search(r'/page/(\d+)', x).group(1)) if re.search(r'/page/(\d+)', x) else 1)

        if not page_urls:
            page_urls = [url]  # Only first page if no pagination

        print(f"Total pages detected: {len(page_urls)}\n")

        # 3️⃣ Scrape each page
        for page_num, page_url in enumerate(page_urls, start=1):
            print(f"Scraping page {page_num}...")
            response = self.session.get(page_url, headers=self.headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            rows = soup.select("tbody tr.odd, tbody tr.even")
            for row in rows:
                cols = row.find_all("td")

                # Extract country & league info
                country_img = cols[3].find("img")
                league_link = cols[3].find("a")

                all_data.append({
                    "club": cols[2].text.strip(),
                    "club_url": "https://www.transfermarkt.com" + cols[2].find("a")["href"],
                    "country": country_img["title"] if country_img else "",
                    "league": league_link.text.strip() if league_link else "",
                    "transfers": cols[4].text.strip(),
                    "loans": cols[5].text.strip(),
                    "transfer_volume": cols[6].text.strip()
                })

            print(f"✅ Page {page_num} scraped")
            time.sleep(1)  # polite delay

        return pd.DataFrame(all_data)
    
    def extract_loan_from_history(self, url: str) -> pd.DataFrame:
        """
        Scrape loan-in history data from a Transfermarkt club page.

        The function extracts structured information about players loaned
        from other clubs, including player details, origin club, league,
        loan period, performance statistics, and market value at the end
        of the loan spell.

        Args:
            url (str): Transfermarkt URL containing the loan-in history table.

        Returns:
            pd.DataFrame: DataFrame containing structured loan-in history data.
        """
     
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Buscar la tabla de préstamos
        table = soup.find("table", {"class": "items"})
        rows = table.find("tbody").find_all("tr", recursive=False)

        data = []

        for row in rows:
            cells = row.find_all("td", recursive=False)
            
            # Player tags
            player_tag = cells[0].find("a")
            img_tag = cells[0].find("img")
        
            # Nation
            nat_imgs = cells[2].find_all("img")
            
            # Club de origen con información detallada
            loan_table = cells[3].find("table", class_="inline-table")
            if loan_table:
                loan_rows = loan_table.find_all("tr")
                
                # Primer row: escudo y nombre
                club_img_tag = loan_rows[0].find("td").find("img")
                club_shield = club_img_tag['src'] if club_img_tag else ""
                
                club_name_tag = loan_rows[0].find("td", class_="hauptlink").find("a")
                club_name = club_name_tag.text.strip() if club_name_tag else ""
                
                # Segundo row: bandera y liga
                league_td = loan_rows[1].find_all("td")[0]
                league_img_tag = league_td.find("img")
                league_flag = league_img_tag['src'] if league_img_tag else ""
                
                league_name_tag = league_td.find("a")
                league_name = league_name_tag.text.strip() if league_name_tag else ""
            else:
                club_name = club_shield = league_name = league_flag = ""
                    
            data.append({
                "player": player_tag.text.strip(),
                "player_url": "https://www.transfermarkt.com" + player_tag['href'],
                "player_photo": img_tag['data-src'] if img_tag and 'data-src' in img_tag.attrs else (img_tag['src'] if img_tag else ""),
                "age": cells[1].text.strip(),
                "nationality": nat_imgs[0]['title'] if nat_imgs else "",
                "nationality_url":  nat_imgs[0]['src'] if nat_imgs else "",
                "on_loan_from": club_name,
                "club_photo": club_shield,
                "league": league_name,
                "league_photo": league_flag,
                "loan_start": cells[4].text.strip(),
                "loan_end": cells[5].text.strip(),
                "in_squad": cells[6].text.strip(),
                "appearances": cells[7].text.strip(),
                "goals": cells[8].text.strip(),
                "market_value_end_loan": cells[9].text.strip()
            })

        return pd.DataFrame(data)

    def extract_loan_out_history(self, url: str) -> pd.DataFrame:
        """
        Scrape loan-out history data from a Transfermarkt club page.

        The function extracts structured information about players loaned out,
        including personal details, destination club, league, loan period,
        performance statistics, and market value at the end of the loan.

        Args:
            url (str): Transfermarkt URL containing the loan-out history table.

        Returns:
            pd.DataFrame: DataFrame containing structured loan-out history data.
        """

        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()


        soup = BeautifulSoup(response.content, "html.parser")

        table = soup.find("table", {"class": "items"})
        rows = table.find("tbody").find_all("tr", recursive=False)

        data = []

        for row in rows:
            cells = row.find_all("td", recursive=False)
            
            #Player
            player_tag = cells[0].find("a")
            img_tag = cells[0].find("img")
            
            # Nation
            nat_imgs = cells[2].find_all("img")
            
            #Loan club block
            loan_table = cells[3].find("table", class_="inline-table")
            if loan_table:
                loan_rows = loan_table.find_all("tr")
                
                # Primer row: escudo y nombre
                club_img_tag = loan_rows[0].find("td").find("img")
                club_shield = club_img_tag['src'] if club_img_tag else ""
                
                club_name_tag = loan_rows[0].find("td", class_="hauptlink").find("a")
                club_name = club_name_tag.text.strip() if club_name_tag else ""
                
                # Segundo row: bandera y liga
                league_td = loan_rows[1].find_all("td")[0]
                league_img_tag = league_td.find("img")
                league_flag = league_img_tag['src'] if league_img_tag else ""
                
                league_name_tag = league_td.find("a")
                league_name = league_name_tag.text.strip() if league_name_tag else ""
            else:
                club_name = club_shield = league_name = league_flag = ""
            
        
            data.append({
                    "player": player_tag.text.strip(),
                    "player_url": "https://www.transfermarkt.com" + player_tag['href'],
                    "player_photo": img_tag['data-src'] if img_tag and 'data-src' in img_tag.attrs else (img_tag['src'] if img_tag else ""),
                    "age": cells[1].text.strip(),
                    "nationality": nat_imgs[0]['title'] if nat_imgs else "",
                    "nationality_url":  nat_imgs[0]['src'] if nat_imgs else "",
                    "on_loan_from": club_name,
                    "club_photo": club_shield,
                    "league": league_name,
                    "league_photo": league_flag,
                    "loan_start": cells[4].text.strip(),
                    "loan_end": cells[5].text.strip(),
                    "in_squad": cells[6].text.strip(),
                    "appearances": cells[7].text.strip(),
                    "goals": cells[8].text.strip(),
                    "market_value_end_loan": cells[9].text.strip()
                })
        
        return pd.DataFrame(data)

    def extract_record_arrivals(self, url: str) -> pd.DataFrame:
        """
        Scrape record arrival transfers from a Transfermarkt club page.

        The function iterates through all paginated results and extracts
        structured information about incoming transfers, including player
        details, previous club, league, market value, and transfer fee.

        Args:
            url (str): Base Transfermarkt URL for record arrivals.


        Returns:
            pd.DataFrame: DataFrame containing structured arrival transfer data.
        """
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
            
        first_url = url + "/page/1"
        response = requests.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")

        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)
        print("" )

        all_data = []

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)
            
            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")
            
            rows = soup.select("tbody tr.odd, tbody tr.even")
            for row in rows:
                cols= row.find_all("td")
                
                inner_table = cols[1].find("table", class_="inline-table")
                inner_rows = inner_table.find_all("tr")

                # Player
                player_td = inner_rows[0].find("td", class_="hauptlink")
                player_a = player_td.find("a")
        
                # Player image
                player_img_tag = inner_rows[0].find("img")
            
                nation = cols[6].find("img")
        

                current_club_table = cols[7].find("a")
                current_club_image = cols[7].find("img")

                left_team_table = cols[10].find("a")
                left_team_image = cols[10].find("img")

                left_league_link= cols[12].find("a")


                all_data.append({
                    "player_name": player_a.get("title", player_a.text.strip()).strip(),
                    "player_profile_url": "https://www.transfermarkt.com" + player_a.get("href", "").strip(),
                    "player_photo": player_img_tag.get("data-src") if player_img_tag else None,
                    "position": cols[4].text.strip(),
                    "age": cols[5].text.strip(),
                    "nation": nation["title"] if nation else None,
                    "nation_flag": nation.get("src") if nation else None,
                    "current_club_name": current_club_table["title"] if current_club_table else None,
                    "current_club_logo": current_club_image["src"] if current_club_image else None,
                    "current_club_link": "https://www.transfermarkt.com" + current_club_table["href"] if current_club_table else None,
                    "season": cols[8].text.strip(),
                    "left_team_name": left_team_table["title"] if left_team_table else None,
                    "left_team_logo": left_team_image["src"] if left_team_image else None,
                    "left_team_link": "https://www.transfermarkt.com" + left_team_table["href"] if left_team_table else None,
                    "left_league_name": cols[12].text.strip(),
                    "left_league_url":  "https://www.transfermarkt.com" + left_league_link["href"] if left_league_link else None,
                    "market_value_at_the_time": cols[13].text.strip(),
                    "fee": cols[14].text.strip() 
                })
            
            print(f"✅ Page {page} scraped")
            time.sleep(1)

        return pd.DataFrame(all_data)
    
    def extract_record_departures(self, url: str) -> pd.DataFrame:
        """
        Scrape record departure data from a Transfermarkt club page.

        The function navigates through all paginated results and extracts
        structured player transfer information including player details,
        current club, destination club, league, market value, and transfer fee.

        Args:
            url (str): Base Transfermarkt URL for record departures.

        Returns:
            pd.DataFrame: DataFrame containing structured transfer data.
        """
                
        first_url = url + "/page/1"
        response = self.session.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")

        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)
        print("" )

        all_data = []

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)
            
            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")
            
            rows = soup.select("table.items > tbody > tr")
            for row in rows:
                cells = row.find_all("td", recursive=False)
                if len(cells) < 9:
                    continue

                # --- PLAYER ---
                player_a = row.select_one("td.hauptlink a")
                if not player_a:
                    continue

                img_tag = row.select_one("td.links img")
                inner_table = row.select_one("table.inline-table")

                # --- BASIC INFO ---
                nation_img = cells[3].find("img", class_="flaggenrahmen")
            

                # --- CURRENT CLUB ---
                club_a = cells[4].find("a")
                club_img = cells[4].find("img")

                # --- JOINED TEAM ---
                join_table = cells[6].select_one("table.inline-table")

                joined_team_name = joined_team_url = joined_team_logo = None
                joined_league_name = joined_league_url = joined_league_country = None

                if join_table:
                    club_a = join_table.select_one("td.hauptlink a")
                    club_img = join_table.find("img")

                    joined_team_name = club_a.get("title") if club_a else None
                    joined_team_url = "https://www.transfermarkt.com" + club_a.get("href", "") if club_a else None
                    joined_team_logo = club_img.get("src") if club_img else None

                    league_a = join_table.find_all("a")[-1] if join_table.find_all("a") else None
                    flag_img = join_table.find("img", class_="flaggenrahmen")

                    joined_league_name = league_a.get("title") if league_a else None
                    joined_league_url = "https://www.transfermarkt.com" + league_a.get("href", "") if league_a else None
                    joined_league_country = flag_img.get("title") if flag_img else None

                all_data.append({
                    "player_name": player_a.get("title", player_a.text.strip()),
                    "player_profile_url": "https://www.transfermarkt.com" + player_a.get("href", ""),
                    "player_photo": img_tag.get("data-src") or img_tag.get("src") if img_tag else None,
                    "position": ( inner_table.find_all("tr")[1].find("td").text.strip() if inner_table and len(inner_table.find_all("tr")) > 1 else None ),
                    "age": cells[2].text.strip(),
                    "nation": nation_img.get("title") if nation_img else None,
                    "nation_flag": nation_img.get("src") if nation_img else None,
                    "current_club_name": club_a.get("title") if club_a else None,
                    "current_club_logo": club_img.get("src") if club_img else None,
                    "current_club_url": "https://www.transfermarkt.com" + club_a.get("href", "") if club_a else None,
                    "season": cells[5].text.strip(),
                    "joined_team_name": joined_team_name,
                    "joined_team_url": joined_team_url,
                    "joined_team_logo": joined_team_logo,
                    "joined_league_name": joined_league_name,
                    "joined_league_url": joined_league_url,
                    "joined_league_country": joined_league_country,
                    "market_value_at_time": cells[7].text.strip(),
                    "fee": cells[8].text.strip()
                })
            
            print(f"✅ Page {page} scraped")
            time.sleep(1)

        return pd.DataFrame(all_data)
    
    def extract_most_valuable_arrivals(self, url: str) -> pd.DataFrame:
        """
        Scrape the most valuable arrivals from a Transfermarkt club page.

        The function iterates through all paginated results and extracts
        structured player transfer data including player details, previous club,
        league information, transfer fee, and market value at the time.

        Args:
            url (str): Base Transfermarkt URL for most valuable arrivals.

        Returns:
            pd.DataFrame: DataFrame containing structured arrival transfer data.
        """

        all_data = []



        first_url = url + "/page/1"
        response = self.session.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")
        total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1)) if last_page else 1

        print("Total pages:", total_pages, "\n")

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)

            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            rows = soup.select("table.items > tbody > tr")

            for row in rows:
                cells = row.find_all("td", recursive=False)

                # --- PLAYER ---
                player_a = row.select_one("td.hauptlink a")
                if not player_a:
                    continue

                img_tag = row.select_one("td.links img")

                # --- POSITION INFO ---
                inner_table = row.select_one("table.inline-table")
                
                # --- NATION INFO ---
                nation_img = cells[3].find("img", class_="flaggenrahmen")

                # --- CURRENT CLUB ---
                club_a = cells[4].find("a")
                club_img = cells[4].find("img")
            
                # --- LEFT TEAM ---
                left_table = cells[6].select_one("table.inline-table")

                left_team_name = left_team_url = left_team_logo = None
                left_league_name = left_league_url = left_league_country = None

                if left_table:
                    club_a = left_table.select_one("td.hauptlink a")
                    club_img = left_table.find("img")

                    left_team_name = club_a.get("title") if club_a else None
                    left_team_url = "https://www.transfermarkt.com" + club_a.get("href", "") if club_a else None
                    left_team_logo = club_img.get("src") if club_img else None

                    league_a = left_table.find_all("a")[-1] if left_table.find_all("a") else None
                    flag_img = left_table.find("img", class_="flaggenrahmen")

                    left_league_name = league_a.get("title") if league_a else None
                    left_league_url = "https://www.transfermarkt.com" + league_a.get("href", "") if league_a else None
                    left_league_country = flag_img.get("title") if flag_img else None

                all_data.append({
                    "player_name": player_a.get("title", player_a.text.strip()),
                    "player_profile_url": "https://www.transfermarkt.com" + player_a.get("href", ""),
                    "player_photo": img_tag.get("data-src") or img_tag.get("src") if img_tag else None,
                    "position": (inner_table.find_all("tr")[1].find("td").text.strip() if inner_table and len(inner_table.find_all("tr")) > 1 else None),
                    "age": cells[2].text.strip(),
                    "nation": nation_img.get("title") if nation_img else None,
                    "nation_flag": nation_img.get("src") if nation_img else None,
                    "current_club_name": club_a.get("title") if club_a else None,
                    "current_club_logo": club_img.get("src") if club_img else None,
                    "current_club_url": "https://www.transfermarkt.com" + club_a.get("href", "") if club_a else None,
                    "season": cells[5].text.strip(),
                    "left_team_name": left_team_name,
                    "left_team_url": left_team_url,
                    "left_team_logo": left_team_logo,
                    "left_league_name": left_league_name,
                    "left_league_url": left_league_url,
                    "left_league_country": left_league_country,
                    "fee": cells[7].text.strip(),
                    "difference":  cells[8].text.strip(),
                    "fmarket_value_at_timee": cells[9].text.strip()
                })
        
            print(f"✅ Page {page} scraped")
            time.sleep(1)            

        return pd.DataFrame(all_data)
    
    def extract_most_valuable_departures(self, url: str) -> pd.DataFrame:
        """
        Scrape the most valuable departures from a Transfermarkt club page.

        The function iterates through all paginated results and extracts
        structured transfer data including player details, destination club,
        league information, transfer fee, value difference, and market value
        at the time of transfer.

        Args:
            url (str): Base Transfermarkt URL for most valuable departures.

        Returns:
            pd.DataFrame: DataFrame containing structured departure transfer data.
        """

        all_data = []


        first_url = url + "/page/1"
        response = self.session.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")
        total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1)) if last_page else 1

        print("Total pages:", total_pages, "\n")

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)

            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            rows = soup.select("table.items > tbody > tr")

            for row in rows:
                cells = row.find_all("td", recursive=False)

                # --- PLAYER ---
                player_a = row.select_one("td.hauptlink a")
                if not player_a:
                    continue

                img_tag = row.select_one("td.links img")

                # --- POSITION INFO ---
                inner_table = row.select_one("table.inline-table")

                # --- NATION INFO ---
                nation_img = cells[3].find("img", class_="flaggenrahmen")

                # --- CURRENT CLUB ---
                club_a = cells[4].find("a")
                club_img = cells[4].find("img")
            
                # --- JOIN TEAM ---
                joined_table = cells[6].select_one("table.inline-table")

                joined_team_name = joined_team_url = joined_team_logo = None
                joined_league_name = joined_league_url = joined_league_country = None

                if joined_table:
                    club_a = joined_table.select_one("td.hauptlink a")
                    club_img = joined_table.find("img")

                    joined_team_name = club_a.get("title") if club_a else None
                    joined_team_url = "https://www.transfermarkt.com" + club_a.get("href", "") if club_a else None
                    joined_team_logo = club_img.get("src") if club_img else None

                    league_a = joined_table.find_all("a")[-1] if joined_table.find_all("a") else None
                    flag_img = joined_table.find("img", class_="flaggenrahmen")

                    joined_league_name = league_a.get("title") if league_a else None
                    joined_league_url = "https://www.transfermarkt.com" + league_a.get("href", "") if league_a else None
                    joined_league_country = flag_img.get("title") if flag_img else None

                all_data.append({
                    "player_name": player_a.get("title", player_a.text.strip()),
                    "player_profile_url":  "https://www.transfermarkt.com" + player_a.get("href", ""),
                    "player_photo": img_tag.get("data-src") or img_tag.get("src") if img_tag else None,
                    "position": (inner_table.find_all("tr")[1].find("td").text.strip() if inner_table and len(inner_table.find_all("tr")) > 1 else None),
                    "age": cells[2].text.strip(),
                    "nation": nation_img.get("title") if nation_img else None,
                    "nation_flag": nation_img.get("src") if nation_img else None,
                    "current_club_name": club_a.get("title") if club_a else None,
                    "current_club_logo": club_img.get("src") if club_img else None,
                    "current_club_url": "https://www.transfermarkt.com" + club_a.get("href", "") if club_a else None,
                    "season": cells[5].text.strip(),
                    "joined_team_name": joined_team_name,
                    "joined_team_url": joined_team_url,
                    "joined_team_logo": joined_team_logo,
                    "joined_league_name": joined_league_name,
                    "joined_league_url": joined_league_url,
                    "joined_league_country": joined_league_country,
                    "fee": cells[7].text.strip(),
                    "difference": cells[8].text.strip(),
                    "market_value_at_timee": cells[9].text.strip()

                })
        
            print(f"✅ Page {page} scraped")
            time.sleep(1)            

        return pd.DataFrame(all_data)
    
    def extract_rumors_about_arrivals(self, url: str) -> pd.DataFrame:
        """
        Scrape transfer rumors about potential arrivals from a Transfermarkt page.

        The function extracts structured data including player information,
        nationality, interested club, contract details, market value,
        and the most recent rumor source.

        Args:
            url (str): Transfermarkt URL containing arrival rumors.

        Returns:
            pd.DataFrame: DataFrame containing structured rumor data.
        """
      
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        rows = soup.select("tbody tr.odd, tbody tr.even")
        all_data = []

        for row in rows:
            cols = row.find_all("td")

            # --- PLAYER ---
            player_table = row.find("table", class_="inline-table")
            if player_table:
                first_tr = player_table.find_all("tr")[0]
                img_tag = first_tr.find("img")
                player_photo = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

                a_tag = first_tr.select_one("td.hauptlink a")
                player_name = a_tag.get("title") if a_tag else None
                player_profile_url = "https://www.transfermarkt.com" + a_tag.get("href") if a_tag else None
            else:
                player_name = player_profile_url = player_photo = None

            # ---NATION BLOCK ---
            nation_img = cols[5].find("img", class_="flaggenrahmen") if len(cols) > 6 else None

            # --- INTEREST CLUB ---
            team_cell = cols[9] if len(cols) > 9 else None
            team_a = team_cell.find("a") if team_cell else None
            team_img = team_cell.find("img") if team_cell else None
        

            all_data.append({
                "player_name": player_name,
                "player_profile_url": player_profile_url,
                "player_photo": player_photo,
                "position": cols[4].text.strip(),
                "age": cols[6].text.strip(),
                "nation": nation_img.get("title") if nation_img else None,
                "nation_flag_url": nation_img.get("src") if nation_img else None,
                "joined": cols[7].text.strip(),
                "contract_expires": cols[8].text.strip(),
                "interest_team_name": team_a.get("title") if team_a else None,
                "interest_team_url": "https://www.transfermarkt.com" + team_a.get("href") if team_a else None,
                "interest_team_photo": team_img.get("src") if team_img else None,
                "market_value":  cols[10].text.strip(),
                "most_recent_source":  cols[11].text.strip()
            })

        return pd.DataFrame(all_data)

    def extract_rumors_about_departures(self, url: str) -> pd.DataFrame:
        """
        Scrape transfer rumors about potential departures from a Transfermarkt page.

        Extracts structured data for each player including name, profile,
        nationality, current club, interested club, market value, and the
        most recent source of the rumor.

        Args:
            url (str): Transfermarkt URL containing departure rumors.

        Returns:
            pd.DataFrame: DataFrame containing structured rumor data for departures.
        """
       
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        rows = soup.select("tbody tr.odd, tbody tr.even")
        all_data = []

        for row in rows:
            cols = row.find_all("td")

            # --- PLAYER ---
            player_table = row.find("table", class_="inline-table")
            if player_table:
                first_tr = player_table.find_all("tr")[0]
                img_tag = first_tr.find("img")
                player_photo = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

                a_tag = first_tr.select_one("td.hauptlink a")
                player_name = a_tag.get("title") if a_tag else None
                player_profile_url = "https://www.transfermarkt.com" + a_tag.get("href") if a_tag else None
            else:
                player_name = player_profile_url = player_photo = None

            # --- NATION BLOCK---
            nation_img = cols[6].find("img", class_="flaggenrahmen") if len(cols) > 6 else None

            # --- INTEREST CLUB ---
            team_cell = cols[9] if len(cols) > 9 else None
            team_a = team_cell.find("a") if team_cell else None
            team_img = team_cell.find("img") if team_cell else None
        
            all_data.append({
                "player_name": player_name,
                "player_profile_url": player_profile_url,
                "player_photo": player_photo,
                "position": cols[4].text.strip(),
                "age": cols[5].text.strip(),
                "nation": nation_img.get("title") if nation_img else None,
                "nation_flag_url": nation_img.get("src") if nation_img else None,
                "joined": cols[7].text.strip(),
                "contract_expires": cols[8].text.strip(),
                "interest_team_name": team_a.get("title") if team_a else None,
                "interest_team_url": "https://www.transfermarkt.com" + team_a.get("href") if team_a else None,
                "interest_team_photo": team_img.get("src") if team_img else None,
                "market_value": cols[10].text.strip(),
                "most_recent_source": cols[11].text.strip()
            })

        return pd.DataFrame(all_data)
    
    def extract_achievements(self, url: str) -> pd.DataFrame:
        """
        Scrape all titles and achievements of a team or player from Transfermarkt.

        Extracts season, title name, and associated image URL.
        Filters out non-competitive achievements like "Participant".

        Args:
            url (str): Transfermarkt URL of the player or team.

        Returns:
            pd.DataFrame: DataFrame with columns ['Season', 'Title', 'Image'].
        """
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    
        table = soup.find("h2", string="All titles").find_next("table")

        data = [
            {
                "season": row.find("td", class_="zentriert").get_text(strip=True),
                "title": row.find("td", class_="no-border-links").get_text(strip=True),
                "title_photo": (img["src"] if (img := row.find("img")) else "")
            }
            for row in table.tbody.find_all("tr")
        ]

        df = pd.DataFrame(data)
        return df[~df["title"].str.contains("Participant", case=False, na=False)]

    def extract_attendance_team(self, url: str) -> pd.DataFrame:
        """
        Scrape team attendance data from Transfermarkt.

        Extracts season, league, league URL, league logo, matches, tickets sold,
        spectators, and average spectators.

        Args:
            url (str): Transfermarkt URL of the team's attendance page.


        Returns:
            pd.DataFrame: DataFrame containing attendance information per season.
        """
    
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.select_one("table.items")
        if not table:
            raise ValueError("Table not found")

        all_data = []
        rows = soup.select("tbody tr.odd, tbody tr.even")
        for row in rows:
            cols = row.find_all("td")

            all_data.append({
                    "season": cols[0].text.strip(),
                    "league": cols[1].text.strip(),
                    "league_url": "https://www.transfermarkt.com" + cols[1].find("a")["href"] if cols[1].find("a") else None,
                    "league_logo":  cols[1].find("img")["src"] if cols[1].find("img") else None,
                    "matches": cols[2].text.strip(),
                    "sold_tickets": cols[3].text.strip(),
                    "spectators": cols[4].text.strip(),
                    "avg_spectators": cols[5].text.strip()
                })

        return pd.DataFrame(all_data)

    def extract_historical_standings(self, url: str) -> pd.DataFrame:
        """
        Scrape historical league standings from Transfermarkt.

        Extracts season, league info, tier, matches, wins, draws, goals, points, position, and coach.

        Args:
            url (str): Transfermarkt URL of the historical standings page.
    

        Returns:
            pd.DataFrame: DataFrame containing historical standings.
        """

        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.select_one("table.items")
        if not table:
            raise ValueError("Table not found")

        rows = table.select("tbody tr")

        data = []

        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 10:
                continue

            # Detect goals column automatically
            goals_col = next((c for c in cols if ":" in c), None)

            goals_for, goals_against = (goals_col.split(":") if goals_col else (None, None))

            league_tag = row.select_one("td.hauptlink a")
            coach_tag = row.select("td a")[-1] if row.select("td a") else None

            data.append({
                "season": cols[0],
                "league": league_tag.get_text(strip=True) if league_tag else None,
                "league_url": "https://www.transfermarkt.com"  + league_tag["href"] if league_tag else None,
                "league_photo": row.find("img")["src"] if row.find("img") else None,
                "tier": cols[3] if len(cols) > 3 else None,
                "matches": safe_int(cols[4]) if len(cols) > 4 else None,
                "wins": safe_int(cols[5]) if len(cols) > 5 else None,
                "draws": safe_int(cols[6]) if len(cols) > 6 else None,
                "goals_for": safe_int(goals_for),
                "goals_against": safe_int(goals_against),
                "goal_difference": safe_int(cols[-4]),
                "points": safe_int(cols[-3]),
                "position": safe_int(cols[-2]),
                "coach": coach_tag.get_text(strip=True) if coach_tag else None,
            })

        return pd.DataFrame(data)

    def extract_cup_history(self, url: str) -> pd.DataFrame:
        """
        Extract cup history from a Transfermarkt team or player page.

        Args:
            url (str): URL to the cup history page.


        Returns:
            pd.DataFrame: DataFrame containing cup history.
        """

       
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        container = soup.select_one("div.responsive-table")

        if not container:
            raise ValueError("Cup history table not found")

        data = []

        current_competition = None
        current_competition_url = None
        current_competition_logo = None

        for row in container.find_all("tr"):

            classes = row.get("class", [])
            if "bg_blau_20" in classes and "hauptlink" in classes:
                img_tag = row.find("img")
                link_tag = row.find("a")

                current_competition = link_tag.get_text(strip=True) if link_tag else None
                current_competition_url = "https://www.transfermarkt.com" + link_tag["href"] if link_tag else None
                current_competition_logo = img_tag["src"] if img_tag else None
                continue

            cols = row.find_all("td")
            if len(cols) < 3:
                continue
        
            season_tag = cols[0].find("a")

            is_group_stage = cols[2].get("colspan") is not None

            if is_group_stage:
                opponents, opponent_urls = parse_group_stage_opponents(cols[2])
                first_leg = first_leg_url = second_leg = second_leg_url = None
            else:
                opponents, opponent_urls = parse_knockout_opponents(cols[2])
                first_leg, first_leg_url, second_leg, second_leg_url = extract_legs_from_row_with_url(row)

            data.append({
                "competition": current_competition,
                "competition_url": current_competition_url,
                "competition_photo": current_competition_logo,
                "season": season_tag.get_text(strip=True) if season_tag else None,
                "season_url": "https://www.transfermarkt.com" + season_tag["href"] if season_tag else None,
                "round_achieved": cols[1].get_text(strip=True),
                "opponents": ", ".join(opponents) if opponents else None,
                "opponent_urls": opponent_urls,
                "first_leg": first_leg,
                "first_leg_url": first_leg_url,
                "second_leg": second_leg,
                "second_leg_url": second_leg_url
            })

        return pd.DataFrame(data)
    
    def extract_record_against(self, url: str) -> pd.DataFrame:
        """
        Extrae el registro histórico de partidos contra equipos desde Transfermarkt.

        Args:
            url (str): URL de la página de historial.

        Returns:
            pd.DataFrame: Registro histórico por equipo.
        """

        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        
        first_url = url + "/page/1"
        response = requests.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")

        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)
        print("" )

        all_data = []

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)
            
            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")
            
            rows = soup.select("table.items tbody tr")
            for row in rows:

                club_tag = row.select_one("td.hauptlink a")

                logo_img = row.select_one("table.inline-table img")
        
                flag_img = row.select_one("td.zentriert img")

                stats = row.select("td.zentriert, td.rechts")

                if len(stats) >= 9: 
                    goals = stats[5].text.strip()
                    try:
                        goals_for, goals_against = goals.split(":")
                    except ValueError:
                        goals_for, goals_against = None, None

                else:
                    continue

                all_data.append({
                    "team": club_tag.text.strip() if club_tag else None,
                    "team_url": "https://www.transfermarkt.com" + club_tag["href"] if club_tag else None,
                    "team_photo": logo_img["src"].strip() if logo_img else None,
                    "nation":  flag_img["alt"].strip() if flag_img else None,
                    "nation_url": flag_img["src"].strip() if flag_img else None,
                    "matches": stats[1].text.strip(),
                    "w": stats[2].text.strip(),
                    "d": stats[3].text.strip(),
                    "l": stats[4].text.strip(),
                    "goals_for": goals_for,
                    "goals_against": goals_against,
                    "diff": stats[6].text.strip(),
                    "points": stats[7].text.strip(),
                    "ppg": stats[8].text.strip(),
                    "win_ratio": stats[9].text.strip() if len(stats) > 9 else None,
                    "average_attendance":  stats[10].text.strip() if len(stats) > 10 else None
                })
                
            print(f"✅ Page {page} scraped")
            time.sleep(1)

        return pd.DataFrame(all_data)
    
    def extract_record_players(self, url: str) -> pd.DataFrame:
        """
        Extrae estadísticas históricas de jugadores desde Transfermarkt.

        Args:
            url (str): URL de la página de ranking de jugadores.

        Returns:
            pd.DataFrame: Datos de jugadores con estadísticas completas.
        """
        all_data = []

      
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        

        first_url = url + "/page/1"
        response = requests.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")


        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")
        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)

    
        for page in range(1, total_pages + 1):
            print(f"Scraping page {page}...")
            url_page = url + f"/page/{page}"
            response = requests.get(url_page, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")
        

            table = soup.find("table", class_="items")
            if not table:
                print("⚠️ Table not found on page", page)
                continue

            for tr in table.tbody.find_all("tr"):
                tds = tr.find_all("td")
                if not tds or len(tds) < 14:
                    continue
                
            
                tr_classes = tr.get("class", [])
                active = "bg_blau_20" in tr_classes

                # PLAYER + CLUB
                inner_table = tds[1].find("table", class_="inline-table")
                inner_rows = inner_table.find_all("tr")

                # Player
                player_td = tds[1].find("td", class_="hauptlink")
                if not player_td:
                    continue

                player_a = player_td.find("a")
                if not player_a:
                    continue

                # PLAYER IMAGE
                player_img_tag = tds[1].find("img")

                # Club / Retired
                second_row_td = inner_rows[1].find("td")
                club_link = second_row_td.find("a")
                if club_link:
                    current_club = club_link["title"].strip()
                else:
                    current_club = second_row_td.text.strip()

                # Nations
                nation = None
                nation_flag_url = None    

                if len(tds) > 5:
                    nation_cell = tds[5]  # este es el correcto en tu estructura
                    first_flag = nation_cell.find("img", class_="flaggenrahmen")

                if first_flag:
                    nation = first_flag.get("title")
                    nation_flag_url = first_flag.get("src") 
                else:
                    nation = None
                    nation_flag_url = None 

                all_data.append({
                    "rank": tds[0].text.strip(),
                    "player": player_a.get("title", player_a.text.strip()).strip(),
                    "current_club": current_club,
                    "active": active,
                    "player_url": "https://www.transfermarkt.com" + player_a.get("href", "").strip(),
                    "player_photo": player_img_tag.get("src") if player_img_tag else None,
                    "nation": nation,
                    "nation_flag_url": nation_flag_url,
                    "date_of_birth": tds[6].text.strip(),
                    "appearances": tds[7].text.strip(),
                    "goals": tds[8].text.strip(),
                    "assists": tds[9].text.strip(),
                    "own_goals": tds[10].text.strip(),
                    "yellow_cards": tds[11].text.strip(),
                    "second_yellow": tds[12].text.strip(),
                    "red_cards": tds[13].text.strip(),
                    "substituted_on": tds[14].text.strip(),
                    "substituted_off": tds[15].text.strip(),
                    "minutes_played": tds[16].text.strip()
                    })


            print(f"✅ Page {page} scraped")
            time.sleep(1)  

        return  pd.DataFrame(all_data)
    
    def extract_top_scorers(self, url: str) -> pd.DataFrame:
        """
        Extrae los máximos goleadores desde Transfermarkt.
        """

        all_data = []

        # Obtener total de páginas
        first_url = url + "/page/1"
        response = self.session.get(first_url, headers=self.headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")
        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)

        # Loop por páginas
        for page in range(1, total_pages + 1):
            print(f"Scraping page {page}...")

            url_page = f"{url}/page/{page}"
            response = self.session.get(url_page, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            table = soup.find("table", class_="items")
            if not table:
                print("⚠️ No se encontró tabla")
                continue

            rows = table.select("tbody > tr")

            for tr in rows:
                try:
                    tds = tr.find_all("td")

                    if len(tds) < 15:
                        continue

                    # 🔹 Player (mucho más robusto)
                    player_a = tr.select_one("td.hauptlink a")
                    if not player_a:
                        continue

                    player_name = player_a.get("title", player_a.text).strip()
                    player_url = "https://www.transfermarkt.com" + player_a.get("href", "").strip()

                    # 🔹 Foto jugador
                    player_img = tr.select_one("img")
                    player_photo = player_img.get("src") if player_img else None

                    # 🔹 Club
                    club_a = tr.select_one("td:nth-of-type(2) tr:nth-of-type(2) a")
                    current_club = club_a.get("title").strip() if club_a else None

                    # 🔹 Nación
                    nation_img = tds[5].select_one("img")
                    nation = nation_img.get("title") if nation_img else None
                    nation_photo = nation_img.get("src") if nation_img else None

                    # 🔹 Datos numéricos
                    data = {
                        "rank": tds[0].text.strip(),
                        "player": player_name,
                        "player_url": player_url,
                        "player_photo": player_photo,
                        "current_club": current_club,
                        "nation": nation,
                        "nation_photo": nation_photo,
                        "date_of_birth": tds[6].text.strip(),
                        "appearances": tds[7].text.strip(),
                        "assists": tds[8].text.strip(),
                        "substituted_on": tds[9].text.strip(),
                        "substituted_off": tds[10].text.strip(),
                        "minutes_played": tds[11].text.strip(),
                        "minutes_per_goal": tds[12].text.strip(),
                        "goals_per_match": tds[13].text.strip(),
                        "goals": tds[14].text.strip(),
                    }

                    all_data.append(data)

                except Exception as e:
                    print("⚠️ Error en fila:", e)
                    continue

            print(f"✅ Page {page} scraped")
            time.sleep(1)

        return pd.DataFrame(all_data)
    
    def extract_top_scores_by_season(self, url: str) -> pd.DataFrame:
        """
        Extrae los máximos goleadores por temporada desde Transfermarkt, incluyendo datos de jugador,
        club, posición y estadísticas.

        Args:
            url (str): URL de la página de top scorers por temporada.

        Returns:
            pd.DataFrame: Tabla con datos completos de los jugadores por temporada.
        """

        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        
        response = requests.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", {"class": "items"})

        all_data = []
        current_season = None

        for tr in table.tbody.find_all("tr"):

            # 🔹 Detectar season
            season_td = tr.find("td", class_="extrarow")
            if season_td:
                season_link = season_td.find("a")
                if season_link:
                    current_season = season_link.text.strip()
                continue

            # Fila de jugador
            elif "odd" in tr.get("class", []) or "even" in tr.get("class", []):
                tds = tr.find_all("td")
            
                
                # Competition
                competition_a = tds[1].find("a")

                # Tabla interna jugador
                inner_table = tds[2].find("table", {"class": "inline-table"})
                inner_rows = inner_table.find_all("tr")
                
                player_a = inner_rows[0].find("a")
                
                # PLAYER IMAGE
                player_img_tag = inner_table.select_one("td[rowspan='2'] img")

                if player_img_tag:
                    player_img = player_img_tag.get("data-src") or player_img_tag.get("src")
                    player_img = player_img.strip() if player_img else None
                else:
                    player_img = None

                # Appearances (dentro de <a>)
                appearances_a = tds[6].find("a")

                all_data.append({
                    "season": current_season, 
                    "competition": competition_a["title"].strip() if competition_a else tds[1].text.strip(), 
                    "competition_photo":tds[0].find("img")["src"],
                    "player":player_a["title"].strip() if player_a else inner_rows[0].text.strip(), 
                    "player_photo":player_img, 
                    "position": inner_rows[1].find("td").text.strip(),
                    "appearances": appearances_a.text.strip() if appearances_a else tds[6].text.strip(), 
                    "assists":tds[7].text.strip(), 
                    "substituted_on":tds[8].text.strip(),
                    "substituted_off":tds[9].text.strip(), 
                    "minutes_played":tds[10].text.strip(),
                    "minutes_per_goal":tds[11].text.strip(), 
                    "goals_per_match": tds[12].text.strip(),  
                    "goals":tds[13].text.strip()
                })

        return pd.DataFrame(all_data)
    
    def extract_most_value_players(self, url: str) -> pd.DataFrame:
        """
        Extrae los jugadores más valiosos de Transfermarkt, incluyendo info de jugador,
        club, posición y valor máximo alcanzado.

        Args:
            url (str): URL de la sección de jugadores más valiosos.

        Returns:
            pd.DataFrame: Tabla con información de los jugadores más valiosos.
        """    
        
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
        
        first_url = url + "/page/1"
        response= requests.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")

        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)
        print("" )

        all_data = []

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)

            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            rows = soup.select("table.items tbody tr")
            rows = [row for row in rows if row.select_one("td table.inline-table")]
            for row in rows:
                # PLAYER INFO
                inline_table = row.select_one("td table.inline-table")
                if inline_table:
                
                    # PLAYER IMAGE
                    player_img_tag = row.select_one("td table.inline-table td[rowspan='2'] img")

                    if player_img_tag:
                        player_img = player_img_tag.get("data-src") or player_img_tag.get("src")
                        player_img = player_img.strip() if player_img else None
                    else:
                        player_img = None

                    # Nombre jugador y URL
                    player_tag = inline_table.select_one("td.hauptlink a")
                    player_name = player_tag.text.strip() if player_tag else None
                    player_url = "https://www.transfermarkt.com" + player_tag["href"] if player_tag else None

                    # Posición
                    position_tag = inline_table.select("tr")[1].select_one("td")
                    position = position_tag.text.strip() if position_tag else None
                else:
                    player_img = player_name = player_url = position = None
        
                club_td = row.select_one("td.zentriert")  
                club_img = club_td.select_one("img") if club_td else None

                if club_img:
                    current_club = club_img.get("title", "").strip()
                    club_logo = club_img.get("src", "").strip()
                else:
                    current_club = None
                    club_logo = None

                # COLUMNAS NUMÉRICAS
                cells_rechts = row.select("td.rechts")
                cells_zentriert = row.select("td.zentriert")

                all_data.append({
                    "player":player_name,
                    "player_url":player_url, 
                    "player_photo": player_img, 
                    "position":position,
                    "current_team":current_club, 
                    "current_team_photo":club_logo, 
                    "highest_market_value":cells_rechts[0].text.strip() if len(cells_rechts) >= 1 else None,
                    "date":cells_rechts[1].text.strip() if len(cells_rechts) >= 2 else None, 
                    "im_verein_from": cells_zentriert[1].text.strip() if len(cells_zentriert) >= 2 else None, 
                    "in_club_until":cells_zentriert[2].text.strip() if len(cells_zentriert) >= 3 else None    
                    })

            print(f"✅ Page {page} scraped")
            time.sleep(1)  

        return pd.DataFrame(all_data)
    
    def extract_foreign_players(self, url: str) -> pd.DataFrame:
        """
        Extrae información de jugadores extranjeros de un club o liga en Transfermarkt.

        Args:
            url (str): URL de la sección de jugadores extranjeros.

        Returns:
            pd.DataFrame: Información de jugadores extranjeros.
        """    
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()  

        first_url = url + "/page/1"
        response = requests.get(first_url, headers=self.headers)
        soup = BeautifulSoup(response.text, "html.parser")

        last_page = soup.select_one("li.tm-pagination__list-item--icon-last-page a")

        if last_page:
            total_pages = int(re.search(r'page/(\d+)', last_page["href"]).group(1))
        else:
            total_pages = 1

        print("Total pages:", total_pages)
        print("" )

        all_data = []

        for page in range(1, total_pages + 1):
            print("Scraping page...", page)

            url_pagina = url + f"/page/{page}"
            response = requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")


            rows = soup.select("tbody tr.odd, tbody tr.even")


            for row in rows:
                cols = row.find_all("td")

                # --- País ---
                country_tag = cols[0].find("a")

                # --- Jugador ---
                player_tag = cols[4].find("a")
                
                # --- Matches ---
                matches_text = cols[5].text.strip()

                all_data.append({
                    "nation": country_tag.text.strip() if country_tag else None,
                    "nation_photo": cols[0].find("img")["src"].strip() if cols[0].find("img") else None,
                    "players": cols[1].text.strip(),
                    "minutes": cols[2].text.strip(),
                    "goals": cols[3].text.strip(),
                    "player_name": player_tag.text.strip() if player_tag else None,
                    "player_url": "https://www.transfermarkt.com" + player_tag["href"] if player_tag else None,
                    "max_matches_apperances": matches_text.replace(" matches", "")

                })

            print(f"✅ Page {page} scraped")
            time.sleep(1)  

        return pd.DataFrame(all_data)
    
    def parse_page(self, url: str):
            
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()  

        soup = BeautifulSoup(response.text, "html.parser")

        tables = soup.find_all("div", class_="responsive-table")
        page_data = []

        for i, table in enumerate(tables):
            category = "Youngest" if i == 0 else "Oldest"
            rows = table.select("tbody tr.odd, tbody tr.even")

            for row in rows:
                cells = row.find_all("td")
                if not cells or len(cells) < 10:
                    continue

                # Jugador
                player_table = cells[1].find("table", class_="inline-table")
                player_tag = player_table.find("a")


                player_photo_tag = player_table.find("img")
                player_photo = (
                    player_photo_tag.get("data-src")
                    if player_photo_tag and player_photo_tag.get("data-src")
                    else player_photo_tag.get("src") if player_photo_tag else None
                )

                # Nacionalidad
                nationality_img = cells[5].find("img")

                # Manager
                manager_tag = cells[6].find("a")

                # Equipo local
                team_home_tag = cells[8].find("a")
                team_name_home = (
                    team_home_tag.get("title")
                    if team_home_tag and team_home_tag.get("title")
                    else cells[8].find("img").get("alt")
                    if cells[8].find("img")
                    else None
                )

                # Equipo visitante
                team_away_tag = cells[10].find("a")
                team_name_away = (
                    team_away_tag.get("title")
                    if team_away_tag and team_away_tag.get("title")
                    else cells[10].find("img").get("alt")
                    if cells[10].find("img")
                    else None
                )

                page_data.append({
                    "number": cells[0].text.strip(),
                    "player":  player_tag.text.strip(),
                    "player_url": "https://www.transfermarkt.com" + player_tag["href"],
                    "player_photo": player_photo,
                    "position": player_table.find_all("tr")[1].text.strip(),
                    "nation": nationality_img["title"].strip() if nationality_img else None,
                    "nation_photo": nationality_img["src"].strip() if nationality_img else None,
                    "manager": manager_tag.text.strip() if manager_tag else None,
                    "manager_url": "https://www.transfermarkt.com" + manager_tag["href"] if manager_tag else None,
                    "debut_date": cells[7].text.strip(),
                    "home_team": team_name_home,
                    "result": cells[9].text.strip(),
                    "away_team": team_name_away,
                    "age_at_that_time":  cells[-1].text.strip(),
                    "category": category,
                })

            # Siguiente página (solo hay un pager arriba)
            next_page_tag = soup.select_one("li.tm-pagination__list-item--icon-next-page a")
            next_page_url = "https://www.transfermarkt.com" + next_page_tag["href"] if next_page_tag else None

        return page_data, next_page_url
    
    def extract_debut_young_old_players(self, url: str):
        """
        Extrae información de los jugadores más jóvenes y más veteranos en su debut.

        Args:
            url (str): URL de la sección de debut de jugadores en Transfermarkt.
 
        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: (df_jugadores_jovenes, df_jugadores_viejos)
        """ 
        

        current_url = url
        all_data = []

        while current_url:
            page_data, current_url = self.parse_page(current_url)
            all_data.extend(page_data)

        df = pd.DataFrame(all_data)
        df_debut_youngest= df[df['category']=='Youngest'].reset_index(drop=True)
        df_debut_youngest = df_debut_youngest.drop(columns=['category'])
        df_debut_oldest= df[df['category']=='Oldest'].reset_index(drop=True)
        df_debut_oldest = df_debut_oldest.drop(columns=['category'])

        return df_debut_youngest, df_debut_oldest
    
    def extract_where_ex_players(self, url: str) -> pd.DataFrame:
        """
        Extrae información de ex-jugadores y sus equipos actuales desde Transfermarkt.

        Args:
            url (str): URL de la sección de ex-jugadores.

        Returns:
            pd.DataFrame: Datos de ex-jugadores con información de club actual y estadísticas.
        """
        
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
            response= requests.get(url_pagina, headers=self.headers)
            soup = BeautifulSoup(response.text, "html.parser")

            rows = soup.select("tbody tr.odd, tbody tr.even")

            for row in rows:
                cols = row.find_all("td")

                nation_img = cols[5].find("img")

                all_data.append({
                    "player": cols[2].find("a").text.strip(),
                    "player_url": "https://www.transfermarkt.com" + cols[2].find("a")["href"].strip(),
                    "player_photo": cols[1].find("img")["src"].strip() if cols[1].find("img") else None,
                    "position": cols[3].text.strip(),
                    "age": cols[4].text.strip(),
                    "nation": nation_img["title"].strip() if nation_img else None,
                    "nation_flag": nation_img["src"].strip() if nation_img else None,
                    "appearances": cols[6].text.strip(),
                    "goals": cols[7].text.strip(),
                    "mv_at_transfer": cols[8].text.strip(),
                    "player_exit_date": cols[9].text.strip(),
                    "current_market_value": cols[10].text.strip(),
                    "current_club": cols[13].text.strip(),
                    "current_club_logo": cols[11].find("img")["src"].strip() if cols[11].find("img") else None,
                    "current_club_url": "https://www.transfermarkt.com" + cols[11].find("a")["href"].strip() if cols[11].find("a") else None,
                    "current_club_division": cols[14].text.strip()
                    

                    })
            print(f"✅ Page {page} scraped")
            time.sleep(1)  
            
        return pd.DataFrame(all_data)
    
    def extract_returned_players(self, url: str) -> pd.DataFrame:
        """
        Extracts information about players who returned to a club from Transfermarkt.

        Args:
                url (str): URL of the page listing returned players.


        Returns:
                pd.DataFrame: DataFrame containing player info, position, nationality, previous and current club details,
                        transfer fees, appearances, and days away.
        """
       
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status() 

        soup = BeautifulSoup(response.content, "html.parser")

        rows = soup.select("tbody tr.odd, tbody tr.even")

        all_data= []
        for row in rows:
                cols = row.find_all("td")
                
                # Jugador
                player_table = cols[1].find("table", class_="inline-table")
                player_tag = player_table.find("a")
                
                all_data.append({
                        "player":  player_tag.text.strip(),
                        "player_url": "https://www.transfermarkt.com" + player_tag["href"],
                        "player_photo": player_table.find("img")["data-src"] if player_table.find("img") else None,
                        "position": cols[4].text.strip(),
                        "nation": cols[5].find("img")["title"].strip() if cols[5].find("img") else None,
                        "nation_flag": cols[5].find("img")["src"].strip() if cols[5].find("img") else None,
                        "left_to_sing_for_season": cols[6].text.strip(),
                        "left_to_sing_for_club": cols[9].text.strip(),
                        "left_to_sing_for_club_logo": cols[7].find("img")["src"].strip() if cols[7].find("img") else None,
                        "left_to_sing_for_club_division": cols[10].text.strip(),
                        "left_to_sing_for_club_division_url": "https://www.transfermarkt.com" + cols[10].find("a")["href"].strip() if cols[10].find("a") else None,
                        "left_to_sing_for_fee": cols[11].text.strip(),
                        "appearances_after": cols[12].text.strip(),
                        "days_away": cols[13].text.strip(),
                        "appearances_before": cols[14].text.strip(),
                        "joined_from_season": cols[15].text.strip(),
                        "joined_from_club": cols[18].text.strip(),
                        "joined_from_club_logo": cols[16].find("img")["src"].strip() if cols[16].find("img") else None,
                        "joined_from_club_division": cols[19].text.strip(),
                        "joined_from_club_division_url":  "https://www.transfermarkt.com" + cols[19].find("a")["href"].strip() if cols[19].find("a") else None,
                        "joined_from_fee":  cols[20].text.strip()
                        })

        return pd.DataFrame(all_data)
    
    def extract_staff_history(self, url: str) -> pd.DataFrame:
        """
        Extracts historical information of staff members (e.g., coaches) from Transfermarkt.

        Args:
            url (str): URL of the staff history page.
        

        Returns:
            pd.DataFrame: DataFrame containing coach/staff name, photo, date of birth,
                        nationality, appointment dates, tenure, match stats, and points per game.
        """

        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()  

        soup = BeautifulSoup(response.content, "html.parser")

        table = soup.find("table", class_="items")
        rows = table.find("tbody").find_all("tr")

        all_data = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 10:
                continue  # fila inesperada
        
            # --- Name, DOB y photos ---
            staff_info_table = cols[0].find("table", class_="inline-table")
 
            img_tag = staff_info_table.find("img")
            name_tag = staff_info_table.find("a", {"title": True})
            country_img = cols[4].find("img")

            all_data.append({
                "coach": name_tag.text.strip() if name_tag else None,
                "coach_photo": img_tag["src"] if img_tag else None,
                "date_of_birth": cols[3].text.strip() if cols[3] else None,
                "nation": country_img["title"] if country_img else None,
                "nation_photo": country_img["src"] if country_img else None,
                "appointed": cols[5].text.strip(),
                "end_of_post": cols[6].text.strip(),
                "time_in_post": cols[7].text.strip(),
                "matches": cols[8].text.strip(),
                "w": cols[9].text.strip(),
                "d": cols[10].text.strip(),
                "l": cols[11].text.strip(),
                "ppg": cols[12].text.strip()
            })

        return pd.DataFrame(all_data)
    
    def extract_referee_statistics(self, url: str) -> pd.DataFrame:
        """
        Extract referee statistics from Transfermarkt, including cards and penalties for and against.

        Args:
            url (str): URL of the referee statistics page.
    

        Returns:
            pd.DataFrame: Referee statistics including matches, W-D-L, yellow/red cards, and penalties.
        """
  
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
                rows = table.find("tbody").find_all("tr")


                for row in rows:
                    cols = row.find_all("td")
                    
                    if len(cols) < 11:
                        continue
                    
                    referee_info = cols[0].find("table", class_="inline-table")
                    if referee_info is None:
                        print("Fila ignorada por estructura inesperada:", row)
                        continue
                    
                    # Basic info
                    img_tag = referee_info.find("img")
                    name_tag = referee_info.find("a", {"title": True})
                    
                    # Nation
                    country_img = referee_info.find("img", class_="flaggenrahmen")

                    # Estadísticas
                    stats_for = [c.get_text(strip=True) for c in cols[6:10]]  # For FC Barcelona
                    stats_vs = [c.get_text(strip=True) for c in cols[10:15]]  # vs FC Barcelona
                
                    all_data.append({
                        "referee": name_tag.text.strip() if name_tag else None,
                        "referee_photo": img_tag["src"] if img_tag else None,
                        "nation": country_img["title"] if country_img else None,
                        "nation_url": country_img["src"] if country_img else None,
                        "matches": cols[4].get_text(strip=True),
                        "w-d-l":  cols[5].get_text(strip=True),
                        "yellow_for": stats_for[0],
                        "second_yellow_for": stats_for[1],
                        "red_for": stats_for[2],
                        "penalty_for": stats_for[3],
                        "yellow_vs": stats_vs[0],
                        "second_yellow_vs": stats_vs[1],
                        "red_vs": stats_vs[2],
                        "penalty_vs": stats_vs[3]
                    })
                
                print(f"✅ Page {page} scraped")
                time.sleep(1)  

        return pd.DataFrame(all_data)

    def extract_penalty_statistics(self, url: str) -> pd.DataFrame:
        """
        Extract player penalty statistics from Transfermarkt, including penalties taken, converted, missed, and success ratio.

        Args:
            url (str): URL of the penalty statistics page.


        Returns:
            pd.DataFrame: Player penalty statistics including player info, nation, position, and penalty stats.
        """

        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
    
        soup = BeautifulSoup(response.content, "html.parser")

        table = soup.find("table", {"class": "items"})
        rows = table.find("tbody").find_all("tr", recursive=False)

        all_data = []

        for row in rows:
            cells = row.find_all("td", recursive=False)
            
            # Jugador y tabla anidada
            player_table = cells[0].find("table", class_="inline-table")
            player_img_tag = player_table.find("img")
            
            player_tag = player_table.find("a")
            
            # Nacionalidad (primera)
            nat_imgs = cells[1].find_all("img")

            penalties_tag = cells[2].find("a")
            converted_tag = cells[3].find("a")
            missed_tag = cells[4].find("a")
            ratio_tag = cells[5].find("a")

            all_data.append({
                "player": player_tag.text.strip(),
                "player_url": "https://www.transfermarkt.com" + player_tag['href'],
                "player_photo": player_img_tag['data-src'] if player_img_tag and 'data-src' in player_img_tag.attrs else player_img_tag['src'],
                "position": player_table.find_all("tr")[1].find("td").text.strip(),
                "nation":  nat_imgs[0]['title'] if nat_imgs else "",
                "nation_photo": nat_imgs[0]['src'] if nat_imgs else "",
                "penalties": penalties_tag.text.strip() if penalties_tag else cells[2].text.strip(),
                "converted":  converted_tag.text.strip() if converted_tag else cells[3].text.strip(),
                "missed": missed_tag.text.strip() if missed_tag else cells[4].text.strip(),
                "ratio":  ratio_tag.text.strip() if ratio_tag else cells[5].text.strip()
            })

        return pd.DataFrame(all_data) 

    def extract_penalty_shootouts(self, url: str) -> pd.DataFrame:
        """
        Extract information on matches decided by penalty shootouts from Transfermarkt.

        Args:
            url (str): URL of the penalty shootouts page.

        Returns:
            pd.DataFrame: Information on competition, teams, results, and missed penalties.
        """
    
   
        response = self.session.get(url, headers=self.headers)
        response.raise_for_status()
    
        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.find("table", class_="items")
        all_data = []

        for row in table.tbody.find_all("tr"):
            zentriert_cells = row.find_all("td", class_="zentriert")
            
            # Solo procesar filas que tengan suficientes celdas "zentriert"
            if len(zentriert_cells) < 3:
                continue

            # Competición
            comp_tag = row.find("td", class_="hauptlink")

            # Equipo local y logo
            team_home_tag = row.find("td", class_="rechts hauptlink no-border-rechts")
            team_home_logo_tag = row.find("td", class_="zentriert no-border-links wappen-table-td")

            # Equipo visitante y logo
            team_away_tag = row.find("td", class_="links hauptlink no-border-links")
            team_away_logo_tag = row.find("td", class_="zentriert no-border-rechts wappen-table-td")

            # Resultado
            result_tag = row.find("a", class_="ergebnis-link")

            all_data.append({
                "competition": comp_tag.find("a").text.strip() if comp_tag and comp_tag.find("a") else "",
                "competition_photo": comp_tag.find("img")["src"] if comp_tag and comp_tag.find("img") else "",
                "season": zentriert_cells[0].text.strip(),
                "round": zentriert_cells[1].text.strip(),
                "missed_home": zentriert_cells[2].text.strip(),
                "team_home": team_home_tag.find("a").text.strip() if team_home_tag else "",
                "team_home_photo": team_home_logo_tag.find("img")["src"] if team_home_logo_tag else "",
                "result": result_tag.text.strip() if result_tag else "",
                "team_away": team_away_tag.find("a").text.strip() if team_away_tag else "",
                "team_away_photo": team_away_logo_tag.find("img")["src"] if team_away_logo_tag else "",
                "missed_away": zentriert_cells[-1].text.strip()
            })

        return pd.DataFrame(all_data)  

