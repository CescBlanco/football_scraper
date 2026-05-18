import requests
import time
import pandas as pd

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from selenium.webdriver.common.by import By

from providers.scoresway.constants import BASE_URL, BASE_URL_COMPETITIONS
from providers.scoresway.utils import _create_driver

class ScoreswayCompetitionScraper:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None

    def extract_competitions(self):
        """
        Extract football competitions data from Scoresway.

        This function navigates through the Scoresway competitions page,
        expands all continents and countries dynamically, parses the HTML,
        and extracts league information grouped by continent and country.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - continent : str
            - country : str
            - country_photo : str
            - league : str
            - league_url : str

        Raises
        ------
        RuntimeError
            If the scraping process fails.
        ValueError
            If no competition data is found.
        """

        driver = None

        try:
            driver = _create_driver()

            # Build competitions URL
            driver.get(BASE_URL_COMPETITIONS)

            # Wait for page content to load completely
            time.sleep(3)

            # ------------------------
            # EXPAND CONTINENTS
            # ------------------------
            continentes = driver.find_elements(By.CLASS_NAME, "continentBar")

            for cont in continentes:
                try:
                    # Use JavaScript click to avoid Selenium interaction issues
                    driver.execute_script("arguments[0].click();", cont)
                    time.sleep(0.3)
                except Exception:
                    # Ignore non-clickable continent elements
                    continue

            # ------------------------
            # EXPAND COUNTRIES
            # ------------------------
            paises = driver.find_elements(By.CLASS_NAME, "countryBar")

            for pais in paises:
                try:
                    # Expand country competitions section
                    driver.execute_script("arguments[0].click();", pais)
                    time.sleep(0.2)
                except Exception:
                    # Ignore non-clickable country elements
                    continue

            # Allow dynamic content rendering
            time.sleep(2)

            # ------------------------
            # PARSE HTML
            # ------------------------
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # ------------------------
            # EXTRACT DATA
            # ------------------------
            data = []

            for cont in soup.select("div.continent"):

                nombre_cont_elem = cont.select_one("div.continentBar span.name")

                if not nombre_cont_elem:
                    continue

                nombre_cont = nombre_cont_elem.text.strip()

                # Iterate through countries inside each continent
                for country in cont.select("div.country"):

                    country_bar = country.select_one("div.countryBar")

                    if not country_bar:
                        continue

                    nombre_pais_elem = country_bar.select_one("span.name")
                    flag_elem = country_bar.select_one("img")

                    nombre_pais =  nombre_pais_elem.text.strip()  if nombre_pais_elem else None
                    flag_url = flag_elem.get("src") if flag_elem else None

                    if flag_url:
                        # Convert relative URL into absolute URL
                        flag_url = urljoin(BASE_URL, flag_url)

                    # Iterate through leagues inside the country
                    for a in country.select("li.comp a"):

                        liga = a.text.strip()
                        url_liga = urljoin(BASE_URL, a.get("href"))

                        data.append({
                            "continent": nombre_cont,
                            "country": nombre_pais,
                            "country_photo": flag_url,
                            "league": liga,
                            "league_url": url_liga
                        })

            if not data:
                raise ValueError("No competition data was extracted from Scoresway")

            df_final= pd.DataFrame(data)

            self._competitions_cache = df_final
            return df_final

        except Exception as e:
            raise RuntimeError(f"Failed to extract competitions from Scoresway: {str(e)}")

        finally:
            # Always close the browser to free system resources
            if driver:
                driver.quit()

    def _get_competitions_cache(self) -> pd.DataFrame:
        """
        Return cached competitions data.
        Scrapes Scoresway only if cache is empty.
        """

        if self._competitions_cache is None:
            self._competitions_cache = self.extract_competitions()

        return self._competitions_cache
    
    def list_countries_available(self):
        """
        Retrieve all available countries from Scoresway competitions data.

        Returns
        -------
        list[str]
            List of unique country names.

        Raises
        ------
        RuntimeError
            If competition data cannot be retrieved.
        """

        try:
            # Extract competitions dataset
            df = self._get_competitions_cache()

            # Return unique countries
            return list(df["country"].dropna().unique())

        except Exception as e:
            raise RuntimeError( f"Failed to retrieve available countries: {str(e)}")
        
    def list_competitions_available(self):
        """
        Retrieve all available football competitions from Scoresway.

        Returns
        -------
        list[str]
            List of unique competition names.

        Raises
        ------
        RuntimeError
            If competition data cannot be retrieved.
        """

        try:
            # Extract competitions dataset
            df = self._get_competitions_cache()

            # Return unique league names
            return list(df["league"].dropna().unique())

        except Exception as e:
            raise RuntimeError(f"Failed to retrieve available competitions: {str(e)}")
        
    def get_league_by_country_and_name(self,country_name: str, league_name: str):
        """
        Retrieve league information filtered by country and league name.

        Parameters
        ----------
        country_name : str
            Country name to filter competitions.
        league_name : str
            League name to search for.

        Returns
        -------
        pd.DataFrame | None
            DataFrame containing matching league information if found,
            otherwise None.

        Raises
        ------
        TypeError
            If country_name or league_name is not a string.
        ValueError
            If country_name or league_name is empty.
        RuntimeError
            If the competitions data cannot be processed.
        """

        try:
            # Validate country_name type
            if not isinstance(country_name, str):
                raise TypeError("country_name must be a string")

            # Validate league_name type
            if not isinstance(league_name, str):
                raise TypeError("league_name must be a string")

            # Validate empty values
            if not country_name.strip():
                raise ValueError("country_name cannot be empty")

            if not league_name.strip():
                raise ValueError("league_name cannot be empty")

            # Load competitions dataset
            df = self._get_competitions_cache()

            # Filter competitions by country
            df = df[df["country"] == country_name]

            # Perform case-insensitive league search
            result = df[ df["league"].str.lower() == league_name.lower()]

            # Return matching rows if available
            if not result.empty:
                return result

            return None

        except Exception as e:
            raise RuntimeError( f"Failed to retrieve league '{league_name}' for country '{country_name}': {str(e)}")