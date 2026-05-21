import requests

from football_scraper.providers.three_sixty_five_scores.client import Scores365Client
from football_scraper.providers.transfermarkt.client import TransfermarktClient
from football_scraper.providers.sofascore.client import SofascoreClient
from football_scraper.providers.fotmob.client import FotmobClient
from football_scraper.providers.understat.client import UnderstatClient
from football_scraper.providers.espn.client import ESPNClient
from football_scraper.providers.scoresway.client import ScoreswayClient


class FootballClient:
    def __init__(self):
        self.session = requests.Session()

        # Providers
        self.three_sixty_five_scores = Scores365Client(self.session)
        self.transfermarkt = TransfermarktClient(self.session)
        self.sofascore = SofascoreClient(self.session)
        self.fotmob = FotmobClient(self.session)
        self.understat = UnderstatClient(self.session)
        self.espn = ESPNClient(self.session)
        self.scoresway = ScoreswayClient(self.session)