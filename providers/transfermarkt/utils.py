import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests
from providers.transfermarkt.constants import BASE_URL, COMPETITIONS_URL, DEFAULT_HEADERS

def extract_competition_id(url: str) -> str:
    """
    Extrae el ID de la competición desde una URL de Transfermarkt.

    """
    if "/wettbewerb/" in url:
        return url.split("/wettbewerb/")[1].split("/")[0].split("?")[0]
    return None

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

def parse_int(text):
    """Convert text to int safely, replacing '-' with 0"""
    return int(text.strip().replace("-", "0")) if text.strip() else 0

def parse_minutes(text: str)-> int:
    """
    Convert minutes string to int safely.
    
    Handles:
    - '-' -> 0
    - '10.814' -> 10814
    - '1.234' -> 1234
    - removes apostrophes
    """
    if not text or text.strip() == "-":
        return 0
    
    clean_text = text.strip().replace("'", "").replace(".", "").replace(",", "")
    
    try:
        return int(clean_text)
    except ValueError:
        return 0
    


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
