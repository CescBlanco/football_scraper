from .team import TransfermarktTeamScraper
from .player import TransfermarktPlayerScraper

class TransfermarktClient:
    def __init__(self, session=None):
        self.team = TransfermarktTeamScraper(session)
        self.player = TransfermarktPlayerScraper(session)