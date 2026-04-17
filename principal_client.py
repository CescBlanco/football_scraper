import requests

from providers.three_sixty_five_scores.client import Scores365Client
from providers.transfermarkt.client import TransfermarktClient
from providers.transfermarkt.client import SofascoreClient

class FootballClient:
    def __init__(self):
        self.session = requests.Session()

        # Providers
        self.three_sixty_five_scores = Scores365Client(self.session)
        self.transfermarkt = TransfermarktClient(self.session)
        self.sofascore = SofascoreClient(self.session)