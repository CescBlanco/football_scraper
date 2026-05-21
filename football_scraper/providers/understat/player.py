import requests
import pandas as pd

from football_scraper.providers.understat.constants import BASE_URL, DEFAULT_HEADERS

class UnderstatPlayerScraper:
    def __init__(self, session: requests.Session, team_service, headers=None):
        self.session = session
        self.team_service = team_service
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_json_player(self, team_name: str, player_name: str, season: str) -> dict:
        """
        Retrieve full JSON data for a specific player from Understat.

        The function first finds the player ID from the team squad,
        then uses it to request detailed player statistics.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season used to locate the team.

        Returns:
            dict: Raw JSON response containing full player statistics.

        Raises:
            ValueError: If the player is not found in the team squad.
            requests.exceptions.RequestException: If API request fails.
            IndexError: If player lookup fails (no match found).
        """

        # Get team squad
        squad_df = self.team_service.extract_players(team_name, season)

        # Find player ID
        filtered = squad_df[squad_df["player_name"] == player_name]

        if filtered.empty:
            raise ValueError(f"Player '{player_name}' not found in team '{team_name}'")

        player_id = filtered["id"].iloc[0]

        # Request player data
        api_url = f"https://understat.com/getPlayerData/{player_id}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        return response.json()
    
    def extract_stats_season(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract season-level statistics for a specific player from Understat.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Season-level player statistics including:
                - appearances, minutes, goals, assists
                - advanced metrics (xG, xA, etc.)
                - per-90 metrics
                - team URL information

        Raises:
            ValueError: If the player is not found in the team squad.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        # Extract season-level data
        df = pd.DataFrame(data["groups"]["season"])

        # Select relevant columns
        df = df[['season',	'team', 'position', 'games' ,'time', 'goals',  'npg', 'assists', 'shots', 'key_passes', 'yellow','red' ,'xG',  'xA',  'npxG','xGChain',	'xGBuildup' ]]
        
        # Rename columns
        df.rename(columns={'games': 'Apps','time': 'Min','goals': 'G','npg': 'NPG','assists': 'A', 'shots':'shots','key_passes': 'key pases', 'xG': 'xG','npxG': 'NPxG','xA': 'xA',
                        'xGChain': 'xGChain','xGBuildup': 'xGBuildup', 'position': 'position','yellow': 'yellow_cards',	'red':	'red_cards'}, inplace=True)

        # Convert numeric columns
        numeric_cols = ["Min", "shots", "key pases","G", "NPG", "A","xG", "NPxG", "xA", "xGChain", "xGBuildup"]

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Compute per-90 metrics
        per90_cols = ["shots", "key pases", "xG", "NPxG", "xA", "xGChain", "xGBuildup"]

        for col in per90_cols:
            df[f"{col}90"] = (df[col] / df["Min"]) * 90

        # Round values
        round_cols = per90_cols + [f"{col}90" for col in per90_cols]
        df[round_cols] = df[round_cols].round(2)

        # Combined metrics
        df["xG90 + xA90"] = (df["xG90"] + df["xA90"]).round(2)
        df["NPxG90 + xA90"] = (df["NPxG90"] + df["xA90"]).round(2)

        # Build team URL
        df['team_url'] = BASE_URL + 'team/' +   df['team'].str.replace(' ', '_') + "/" + df['season']

        return df
    
    def extract_stats_position(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract player statistics by position for a given season from Understat.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Position-based player statistics with per-90 metrics.

        Raises:
            ValueError: If player is not found in the team squad.
            requests.exceptions.RequestException: If API request fails.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        stats = data["groups"]["position"][season]

        rows = []

        for position, values in stats.items():
            rows.append({
                "position": position,
                "season": values.get("season", 0),
                "games": values.get("games", 0),
                "time": values.get("time", 0),
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "npg": values.get("npg", 0),
                "assists": values.get("assists", 0),
                "key_passes": values.get("key_passes", 0),
                "yellow_cards": values.get("yellow", 0),
                "red_cards": values.get("red", 0),
                "xG": values.get("xG", 0),
                "xA": values.get("xA", 0),
                "npxG": values.get("npxG", 0),
                "xGChain": values.get("xGChain", 0),
                "xGBuildup": values.get("xGBuildup", 0)
            })

        df = pd.DataFrame(rows)

        df.rename(columns={'games': 'Apps','time': 'Min','goals': 'G','npg': 'NPG','assists': 'A', 'shots':'shots','key_passes': 'key pases', 'xG': 'xG','npxG': 'NPxG','xA': 'xA',
                        'xGChain': 'xGChain','xGBuildup': 'xGBuildup', 'position': 'position','yellow': 'yellow_cards',	'red':	'red_cards'}, inplace=True)
        
        
        numeric_cols = ['Min', 'shots', 'key pases','G', 'NPG', 'A', 'xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        per90_cols = ['shots', 'key pases', 'xG', 'NPxG', 'xA', 'xGChain', 'xGBuildup']
        for col in per90_cols:
            df[f"{col}90"] = (df[col] / df["Min"]) * 90

        round_cols = per90_cols + [f"{c}90" for c in per90_cols]
        df[round_cols] = df[round_cols].round(2)

        df["xG90 + xA90"] = (df["xG90"] + df["xA90"]).round(2)
        df["NPxG90 + xA90"] = (df["NPxG90"] + df["xA90"]).round(2)

        return df
    
    def extract_stats_situation(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract player statistics by situation (game context) from Understat.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Situation-based performance metrics.

        Raises:
            ValueError: If player is not found in team squad.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        stats = data["groups"]["situation"][season]

        rows = []

        for situation, values in stats.items():
            rows.append({
                "situation": situation,
                "season": values.get("season", 0),
                "time": values.get("time", 0),
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "assists": values.get("assists", 0),
                "key_passes": values.get("key_passes", 0),
                "xG": values.get("xG", 0),
                "xA": values.get("xA", 0),
                "npxG": values.get("npxG", 0)
            })

        df = pd.DataFrame(rows)

        numeric_cols = ['time', 'shots', 'goals', 'assists', 'key_passes', 'xG', 'xA', 'npxG']

        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

        df["time"] = df["time"].replace(0, pd.NA)

        df["xG90"] = (df["xG"] / df["time"]) * 90
        df["xA90"] = (df["xA"] / df["time"]) * 90
        df["npxG90"] = (df["npxG"] / df["time"]) * 90

        df["xG90 + xA90"] = df["xG90"] + df["xA90"]
        df["NPxG90 + xA90"] = df["npxG90"] + df["xA90"]

        df["xG/Sh"] = df["xG"] / df["shots"]
        df["xA/KP"] = df["xA"] / df["key_passes"]

        return df.round(2)
    
    def extract_stats_shot_zones(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract player shot zone statistics from Understat.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Shot zone performance metrics.

        Raises:
            ValueError: If player is not found in team squad.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        stats = data["groups"]["shotZones"][season]

        rows = []

        for zone, values in stats.items():
            rows.append({
                "shot_zone": zone,
                "season": values.get("season", 0),
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "npg": values.get("npg", 0),
                "assists": values.get("assists", 0),
                "key_passes": values.get("key_passes", 0),
                "xG": values.get("xG", 0),
                "xA": values.get("xA", 0),
                "npxG": values.get("npxG", 0)
            })

        df = pd.DataFrame(rows)

        cols = ["shots", "key_passes", "xG", "npxG", "xA"]

        df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")

        df[cols] = df[cols].round(2)

        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xA/KP"] = (df["xA"] / df["key_passes"]).round(2)

        return df
    
    def extract_stats_shot_types(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract player shot type statistics from Understat.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Shot type performance metrics.

        Raises:
            ValueError: If player is not found in team squad.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        stats = data["groups"]["shotTypes"][season]

        rows = []

        for shot_type, values in stats.items():
            rows.append({
                "shot_type": shot_type,
                "season": values.get("season", 0),
                "shots": values.get("shots", 0),
                "goals": values.get("goals", 0),
                "npg": values.get("npg", 0),
                "assists": values.get("assists", 0),
                "key_passes": values.get("key_passes", 0),
                "xG": values.get("xG", 0),
                "xA": values.get("xA", 0),
                "npxG": values.get("npxG", 0)
            })

        df = pd.DataFrame(rows)

        cols = ["shots", "key_passes", "xG", "npxG", "xA"]

        df[cols] = df[cols].apply(pd.to_numeric, errors="coerce")

        df[cols] = df[cols].round(2)

        df["xG/Sh"] = (df["xG"] / df["shots"]).round(2)
        df["xA/KP"] = (df["xA"] / df["key_passes"]).round(2)

        return df
    
    def extract_matches_played(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract all matches played by a specific player in a given season from Understat.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Match-level player performance data including:
                - match information (teams, goals, date)
                - player performance metrics (shots, goals, xG, etc.)
                - derived metrics and URLs

        Raises:
            ValueError: If player is not found in the team squad.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        # Create DataFrame from matches
        df = pd.DataFrame(data["matches"])

        # Select relevant columns
        df =  df[['id','date', 'season' ,'h_team', 'h_goals', 'a_team' ,'a_goals' , 'position' ,'time' ,'shots' , 'goals' ,'npg', 'key_passes',  'assists',  'xG' ,'npxG', 'xA', 'xGChain','xGBuildup']]

        # Convert numeric columns safely
        numeric_cols = ["xG", "npxG", "xA", "xGChain", "xGBuildup"]

        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Round values
        df[numeric_cols] = df[numeric_cols].round(2)

        # Derived metric
        df["npxG + xA"] = (df["npxG"] + df["xA"]).round(2)

        # Build URLs
        df["match_url"] = BASE_URL + "match/" + df["id"].astype(str)
        df['team_local_url'] = BASE_URL + 'team/' +   df['h_team'].str.replace(' ', '_') + f"/{season}"
        df['team_away_url'] = BASE_URL + 'team/' +   df['a_team'].str.replace(' ', '_') + f"/{season}"

        return df
    
    def extract_shotmap(self, team_name: str, player_name: str, season: str) -> pd.DataFrame:
        """
        Extract shot map data for a specific player in a given season from Understat.

        This function retrieves all shot events for a player and enriches them
        with datetime parsing and match/team URLs.

        Args:
            team_name (str): Name of the team.
            player_name (str): Name of the player.
            season (str): Season to retrieve data for.

        Returns:
            pd.DataFrame: Shot-level dataset including:
                - shot coordinates and metadata
                - match datetime (date and time)
                - match and team URLs

        Raises:
            ValueError: If player is not found in the team squad.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        #Extracting the JSON data from a previous function 
        data= self.extract_json_player(team_name, player_name, season)

        # Build DataFrame from shots
        df = pd.DataFrame(data["shots"])

        # Convert datetime
        dt = pd.to_datetime(df['date'],  utc=True).dt.tz_convert('Europe/Madrid').drop(columns=['date'])
        df["match_date"] = dt.dt.date
        df["match_time"] = dt.dt.time

        # Drop original date column
        df.drop(columns=["date"], inplace=True)

        # Build URLs
        df["match_url"] = BASE_URL + "match/" + df["match_id"].astype(str)
        df['team_local_url'] = BASE_URL + 'team/' +   df['h_team'].str.replace(' ', '_')+ "/" + df['season']
        df['team_away_url'] = BASE_URL + 'team/' +   df['a_team'].str.replace(' ', '_') +"/" + df['season']

        return df