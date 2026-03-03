import requests
from bs4 import BeautifulSoup

from providers.transfermarkt.constants import BASE_URL, COMPETITIONS_URL, DEFAULT_HEADERS
from providers.transfermarkt.utils import extract_competition_id

class TransfermarktCompetitionService:
    def __init__(self, session: requests.Session):
        self.session = session
        self._competitions_cache = None
 
    def fetch_all(self, url: str) -> dict:

        competitions_dict = {}

        try:
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            for section in soup.select("section.tm-button-list__wrapper"):
                category = section.find("h2")
                category = category.text.strip() if category else "Other"
                competitions_dict.setdefault(category, {})

                for li in section.select("ul.tm-button-list li"):
                    link = li.find("a", class_="tm-button-list__list-item")
                    label = li.find("a", class_="tm-button-list__list-item--label")
                    if not (link and label):
                        continue

                    full_url = f"{BASE_URL}{link['href']}"
                    comp_id = extract_competition_id(full_url)
                    slug_nation = full_url.rsplit("/", 1)[-1]

                    imgs = link.find_all("img") + [None, None]
                    logo = imgs[0]["src"] if imgs[0] else None
                    nation = imgs[1]["alt"] if imgs[1] else None
                    flag = imgs[1]["src"] if imgs[1] else None

                    name = label.text.strip()
                    display_name = f"{name} - {nation} ({slug_nation})" if nation else name

                    competitions_dict[category][comp_id] = {
                        "name": name,
                        "nation": nation,
                        "display_name": display_name,
                        "slug_nation": slug_nation,
                        "url": full_url,
                        "logo": logo,
                        "flag": flag,
                    }

        except requests.RequestException as e:
            raise RuntimeError(f"Error fetching URL {url}") from e
        
        self._competitions_cache = competitions_dict
        return competitions_dict
    
    def get_by_name(self, name: str):
        """Search for a competition by its display_name (case-insensitive)."""
        if not self._competitions_cache:
            raise RuntimeError("Competitions not loaded. Call fetch_all() first.")
        
        name = name.lower().strip()

        for category in self._competitions_cache.values():
            for comp in category.values():
                    if comp["display_name"].lower() == name:
                        return comp
                    
        raise ValueError(f"Competition not found: {name}")


    def list_all(self):
        """Return a list of unique display_names for all competitions."""
        if not self._competitions_cache:
            raise RuntimeError("Competitions not loaded. Call fetch_all() first.")
        
        return [
            comp["display_name"]
            for category in self._competitions_cache.values()
            for comp in category.values()
        ]

