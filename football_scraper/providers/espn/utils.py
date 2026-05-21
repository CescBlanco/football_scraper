import re
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)


from typing import Optional, Set, Dict, Tuple, Any

#----------------------------------------------DRIVE SELENIUM---------------------------------------------

def _create_driver():
    from webdriver_manager.chrome import ChromeDriverManager
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)

    driver.execute_script("""
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    })
    """)

    return driver
#------------------------------------------------COMPETITIONS----------------------------------------------
def clean_country(text: str) -> str:
    """
    Normalize country/region names into a standardized format.

    Parameters
    ----------
    text : str
        Raw country or competition region string.

    Returns
    -------
    str
        Cleaned and standardized country name.

    Raises
    ------
    TypeError
        If input is not a string.

    Notes
    -----
    - Fixes inconsistent casing for known regions.
    - Normalizes abbreviations such as "EE.UU.".
    - Ensures conjunction "y" is lowercase.
    """

    if not isinstance(text, str):
        raise TypeError("Input must be a string")


    # Standardize specific cases
    text = text.replace("Ee.Uu.", "EE.UU.")
    text = text.replace("EE.Uu.", "EE.UU.")
    text = text.replace("Ee.uu.", "EE.UU.")
    text = text.replace("Concacaf", "CONCACAF")

    # Normalize conjunction
    text = text.replace(" Y ", " y ")

    return text

#------------------------------------------------LEAGUE----------------------------------------------
def expand_positions(text: str) -> Set[int]:
    """
    Expand position strings into a set of integers.

    Converts expressions like:
        "1-4", "1–4", "1, 2, 3" → {1, 2, 3, 4}

    Parameters
    ----------
    text : str
        Raw text containing position ranges or individual positions.

    Returns
    -------
    Set[int]
        Set of expanded integer positions.

    Raises
    ------
    TypeError
        If input is not a string.

    Notes
    -----
    - Supports both hyphen (-) and en-dash (–).
    - Removes duplicates automatically via set.
    """

    if not isinstance(text, str):
        raise TypeError("Input must be a string")

    positions = set()

    # Ranges (e.g. 1-4, 1–4)
    ranges = re.findall(r"(\d+)\s*[-–]\s*(\d+)", text)
    for start, end in ranges:
        positions.update(range(int(start), int(end) + 1))

    # Individual numbers
    singles = re.findall(r"\b\d+\b", text)
    for s in singles:
        positions.add(int(s))

    return positions

def parse_footer(driver) -> Dict[int, str]:
    """
    Parse standings footer to map positions to zone labels.

    Parameters
    ----------
    driver : webdriver
        Selenium WebDriver instance already loaded on standings page.

    Returns
    -------
    Dict[int, str]
        Mapping of position -> competition zone label.

    Raises
    ------
    WebDriverException
        If footer elements cannot be accessed.

    Notes
    -----
    - Extracts position ranges and their meaning.
    - Works for any ESPN competition layout.
    """

    footer = driver.find_elements(By.CSS_SELECTOR, "div.Standings__Footer p")

    mapping: Dict[int, str] = {}

    for p in footer:

        text = p.text.strip()
        if not text:
            continue

        positions = expand_positions(text)

        # Remove position prefix
        label = re.sub(r"^positions?\s[\d,\s\-–]+[:\.]?\s*", "", text, flags=re.IGNORECASE).strip()

        if label:
            label = label[0].upper() + label[1:]

        for pos in positions:
            mapping[pos] = label

    return mapping

#------------------------------------------------TEAM----------------------------------------------

def clean_text(value: str) -> str:
    """
    Normalize whitespace in a text string.

    Parameters
    ----------
    value : str
        Input text value.

    Returns
    -------
    str
        Cleaned text with normalized spaces.

    Notes
    -----
    - Non-string values are returned unchanged.
    """

    if not isinstance(value, str):
        return value

    return " ".join(value.split())

def parse_match_cell(col) -> str:
    """
    Parse a MATCH cell from ESPN statistics tables.

    Parameters
    ----------
    col : selenium.webdriver.remote.webelement.WebElement
        Table cell element containing match information.

    Returns
    -------
    str
        Parsed match string in format:
        'HomeTeam score AwayTeam'

    Raises
    ------
    TypeError
        If the provided element is invalid.

    Notes
    -----
    - Uses DOM parsing for accurate match extraction.
    - Falls back to raw text if structured parsing fails.
    """

    if col is None:
        raise TypeError("col cannot be None")

    try:
        container = col.find_element( By.CSS_SELECTOR, "div.team-match")

        # Teams
        teams = container.find_elements( By.CSS_SELECTOR, "span.hide-mobile a")

        if len(teams) < 2:
            teams = container.find_elements(By.CSS_SELECTOR,"a.AnchorLink")

        if len(teams) < 2:
            raise ValueError("Could not identify both teams in match cell")

        home_team = teams[0].get_attribute("textContent").strip()
        away_team = teams[-1].get_attribute("textContent").strip()

        # Score
        score = container.find_element(By.CSS_SELECTOR,"span.score").get_attribute("textContent")
        score = " ".join(score.split())

        return f"{home_team} {score} {away_team}"

    except Exception:
        # Safe fallback
        return col.get_attribute("textContent").strip()
    
def parse_squad(driver: webdriver.Chrome) -> list[dict]:
    """
    Parse squad statistics tables from an ESPN squad page.

    Parameters
    ----------
    driver : webdriver.Chrome
        Selenium WebDriver instance already positioned
        on the squad page.

    Returns
    -------
    list[dict]
        List of player dictionaries containing squad data.

        Common fields:
            - section
            - player_name
            - player_url
            - position
            - age
            - height
            - weight
            - nation
            - appearances
            - substitut_app

        Goalkeeper-specific fields:
            - saves
            - goals_against
            - assists
            - fouls_committed
            - fouls_received
            - yellow_cards
            - red_cards

        Outfield player fields:
            - goals
            - assists
            - shots
            - shots_on_target
            - fouls_committed
            - fouls_received
            - yellow_cards
            - red_cards

    Raises
    ------
    TypeError
        If the provided driver is invalid.

    TimeoutException
        If squad sections fail to load.

    Notes
    -----
    - Parses all roster sections dynamically.
    - Supports goalkeepers and outfield players.
    - Rows with invalid or incomplete data are skipped safely.
    """

    if driver is None:
        raise TypeError("driver cannot be None")

    squad = []

    try:
        sections = WebDriverWait(driver, 15).until(EC.presence_of_all_elements_located( (By.CSS_SELECTOR, ".Roster__MixedTable")))

    except TimeoutException:
        raise TimeoutException("Squad sections failed to load" )

    for idx in range(len(sections)):

        try:
            section = driver.find_elements(By.CSS_SELECTOR,".Roster__MixedTable")[idx]

            title = section.find_element(By.CLASS_NAME,"Table__Title").text.strip().lower()

            table = section.find_element(By.TAG_NAME,"table")

            rows = table.find_elements(By.CSS_SELECTOR,"tbody tr")

            for row in rows:
                cols = row.find_elements( By.TAG_NAME, "td")
                values = [c.text.strip() for c in cols]

                if len(values) < 10:
                    continue

                try:
                    a_tag = cols[0].find_element( By.TAG_NAME, "a")

                    player = {
                        "section": title,
                        "player_name": a_tag.text,
                        "player_url": a_tag.get_attribute("href"),
                        "position": values[1],
                        "age": values[2],
                        "height": values[3],
                        "weight": values[4],
                        "nation": values[5],
                        "appearances": values[6],
                        "substitut_app": values[7]
                    }

                    # Goalkeeper stats
                    if "goalkeeper" in title:
                        player.update({
                            "saves": values[8],
                            "goals_against": values[9],
                            "assists": values[10] if len(values) > 10 else "",
                            "fouls_committed": values[11] if len(values) > 11 else "" ,
                            "fouls_received": values[12] if len(values) > 12 else "",
                            "yellow_cards": values[13] if len(values) > 13 else "",
                            "red_cards": values[14] if len(values) > 14 else "" 
                        })

                    # Outfield player stats
                    else:
                        player.update({
                            "goals": values[8],
                            "assists": values[9],
                            "shots": values[10] if len(values) > 10 else "",
                            "shots_on_target": values[11] if len(values) > 11 else "",
                            "fouls_committed": values[12] if len(values) > 12 else "",
                            "fouls_received": values[13] if len(values) > 13 else "",
                            "yellow_cards": values[14] if len(values) > 14 else "",
                            "red_cards": values[15] if len(values) > 15 else ""
                        })

                    squad.append(player)

                except ( NoSuchElementException,IndexError ):
                    continue

        except NoSuchElementException:
            continue

    return squad

#------------------------------------------------MATCH----------------------------------------------
def parse_game_info(driver: webdriver.Chrome) -> Dict[str, Optional[Any]]:
    """
    Extract game information from the match details section.

    Parameters
    ----------
    driver : webdriver.Chrome
        Selenium WebDriver instance already loaded with the match page.

    Returns
    -------
    Dict[str, Optional[Any]]
        Dictionary containing:
            - stadium (Optional[str]): Stadium name.
            - datetime (Optional[str]): Match date and time.
            - coverage (Optional[str]): TV or streaming coverage.
            - city (Optional[str]): Match city and country.
            - attendance (Optional[int]): Attendance number.
            - referees (Optional[str]): Referee names.

    Exceptions
    ----------
    - Returns default values when elements cannot be found.
    - Raises no exception intentionally to keep scraping flow stable.
    """

    info = {
        "stadium": None,
        "datetime": None,
        "coverage": None,
        "city": None,
        "attendance": None,
        "referees": None
    }

    try:
        section = driver.find_element( By.CSS_SELECTOR, "section[data-testid='gameInformation']")
    except NoSuchElementException:
        return info

    # Stadium
    try:
        info["stadium"] = section.find_element( By.CSS_SELECTOR,".GameInfo__Location__Name--noImg" ).text.strip()
    except NoSuchElementException:
        pass

    # Match date/time and coverage
    try:
        meta_spans = section.find_elements(By.CSS_SELECTOR,".GameInfo__Meta span")

        if len(meta_spans) >= 1:
            info["datetime"] = meta_spans[0].text.strip()

        if len(meta_spans) >= 2:
            coverage_text = meta_spans[1].text.strip()
            info["coverage"] = re.sub( r"^Coverage:\s*","", coverage_text)
    except Exception:
        pass

    # City
    try:
        info["city"] = section.find_element(By.CSS_SELECTOR,".Location__Text").text.strip()
    except NoSuchElementException:
        pass

    # Attendance
    try:
        attendance_text = section.find_element( By.CSS_SELECTOR,".Attendance__Numbers").text.strip()
        digits_only = re.sub( r"[^\d]", "",attendance_text.split(":")[-1] )

        if digits_only:
            info["attendance"] = int(digits_only)

    except (NoSuchElementException, ValueError):
        pass

    # Referees
    try:
        ref_items = section.find_elements(By.CSS_SELECTOR, ".GameInfo__List__Item")
        if ref_items:
            info["referees"] = ref_items[0].text.strip()

    except Exception:
        pass

    return info

def get_team_name(link_el) -> str:
    """
    Extract the full team name from a team link element.

    Parameters
    ----------
    link_el : WebElement
        Selenium WebElement containing the team link.

    Returns
    -------
    str
        Team name extracted from visible text or fallback URL slug.

    Exceptions
    ----------
    - Returns a formatted URL slug if visible text is unavailable.
    """

    spans = link_el.find_elements(By.TAG_NAME, "span")
    for span in spans:
        text = span.text.strip()

        if 4 <= len(text) <= 30 and not text.isupper():
            return text

    href = link_el.get_attribute("href")
    if not href:
        return "Unknown Team"

    slug = href.rstrip("/").split("/")[-1]

    return slug.replace("-", " ").title()

def get_record_points_by_uid( driver: webdriver.Chrome, gamestrip, record_pattern: re.Pattern, points_pattern: re.Pattern, uid: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Extract team record and points using the clubhouse UID.

    Parameters
    ----------
    driver : webdriver.Chrome
        Selenium WebDriver instance.

    gamestrip : WebElement
        Main gamestrip container element.

    record_pattern : re.Pattern
        Compiled regex pattern for team records.

    points_pattern : re.Pattern
        Compiled regex pattern for points.

    uid : str
        Team clubhouse UID.

    Returns
    -------
    Tuple[Optional[str], Optional[int]]
        Tuple containing:
            - team record (e.g. "10-2-1")
            - points value

    Exceptions
    ----------
    - Returns (None, None) when extraction fails.
    """

    try:
        links = gamestrip.find_elements( By.XPATH, f".//a[@data-clubhouse-uid='{uid}' and .//span]" )

        for link in links:

            try:
                container = link.find_element(   By.XPATH, "./ancestor::div[2]")
                sibling_divs = container.find_elements( By.XPATH,  "./following-sibling::div")

                for div in sibling_divs:

                    spans = div.find_elements(By.XPATH, "./span")
                    if len(spans) < 2:
                        continue

                    t0 = driver.execute_script("return arguments[0].textContent",spans[0]).strip()
                    t1 = driver.execute_script( "return arguments[0].textContent",spans[1]).strip()

                    if record_pattern.match(t0):

                        pts_match = points_pattern.search(t1)

                        return ( t0,int(pts_match.group(1)) if pts_match else None)

            except NoSuchElementException:
                continue

    except Exception:
        pass

    return None, None

def extract_events(driver):
    eventos = []

    filas = driver.find_elements(By.CSS_SELECTOR, "tbody.Table__TBODY tr")

    for fila in filas:

        # buscar bloque comentario
        comentario = fila.find_elements(By.CSS_SELECTOR, ".MatchCommentary__Comment")

        # si no existe -> saltar
        if not comentario:
            continue

        comentario = comentario[0]

        # timestamp
        timestamp = comentario.find_elements( By.CSS_SELECTOR,".MatchCommentary__Comment__Timestamp span")
        minuto = timestamp[0].text.strip() if timestamp else None

        # descripcion
        detalles = comentario.find_elements(By.CSS_SELECTOR, ".MatchCommentary__Comment__GameDetails span")
        descripcion = detalles[0].text.strip() if detalles else None

        # tipo evento
        icono = comentario.find_elements(By.CSS_SELECTOR,".MatchCommentary__Comment__PlayIcon svg" )
        
        tipo = None
        if icono:
            tipo = icono[0].get_attribute("aria-label")

        eventos.append({
            "minute": minuto,
            "event_type": tipo,
            "description": descripcion
        })

    return pd.DataFrame(eventos)




