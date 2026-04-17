import requests 
# from .competitions import Scores365CompetitionService
# from .league import Scores365LeagueScraper
from .team import SofascoreTeamScraper
from .player import SofascorePlayerScraper
# from .match import Scores365MatchScraper
from .manager import SofascoreManagerScraper
from providers.sofascore.constants import DEFAULT_HEADERS


class SofascoreClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # 🔥 SOLO aquí se configuran headers globales
        self.session.headers.update(DEFAULT_HEADERS)

        # Servicios
        # self.competition = Scores365CompetitionService(self.session)
        # self.league= Scores365LeagueScraper(self.session, self.competition)
        self.team= SofascoreTeamScraper(self.session)
        self.player= SofascorePlayerScraper(self.session)
        # self.match= Scores365MatchScraper(self.session)
        self.manager= SofascoreManagerScraper(self.session)