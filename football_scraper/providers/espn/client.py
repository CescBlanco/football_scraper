import requests 
from .competitions import ESPNCompetitionScraper
from .league import ESPNLeagueScraper
from .team import ESPNTeamScraper
from .player import ESPNPlayerScraper
from .match import ESPNMatchScraper 


class ESPNClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # # Services
        self.competition = ESPNCompetitionScraper(self.session)
        self.league= ESPNLeagueScraper(self.session, self.competition)
        self.team = ESPNTeamScraper(self.session, self.league)
        self.player = ESPNPlayerScraper(self.session, self.team)
        self.match = ESPNMatchScraper(self.session)