import requests 
from .competitions import ScoreswayCompetitionScraper
from .league import ScoreswayLeagueScraper
from .team import ScoreswayTeamScraper
from .player import ScoreswayPlayerScraper
from .pre_match import ScoreswayPreMatchScraper 
from .post_match import ScoreswayPostMatchScraper 
from .events_match import ScoreswayEventsMatchScraper 


class ScoreswayClient:
    def __init__(self, session=None):
        self.session = session or requests.Session()

        # # Services
        self.competition = ScoreswayCompetitionScraper(self.session)
        self.league= ScoreswayLeagueScraper(self.session, self.competition)
        self.team = ScoreswayTeamScraper(self.session, self.league)
        self.player = ScoreswayPlayerScraper(self.session, self.team)
        self.pre_match = ScoreswayPreMatchScraper(self.session)
        self.post_match = ScoreswayPostMatchScraper(self.session)
        self.events_match = ScoreswayEventsMatchScraper(self.session)