import requests 
from .competitions import UnderstatCompetitionScraper
from .league import UnderstatLeagueScraper
from .team import UnderstatTeamScraper
from .player import UnderstatPlayerScraper
from .match import UnderstatMatchScraper 

class UnderstatClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # Services
        self.competitions = UnderstatCompetitionScraper(self.session)
        self.league= UnderstatLeagueScraper(self.session, self.competitions)
        self.team = UnderstatTeamScraper(self.session)
        self.player = UnderstatPlayerScraper(self.session, self.team)
        self.match = UnderstatMatchScraper(self.session)