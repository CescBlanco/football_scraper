import requests
import time
import pandas as pd

from bs4 import BeautifulSoup
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException, WebDriverException)

from football_scraper.providers.espn.constants import BASE_URL_COMPETITIONS
from football_scraper.providers.espn.utils import _create_driver, clean_country

class ESPNCompetitionScraper:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None

    def extract_all_competitions(self) -> pd.DataFrame:
        """
        Scrape all available football competitions from ESPN Soccer.

        Returns
        -------
        pd.DataFrame
            DataFrame with competitions and metadata.

        Raises
        ------
        WebDriverException
            If Selenium driver fails to initialize or run.

        TimeoutException
            If the page does not load required elements within time limit.

        Notes
        -----
        - Uses headless Chrome.
        - Parses dynamic ESPN competitions page.
        - Filters out "Top Competitions" section.
        """

        driver= _create_driver()

        try:
            driver.get(BASE_URL_COMPETITIONS)

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "ContentList__Item")))

            time.sleep(3)

            soup = BeautifulSoup(driver.page_source, "html.parser")
        
        except TimeoutException:
            raise TimeoutException("Page load timeout while scraping competitions")

        except WebDriverException as e:
            raise WebDriverException(f"WebDriver error: {str(e)}")
        
        finally:
            driver.quit()

        sections = soup.find_all("div", class_="layout is-split")

        rows = []

        for section in sections:

            header = section.find_previous("h3")
            block_name = header.text.strip() if header else "Unknown"

            items = section.find_all("div", class_="ContentList__Item")

            for item in items:

                a_tag = item.find("a", href=True)
                img = item.find("img")
                title = item.find("h2")

                links = item.select("div.TeamLinks__Links a")

                fixtures = None
                teams = None
                stats = None

                for l in links:
                    href = l.get("href", "")
                    text = l.text.lower()

                    if "schedule" in href:
                        fixtures = href
                    elif "teams" in href:
                        teams = href
                    elif "stats" in href:
                        stats = href

                rows.append({
                    "country": block_name.title(),
                    "competition": title.text.strip() if title else None,
                    "competition_url": a_tag["href"] if a_tag else None,
                    "competition_photo": img["src"] if img else None,
                    "competition_url_fixtures": fixtures,
                    "competition_url_teams": teams,
                    "competition_url_stats": stats
                })

        df = pd.DataFrame(rows)

        df = df[df["country"] != "Top Competitions"].reset_index(drop=True)

        df["country"] = df["country"].apply(clean_country)

        df["competition_slug"] = df["competition_url"].str.split("/name/").str[-1].str.upper()
        
        self._competitions_cache = df

        return df
    
    def _get_competitions_cache(self) -> pd.DataFrame:
        """
        Return cached competitions data.
        Scrapes ESPN only if cache is empty.
        """

        if self._competitions_cache is None:
            self._competitions_cache = self.extract_all_competitions()

        return self._competitions_cache

    def list_competitions_available(self) -> List[str]:
        """
        Get a list of all available competition names.

        Returns
        -------
        List[str]
            Unique competition names extracted from ESPN.

        Raises
        ------
        WebDriverException
            If competition scraping fails.
            
        Notes
        -----
        - Internally calls `extract_all_competitions()`.
        """

        leagues = self._get_competitions_cache()

        return list(leagues["competition"].unique())

    def get_league_by_name(self,league_name: str) -> Optional[pd.DataFrame]:
        """
        Retrieve competition information by its name.

        Parameters
        ----------
        league_name : str
            Name of the league/competition (case-insensitive).

        Returns
        -------
        Optional[pd.DataFrame]
            DataFrame with matching competition row(s),
            or None if no match is found.

        Raises
        ------
        TypeError
            If league_name is not a string.

        WebDriverException
            If competition scraping fails.

        Notes
        -----
        - Performs case-insensitive filtering.
        - Returns full competition metadata.
        """

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")
        
        leagues = self._get_competitions_cache()

        result = leagues[leagues["competition"].str.lower() == league_name.lower()]
        if not result.empty:
            return result

        return None