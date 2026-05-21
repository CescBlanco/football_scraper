from .team import TransfermarktTeamScraper
from .player import TransfermarktPlayerScraper
from .competitions import TransfermarktCompetitionService
import requests 

class TransfermarktClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        self.competition = TransfermarktCompetitionService(self.session)
        self.team = TransfermarktTeamScraper(self.session, self.competition)
        self.player = TransfermarktPlayerScraper(self.session)