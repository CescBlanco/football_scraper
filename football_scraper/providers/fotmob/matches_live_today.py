import requests
import pandas as pd
from typing import List, Dict, Any,Tuple, Optional

from football_scraper.providers.fotmob.constants import  BASE_URL_MATCHES_TODAY


class FotmobMatchesTodayService:
    def __init__(self, session: requests.Session):
        self.session = session
        
    def extract_matches_live_full(self) -> pd.DataFrame:
        """
        Fetch and transform match data from a FotMob API endpoint into a flat DataFrame.

        This function retrieves match data grouped by leagues, flattens the nested JSON
        structure, and returns a pandas DataFrame where each row represents a single match
        with detailed metadata.


        Returns:
            pd.DataFrame: A DataFrame where each row corresponds to a match, including:
                - League metadata (ccode, league_name, parent league info)
                - Match identifiers and status
                - Home and away team details (IDs, names, scores)
                - Match timing and progression (halves, extra time)
                - Status descriptions and reasons

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
            ValueError: If the response is not valid JSON.
            KeyError: If expected keys like "leagues" are missing in the response.
            TypeError: If the input URL is not a string.
        """
        if not isinstance(BASE_URL_MATCHES_TODAY, str):
            raise TypeError("url must be a string")

        try:
            response = requests.get(BASE_URL_MATCHES_TODAY)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException( f"Error fetching match data from {BASE_URL_MATCHES_TODAY}: {e}")

        try:
            data: Dict[str, Any] = response.json()
        except ValueError as e:
            raise ValueError(f"Invalid JSON response from {BASE_URL_MATCHES_TODAY}: {e}")

        if "leagues" not in data:
            raise KeyError("Missing 'leagues' key in response data")

        leagues: List[Dict[str, Any]] = data.get("leagues", [])
        all_matches: List[Dict[str, Any]] = []

        for league in leagues:
            ccode = league.get("ccode")
            league_name = league.get("name")
            league_id = league.get("id")
            primary_id = league.get("primaryId")
            parent_league_name = league.get("parentLeagueName")
            matches = league.get("matches", [])

            for match in matches:
                status = match.get("status", {})
                reason = status.get("reason", {})
                halfs = status.get("halfs", {})

                all_matches.append({
                    "ccode": ccode,
                    "ccode_id": league_id,
                    "parent_league_id": primary_id,
                    "league_name": league_name,
                    "parent_league_name": parent_league_name,
                    "match_id": match.get("id"),
                    "tournament_stage": match.get("tournamentStage"),

                    "home_team_id": match.get("home", {}).get("id"),
                    "home_team_name": match.get("home", {}).get("name"),
                    "home_team_long_name": match.get("home", {}).get("longName"),
                    "home_score": match.get("home", {}).get("score"),

                    "away_team_id": match.get("away", {}).get("id"),
                    "away_team_name": match.get("away", {}).get("name"),
                    "away_team_long_name": match.get("away", {}).get("longName"),
                    "away_score": match.get("away", {}).get("score"),

                    "eliminated_team_id": str(match.get("eliminatedTeamId")),

                    "status_id": match.get("statusId"),
                    "finished": status.get("finished"),
                    "started": status.get("started"),
                    "cancelled": status.get("cancelled"),
                    "awarded": status.get("awarded"),

                    "score_str": status.get("scoreStr"),
                    "global_score_str": status.get("aggregatedStr"),

                    "reason_short": reason.get("short"),
                    "reason_long": reason.get("long"),

                    "match_time_local": pd.to_datetime(match.get("time"),format="%d.%m.%Y %H:%M", errors="coerce"),

                    "first_half_started": halfs.get("firstHalfStarted"),
                    "second_half_started": halfs.get("secondHalfStarted"),
                    "first_extra_half_started": halfs.get("firstExtraHalfStarted"),
                    "second_extra_half_started": halfs.get("secondExtraHalfStarted"),

                    "period_length": status.get("periodLength"),
                })

        return pd.DataFrame(all_matches)    