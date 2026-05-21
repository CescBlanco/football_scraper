import requests 
from .competitions import FotmobCompetitionService
from .matches_live_today import FotmobMatchesTodayService
from .league import FotmobLeagueService
from .team import FotmobTeamService
from .player import FotmobPlayerService
from .match import FotmobMatchService 


class FotmobClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # Services
        self.competition = FotmobCompetitionService(self.session)
        self.matches_live_today = FotmobMatchesTodayService(self.session)
        self.league= FotmobLeagueService(self.session, self.competition)
        self.team = FotmobTeamService(self.session)

        self.player = FotmobPlayerService()
        self.match = FotmobMatchService()
        