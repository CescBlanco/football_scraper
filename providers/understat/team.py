import pandas as pd
import requests

from providers.understat.constants import DEFAULT_HEADERS, BASE_URL
#from providers.sofascore.utils import sofascore_requests, clear_data_transfers, extract_start_year,get_all_next_events_fast, clean_events,process_players, extract_top_players_stats_available

class UnderstatTeamScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS
        self._team_cache = None

    def extract_players(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract basic player information for a given team and season from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: DataFrame containing player identifiers and basic metadata:
                - id (str)
                - player_name (str)
                - team_title (str)
                - position (str)
                - player_url (str)
                - team_url (str)

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        players_df = pd.DataFrame(data["players"])

        # Select relevant columns
        columns = ["id", "player_name", "team_title", "position"]
        df = players_df[columns].copy()

        # Build URLs
        df["player_url"] = BASE_URL + "player/" + df["id"].astype(str)
        df['team_url'] = BASE_URL + 'team/' +   df['team_title'].str.replace(' ', '_') + f"/{season}"

        self._team_cache = df
        return df

    def extract_matches(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract all match data for a specific team and season from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Match data including predictions, URLs, and metadata.

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        # Format team name for API
        team_slug = team_name.replace(" ", "_")

        # API request
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"
        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        # Normalize match data
        df = pd.json_normalize(data["dates"])

        # Convert datetime
        dt = pd.to_datetime(df['datetime'],  utc=True).dt.tz_convert('Europe/Madrid').drop(columns=['datetime'])
        df["match_date"] = dt.dt.date
        df["match_time"] = dt.dt.time

        # Drop original datetime column
        df.drop(columns=["datetime"], inplace=True)

        # Build match URL
        df["match_url"] = BASE_URL + "match/" + df["id"].astype(str)

        # Rename prediction columns
        df.rename(columns={"forecast.w": "predict_win_local","forecast.d": "predict_draw","forecast.l": "predict_win_visitor"}, inplace=True)

        # Build team URLs
        df['team_local_url'] = BASE_URL + 'team/' +   df['h.title'].str.replace(' ', '_') + f"/{season}"
        df['team_away_url'] = BASE_URL + 'team/' +   df['a.title'].str.replace(' ', '_') + f"/{season}"

        return df
    
    def extract_stats_situation(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract team shooting statistics by situation from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Situation-based stats including shots, goals and xG metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["situation"]

        rows = []

        # Build rows per situation type
        for situation, values in stats.items():
            rows.append({
                "situation": situation,
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        # Derived metrics
        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xGA/ShA"] = (df["against_xG"] / df["against_shots"]).round(2)

        return df
    
    def extract_stats_attack_speed(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract attack speed statistics for a team from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Attack speed categories with shooting and xG metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["attackSpeed"]

        rows = []

        for speed_type, values in stats.items():
            rows.append({
                "attack_speed": speed_type,
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xGA/ShA"] = (df["against_xG"] / df["against_shots"]).round(2)

        return df
    
    def extract_stats_formation(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract formation-based statistics for a team from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Formation statistics including xG per 90 metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["formation"]

        rows = []

        for formation, values in stats.items():
            rows.append({
                "formation": formation,
                "time": values.get("time", 0),
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG90"] = (df["xG"] / df["time"] * 90).round(2)
        df["xGA90"] = (df["against_xG"] / df["time"] * 90).round(2)

        return df
    
    def extract_stats_game_state(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract game state statistics for a team from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Game state performance metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["gameState"]

        rows = []

        for state, values in stats.items():
            rows.append({
                "game_state": state,
                "time": values.get("time", 0),
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG90"] = (df["xG"] / df["time"] * 90).round(2)
        df["xGA90"] = (df["against_xG"] / df["time"] * 90).round(2)

        return df
    
    def extract_stats_result(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract match result-based statistics for a team from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Result-based performance metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["result"]

        rows = []

        for result_type, values in stats.items():
            rows.append({
                "result_type": result_type,
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xGA/ShA"] = (df["against_xG"] / df["against_shots"]).round(2)

        return df
    
    def extract_stats_shot_zone(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract shot zone statistics for a team from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Shot zone distribution with xG metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["shotZone"]

        rows = []

        for zone, values in stats.items():
            rows.append({
                "shot_zone": zone,
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xGA/ShA"] = (df["against_xG"] / df["against_shots"]).round(2)

        return df

    def extract_stats_timing(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract time-based shot statistics for a team from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Timing-based performance metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        stats = data["statistics"]["timing"]

        rows = []

        for timing, values in stats.items():
            rows.append({
                "timing": timing,
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "xG": values.get("xG", 0),
                "against_shots": values.get("against", {}).get("shots", 0),
                "against_goals": values.get("against", {}).get("goals", 0),
                "against_xG": values.get("against", {}).get("xG", 0)
            })

        df = pd.DataFrame(rows)

        df[["xG", "against_xG"]] = df[["xG", "against_xG"]].round(2)
        df["xGD"] = (df["xG"] - df["against_xG"]).round(2)
        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xGA/ShA"] = (df["against_xG"] / df["against_shots"]).round(2)

        return df
    
    def extract_stats_player_team(self, team_name: str, season: str) -> pd.DataFrame:
        """
        Extract player statistics for a given team and season from Understat.

        Args:
            team_name (str): Name of the team.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Player performance statistics including per-90 metrics.

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        team_slug = team_name.replace(" ", "_")
        api_url = f"https://understat.com/getTeamData/{team_slug}/{season}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        players_df = pd.DataFrame(data["players"])

        # Columns to keep
        columns = ['id', 'player_name', 'team_title','position', 'games', 'time', 'goals', 'npg', 'assists', 'shots','key_passes',   'xG', 'npxG', 'xA', 'xGChain', 'xGBuildup' , 'yellow_cards', 	'red_cards']

        df = players_df[columns].copy()

        # Rename columns for clarity
        df.rename(columns={'player_name': 'Player','team_title': 'Team','games': 'Apps','time': 'Min','goals': 'G','npg': 'NPG','assists': 'A', 'shots':'shots','key_passes': 'key pases', 'xG': 'xG','npxG': 'NPxG','xA': 'xA','xGChain': 'xGChain',
                            'xGBuildup': 'xGBuildup', 'position': 'position'}, inplace=True)

        # Convert numeric columns
        numeric_cols = ['Min', 'shots', 'key pases','G', 'NPG', 'A', 'xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Compute per-90 metrics
        per90_cols = ['shots', 'key pases', 'xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']

        for col in per90_cols:
            df[f"{col}90"] = (df[col] / df["Min"]) * 90

        # Round values
        round_cols = per90_cols + [f"{col}90" for col in per90_cols]
        df[round_cols] = df[round_cols].round(2)

        # Combined metrics
        df["xG90 + xA90"] = (df["xG90"] + df["xA90"]).round(2)
        df["NPxG90 + xA90"] = (df["NPxG90"] + df["xA90"]).round(2)

        # Build URLs
        df["player_url"] = BASE_URL + "player/" + df["id"].astype(str)
        df['team_url'] = BASE_URL + 'team/' +   df['Team'].str.replace(' ', '_') + f"/{season}"

        return df
    