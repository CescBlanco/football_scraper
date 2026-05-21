import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np
from typing import List, Dict, Optional, Any, Tuple,Union
import logging

from football_scraper.providers.sofascore.constants import DEFAULT_HEADERS, BASE_URL
from football_scraper.providers.sofascore.utils import sofascore_requests, safe_expand, safe_manager,safe_extract_players, process_team, safe_expand_one_player

class SofascoreMatchScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS

    def exctract_match_info(self, id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract detailed match information from SofaScore API.

        This function retrieves full event metadata including teams,
        venue, referee, scores, and timestamps, and returns a cleaned
        DataFrame with selected fields.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                DataFrame containing match-level detailed information.

        Raises:
            KeyError:
                If 'event' is missing in API response.

            Exception:
                Propagates request/parsing errors.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}"
        json_data = sofascore_requests(api)

        if not json_data or "event" not in json_data:
            raise KeyError("Missing 'event' in API response")

        # -----------------------------
        # Normalize JSON
        # -----------------------------
        event_details_row = pd.json_normalize(json_data["event"])

        if event_details_row.empty:
            return pd.DataFrame()

        # -----------------------------
        # KEEP YOUR ORIGINAL SCHEMA
        # -----------------------------
        cols_keep = ['winnerCode', 'id', 'slug', 	'startTimestamp','tournament.name', 'tournament.slug', 'tournament.category.name',	'tournament.category.slug',
                        'tournament.category.country.alpha3',  'roundInfo.round', 'status.description', 'venue.venueCoordinates.latitude',
                        'venue.venueCoordinates.longitude', 'venue.slug',	'venue.name','attendance',	'venue.capacity','venue.country.name',	'venue.country.slug',	'venue.id',	'venue.city.name',  'homeTeam.foundationDateTimestamp', 
                        'referee.name', 'referee.slug',	'referee.yellowCards',	'referee.redCards',	'referee.yellowRedCards',	'referee.games', 'referee.country.name',	'referee.country.slug',	'referee.id',
                        'homeTeam.name',  'homeTeam.slug',	'homeTeam.shortName', 'homeTeam.nameCode','homeTeam.country.name',	'homeTeam.country.slug',	'homeTeam.id',	'homeTeam.manager.name',
                        'homeTeam.manager.slug'	,'homeTeam.manager.shortName','homeTeam.manager.country.name','homeTeam.manager.country.slug'	,'homeTeam.manager.id', 
                        'awayTeam.name',  'awayTeam.slug',	'awayTeam.shortName', 'awayTeam.nameCode','awayTeam.country.name',	'awayTeam.country.slug',	'awayTeam.id'	,'awayTeam.manager.name',
                        'awayTeam.manager.slug'	,'awayTeam.manager.shortName','awayTeam.manager.country.name','awayTeam.manager.country.slug'	,'awayTeam.manager.id', 
                        'homeScore.current'	,	'homeScore.period1',	'homeScore.period2'	,	'awayScore.current'	,'awayScore.period1',	'awayScore.period2']


        # -----------------------------
        # Safe column selection
        # -----------------------------
        event_details = event_details_row[ [c for c in cols_keep if c in event_details_row.columns]].copy()

        # -----------------------------
        # Safe datetime conversion
        # -----------------------------
        try:
            if "startTimestamp" in event_details.columns:
                dt = pd.to_datetime(event_details["startTimestamp"],unit="s",utc=True,errors="coerce").dt.tz_convert("Europe/Madrid")

                event_details["match_date"] = dt.dt.date
                event_details["match_time"] = dt.dt.time

        except Exception as e:
            logging.warning(f"Error parsing startTimestamp: {e}")

        try:
            if "homeTeam.foundationDateTimestamp" in event_details.columns:
                dt = pd.to_datetime(event_details["homeTeam.foundationDateTimestamp"],unit="s",utc=True,errors="coerce").dt.tz_convert("Europe/Madrid")
                event_details["venue_opened_date"] = dt.dt.date

        except Exception as e:
            logging.warning(f"Error parsing foundationDateTimestamp: {e}")

        # -----------------------------
        # Drop raw timestamp columns
        # -----------------------------
        return  event_details.drop(columns=["startTimestamp","homeTeam.foundationDateTimestamp"],errors="ignore" )
    
    def extract_match_momentum(self, id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract match momentum (graph points) data from SofaScore API.

        This function retrieves time-series momentum data for a given match,
        typically used to visualize which team was dominating over time.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                DataFrame containing momentum graph points.
                Returns empty DataFrame if no data is available.

        Raises:
            KeyError:
                If API response structure is invalid.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/graph"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame()

        # -----------------------------
        # Extract graph points safely
        # -----------------------------
        graph_points = json_data.get("graphPoints")

        if not graph_points:
            logging.warning(f"No momentum data for match {id_match_sofascore}")
            return pd.DataFrame()

        df = pd.DataFrame(graph_points)

        if df.empty:
            return df

        # -----------------------------
        # Optional: basic cleaning
        # -----------------------------
        # Ensure expected columns exist
        expected_cols = ["minute", "value"]
        return df[[c for c in expected_cols if c in df.columns]]
    
    def extract_incidents(self,id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract match incidents (goals, substitutions, cards, assists, etc.)
        from SofaScore API.

        This function flattens nested player-related structures such as:
            - player
            - playerIn
            - playerOut
            - assist1

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                Flattened DataFrame containing all match incidents.

        Raises:
            KeyError:
                If 'incidents' is missing in API response.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/incidents"
        json_data = sofascore_requests(api)

        if not json_data or "incidents" not in json_data:
            raise KeyError("Missing 'incidents' in API response")

        incidents = pd.DataFrame(json_data["incidents"])

        if incidents.empty:
            return incidents

        # -----------------------------
        # Drop irrelevant columns safely
        # -----------------------------
        drop_cols = ["reversedPeriodTime","reversedPeriodTimeSeconds","isLive","playerName","id"]
        incidents = incidents.drop(columns=drop_cols, errors="ignore")

        # -----------------------------
        # Expand nested structures
        # -----------------------------
        player = safe_expand(incidents, "player", "player_incident")
        player_in = safe_expand(incidents, "playerIn", "player_in")
        player_out = safe_expand(incidents, "playerOut", "player_out")
        assist1 = safe_expand(incidents, "assist1", "assist1")

        # -----------------------------
        # Combine all
        # -----------------------------
        df = pd.concat( [incidents.drop(columns=["player", "playerIn", "playerOut", "assist1"], errors="ignore"),player,player_in,player_out,assist1],axis=1)

        return df
    
    def extract_info_managers(self, id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract home and away team managers information from SofaScore API.

        This function retrieves manager data for both teams in a match
        and returns a flattened DataFrame.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                Single-row DataFrame containing home and away manager info.

        Raises:
            KeyError:
                If API response structure is invalid.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/managers"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame()

        home = json_data.get("homeManager")
        away = json_data.get("awayManager")

        # -----------------------------
        # Build outputs safely
        # -----------------------------
        home_manager = safe_manager(home, "home")
        away_manager = safe_manager(away, "away")

        # -----------------------------
        # Combine
        # -----------------------------
        df_managers = pd.concat([home_manager, away_manager], axis=1)

        return df_managers
    
    def extract_match_stats(self, id_match_sofascore: Union[str, int],part: str = "all") -> pd.DataFrame:
        """
        Extract match statistics from SofaScore API.

        This function retrieves structured match statistics grouped by category
        (e.g. full match, first half, second half) and returns a flattened DataFrame.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

            part (str, optional):
                Match period to extract:
                    - 'all' (full match)
                    - 'firstPart' (first half)
                    - 'secondPart' (second half)

                Default is 'all'.

        Returns:
            pd.DataFrame:
                Flattened DataFrame with match statistics by group.

        Raises:
            ValueError:
                If 'part' is not valid.

            KeyError:
                If API response structure is invalid.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api_statistics = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/statistics"
        json_data = sofascore_requests(api_statistics)

        if not json_data or "statistics" not in json_data:
            raise KeyError("Missing 'statistics' in API response")

        # -----------------------------
        # Validate part
        # -----------------------------
        mapping = {"all": 0, "firstPart": 1, "secondPart": 2}
        idx = mapping.get(part)

        if idx is None:
            raise ValueError("part must be 'all', 'firstPart' or 'secondPart'")

        stats_list = json_data["statistics"]

        if not isinstance(stats_list, list) or len(stats_list) <= idx:
            return pd.DataFrame()

        groups = stats_list[idx].get("groups", [])

        if not groups:
            return pd.DataFrame()

        # -----------------------------
        # Normalize groups
        # -----------------------------
        df = pd.json_normalize(groups)

        if df.empty or "statisticsItems" not in df.columns:
            return pd.DataFrame()

        # -----------------------------
        # Explode safely
        # -----------------------------
        df_exploded = df.explode("statisticsItems")

        stats = pd.json_normalize(df_exploded["statisticsItems"])

        # -----------------------------
        # Combine
        # -----------------------------
        df_final = pd.concat([ df_exploded[["groupName"]].reset_index(drop=True),stats.reset_index(drop=True)],axis=1)

        # -----------------------------
        # Add metadata
        # -----------------------------
        df_final["match_part"] = part

        return df_final
    
    def extract_shotmap(self, id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract shotmap data from SofaScore API.

        This function retrieves all shots from a match and flattens
        nested structures including player, goalkeeper, and coordinates
        into a structured DataFrame.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                Flattened DataFrame containing all shot events.

        Raises:
            KeyError:
                If 'shotmap' is missing in API response.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api_shotmap = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/shotmap"
        json_data = sofascore_requests(api_shotmap)

        if not json_data or "shotmap" not in json_data:
            raise KeyError("Missing 'shotmap' in API response")

        match_shots = pd.DataFrame(json_data["shotmap"])

        if match_shots.empty:
            return match_shots

        # -----------------------------
        # Drop safe columns
        # -----------------------------
        match_shots = match_shots.drop(columns=["reversedPeriodTime","reversedPeriodTimeSeconds","periodTimeSeconds"],errors="ignore")

        # -----------------------------
        # Safe expand helper
        # -----------------------------
        players = match_shots.player.apply(pd.Series)
        players= players.drop(columns=['fieldTranslations', 'firstName', 'lastName'],errors='ignore')

        coordenates = match_shots.playerCoordinates.apply(pd.Series)

        goalkeeper = match_shots.goalkeeper.apply(pd.Series)
        goalkeeper= goalkeeper.drop(columns=['fieldTranslations', 'firstName', 'lastName', 'sofascoreId','userCount', 'gender'], errors='ignore')

        goalMouthCoordinates = match_shots.goalMouthCoordinates.apply(pd.Series)
        goalMouthCoordinates = goalMouthCoordinates.rename(columns= {'x':'goalMouthCoordinates_x','y' :'goalMouthCoordinates_y','z': 'goalMouthCoordinates_z'})


        blockCoordinates = match_shots.blockCoordinates.apply(pd.Series)
        blockCoordinates= blockCoordinates.drop(columns=[0])
        blockCoordinates = blockCoordinates.rename(columns= {'x':'blockCoordinates_x','y' :'blockCoordinates_y','z': 'blockCoordinates_z'})

        # -----------------------------
        # Merge everything safely
        # -----------------------------
        match_shots = pd.concat([match_shots.drop(columns=['player']), players], axis=1)
        match_shots = pd.concat([match_shots.drop(columns=['goalkeeper']), goalkeeper], axis=1)
        match_shots = pd.concat([match_shots.drop(columns=['playerCoordinates']), coordenates], axis=1)
        match_shots = pd.concat([match_shots.drop(columns=['goalMouthCoordinates']), goalMouthCoordinates], axis=1)
        match_shots = pd.concat([match_shots.drop(columns=['blockCoordinates']), blockCoordinates], axis=1)

        return match_shots
    
    def extract_head_to_head(self, id_match_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract head-to-head (H2H) data for a SofaScore match.

        This function retrieves historical comparison data between:
            - Teams (team duel)
            - Managers (manager duel)

        If no data is available, returns empty DataFrames with a message column.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            tuple:
                - pd.DataFrame: team head-to-head statistics
                - pd.DataFrame: manager head-to-head statistics

        Raises:
            KeyError:
                If API response is invalid or missing expected structure.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/h2h"
        json_data = sofascore_requests(api)

        if not json_data:
            return (pd.DataFrame({"message": ["No H2H data available"]}), pd.DataFrame({"message": ["No H2H data available"]}))

        # -----------------------------
        # TEAM DUEL
        # -----------------------------
        team_duel = json_data.get("teamDuel")

        if isinstance(team_duel, dict):
            df_teams_duels_h2h = pd.json_normalize(team_duel)
        else:
            df_teams_duels_h2h = pd.DataFrame({"message": ["No head-to-head data available for the teams."]})

        # -----------------------------
        # MANAGER DUEL
        # -----------------------------
        manager_duel = json_data.get("managerDuel")

        if isinstance(manager_duel, dict):
            df_manager_duel = pd.json_normalize(manager_duel)
        else:
            df_manager_duel = pd.DataFrame( {"message": ["No head-to-head data available for the managers."]} )

        return df_teams_duels_h2h, df_manager_duel
    
    def extract_team_form(self, id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract pre-match team form information from SofaScore API.

        This function retrieves the recent form of both teams before a match
        (e.g. last results, performance indicators).

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                Flattened DataFrame containing team form data.

        Raises:
            KeyError:
                If API response is invalid or missing expected structure.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/pregame-form"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame()

        # -----------------------------
        # Normalize safely
        # -----------------------------
        df_teams_form = pd.json_normalize(json_data)

        if df_teams_form.empty:
            return df_teams_form

        # -----------------------------
        # Drop optional column safely
        # -----------------------------

        return df_teams_form.drop(columns=["label"], errors="ignore")
    
    def extract_best_players_team(self, id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract best players summary for both teams in a match.

        This function retrieves the top-performing players from both
        home and away teams and returns a unified DataFrame.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                DataFrame containing best players from both teams.

        Raises:
            KeyError:
                If API response structure is invalid.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/best-players/summary"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame()

        # -----------------------------
        # Safe player extractor
        # -----------------------------
        

        # -----------------------------
        # Extract both teams
        # -----------------------------
        home_players = safe_extract_players( json_data.get("bestHomeTeamPlayers"), "Home")

        away_players = safe_extract_players(json_data.get("bestAwayTeamPlayers"),"Away" )

        # -----------------------------
        # Combine
        # -----------------------------
        df_final = pd.concat([home_players, away_players], ignore_index=True)

        return df_final
    
    def extract_player_of_match(self,  id_match_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract Player of the Match (POTM) from SofaScore API.

        This function retrieves the best player of a match and returns
        a flattened DataFrame with both player details and match-level
        POTM metadata.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            pd.DataFrame:
                DataFrame containing Player of the Match information.

        Raises:
            KeyError:
                If API response is invalid or missing POTM data.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/best-players/summary"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame()

        potm = json_data.get("playerOfTheMatch")

        if not potm or not isinstance(potm, dict):
            return pd.DataFrame()

        # -----------------------------
        # Build base row
        # -----------------------------
        row = pd.DataFrame([potm])

        if "player" not in row.columns:
            return pd.DataFrame()

        # -----------------------------
        # Expand player safely
        # -----------------------------
        player = row["player"].apply(lambda x: {} if not isinstance(x, dict) else x).apply(pd.Series)

        cols = ["name", "slug", "shortName","position", "jerseyNumber", "height", "id", "dateOfBirthTimestamp"]

        player = player[[c for c in cols if c in player.columns]]

        if "dateOfBirthTimestamp" in player.columns:
            player["dateOfBirthTimestamp"] = pd.to_datetime(player["dateOfBirthTimestamp"], unit="s", errors="coerce" )

        # -----------------------------
        # Combine player + metadata
        # -----------------------------
        df_final = pd.concat([player.reset_index(drop=True),row.drop(columns=["player"]).reset_index(drop=True)],axis=1)

        return df_final
    
    def extract_info_lineups(self, id_match_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract match lineups information from SofaScore API.

        This function retrieves detailed lineup data for both teams,
        including player-level information, statistics, country data,
        and market value.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            tuple:
                - pd.DataFrame: home team players
                - pd.DataFrame: away team players
                - pd.DataFrame: home team info
                - pd.DataFrame: away team info
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/lineups"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        

        # -----------------------------
        # process players (HOME)
        # -----------------------------
        players_home =pd.DataFrame(json_data['home']['players'])

        player = players_home.player.apply(pd.Series)
        player['dateOfBirth'] = pd.to_datetime(player['dateOfBirthTimestamp'], unit='s')
        player= player.drop(columns=['firstName','lastName', 'userCount', 'gender', 'sofascoreId', 'fieldTranslations','statisticsType','marketValueCurrency', 'dateOfBirthTimestamp'], errors='ignore')

        country= player.country.apply(pd.Series)
        country = country.drop(columns=['alpha2'] , errors='ignore')

        proposedMarketValueRaw= player.proposedMarketValueRaw.apply(pd.Series)
        proposedMarketValueRaw = proposedMarketValueRaw.drop(columns=['currency',0] , errors='ignore')

        player = pd.concat([player.drop(columns=['country']), country], axis=1)
        player = pd.concat([player.drop(columns=['proposedMarketValueRaw']), proposedMarketValueRaw], axis=1)
        players_home = pd.concat([players_home.drop(columns=['player']), player], axis=1)

        statistics = players_home.statistics.apply(pd.Series)
        players_home = pd.concat([players_home.drop(columns=['statistics']), statistics], axis=1)
            
        # -----------------------------
        # process players (AWAY)
        # -----------------------------
        players_away =pd.DataFrame(json_data['away']['players'])

        player = players_away.player.apply(pd.Series)
        player['dateOfBirth'] = pd.to_datetime(player['dateOfBirthTimestamp'], unit='s')
        player= player.drop(columns=['firstName','lastName', 'userCount', 'gender', 'sofascoreId', 'fieldTranslations','statisticsType', 'marketValueCurrency', 'dateOfBirthTimestamp'], errors='ignore')

        country= player.country.apply(pd.Series)
        country = country.drop(columns=['alpha2'] )

        proposedMarketValueRaw= player.proposedMarketValueRaw.apply(pd.Series)
        proposedMarketValueRaw = proposedMarketValueRaw.drop(columns=['currency',0] , errors='ignore')

        player = pd.concat([player.drop(columns=['country']), country], axis=1)
        player = pd.concat([player.drop(columns=['proposedMarketValueRaw']), proposedMarketValueRaw], axis=1)
        players_away = pd.concat([players_away.drop(columns=['player']), player], axis=1)

        statistics = players_away.statistics.apply(pd.Series)
        players_away = pd.concat([players_away.drop(columns=['statistics']), statistics], axis=1)

        # -----------------------------
        # TEAM INFO
        # -----------------------------
        home_info = pd.json_normalize(json_data.get("home", {})).drop(columns=["players", "supportStaff"], errors="ignore")
        away_info = pd.json_normalize(json_data.get("away", {})).drop( columns=["players", "supportStaff"], errors="ignore")

        return players_home, players_away, home_info, away_info
    
    def extract_teams_players_average_position(self, id_match_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract average player positions for both teams in a match.

        This function retrieves spatial average positions of players
        during a match for both home and away teams.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

        Returns:
            tuple:
                - pd.DataFrame: home team player average positions
                - pd.DataFrame: away team player average positions
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/average-positions"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame(), pd.DataFrame()

        # -----------------------------
        # Helper: safe player expand
        # -----------------------------
        
        # -----------------------------
        # HOME / AWAY
        # -----------------------------
        df_home = process_team(json_data.get("home", []))
        df_away = process_team(json_data.get("away", []))

        return df_home, df_away
    
    def extract_heatmap_player(self, id_match_sofascore: Union[str, int],player_id_match: Union[str, int]) -> pd.DataFrame:
        """
        Extract player heatmap data from SofaScore API for a specific match.

        This function retrieves spatial heatmap data representing the
        player's activity zones during a match.

        Args:
            id_match_sofascore (str | int):
                SofaScore match (event) ID.

            player_id_match (str | int):
                Player ID within the match context.

        Returns:
            pd.DataFrame:
                Heatmap data with spatial intensity values.
                Returns raise ValueError(f"No heatmap data for match={id_match_sofascore}, player={player_id_match}") if no data is available.
        """

        # -----------------------------
        # API call
        # -----------------------------
        api = f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/player/{player_id_match}/heatmap"
        json_data = sofascore_requests(api)

        if not json_data:
            return pd.DataFrame()

        # -----------------------------
        # Extract heatmap safely
        # ----------------------------

        heatmap = json_data.get("heatmap")

        if not heatmap:
            raise ValueError(f"No heatmap data for match={id_match_sofascore}, player={player_id_match}")
        

        df_heatmap = pd.DataFrame(heatmap)

        return df_heatmap
    
    def extract_shotmap_player(self, id_match_sofascore: Union[str, int],player_id_match: Union[str, int]) -> pd.DataFrame:
        """
        Extract shotmap data for a specific player in a match.

        Raises:
            ValueError:
                If API response is invalid or missing critical shotmap structure.

        Returns:
            pd.DataFrame:
                Flattened shotmap data for the player.
        """
    
        api= f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/shotmap/player/{player_id_match}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: no API response
        # -----------------------------
        if json_data is None:
            raise ValueError(f"No API response for match={id_match_sofascore}, player={player_id_match}" )

        # -----------------------------
        # Expected structure missing → exception
        # -----------------------------
        if "shotmap" not in json_data:
            raise KeyError(f"'shotmap' missing in response for match={id_match_sofascore}, player={player_id_match}")

        shotmap = json_data["shotmap"]

        # -----------------------------
        # Soft failure (no shots)
        # -----------------------------
        if not shotmap:
            raise ValueError(f"No shotmap data available for player={player_id_match} in match={id_match_sofascore}")

        # -----------------------------
        # Build dataframe
        # -----------------------------
        df_shotmap = pd.DataFrame(shotmap)

        df_shotmap = pd.concat([
            df_shotmap.drop(['player','playerCoordinates','goalMouthCoordinates','goalkeeper','blockCoordinates'],axis=1,errors='ignore'),

            safe_expand_one_player(df_shotmap, 'player', 'player_'),
            safe_expand_one_player(df_shotmap, 'playerCoordinates', 'playerCoordinates_'),
            safe_expand_one_player(df_shotmap, 'goalMouthCoordinates', 'goalMouthCoordinates_'),
            safe_expand_one_player(df_shotmap, 'goalkeeper', 'goalkeeper_'),
            safe_expand_one_player(df_shotmap, 'blockCoordinates', 'blockCoordinates_'),

            ], axis=1)

        final_cols = [
            'player_name','player_slug','player_shortName','player_position','player_jerseyNumber','player_id','playerCoordinates_x','playerCoordinates_y','playerCoordinates_z',
            'goalMouthCoordinates_x','goalMouthCoordinates_y','goalMouthCoordinates_z','blockCoordinates_x','blockCoordinates_y','blockCoordinates_z',
            'isHome','incidentType','shotType','goalType','situation','bodyPart','goalMouthLocation','xg','xgot','id','time','timeSeconds','goalkeeper_name','goalkeeper_slug','goalkeeper_shortName',
            'goalkeeper_jerseyNumber','goalkeeper_id','draw'
            ]

        return df_shotmap.reindex(columns=final_cols)

    def extract_stats_match_player(self, id_match_sofascore: Union[str, int], player_id_match: Union[str, int]) -> Tuple[str, pd.DataFrame]:

        """
        Extract player match statistics and position from SofaScore API.

        Returns:
            tuple:
                - position_match (str): Human-readable player position
                - stats_match (pd.DataFrame): Player statistics

        Raises:
            KeyError:
                If expected fields are missing in API response.
            ValueError:
                If API response is empty or invalid.
        """

        api =  f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/player/{player_id_match}/statistics"


        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: no response
        # -----------------------------
        if not json_data:
            raise ValueError( f"No API response for match={id_match_sofascore}, player={player_id_match}" )

        # -----------------------------
        # Position (critical field)
        # -----------------------------
        if "position" not in json_data:
            raise KeyError(f"Missing 'position' in response for player={player_id_match}")

        position_map = { "G": "Goalkeeper","D": "Defender", "M": "Midfielder","F": "Forward"}
        position_raw = json_data["position"]
        position_match = position_map.get(position_raw, position_raw)

        # -----------------------------
        # Statistics (critical field)
        # -----------------------------
        if "statistics" not in json_data:
            raise KeyError( f"Missing 'statistics' in response for player={player_id_match}" )

        stats_match = pd.json_normalize(json_data["statistics"])

        # -----------------------------
        # Safe column drop
        # -----------------------------
        stats_match = stats_match.drop( columns=[ "statisticsType.sportSlug", "statisticsType.statisticsType","ratingVersions.original" ], errors="ignore" )

        return position_match, stats_match
    
    def extract_events_player_match(self, id_match_sofascore: Union[str, int], player_id_match: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:

        """
        Extract player event breakdown (passes, defensive actions,
        dribbles and ball carries) from SofaScore API.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required event sections are missing.

        Returns:
            tuple of DataFrames:
                - passes
                - defensive
                - dribbles
                - ball_carries
        """

        api =  f"https://www.sofascore.com/api/v1/event/{id_match_sofascore}/player/{player_id_match}/rating-breakdown"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for match={id_match_sofascore}, player={player_id_match}")

        # -----------------------------
        # Passes
        # -----------------------------
        if "passes" not in json_data:
            raise KeyError("Missing 'passes' in API response")

        passes = pd.DataFrame(json_data['passes'])
        passes = pd.concat([
                    passes.drop(['playerCoordinates', 'passEndCoordinates'], axis=1),
                    passes['playerCoordinates'].apply(pd.Series).add_prefix('playerCoordinates_'),
                    passes['passEndCoordinates'].apply(pd.Series).add_prefix('passEndCoordinates_'),
                ], axis=1)


        # -----------------------------
        # Defensive
        # -----------------------------
        if "defensive" not in json_data:
            raise KeyError("Missing 'defensive' in API response")

        defensive = pd.DataFrame(json_data['defensive'])
        defensive = pd.concat([
                    defensive.drop(['playerCoordinates'], axis=1),
                    defensive['playerCoordinates'].apply(pd.Series).add_prefix('playerCoordinates_'),
                ], axis=1)

        # -----------------------------
        # Dribbles
        # -----------------------------
        if "dribbles" not in json_data:
            raise KeyError("Missing 'dribbles' in API response")

        dribbles = pd.DataFrame(json_data['dribbles'])
        dribbles = pd.concat([
                    dribbles.drop(['playerCoordinates'], axis=1),
                    dribbles['playerCoordinates'].apply(pd.Series).add_prefix('playerCoordinates_'),
                ], axis=1)

        # -----------------------------
        # Ball carries
        # -----------------------------
        if "ball-carries" not in json_data:
            raise KeyError("Missing 'ball-carries' in API response")

        ball_carries= pd.DataFrame(json_data['ball-carries'])
        ball_carries = pd.concat([
                    ball_carries.drop(['playerCoordinates', 'passEndCoordinates'], axis=1),
                    ball_carries['playerCoordinates'].apply(pd.Series).add_prefix('playerCoordinates_'),
                    ball_carries['passEndCoordinates'].apply(pd.Series).add_prefix('passEndCoordinates_'),
                ], axis=1)

        return passes, defensive, dribbles, ball_carries