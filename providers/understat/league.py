import requests
import pandas as pd

from providers.understat.constants import BASE_URL, DEFAULT_HEADERS
from providers.understat.utils import extract_standings_total, extract_standings_home, extract_standings_away

class UnderstatLeagueScraper:
    def __init__(self, session: requests.Session, competition_service, headers=None):
        self.session = session
        self.competition_service = competition_service
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_teams(self, league_name: str, season: str = "2025") -> pd.DataFrame:
        """
        Extract team information for a given league and season from Understat.

        Args:
            league_name (str): The name of the league to query.
            season (str, optional): The season to retrieve data for (default is "2025").

        Returns:
            pd.DataFrame: A DataFrame containing:
                - team_id (str): The team identifier.
                - team_name (str): The team name.
                - team_url (str): The URL to the team's Understat page.

        Raises:
            ValueError: If the league is not found.
            requests.exceptions.RequestException: If the API request fails.
            KeyError: If the expected JSON structure is not present in the response.
        """

        # Retrieve league information (name and URL)
        selected_league = self.competition_service.get_competition(league_name)

        # Extract the league slug from the URL
        league_slug = selected_league["url"].split("/")[-1]

        # Build the API endpoint and perform the request
        api_url = f"https://understat.com/getLeagueData/{league_slug}/{season}"
        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        # Convert the teams dictionary into a DataFrame
        teams_df = pd.DataFrame(list(data["teams"].items()), columns=["team_id", "team_info"])

        # Extract and clean team names
        teams_df["team_name"] = teams_df["team_info"].apply(  lambda x: str(x["title"]))

        # Build team URLs based on name and season
        teams_df["team_url"] =   BASE_URL + "team/"  + teams_df["team_name"].str.replace(" ", "_")  + f"/{season}"

        return teams_df.drop(columns="team_info")
    
    def extract_standings(self, league_name: str, season: str = "2025", mode: str = "total") -> pd.DataFrame:
        """
        Extract league standings from Understat for a given season and mode.

        Args:
            league_name (str): Name of the league.
            season (str, optional): Season to query (default is "2025").
            mode (str, optional): Type of standings to return:
                - "total": full season
                - "home": home matches only
                - "away": away matches only

        Returns:
            pd.DataFrame: Processed standings DataFrame depending on selected mode.

        Raises:
            ValueError: If the mode is not 'total', 'home', or 'away'.
            requests.exceptions.RequestException: If the API request fails.
        """

        # Get league metadata
        selected_league = self.competition_service.get_competition(league_name)

        # Extract league slug from URL
        league_slug = selected_league["url"].split("/")[-1]

        # Build API endpoint
        api_url = f"https://understat.com/getLeagueData/{league_slug}/{season}"

        # Fetch data
        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        # Route to appropriate processing function
        if mode == "total":
            return extract_standings_total(data, season)
        elif mode == "home":
            return extract_standings_home(data, season)
        elif mode == "away":
            return extract_standings_away(data, season)
        else:
            raise ValueError("Invalid mode. Use 'total', 'home', or 'away'.")
    
    def extract_matches(self, league_name: str, season: str = "2025") -> pd.DataFrame:
        """
        Extract all match data for a given league and season from Understat.

        Args:
            league_name (str): Name of the league.
            season (str, optional): Season to retrieve (default is "2025").

        Returns:
            pd.DataFrame: DataFrame containing match information including:
                - match date and time
                - match URLs
                - home and away team URLs
                - match metadata

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        # Get league metadata
        selected_league = self.competition_service.get_competition(league_name)

        # Extract league slug from URL
        league_slug = selected_league["url"].split("/")[-1]

        # API request
        api_url = f"https://understat.com/getLeagueData/{league_slug}/{season}"
        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status() 

        data = response.json()

        # Normalize match data
        matches = pd.json_normalize(data["dates"])

        # Convert datetime to Europe/Madrid timezone
        dt = pd.to_datetime(matches['datetime'],  utc=True).dt.tz_convert('Europe/Madrid').drop(columns=['datetime'])

        # Extract date and time
        matches["match_date"] = dt.dt.date
        matches["match_time"] = dt.dt.time

        # Drop original datetime column
        matches.drop(columns=["datetime"], inplace=True)

        # Build URLs
        matches["match_url"] = BASE_URL + "match/" + matches["id"].astype(str)
        matches['team_local_url'] = BASE_URL + 'team/' +   matches['h.title'].str.replace(' ', '_') + f"/{season}"
        matches['team_away_url'] = BASE_URL + 'team/' +   matches['a.title'].str.replace(' ', '_') + f"/{season}"

        return matches
    
    def extract_stats_players(self, name_league, season_selected_understat= '2025'):
        league_selected= self.competition_service.get_competition(name_league)

        slug_league_selected= league_selected['url'].split('/')[-1]

        api= f"https://understat.com/getLeagueData/{slug_league_selected}/{season_selected_understat}"
        response = requests.get(api, headers=self.headers)
        data = response.json()

        # Creamos el DataFrame
        stats_players = pd.DataFrame(data['players'])

        # Columnas que quieres extraer
        cols_to_extract = [ 'id', 'player_name', 'team_title',  'position', 'games', 'time', 'goals', 'npg', 'assists', 'xG', 'npxG', 'xA', 'xGChain', 'xGBuildup']

        # Extraemos solo esas columnas
        df = stats_players[cols_to_extract].copy()

        # Renombramos para que quede como quieres
        df.rename(columns={'player_name': 'Player','team_title': 'Team',  'position': 'position', 'games': 'Apps','time': 'Min','goals': 'G','npg': 'NPG','assists': 'A','xG': 'xG','npxG': 'NPxG','xA': 'xA','xGChain': 'xGChain',
                            'xGBuildup': 'xGBuildup'}, inplace=True)

        # Convertimos a float las columnas numéricas
        num_cols = ['Min', 'G', 'NPG', 'A', 'xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Creamos las columnas por 90 minutos
        for col in ['xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']:
            df[f"{col}90"] = (df[col] / df['Min']) * 90

        # Redondeamos a 2 decimales
        all_cols_to_round = ['xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup'] + [f"{col}90" for col in ['xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']]
        df[all_cols_to_round] = df[all_cols_to_round].round(2)
        df['xG90 + xA90'] = (df['xG90'] + df['xA90']).round(2)
        df['NPxG90 + xA90'] = (df['NPxG90'] + df['xA90']).round(2)
        df['player_url'] = BASE_URL + "player/" +  df['id']
        df['team_url'] = BASE_URL +  df['Team'].str.replace(' ', '_') + f"/{season_selected_understat}"
        return df