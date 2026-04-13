import requests 
from .competitions import Scores365CompetitionService
from .league import Scores365LeagueScraper
from .team import Scores365TeamScraper
from .player import Scores365PlayerScraper
from providers.three_sixty_five_scores.constants import DEFAULT_HEADERS


class Scores365Client:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # 🔥 SOLO aquí se configuran headers globales
        self.session.headers.update(DEFAULT_HEADERS)

        # Servicios
        self.competition = Scores365CompetitionService(self.session)
        self.league= Scores365LeagueScraper(self.session, self.competition)
        self.team= Scores365TeamScraper(self.session, self.competition)
        self.player= Scores365PlayerScraper(self.session)