import requests 
from .competitions import SofascoreCompetitionService
from .league import SofascoreLeagueService
from .team import SofascoreTeamScraper
from .player import SofascorePlayerScraper
from .match import SofascoreMatchScraper
from .manager import SofascoreManagerScraper
from football_scraper.providers.sofascore.constants import DEFAULT_HEADERS


class SofascoreClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # 🔥 SOLO aquí se configuran headers globales
        self.session.headers.update(DEFAULT_HEADERS)

        # Servicios
        self.competition = SofascoreCompetitionService(self.session)
        self.league= SofascoreLeagueService(self.session, self.competition)
        self.team= SofascoreTeamScraper(self.session)
        self.player= SofascorePlayerScraper(self.session)
        self.match= SofascoreMatchScraper(self.session)
        self.manager= SofascoreManagerScraper(self.session)