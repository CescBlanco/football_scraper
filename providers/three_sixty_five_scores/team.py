import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np
from typing import List, Dict, Optional, Any, Tuple

from providers.three_sixty_five_scores.constants import DEFAULT_HEADERS, BASE_URL
from providers.three_sixty_five_scores.utils import get_competition_id

class Scores365TeamScraper:
    def __init__(self, session, competition_service, headers=None):
        self.session = session
        self.competition_service = competition_service
        self.headers = headers if headers else DEFAULT_HEADERS
    
    def extract_squad_and_competition_available(self, url: str) -> pd.DataFrame:
        """
        Extract squad information for a team from the 365Scores API.

        This function retrieves player data for a given team, including
        positions, formation roles, images, and birthdates.

        Args:
            url (str):
                Team URL containing the team ID at the end.

        Returns:
            pd.DataFrame:
                DataFrame containing squad information with columns such as:

                - id (player_id)
                - name
                - position
                - formationPosition
                - birthdate
                - player_image

        Raises:
            ValueError:
                If the team ID cannot be extracted.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected JSON structure is not present.
        """
        
        # Extract team ID
        id_team = url.split("-")[-1]

        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")

        url_team_squad = f'https://webws.365scores.com/web/squads/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitors={id_team}'

        # API request
        try:
            response = requests.get(url_team_squad, headers=self.headers, timeout=10)
            response.raise_for_status()
            squad= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException( f"Error retrieving squad data: {e}") from e

        # Validate JSON structure
        if "squads" not in squad or not squad["squads"]:
            raise KeyError("Invalid API response: 'squads' not found.")

        athletes = squad["squads"][0].get("athletes", [])

        if not athletes:
            return pd.DataFrame()  # return empty DF safely

        df = pd.DataFrame(athletes)

        # Safe transformations
        if "position" in df.columns:
            df["position"] = df["position"].apply(lambda x: x.get("name", "Staff") if isinstance(x, dict) else "Staff")

        if "formationPosition" in df.columns:
            df["formationPosition"] = df["formationPosition"].apply(lambda x: x.get("name") if isinstance(x, dict) else None)

        if "id" in df.columns:
            df["player_image"] = df["id"].apply(
                lambda x: (F"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}"))

        if "birthdate" in df.columns:
            df["birthdate"] = df["birthdate"].str.split("T").str[0]

        return df.drop(columns=["gender", "sportId", "clubId", "imageVersion", "createdAt"], errors="ignore" )
    
    def extract_competition_available(self, url: str) -> pd.DataFrame:
        """
        Extract competitions in which a team participates from the 365Scores API.

        Args:
            url (str):
                Team URL containing the team ID at the end.

        Returns:
            pd.DataFrame:
                DataFrame containing available competitions with basic metadata
                and competition image URLs.

        Raises:
            ValueError:
                If the team ID cannot be extracted.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the expected JSON structure is missing.
        """

        # Extract team ID
        id_team = url.split("-")[-1]
        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")

        url_team_squad = f'https://webws.365scores.com/web/squads/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitors={id_team}'

        # API request
        try:
            response = requests.get(url_team_squad, headers=self.headers, timeout=10)
            response.raise_for_status()
            squad= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving competitions data: {e}") from e

        # Validate JSON structure
        if "competitions" not in squad:
            raise KeyError("Invalid API response: 'competitions' not found.")

        competitions_available = squad.get("competitions", [])

        if not competitions_available:
            return pd.DataFrame()

        df = pd.DataFrame(competitions_available)

        # Drop unnecessary columns safely
        drop_columns = ['hasStandings', 'hasLiveStandings', 'hasStandingsGroups','sportId', 'hasBrackets', 'currentPhaseNum','currentStageType', 'competitorsType', 'currentSeasonNum',
            'currentStageNum', 'hasStats', 'popularityRank', 'color','imageVersion', 'isInternational', 'hasHistory','shortName', 'createdAt']
        df = df.drop(columns=drop_columns, errors="ignore")

        # Add competition image URL
        if "id" in df.columns:
            df["competition_image"] = df["id"].apply(lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_24,h_24,c_limit,q_auto:eco,dpr_3,d_Countries:Round:4.png/v2/Competitions/{x}" )

        return df
    
    def extract_recent_form(self, url_team: str) -> pd.DataFrame:
        """
        Extract recent form (last matches) for a team from the 365Scores API.

        Args:
            url_team (str):
                Team URL containing the team ID.

        Returns:
            pd.DataFrame:
                DataFrame with recent matches, including:
                - match_date
                - match_time
                - competition info
                - result color indicator

        Raises:
            ValueError:
                If the team ID cannot be extracted.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If expected keys are missing in the API response.
        """

        # Extract team ID
        id_team = url_team.split("-")[-1]
        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")

        url_recent_form = f"https://webws.365scores.com/web/competitors/recentForm?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitor={id_team}&numOfGames=8"

        # API request
        try:
            response = requests.get(url_recent_form, headers=self.headers, timeout=10)
            response.raise_for_status()
            recent_form= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving recent form: {e}") from e

        # Validate JSON
        if "competitions" not in recent_form or "games" not in recent_form:
            raise KeyError("Invalid API response: missing 'competitions' or 'games'.")

        # --- Competitions ---
        competitions = pd.json_normalize(recent_form["competitions"])

        competitions = competitions.drop(
            columns=['sportId', 'shortName', 'countryId', 'hasStandings','hasStandingsGroups', 'hasBrackets', 'hasStats', 'popularityRank', 'imageVersion', 'currentStageType',
                'color', 'competitorsType', 'currentPhaseNum','currentSeasonNum', 'currentStageNum', 'isInternational','hasHistory', 'hasLiveStandings'],errors="ignore")

        competitions = competitions.rename( columns={ "id": "competitionId","name": "competition","nameForURL": "competition_for_url"})

        # --- Games ---
        games = pd.json_normalize(recent_form["games"])

        if games.empty:
            return games

        # Safe date parsing
        games["match_date"] = games["startTime"].str.split("T").str[0]
        games["match_time"] = games["startTime"].str.split("T").str[1].str.split("+").str[0]

        # Drop unnecessary columns
        games = games.drop(
            columns=['sportId', 'statusGroup', 'shortStatusText','gameTimeAndStatusDisplayType', 'homeAwayTeamOrder','groupNum', 'scores', 'startTime','hasPointByPoint', 'hasVideo',
                    'homeCompetitor.sportId', 'homeCompetitor.isWinner','homeCompetitor.type', 'homeCompetitor.popularityRank','homeCompetitor.outcome', 'homeCompetitor.imageVersion',
                    'homeCompetitor.hasSquad', 'homeCompetitor.hasTransfers','homeCompetitor.competitorNum', 'homeCompetitor.hideOnSearch','homeCompetitor.hideOnCatalog', 'homeCompetitor.countryId',
                    'awayCompetitor.countryId', 'awayCompetitor.sportId','awayCompetitor.isWinner', 'awayCompetitor.type','awayCompetitor.popularityRank', 'awayCompetitor.outcome',
                    'awayCompetitor.imageVersion', 'awayCompetitor.hasSquad','awayCompetitor.hasTransfers', 'awayCompetitor.competitorNum','awayCompetitor.hideOnSearch', 'awayCompetitor.hideOnCatalog',
                    'homeCompetitor.aggregatedScore','awayCompetitor.aggregatedScore'
                    ],errors="ignore")

        # --- Result color mapping ---
        if "outcome" in games.columns:
            conditions = [
                games["outcome"] == 0,  # Draw
                games["outcome"] == 1,  # Win
                games["outcome"] == 2   # Loss
            ]

            choices = ['#FFA500', '#008000', '#FF0000']

            games["color_result"] = np.select(conditions,choices,default="#000000")

        # --- Merge ---
        df_recent_form_team = games.merge( competitions,how="left", on="competitionId")

        return df_recent_form_team
    
    def extract_next_matches(self, url_team: str) -> pd.DataFrame:
        """
        Extract upcoming scheduled matches for a team from the 365Scores API.

        Args:
            url_team (str):
                Team URL containing the team ID.

        Returns:
            pd.DataFrame:
                DataFrame containing upcoming matches with cleaned columns,
                including match date and time.

        Raises:
            ValueError:
                If the team ID cannot be extracted.

            requests.exceptions.RequestException:
                If the API request fails.

            KeyError:
                If the API response structure is invalid.
        """

        # Extract team ID
        id_team = url_team.split("-")[-1]
        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")

        url_next_matches = f"https://webws.365scores.com/web/games/current/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitors={id_team}"

        # API request
        try:
            response = requests.get(url_next_matches, headers=self.headers, timeout=10)
            response.raise_for_status()
            next_matches= response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException( f"Error retrieving next matches: {e}") from e

        # Validate JSON
        if "games" not in next_matches:
            raise KeyError("Invalid API response: 'games' not found.")

        games = next_matches.get("games", [])
        if not games:
            return pd.DataFrame()

        df = pd.json_normalize(games)

        # Filter only scheduled matches
        if "statusText" in df.columns:
            df = df[df["statusText"] == "Scheduled"].reset_index(drop=True)

        if df.empty:
            return df

        # Safe date parsing
        if "startTime" in df.columns:
            df["match_date"] = df["startTime"].str.split("T").str[0]
            df["match_time"] = df["startTime"].str.split("T").str[1].str.split("+").str[0]

        # Columns to drop
        drop_columns = [
            'sportId', 'statusGroup', 'shortStatusText','gameTimeAndStatusDisplayType', 'homeAwayTeamOrder','groupNum', 'scores', 'startTime','hasPointByPoint', 'hasVideo',
            'homeCompetitor.sportId', 'homeCompetitor.isWinner','homeCompetitor.type', 'homeCompetitor.popularityRank','homeCompetitor.outcome', 'homeCompetitor.imageVersion',
            'homeCompetitor.hasSquad', 'homeCompetitor.hasTransfers','homeCompetitor.competitorNum', 'homeCompetitor.hideOnSearch','homeCompetitor.hideOnCatalog', 'homeCompetitor.countryId',
            'awayCompetitor.countryId', 'awayCompetitor.sportId','awayCompetitor.isWinner', 'awayCompetitor.type','awayCompetitor.popularityRank', 'awayCompetitor.outcome',
            'awayCompetitor.imageVersion', 'awayCompetitor.hasSquad','awayCompetitor.hasTransfers', 'awayCompetitor.competitorNum','awayCompetitor.hideOnSearch', 'awayCompetitor.hideOnCatalog',
            'homeCompetitor.aggregatedScore', 'awayCompetitor.aggregatedScore','justEnded', 'gameTimeDisplay', 'hasLineups','hasMissingPlayers', 'hasFieldPositions',
            'lineupsStatus', 'lineupsStatusText', 'hasTVNetworks','winDescription', 'isHomeAwayInverted', 'hasStats','hasStandings', 'standingsName', 'hasBrackets',
            'hasPreviousMeetings', 'hasRecentMatches','hasBets', 'hasPlayerBets', 'hasNews','homeCompetitor.redCards', 'awayCompetitor.redCards',
            'homeCompetitor.isQualified', 'homeCompetitor.toQualify','awayCompetitor.isQualified', 'awayCompetitor.toQualify','homeCompetitor.shortName', 'awayCompetitor.shortName','gameTime'
            ]

        return df.drop(columns=drop_columns, errors="ignore")
    
    def extract_results(self, url_team: str, season_year: str = "2025") -> pd.DataFrame:
        """
        Extract recent match results for a team from the 365Scores API,
        filtered by season start date.

        Args:
            url_team (str): Team URL containing the team ID.
            season_year (str, optional): Season start year. Defaults to "2025".

        Returns:
            pd.DataFrame: Cleaned DataFrame with match results.
        """

        # Extract team ID
        id_team = url_team.split("-")[-1]
        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")
        
        url = (f"{BASE_URL}/web/games/results/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=7&competitors={id_team}&showOdds=true")

        season_start = pd.Timestamp(f"{season_year}-07-01")

        all_games = []
        stop_loop = False

        # Pagination loop
        while url and not stop_loop:
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                data= response.json()

            except requests.exceptions.RequestException as e:
                raise requests.exceptions.RequestException( f"Error retrieving team results: {e}") from e

            games = data.get("games", [])

            for game in games:
                start_time = game.get("startTime")
                if not start_time:
                    continue

                try:
                    match_date = pd.to_datetime(start_time.split("T")[0])
                except Exception:
                    continue

                # 🔥 CORTE INTELIGENTE
                if match_date < season_start:
                    stop_loop = True
                    break

                all_games.append(game)

            # Pagination
            prev_page = data.get("paging", {}).get("previousPage")
            url = BASE_URL + prev_page if prev_page and not stop_loop else None

        if not all_games:
            return pd.DataFrame()

        # Normalize
        df = pd.json_normalize(all_games)

        # Date parsing
        if "startTime" in df.columns:
            df["match_date"] = df["startTime"].str.split("T").str[0]
            df["match_time"] = df["startTime"].str.split("T").str[1].str.split("+").str[0]

        # Drop columns
        drop_columns = [
            'sportId', 'statusGroup', 'shortStatusText','gameTimeAndStatusDisplayType', 'homeAwayTeamOrder','groupNum', 'scores', 'startTime','hasPointByPoint', 'hasVideo',
            'homeCompetitor.sportId', 'homeCompetitor.isWinner','homeCompetitor.type', 'homeCompetitor.popularityRank','homeCompetitor.outcome', 'homeCompetitor.imageVersion',
            'homeCompetitor.hasSquad', 'homeCompetitor.hasTransfers','homeCompetitor.competitorNum', 'homeCompetitor.hideOnSearch', 'homeCompetitor.hideOnCatalog', 'homeCompetitor.countryId',
            'awayCompetitor.countryId', 'awayCompetitor.sportId','awayCompetitor.isWinner', 'awayCompetitor.type','awayCompetitor.popularityRank', 'awayCompetitor.outcome',
            'awayCompetitor.imageVersion', 'awayCompetitor.hasSquad','awayCompetitor.hasTransfers', 'awayCompetitor.competitorNum','awayCompetitor.hideOnSearch', 'awayCompetitor.hideOnCatalog',
            'homeCompetitor.aggregatedScore', 'awayCompetitor.aggregatedScore', 'justEnded', 'gameTimeDisplay', 'hasLineups', 'hasMissingPlayers', 'hasFieldPositions',
            'lineupsStatus', 'lineupsStatusText', 'hasTVNetworks','winDescription', 'isHomeAwayInverted', 'hasStats','hasStandings', 'standingsName', 'hasBrackets',
            'hasPreviousMeetings', 'hasRecentMatches','hasBets', 'hasPlayerBets', 'hasNews','homeCompetitor.redCards', 'awayCompetitor.redCards',
            'homeCompetitor.isQualified', 'homeCompetitor.toQualify','awayCompetitor.isQualified', 'awayCompetitor.toQualify','homeCompetitor.shortName', 'awayCompetitor.shortName'
        ]

        return  df.drop(columns=drop_columns, errors="ignore")
    
    def extract_stats_team(self, url: str,competition_name: str) -> pd.DataFrame:
        """
        Extract player statistics for a given team and competition.

        Raises:
            ValueError:
                If competition is not available for the team.
        """

        # Extract team ID
        id_team = url.split("-")[-1]
        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")

        # Get competitions
        df_competitions = self.extract_competition_available(url)

        # VALIDATION + FRIENDLY ERROR
        available_competitions = df_competitions["name"].dropna().unique().tolist()

        if competition_name not in available_competitions:
            suggestions = ", ".join(sorted(available_competitions))

            raise ValueError(
                f"Competition '{competition_name}' is not available for this team.\n"
                f"Available competitions are:\n{suggestions}"
            )

        # Get competition ID (safe now)
        competition_id = get_competition_id(df_competitions, competition_name)

        # Build URL
        url_team_stats = f'https://webws.365scores.com/web/stats/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitions={competition_id}&competitors={id_team}&withSeasons=true'

        # Request
        try:
            response = requests.get(url_team_stats, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving team stats: {e}") from e

        stats_block = data.get("stats", {})
        athletes_stats = stats_block.get("athletesStats", [])

        all_data = []

        for stat in athletes_stats:
            stat_name = stat.get("name")

            for row in stat.get("rows", []):
                entity = row.get("entity", {})
                stats_list = row.get("stats", [])

                all_data.append({
                    "id_player": entity.get("id"),
                    "player": entity.get("name"),
                    "name_for_url": entity.get("nameForURL"),
                    "positionName": entity.get("positionName"),
                    "value": stats_list[0].get("value") if stats_list else None,
                    "name_stat": stat_name,
                })

        return pd.DataFrame(all_data)
    
    def extract_transfers_rumors(self, url: str) -> pd.DataFrame:
        """
        Extract transfer rumors for a given team from 365Scores API.

        Args:
            url (str): Team URL containing the team ID.

        Returns:
            pd.DataFrame: Transfer rumors with detailed info about teams and players.

        Raises:
            ValueError: If team ID is invalid.
            requests.exceptions.RequestException: If the API request fails.
        """

        # Extract team ID
        id_team = url.split('-')[-1]
        if not id_team.isdigit():
            raise ValueError("Invalid team ID extracted from URL.")

        base_url = "https://webws.365scores.com"
        url_transfers = (f"{base_url}/web/transfers/?appTypeId=5&langId=1&timezoneName=Europe/Madrid&userCountryId=2&competitors={id_team}")

        # Request with error handling
        try:
            response = requests.get(url_transfers, headers=self.headers, timeout=10)
            response.raise_for_status()
            transfers = response.json()
        except requests.exceptions.RequestException as e:
            raise requests.exceptions.RequestException(f"Error retrieving transfers: {e}") from e

        # Competitors (teams)
        df_teams = pd.DataFrame(transfers.get("competitors", []))
        drop_teams_cols = [
            'sportId','countryId','type','popularityRank','imageVersion','hasSquad',
            'hasTransfers','hideOnSearch','hideOnCatalog','longName','shortName','competitorNum'
            ]
        df_teams = df_teams.drop(columns=drop_teams_cols, errors="ignore").rename( columns={'id': 'team_id', 'name': 'team_name', 'nameForURL': 'team_name_for_url'})

        # Countries
        df_countries = pd.DataFrame(transfers.get("countries", []))
        df_countries = df_countries.drop(columns=['sportTypes','imageVersion','isInternational'], errors="ignore").rename(columns={'id': 'nationalityId', 'name': 'nationality', 'nameForURL': 'nationality_for_url'})

        # Athletes
        df_players = pd.DataFrame(transfers.get("athletes", []))
        drop_players_cols = ['age','gender','popularityRank','shortName','sportId','imageVersion','createdAt','clubName','clubId']
        df_players = df_players.drop(columns=drop_players_cols, errors="ignore").rename(columns={'id': 'player_id'})
        df_players['player_image'] = df_players['player_id'].apply(
            lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}"
            )

        df_players = df_players.merge(df_countries, how='left', left_on='nationalityId', right_on='nationalityId').drop(columns=['nationalityId'])

        # Transfers
        df_transfers = pd.DataFrame(transfers.get("transfers", []))
        if not df_transfers.empty:
            # Parse dates safely
            df_transfers['post_start_date'] = df_transfers['time'].str.split('T').str[0]
            df_transfers['post_start_time'] = df_transfers['time'].str.split('T').str[1].str.split('+').str[0]

            df_transfers['contract_until_date'] = df_transfers['contractUntil'].str.split('T').str[0]
            df_transfers['contract_until_time'] = df_transfers['contractUntil'].str.split('T').str[1].str.split('+').str[0]

            df_transfers = df_transfers.drop(columns=['ImageVersion','statusId','time','type','contractUntil','positionId'], errors='ignore')
            df_transfers = df_transfers.rename(columns={'origin': 'team_id'})

            # Merge origin and target teams
            df_transfers = df_transfers.merge(df_teams, how='left', left_on='team_id', right_on='team_id').rename(
                columns={'team_name': 'origin_team'}
            )
            df_transfers = df_transfers.merge(df_teams, how='left', left_on='target', right_on='team_id').rename(
                columns={
                    'team_name': 'target_team','symbolicName_x': 'origin_symbolic_name','team_name_for_url_x': 'origin_team_name_for_url','color_x': 'origin_color',
                    'awayColor_x': 'origin_away_color','mainCompetitionId_x': 'origin_mainCompetitionId','symbolicName_y': 'target_symbolic_name','team_name_for_url_y': 'target_team_name_for_url',
                    'color_y': 'target_color','awayColor_y': 'target_away_color', 'mainCompetitionId_y': 'target_mainCompetitionId'
                }).drop(columns=['team_id_x','target','team_id_y'], errors='ignore')

            # Merge with player info
            df_final = df_transfers.merge(df_players, how='left', left_on='athleteId', right_on='player_id').drop(columns=['athleteId'], errors='ignore')
        else:
            # If no transfers
            df_final = pd.DataFrame()

        return df_final
    
    