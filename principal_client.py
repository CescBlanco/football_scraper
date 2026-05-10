import requests

from providers.three_sixty_five_scores.client import Scores365Client
from providers.transfermarkt.client import TransfermarktClient
from providers.sofascore.client import SofascoreClient
from providers.fotmob.client import FotmobClient
from providers.understat.client import UnderstatClient
from providers.espn.client import ESPNClient


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