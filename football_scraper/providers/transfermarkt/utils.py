import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests
from football_scraper.providers.transfermarkt.constants import BASE_URL, COMPETITIONS_URL, DEFAULT_HEADERS

def extract_competition_id(url: str) -> str:
    """
    Extrae el ID de la competición desde una URL de Transfermarkt.

    """
    if "/wettbewerb/" in url:
        return url.split("/wettbewerb/")[1].split("/")[0].split("?")[0]
    return None

#---------------------------TEAM------------------------------------------------
def extract_signed_from(td):
            """Extract 'signed from' info: team name, logo, and URL."""
            team_img = td.find("img")
            team_link = td.find("a")

            return {
                "signed_from":  team_img.get("alt", "").strip() if team_img else None,
                "signed_from_url": f"https://www.transfermarkt.com{team_link['href']}" if team_link and team_link.get("href") else None,
                "signed_from_logo": team_img.get("src") if team_img else None
            }

def extract_bg_color(style):
    """Extrae el color de fondo de un atributo style"""
    if not style:
        return None
    m = re.search(r'background-color\s*:\s*(#[0-9a-fA-F]{6})', style)
    return m.group(1).lower() if m else None

def extract_qualification_legend(soup):
    """Crea un diccionario color -> leyenda"""
    legend = {}
    for span in soup.select("span.farbmarkierung-legende"):
        color = extract_bg_color(span.get("style"))
        if color:
            legend[color] = span.get_text(strip=True)
    return legend

def parse_general_table(table, league, season, qualification_legend):
    rows = []
    for tr in table.tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 10:  # filas válidas
            continue

        logo = tds[1].find("img")

        club_link = tds[2].find("a", href=True)
        goals_for, goals_against = map(int, tds[7].get_text(strip=True).split(":"))

        rows.append({
            "league": league,
            "season": season,
            "position": int(tds[0].get_text(strip=True).replace(".", "")),
            "club": club_link.get_text(strip=True),
            "club_url": "https://www.transfermarkt.com" + club_link["href"],
            "club_logo": logo["src"] if logo else None,
            "matches": int(tds[3].get_text(strip=True)),
            "wins": int(tds[4].get_text(strip=True)),
            "draws": int(tds[5].get_text(strip=True)),
            "losses": int(tds[6].get_text(strip=True)),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_diff": int(tds[8].get_text(strip=True)),
            "points": int(tds[9].get_text(strip=True)),
            "qualification_color": extract_bg_color(tds[0].get("style")),
            "qualification": qualification_legend.get(extract_bg_color(tds[0].get("style")))
        })
    return pd.DataFrame(rows)

def parse_home_away_table(table, league, season, qualification_legend):
    rows = []
    for tr in table.tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue

        logo = tds[1].find("img")
        club_link = tds[2].find("a", href=True)

        # Extraer GF:GA y puntos de forma flexible
        goals_for = goals_against = points = None
        for td in tds[6:]:
            text = td.get_text(strip=True)
            if ":" in text:
                goals_for, goals_against = map(int, text.split(":"))
            elif text.isdigit():
                points = int(text)

        rows.append({
            "league": league,
            "season": season,
            "position": int(tds[0].get_text(strip=True).split()[0]),
            "club": club_link.get_text(strip=True),
            "club_url": "https://www.transfermarkt.com" + club_link["href"],
            "club_logo": logo["src"] if logo else None,
            "wins": int(tds[3].get_text(strip=True)),
            "draws": int(tds[4].get_text(strip=True)),
            "losses":  int(tds[5].get_text(strip=True)),
            "goals_for": goals_for,
            "goals_against": goals_against,
            "goal_diff": goals_for - goals_against if goals_for is not None and goals_against is not None else None,
            "points": points,
            "qualification_color":  extract_bg_color(tds[0].get("style")),
            "qualification": qualification_legend.get( extract_bg_color(tds[0].get("style")))
        })
    return pd.DataFrame(rows)


def extract_transfer_record_current_next_sesion_transfers(soup: BeautifulSoup) -> pd.DataFrame:
    """
    Extracts the transfer record summary (income, expenditure, overall balance) 
    from a Transfermarkt team transfer page.

    Parameters
    ----------
    soup : BeautifulSoup
        Parsed HTML content of the transfer page.

    Returns
    -------
    pd.DataFrame
        A dataframe containing:
        - income_count: number of incoming transfers
        - income_value: total income value
        - expenditure_count: number of outgoing transfers
        - expenditure_value: total expenditure value
        - overall_balance: net balance from transfers
    """
    box = soup.find("div", class_="transfer-record")
    rows = box.find_all("tr")

    data = {}

    for row in rows:
        text = row.get_text(" ", strip=True)

        if "Income" in text:
            cols = row.find_all("td")
            data["income_count"] = cols[1].text.strip()
            data["income_value"] = cols[2].get_text(" ", strip=True)

        elif "Expenditure" in text:
            cols = row.find_all("td")
            data["expenditure_count"] = cols[1].text.strip()
            data["expenditure_value"] = cols[2].get_text(" ", strip=True)

        elif "Overall balance" in text:
            data["overall_balance"] = row.find("td", class_="transfer-record__total").get_text(" ", strip=True)

    return pd.DataFrame([data])

def extract_players_table_current_next_sesion_transfers(table , arrivals: bool = True) -> pd.DataFrame:
    """
    Extracts detailed player transfer information from a Transfermarkt transfers table.

    Parameters
    ----------
    table : bs4.element.Tag
        BeautifulSoup tag of the transfer table (arrivals or departures).
    arrivals : bool, optional
        If True, extracts incoming transfers; if False, extracts outgoing transfers.

    Returns
    -------
    pd.DataFrame
        A dataframe containing for each player:
        - player: player name
        - player_url: URL to player's Transfermarkt page
        - player_photo: URL to player's photo
        - position: player position
        - age: player age
        - market_value: current market value
        - nation: nationality
        - nation_photo: flag image URL
        - left_team / joined_team: club leaving / joining
        - left_team_url / joined_team_url: URL of the club
        - left_team_photo / joined_team_photo: club logo
        - left_league / joined_league: league name
        - left_league_url / joined_league_url: league page URL
        - left_league_photo / joined_league_photo: league flag
        - fee: transfer fee
    """
    rows = table.find("tbody").find_all("tr", recursive=False)
    all_data = []

    for row in rows:
        cols = row.find_all("td", recursive=False)

        # Player
        player_link_tag = cols[1].select_one("td.hauptlink a")
        player_img_tag = cols[1].find("img")

        # Posición
        position_rows = cols[1].find_all("tr")

        # Nation
        nationality_imgs = cols[4].find_all("img")

        # Club anterior
        club_cell = cols[5]

        club_link_tag = club_cell.select_one("td.hauptlink a")
        club_img_tag = club_cell.find("img", class_="tiny_wappen")

        # Liga
        league_link_tag = club_cell.find_all("a")[-1] if len(club_cell.find_all("a")) > 1 else None

        league_flag_img = club_cell.find_all("img")[-1] if len(club_cell.find_all("img")) > 1 else None
        if arrivals==True:
            all_data.append({
                "player": player_link_tag.text.strip() if player_link_tag else None,
                "player_url": "https://www.transfermarkt.com" + player_link_tag["href"] if player_link_tag else None,
                "player_photo": player_img_tag["data-src"] if player_img_tag else None,
                "position": position_rows[1].text.strip() if len(position_rows) > 1 else None,
                "age": cols[2].text.strip(),
                "market_value":  cols[3].text.strip(),
                "nation": [img.get("title") for img in nationality_imgs][0],
                "nation_photo": [img.get("src") for img in nationality_imgs][0],
                "left_team": club_link_tag.text.strip() if club_link_tag else None,
                "left_team_url": "https://www.transfermarkt.com" + club_link_tag["href"] if club_link_tag else None,
                "left_team_photo": club_img_tag["src"] if club_img_tag else None,
                "left_league": league_link_tag.text.strip() if league_link_tag else None,
                "left_league_url": "https://www.transfermarkt.com" + league_link_tag["href"] if league_link_tag else None,
                "left_league_photo": league_flag_img["src"] if league_flag_img else None,
                "fee": cols[6].get_text(" ", strip=True)
            })
        else:
            all_data.append({
                "player": player_link_tag.text.strip() if player_link_tag else None,
                "player_url": "https://www.transfermarkt.com" + player_link_tag["href"] if player_link_tag else None,
                "player_photo": player_img_tag["data-src"] if player_img_tag else None,
                "position": position_rows[1].text.strip() if len(position_rows) > 1 else None,
                "age": cols[2].text.strip(),
                "market_value":  cols[3].text.strip(),
                "nation": [img.get("title") for img in nationality_imgs][0],
                "nation_photo": [img.get("src") for img in nationality_imgs][0],
                "joined_team": club_link_tag.text.strip() if club_link_tag else None,
                "joined_team_url": "https://www.transfermarkt.com" + club_link_tag["href"] if club_link_tag else None,
                "joined_team_photo": club_img_tag["src"] if club_img_tag else None,
                "joined_league": league_link_tag.text.strip() if league_link_tag else None,
                "joined_league_url": "https://www.transfermarkt.com" + league_link_tag["href"] if league_link_tag else None,
                "joined_league_photo": league_flag_img["src"] if league_flag_img else None,
                "fee": cols[6].get_text(" ", strip=True)
            })


    return pd.DataFrame(all_data)

def extract_summary_current_next_sesion_transfers(table) -> pd.DataFrame:
    """
    Extracts summary information from a Transfermarkt table footer (tfoot).

    Parameters
    ----------
    table : bs4.element.Tag
        BeautifulSoup table element for arrivals or departures.

    Returns
    -------
    pd.DataFrame
        A dataframe with key-value pairs extracted from the table footer, 
        e.g., total fees, number of players, or other statistics.
    """
    tfoot = table.find("tfoot")
    data = {}

    if tfoot:
        for td in tfoot.find_all("td"):
            text = td.get_text(" ", strip=True)
            key, value = text.split(":", 1)
            key_clean = key.strip().lower().replace(" ", "_")
            data[key_clean] = value.strip()

    return pd.DataFrame([data])

def safe_int(value):
    """
    Convert a value to int safely. Returns None if conversion fails.
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def parse_group_stage_opponents(td):
    """
    Parse group stage opponents from a <td> element.
    Returns:
        - List of opponent names with (H)/(A) if applicable
        - List of opponent URLs
    """
    opponents = []
    opponent_urls = []

    for item in td.children:
        if item.name == "a" and "/verein/" in item.get("href", ""):
            name = item.get_text(strip=True)

            # buscamos texto siguiente inmediato para ver si es (H) o (A)
            next_text = ""
            if item.next_sibling:
                next_text = str(item.next_sibling).replace("\xa0", "").replace(",", "").strip()
            if next_text in ["(H)", "(A)"]:
                name = f"{name} {next_text}"

            # agregamos solo si hay contenido válido
            if name:
                opponents.append(name)
                opponent_urls.append("https://www.transfermarkt.com" + item["href"])

    return opponents, opponent_urls


def parse_knockout_opponents(td):
    """
    Parse knockout stage opponents from a <td> containing inline-table.
    Returns:
        - List of opponent names
        - List of opponent URLs
    """
    opponents = []
    opponent_urls = []

    for a in td.find_all("a", href=True, title=True):
        href = a["href"]
        if "/verein/" in href:
            name = a.get_text(strip=True)
            if name:
                opponents.append(name)
                opponent_urls.append("https://www.transfermarkt.com" + href)
    return opponents, opponent_urls

def extract_legs_from_row_with_url(row, base_url="https://www.transfermarkt.com"):
    """
    Extract first leg and second leg results and URLs from a knockout row.
    Handles unplayed matches as "-:-".
    """
    td_results = row.find_all("td", class_="zentriert")
    

    first_leg_text = "-:-"
    first_leg_url = None
    second_leg_text = "-:-"
    second_leg_url = None


    results_tds = td_results[-2:] if len(td_results) >= 2 else td_results

    for i, td in enumerate(results_tds):
        text = "-:-"
        url = None

        a_tag = td.find("a")
        if a_tag:
            if "ergebnis-link" in a_tag.get("class", []):
                text = a_tag.get_text(" ", strip=True)
                url = base_url + a_tag["href"] if a_tag.has_attr("href") else None
            else:
                text = "-:-"
                url = None
        else:

            text = "-:-"
            url = None

        if i == 0:
            first_leg_text = text
            first_leg_url = url
        elif i == 1:
            second_leg_text = text
            second_leg_url = url

    return first_leg_text, first_leg_url, second_leg_text, second_leg_url

  
#---------------------------PLAYER------------------------------------------------

# Function to extract data from a span or return default value if not found
def extract_text(soup, class_name, default=None, index=None):
    elements = soup.find_all('span', class_=class_name)
    if index is not None and len(elements) > index:
        return elements[index].text.strip()
    return elements[0].text.strip() if elements else default


# Function to extract other positions from a specific section
def extract_other_positions(soup):
    # Look for the div containing other positions
    other_position_div = soup.find('div', class_='detail-position__position')
    
    if other_position_div:
        # Find all additional positions
        positions = other_position_div.find_all('dd', class_='detail-position__position')
        
        if positions:
            # Return positions as a comma-separated list
            return ', '.join([pos.text.strip() for pos in positions])
    return "-"

def get_img_src(tag):
    """Safe extraction of src from img tag"""
    return tag["src"] if tag and tag.has_attr("src") else None

def parse_int(value):
    if not value or value.strip() in ["", "-"]:
        return None
    
    try:
        return int(value.replace(",", "").strip())
    except ValueError:
        return None

def parse_minutes(value):
    if not value or value.strip() == "":
        return None

    value = value.strip()

    # quitar apóstrofe y separador de miles
    value = value.replace("'", "").replace(".", "")

    try:
        return int(value)
    except ValueError:
        return None
    


def parse_general_stats_player(box):
    """
    Parse the general competition statistics table from a Transfermarkt "box" section.

    Extracts overall season stats for a player, including appearances, goals, assists,
    cards, substitutions, and minutes played.

    Parameters
    ----------
    box : bs4.element.Tag
        A BeautifulSoup object representing a "box" div containing the general stats table.

    Returns
    -------
    pandas.DataFrame or None
        DataFrame with columns:
            - competition
            - competition_photo
            - appearances
            - goals
            - assists
            - own_goals
            - ...
        Returns None if the table is not found in the provided box.

    """
    table = box.find("table", class_="items")
    if not table:
        return None

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")
    all_data = []

    for row in rows:
        cols = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cols) < 14:
            continue

        comp_tag = row.find("td", class_="hauptlink no-border-rechts")

        all_data.append({
            "competition": cols[1],
            "competition_photo": comp_tag.find("img")["src"] if comp_tag and comp_tag.find("img") else "",
            "appearances": cols[2],
            "goals": cols[3],
            "assists": cols[4],
            "own_goals": cols[5],
            "subs_on": cols[6],
            "subs_off": cols[7],
            "yellow_cards": cols[8],
            "second_yellow_cards": cols[9],
            "red_cards": cols[10],
            "penalty_goals": cols[11],
            "minutes_per_goal": cols[12],
            "minutes_played": cols[13],
        })

    return pd.DataFrame(all_data)


def parse_competition_match_stats_player(box):
    """
    Parse the match-by-match statistics table from a Transfermarkt "box" section.

    Extracts detailed statistics for each match in a season, including teams, result,
    individual player performance, cards, substitutions, and minutes played.

    Parameters
    ----------
    box : bs4.element.Tag
        A BeautifulSoup object representing a "box" div containing a match-by-match table.

    Returns
    -------
    pandas.DataFrame or None
        DataFrame with columns:
            - match_day
            - date
            - home_team
            - home_team_photo
            - away_team
            - away_team_photo
            - result
            -...
        Missing data is filled with "-" for consistency.
        Returns None if no table is found in the box.

    """
    responsive = box.find("div", class_="responsive-table")
    if not responsive:
        return None

    table = responsive.find("table")
    if not table:
        return None

    tbody = table.find("tbody")
    rows = tbody.find_all("tr")
    all_data = []

    for row in rows:
        cols = row.find_all("td")
        if not cols or len(cols) < 8:
            continue

        home_logo = cols[2].find("img")["src"] if cols[2].find("img") else ""
        away_logo = cols[4].find("img")["src"] if cols[4].find("img") else ""

        all_data.append({
            "match_day": cols[0].get_text(strip=True),
            "date": cols[1].get_text(strip=True),
            "home_team": cols[3].get_text(strip=True),
            "home_team_photo": home_logo,
            "away_team": cols[5].get_text(strip=True),
            "away_team_photo": away_logo,
            "result": cols[6].get_text(strip=True),
            "position": cols[7].get_text(strip=True),
            "goals": cols[8].get_text(strip=True) if len(cols) > 8 else "-",
            "assists": cols[9].get_text(strip=True) if len(cols) > 9 else "-",
            "own_goals": cols[10].get_text(strip=True) if len(cols) > 10 else "-",
            "subs_on": cols[11].get_text(strip=True) if len(cols) > 11 else "-",
            "subs_off": cols[12].get_text(strip=True) if len(cols) > 12 else "-",
            "yellow_cards": cols[13].get_text(strip=True) if len(cols) > 13 else "-",
            "second_yellow_cards": cols[14].get_text(strip=True) if len(cols) > 14 else "-",
            "red_cards": cols[15].get_text(strip=True) if len(cols) > 15 else "-",
            "penalty_goals": cols[16].get_text(strip=True) if len(cols) > 16 else "-",
            "minutes_per_goal": cols[17].get_text(strip=True) if len(cols) > 17 else "-",
            "minutes_played": cols[-1].get_text(strip=True),
        })

    return pd.DataFrame(all_data)


def extract_all_player_stats(soup):
    """
    Extracts all available player statistics tables from a BeautifulSoup object.

    Iterates through all "box" divs on the page, identifies table type (general stats
    or match-by-match stats), and returns a dictionary of DataFrames.

    Parameters
    ----------
    soup : bs4.BeautifulSoup
        A BeautifulSoup object of the player's season page.

    Returns
    -------
    dict
        Dictionary where keys are section titles (e.g., "General Stats", "UEFA Champions League")
        and values are pandas DataFrames containing the respective statistics.

    """
    boxes = soup.find_all("div", class_="box")
    dataframes = {}

    for box in boxes:
        headline = box.find(lambda tag: tag.name in ["h2", "div"] 
                            and tag.get("class") 
                            and any("content-box-headline" in c for c in tag.get("class")))
        title = headline.get_text(strip=True) if headline else ""

        # Estadísticas generales
        if "Stats" in title and box.find("table", class_="items"):
            df = parse_general_stats_player(box)
            if df is not None:
                dataframes["General Stats"] = df

        # Estadísticas detalladas por partido
        elif box.find("div", class_="responsive-table"):
            df = parse_competition_match_stats_player(box)
            if df is not None:
                # Usamos el título de la sección como clave para diferenciar
                key = title if title else f"match_stats_{len(dataframes)}"
                dataframes[key] = df

    return dataframes


    
def get_soup_selenium(url: str):
 
    options = Options()
    options.add_argument("--headless")

    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        driver.implicitly_wait(5)

        html = driver.page_source
        driver.quit()

        return BeautifulSoup(html, "html.parser")

    except Exception as e:
        raise RuntimeError(f"Selenium error while fetching {url}") from e

def extract_stats_by_competition(soup):
    boxes = soup.find_all("div", class_="box")[1:]

    categories = [
        "national_leagues",
        "domestic_cups",
        "international_cups",
    ]

    result = {}

    for i, box in enumerate(boxes):
        table = box.find("table", class_="items")
        if not table:
            continue

        rows = table.find("tbody").find_all("tr")
        all_data = []

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 16:
                continue

            all_data.append({
                "season": cols[0].get_text(strip=True),
                "competition": cols[2].get_text(strip=True),
                "competition_photo": get_img_src(cols[1].find("img")),
                "team": (
                    cols[3].find("a")["title"]
                    if cols[3].find("a")
                    else None
                ),
                "team_photo": get_img_src(cols[3].find("img")),
                "appearances": cols[4].get_text(strip=True),
                "goals": cols[5].get_text(strip=True),
                "assists": cols[6].get_text(strip=True),
                "own_goals": cols[7].get_text(strip=True),
                "sub_on": cols[8].get_text(strip=True),
                "sub_off": cols[9].get_text(strip=True),
                "yellow_cards": cols[10].get_text(strip=True),
                "second_yellow_card": cols[11].get_text(strip=True),
                "red_cards": cols[12].get_text(strip=True),
                "penalty_goals": cols[13].get_text(strip=True),
                "minutes_per_goal": cols[14].get_text(strip=True),
                "minutes_played": cols[15].get_text(strip=True),
            })

        key = categories[i] if i < len(categories) else f"category_{i}"
        result[key] = pd.DataFrame(all_data)

    return result 

def extract_stats_by_club( soup: BeautifulSoup) -> dict:
        boxes = soup.find_all("div", class_="box")
        if not boxes:
            return {"by_club": pd.DataFrame(), "by_competition": pd.DataFrame()}

        # ---------- First box: stats by club ----------
        first_box = boxes[0]
        table = first_box.find("table", class_="items")
        stats_by_club_data = []

        if table:
            rows = table.find("tbody").find_all("tr", recursive=False)
            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 9:
                    continue
                stats_by_club_data.append({
                    "club": cols[1].text.strip(),
                    "club_photo": get_img_src(cols[0].find("img")),
                    "appearances": parse_int(cols[2].text),
                    "goals": parse_int(cols[3].text),
                    "assists": parse_int(cols[4].text),
                    "yellow_card": parse_int(cols[5].text),
                    "second_yellow_card": parse_int(cols[6].text),
                    "red_card": parse_int(cols[7].text),
                    "minutes_played": parse_minutes(cols[8].text),
                })

        df_stats_by_club = pd.DataFrame(stats_by_club_data)

        # ---------- Remaining boxes: stats by competition ----------
        competitions_data = []

        for box in boxes[1:]:
            h2 = box.find("h2", class_="content-box-headline")
            if not h2:
                continue
            comp_img_tag = h2.find("img")
            comp_name = h2.get_text(strip=True)

            table = box.find("table")
            if not table:
                continue
            rows = table.find("tbody").find_all("tr", recursive=False)

            for row in rows:
                cols = row.find_all("td")
                if len(cols) < 9:
                    continue
                competitions_data.append({
                    "competition": comp_name,
                    "competition_photo": get_img_src(comp_img_tag),
                    "club": cols[1].text.strip(),
                    "club_photo": get_img_src(cols[0].find("img")),
                    "appearances": parse_int(cols[2].text),
                    "goals": parse_int(cols[3].text),
                    "assists": parse_int(cols[4].text),
                    "yellow_card": parse_int(cols[5].text),
                    "second_yellow_card": parse_int(cols[6].text),
                    "red_card": parse_int(cols[7].text),
                    "minutes_played": parse_minutes(cols[8].text),
                })

        df_competitions = pd.DataFrame(competitions_data)

        return {"by_club": df_stats_by_club, "by_competition": df_competitions}
    
def get_total_pages(soup, box_index):
    """
    Get the total number of pages for a table on the Transfermarkt page.

    Parameters:
    ----------
    soup : BeautifulSoup
        BeautifulSoup object containing the HTML content of the page.
    box_index : int
        Index of the box containing the table (0 for 'scored', 1 for 'missed').

    Returns:
    -------
    int
        Total number of pagination pages. Returns 1 if there's no pagination.
    """
    tables = soup.find_all('div', class_='box')
    
    if len(tables) > box_index:
        box = tables[box_index]
        last_page_button = box.find('li', class_='tm-pagination__list-item tm-pagination__list-item--icon-last-page')
        
        if last_page_button:
            text = last_page_button.a['title']
            total_pages = int(text.split('page ')[-1].strip(')'))
            return total_pages
        else:
            return 1  # No pagination
    return 1  # No pagination if the box is not found

def extract_data_from_page(url, page, box_index, is_goalkeeper=False ):
    """
    Extracts data from a specific page of a box on Transfermarkt.

    Parameters:
    ----------
    url : str
        The base URL of the page.
    page : int
        The page number for pagination.
    box_index : int
        Index of the box being scraped ('scored' or 'missed').
    is_goalkeeper : bool
        A flag to indicate if the player is a goalkeeper (True) or not (False).

    Returns:
    -------
    list
        A list of dictionaries with the extracted data from the page.
    """
    response = requests.get(url + f'/page/{page}', headers=DEFAULT_HEADERS)
    all_data = []

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        tables = soup.find_all('div', class_='box')

        if len(tables) > box_index:
            box = tables[box_index]
            table = box.select_one("div.responsive-table table")
            rows = table.find("tbody").find_all("tr", recursive=False)

            for row in rows:
                cols = row.find_all("td", recursive=False)
                comp_img_tag = cols[1].find("img")
                comp_a_tag = cols[1].find("a")
                team_img_tag = cols[2].find("img")
                team_a_tag = cols[2].find("a")
                home_link = cols[4].find("a")
                home_img = cols[4].find("img")
                away_link = cols[6].find("a")
                away_img = cols[6].find("img")
                # Si es un portero, cambiar 'goalkeeper' por 'penalty_taker'
                player_key = "goalkeeper" if not is_goalkeeper else "penalty_taker"

                all_data.append({
                    "season": cols[0].get_text(strip=True),
                    "competition": comp_a_tag["title"] if comp_a_tag else "",
                    "competition_photo": comp_img_tag["src"] if comp_img_tag else "",
                    "team": team_a_tag["title"] if team_a_tag else "",
                    "team_photo": team_img_tag["src"] if team_img_tag else "",
                    "date": cols[3].get_text(strip=True),
                    "home_team": home_link["title"] if home_link else None,
                    "home_team_photo": home_img["src"] if home_img else None,
                    "result": cols[5].get_text(strip=True),
                    "away_team": away_link["title"] if away_link else None,
                    "away_team_photo": away_img["src"] if away_img else None,
                    "minute": cols[7].get_text(strip=True),
                    "score_at_minute": cols[8].get_text(strip=True),
                    player_key: cols[9].get_text(strip=True),
                })
    
    return all_data


def parse_squad_number_table(table) -> pd.DataFrame:
        """
        Parse a Transfermarkt squad number table to extract player squad details.

        Parameters
        ----------
        table : bs4.element.Tag
            A BeautifulSoup table element containing the squad number data.

        Returns
        -------
        pd.DataFrame
            A DataFrame with the parsed squad number data, including season, team,
            team logo, and jersey number.
        
        Raises
        ------
        ValueError
            If the table is malformed and does not contain enough columns for parsing.
        """
        tbody = table.find("tbody")
        rows = tbody.find_all("tr", recursive=False) if tbody else []

        records = []

        for row in rows:
            cells = row.find_all("td", recursive=False)
            if len(cells) < 4:
                continue

            season = cells[0].get_text(strip=True)

            logo_tag = cells[1].find("img")
            team_tag = cells[2].find("a")

            jersey_number = cells[-1].get_text(strip=True)

            records.append({
                "season": season,
                "team": team_tag.get_text(strip=True) if team_tag else None,
                "team_logo": logo_tag["src"] if logo_tag else None,
                "jersey_number": int(jersey_number) if jersey_number.isdigit() else None
            })

        return pd.DataFrame(records)
