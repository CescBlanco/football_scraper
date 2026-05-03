import requests
import pandas as pd

from bs4 import BeautifulSoup
from providers.understat.constants import BASE_URL


class UnderstatCompetitionScraper:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None

    def build_competitions_dict(self, url: str) -> dict:
        """
        Fetch competition links from an Understat webpage and build a dictionary
        mapping competition names to their corresponding URLs.

        Args:
            url (str): The URL of the Understat page to scrape.

        Returns:
            dict[str, str]: A dictionary where:
                - keys are competition names (str)
                - values are full competition URLs (str)

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails
                (e.g., connection error, timeout, invalid response).
            AttributeError: If the expected HTML structure is not found
                (e.g., missing footer or links).
            KeyError: If an expected attribute (such as 'href') is missing.
        """

        # Send an HTTP GET request to the provided URL
        response = self.session.get(url)

        # Raise an exception if the response contains an HTTP error status code
        response.raise_for_status()

        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        # Locate the footer section of the page by its id
        footer = soup.find("footer", id="footer")

        # Find all anchor tags (<a>) inside the footer with href starting with "league/"
        league_links = footer.find_all("a", href=lambda x: x and x.startswith("league/"))

        # Initialize a list to store intermediate competition data
        competitions = []

        # Iterate through each league link found
        for league in league_links:
            # Append a dictionary with the competition name and full URL
            competitions.append({"name": league.text.strip(),  "url": BASE_URL + league["href"]   })

        # Convert the list into a dictionary: {competition_name: competition_url}
        competitions_dict = {competition["name"]: competition["url"]for competition in competitions}

        # Return the resulting dictionary

        self._competitions_cache = competitions_dict
        return competitions_dict

    def list_competitions(self) -> list[str]:
        """
        Generate a list of unique competition names from the COMPETITIONS_UNDERSTAT dictionary.

        Returns:
            list[str]: A list of unique competition names.

        Raises:
            AttributeError: If COMPETITIONS_UNDERSTAT does not have a 'keys' method.
            TypeError: If COMPETITIONS_UNDERSTAT is not an iterable mapping.
        """

        # Initialize a set to keep track of already seen competition names
        seen_names = set()

        # Initialize a list to store unique competition names
        competition_list = []

        # Iterate over all competition names (dictionary keys)
        for name in self._competitions_cache.keys():
            if name not in seen_names:
                seen_names.add(name)
                competition_list.append(name)

        # Return the list of unique competition names
        return competition_list
    
    def get_competition(self, name: str) -> dict[str, str]:
        """
        Retrieve a competition from the COMPETITIONS_UNDERSTAT dictionary by name.

        The search is case-insensitive and ignores leading/trailing whitespace.

        Args:
            name (str): The name of the competition to search for.

        Returns:
            dict[str, str]: A dictionary containing:
                - "name": the original competition name (str)
                - "url": the competition URL (str)

        Raises:
            ValueError: If the competition is not found.
            AttributeError: If COMPETITIONS_UNDERSTAT is not a valid mapping.
        """

        # Normalize input for case-insensitive comparison
        normalized_name = name.lower().strip()

        # Iterate through available competitions to find a match
        for competition_name, url in self._competitions_cache.items():
            if competition_name.lower() == normalized_name:
                return {"name": competition_name,"url": url}

        # Raise an error if no matching competition is found
        raise ValueError(f"Competition not found: {normalized_name}")    