import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
import matplotlib.pyplot as plt

from football_scraper.providers.understat.constants import BASE_URL, DEFAULT_HEADERS
from football_scraper.providers.understat.utils import extract_team_info, parse_data_squads_match, extract_value, extract_pct

class UnderstatMatchScraper:
    def __init__(self, session: requests.Session, headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_lineups(self, url_match: str) -> pd.DataFrame:
        """
        Extract full match lineups and player statistics from Understat.

        This function retrieves both home and away lineups, combines them,
        and enriches them with team and player URLs.

        Args:
            url_match (str): Match URL from Understat.

        Returns:
            pd.DataFrame: Combined lineup data for both teams.

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        match_id = url_match.split("/")[-1]

        api_url = f"https://understat.com/getMatchData/{match_id}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        # Extract team info
        teams = { "h": extract_team_info(data["tmpl"]["home"]), "a": extract_team_info(data["tmpl"]["away"]) }

        # Parse lineups
        df_home = parse_data_squads_match(data, team_side="h")
        df_away = parse_data_squads_match(data, team_side="a")

        df = pd.concat([df_home, df_away], axis=0, ignore_index=True)

        # Map team names
        df["team_name"] = df['h_a'].map({k: v['name'] for k, v in teams.items()})

        # Player URLs
        df["player_url"] = BASE_URL + "player/" + df["player_id"].astype(str)

        # Team URLs
        df['team_url'] = df['h_a'].map( {k: v['url'] for k, v in teams.items()})
        
        return df
    
    def extract_match_stats(self, url_match: str) -> pd.DataFrame:
        """
        Extract match statistical comparison (progress bars) from Understat.

        This function scrapes the match page and parses visual progress-bar
        statistics such as possession, shots, xG-related comparisons, etc.

        Args:
            url_match (str): Understat match URL.

        Returns:
            pd.DataFrame: Match statistics including:
                - stat name
                - home/away/draw values
                - percentage breakdowns

        Raises:
            requests.exceptions.RequestException: If page request fails.
            AttributeError: If expected HTML structure is missing.
        """

        match_id = url_match.split("/")[-1]

        url = f"https://understat.com/match/{match_id}"
        html = self.session.get(url).text

        soup = BeautifulSoup(html, "html.parser")

        rows = []

        for bar in soup.select(".progress-bar"):

            title = bar.select_one(".progress-title")
            if not title:
                continue

            home = bar.select_one(".progress-home")
            away = bar.select_one(".progress-away")
            draw = bar.select_one(".progress-draw")

            row = {
                "stat": title.text.strip(),

                "home": extract_value(home),
                "home_pct": extract_pct(home, "width"),

                "away": extract_value(away),
                "away_pct": extract_pct(away, "width"),

                "draw": extract_value(draw),
                "draw_pct": extract_pct(draw, "width")
            }

            # Fix missing percentages when only one side is present
            if row["home_pct"] is None and extract_pct(home, "left") == 0:
                row["home_pct"] = 0

            if row["home_pct"] is not None and row["away_pct"] is None:
                row["away_pct"] = 100 - row["home_pct"]

            if row["away_pct"] is not None and row["home_pct"] is None:
                row["home_pct"] = 100 - row["away_pct"]

            rows.append(row)

        df = pd.DataFrame(rows)

        # Convert percentage columns safely
        for col in ["home_pct", "away_pct", "draw_pct"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").round(2)

        # Fill missing raw values with percentages if needed
        for side in ["home", "away", "draw"]:
            pct_col = f"{side}_pct"
            if pct_col in df.columns:
                df[side] = df[side].fillna(df[pct_col])

        return df
    
    def extract_shotmap(self, url_match: str) -> pd.DataFrame:
        """
        Extract all shots from a match (home + away) using Understat API.

        Args:
            url_match (str): Understat match URL.

        Returns:
            pd.DataFrame: Combined shot data for both teams including metadata
            such as player, match time, xG, team info and URLs.

        Raises:
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected JSON structure is missing.
        """

        match_id = url_match.split("/")[-1]

        api_url = f"https://understat.com/getMatchData/{match_id}"

        response = self.session.get(api_url, headers=self.headers)
        response.raise_for_status()

        data = response.json()

        shots_home = pd.DataFrame(data["shots"]["h"])
        shots_away = pd.DataFrame(data["shots"]["a"])

        df = pd.concat([shots_home, shots_away], axis=0, ignore_index=True)

        dt = pd.to_datetime(df["date"], utc=True).dt.tz_convert("Europe/Madrid")
        df["match_date"] = dt.dt.date
        df["match_time"] = dt.dt.time

        df.drop(columns=["date"], inplace=True)

        df["match_url"] = BASE_URL + "match/" + df["match_id"].astype(str)
        df["player_url"] = BASE_URL + "player/" + df["player_id"].astype(str)

        df["team_local_url"] = BASE_URL + "team/" + df["h_team"].str.replace(" ", "_") + "/" + df["season"]
        df["team_away_url"] = BASE_URL + "team/" + df["a_team"].str.replace(" ", "_") + "/" + df["season"]

        return df
    
    def extract_timing_chart(self, url_match: str):
        """
        Prepare match data for xG timing chart visualization.

        Splits shots into home and away teams and computes cumulative xG.

        Args:
            url_match (str): Understat match URL.

        Returns:
            tuple:
                - df (pd.DataFrame): All shots
                - df_home (pd.DataFrame): Home team shots with cumulative xG
                - goals_home (pd.DataFrame): Home team goals
                - df_away (pd.DataFrame): Away team shots with cumulative xG
                - goals_away (pd.DataFrame): Away team goals
        """

        df = self.extract_shotmap(url_match)

        df = pd.DataFrame(df)[["minute", "xG", "h_a", "player", "player_id", "result"]]

        df["minute"] = pd.to_numeric(df["minute"])
        df["xG"] = pd.to_numeric(df["xG"])
        df["is_goal"] = df["result"] == "Goal"

        df_home = df[df["h_a"] == "h"].copy().sort_values("minute")
        df_away = df[df["h_a"] == "a"].copy().sort_values("minute")

        df_home["cum_xG"] = df_home["xG"].cumsum().round(2)
        df_away["cum_xG"] = df_away["xG"].cumsum().round(2)

        df_home.reset_index(drop=True, inplace=True)
        df_away.reset_index(drop=True, inplace=True)

        goals_home = df_home[df_home["is_goal"]]
        goals_away = df_away[df_away["is_goal"]]

        return df, df_home, goals_home, df_away, goals_away
    
    def plot_timing_chart(self, url_match: str):
        """
        Plot xG timeline chart for a match showing cumulative xG and goals.

        Args:
            url_match (str): Understat match URL.

        Returns:
            matplotlib.figure.Figure: xG timeline plot.
        """

        df, df_home, goals_home, df_away, goals_away = self.extract_timing_chart(url_match)

        fig, ax = plt.subplots(figsize=(10, 6))

        # HOME
        ax.step(df_home["minute"], df_home["cum_xG"],
                where="post", color="blue", linewidth=2, label="Home")
        ax.fill_between(df_home["minute"], df_home["cum_xG"],
                        step="post", color="blue", alpha=0.2)

        # AWAY
        ax.step(df_away["minute"], df_away["cum_xG"],
                where="post", color="red", linewidth=2, label="Away")
        ax.fill_between(df_away["minute"], df_away["cum_xG"],
                        step="post", color="red", alpha=0.2)

        # GOALS
        ax.scatter(goals_home["minute"], goals_home["cum_xG"],
                color="blue", s=160, edgecolors="black", zorder=5)

        ax.scatter(goals_away["minute"], goals_away["cum_xG"],
                color="red", s=160, edgecolors="black", zorder=5)

        # AXIS CONFIG
        last_minute = df["minute"].max()

        ax.set_xlim(0, last_minute)
        ax.set_xticks([0, 15, 30, 45, 60, 75, 90])

        ax.set_xlabel("Minute")
        ax.set_ylabel("Cumulative xG")
        ax.set_title("Expected Goals (xG) Timeline")
        ax.legend()
        ax.grid(alpha=0.2)

        return fig