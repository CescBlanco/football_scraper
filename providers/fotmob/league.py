import requests
import pandas as pd
import re

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import  Tuple , Optional
from providers.fotmob.utils import fetch_stat, extract_next_opponent, extract_team_form

class FotmobLeagueService:
    def __init__(self, session: requests.Session, competition_service):
        self.session = session
        self.competition_service = competition_service
    
    def validate_season_from_league(self, display_name: str, selected_season: str, ccode3: str = "ESP") -> Tuple[bool, str, Optional[str], Optional[str], Optional[str]]:
        """
        Validate whether a given season is available for a specific league.

        This function checks:
        - That the league exists
        - That the season format is valid (YYYY/YYYY)
        - That the season is available in the FotMob API

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (default is 'ESP').

        Returns:
            Tuple containing:
                - bool: Whether the season is valid
                - str: Message describing the result
                - Optional[str]: Season start year
                - Optional[str]: Season end year
                - Optional[str]: League ID

        Raises:
            TypeError: If inputs are not strings.
        """
        if not isinstance(display_name, str) or not isinstance(selected_season, str):
            raise TypeError("display_name and selected_season must be strings")

        league = self.competition_service.extract_league_by_display_name(display_name)

        if not league:
            return False, "League not found", None, None, None

        id_general_league = league.get("id")

        pattern = r"^\d{4}/\d{4}$"
        if not re.match(pattern, selected_season):
            return False, "Invalid format", None, None, None

        try:
            url = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            available_seasons = data.get("allAvailableSeasons") or []

            if selected_season not in available_seasons:
                return False, "Season not available", None, None, None

            season_in, season_out = selected_season.split("/")

            return True, "Valid season", season_in, season_out, id_general_league

        except requests.exceptions.RequestException as e:
            return False, f"API error: {e}", None, None, None
        
    def extract_row_clean_data(self, display_name: str,selected_season: str,ccode3: str = "ESP") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Retrieve raw and cleaned league data for a given season.

        This function validates the season and fetches detailed league information
        from the FotMob API. It returns both the raw normalized data and a cleaned
        version with unnecessary columns removed.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (default 'ESP').

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - Raw normalized league data
                - Cleaned league data with irrelevant columns removed

        Raises:
            ValueError: If the season is invalid or not available.
            requests.exceptions.RequestException: If API request fails.
        """
        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"
        
        response = requests.get(url_info)
        response.raise_for_status()
        data = response.json()

        row_data_league = pd.json_normalize(data)

        columns_to_drop = ['tabs','QAData',	'playoff','allAvailableSeasons', 'seasons', 'details.shortName', 'details.faqJSONLD', 'details.breadcrumbJSONLD.@context',
            'details.breadcrumbJSONLD.@type',	'details.breadcrumbJSONLD.itemListElement',	'details.canSyncCalendar', 'details.dataProvider',
            'transfers.type',	'transfers.data', 'fixtures.fixtureInfo.teams',	'fixtures.fixtureInfo.groups' , 'fixtures.fixtureInfo.activeRound.localizedKey',
            'fixtures.fixtureInfo.rounds', 'fixtures.firstUnplayedMatch.firstUnplayedMatchIndex',	'fixtures.firstUnplayedMatch.firstUnplayedMatchId',
            'overview.matches.fixtureInfo.teams', 'overview.matches.firstUnplayedMatch.firstUnplayedMatchIndex',	'overview.matches.firstUnplayedMatch.firstUnplayedMatchId',
            'fixtures.allMatches',	'fixtures.hasOngoingMatch','overview.matches.hasOngoingMatch', 'overview.matches.fixtureInfo.activeRound.localizedKey',
            'overview.matches.fixtureInfo.rounds', 'overview.table', 'table', 'overview.topPlayers.seeAllUrl',	'overview.hasTotw', 'stats.seasonStatLinks',
            'stats.seasonsWithLinks', 'overview.matches.allMatches', 'overview.leagueOverviewMatches', 'overview.hasOngoingMatch','overview.shotMap', 
            'overview.matches.fixtureInfo.activeRound.roundId',	'overview.matches.fixtureInfo.groups', 'overview.season',	'overview.selectedSeason',
            'overview.topPlayers.byRating.players',	'overview.topPlayers.byRating.seeAllLink'	,'overview.topPlayers.byGoals.players',	'overview.topPlayers.byGoals.seeAllLink',
            'overview.topPlayers.byAssists.players',	'overview.topPlayers.byAssists.seeAllLink'	,'stats.players',	'stats.teams']

        clean_data_league = row_data_league.drop(columns=columns_to_drop, errors="ignore")

        return row_data_league, clean_data_league
    
    def extract_teams(self, display_name: str,selected_season: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract team information for a given league and season.

        This function retrieves team data and standings from the FotMob API,
        merges both datasets, and returns a unified DataFrame containing
        team identifiers, logos, and URLs.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (default 'ESP').

        Returns:
            pd.DataFrame: DataFrame containing enriched team data including:
                - Team IDs
                - Team names and logos
                - Team page URLs

        Raises:
            ValueError: If the season validation fails.
            requests.exceptions.RequestException: If API calls fail.
        """
        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"
        
        response = requests.get(url_info)
        response.raise_for_status()
        data = response.json()

        df1 = pd.json_normalize(data["fixtures"]["fixtureInfo"]["teams"])
        df1["team_photo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df1["id"].astype(str) + ".png"
        

        url_standings = f"https://www.fotmob.com/api/data/tltable?leagueId={id_general_league}"
        

        response2 = requests.get(url_standings)
        response2.raise_for_status()
        data2 = response2.json()

        row_data_standings = pd.json_normalize(data2[0]["data"])
        teams = row_data_standings["table.all"].iloc[0]

        df2 = pd.DataFrame(teams)[["id", "pageUrl"]]
        df2["team_url"] = "https://www.fotmob.com" + df2["pageUrl"].astype(str)
        df2 = df2.drop(columns=["pageUrl"])

        df1["id"] = df1["id"].astype(str)
        df2["id"] = df2["id"].astype(str)

        return df1.merge(df2, on="id", how="left")
    
    def extract_team_of_week(self, display_name: str,selected_season: str,ccode3: str,max_workers: int = 10) -> pd.DataFrame:
        """
        Extract Team of the Week data for all rounds in a given league season.

        This function retrieves all available rounds for a league season and then
        fetches Team of the Week data for each round in parallel using threads.
        The final result is a concatenated DataFrame enriched with player and team images.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').
            max_workers (int): Maximum number of threads for parallel requests.

        Returns:
            pd.DataFrame: Combined DataFrame containing Team of the Week data for all rounds,
            including:
                - Player information
                - Team information
                - Round ID
                - Player image URL
                - Team logo URL

        Raises:
            ValueError: If the season validation fails.
            requests.exceptions.RequestException: If any API request fails.
            TypeError: If inputs are not of expected types.
        """
        if not isinstance(display_name, str) or not isinstance(selected_season, str):
            raise TypeError("display_name and selected_season must be strings")

        session = requests.Session()

        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_round = f"https://www.fotmob.com/api/data/team-of-the-week/rounds?leagueId={id_general_league}&season={season_in}%2F{season_out}"
        

        response = session.get(url_round)
        response.raise_for_status()
        data = response.json()

        rounds = pd.json_normalize(data["rounds"])[["roundId"]]
        rounds = rounds.sort_values(by="roundId", ascending=False).reset_index(drop=True)

        def fetch_round(round_id: int) -> pd.DataFrame:
            """
            Fetch Team of the Week data for a specific round.

            Args:
                round_id (int): Round identifier.

            Returns:
                pd.DataFrame: DataFrame containing players for that round.
            """
            url_info = f"https://www.fotmob.com/api/data/team-of-the-week/team?leagueId={id_general_league}&roundId={round_id}&season={season_in}%2F{season_out}"
            

            response = session.get(url_info)
            response.raise_for_status()

            data = response.json()
            df = pd.json_normalize(data)
            df["roundId"] = round_id

            return df

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            dfs = list(executor.map(fetch_round, rounds["roundId"]))

        final_df = pd.concat(dfs, ignore_index=True)

        final_df["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/" + final_df["id"].astype(str) + ".png"
        

        final_df["logo_url_fromClub"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ final_df["teamId"].astype(str) + ".png"

        return final_df
    
    def extract_teamofweek_by_round(self, display_name: str,selected_season: str,ccode3: str, round_id: int, max_workers: int = 10) -> pd.DataFrame:
        """
        Extract Team of the Week data for a specific round in a given league season.

        This function retrieves the full Team of the Week dataset for all rounds
        of a league season and filters the result by the provided round ID.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').
            round_id (int): Identifier of the round to filter.
            max_workers (int, optional): Number of threads for data extraction. Default is 10.

        Returns:
            pd.DataFrame: Filtered DataFrame containing only the selected round data.

        Raises:
            TypeError: If round_id is not an str or inputs are invalid.
            ValueError: If no data is found for the given round.
        """
        if not isinstance(round_id, str):
            raise TypeError("round_id must be an str")

        df = self.extract_team_of_week(display_name=display_name,selected_season=selected_season,ccode3=ccode3, max_workers=max_workers)

        filtered = df[df["roundId"] == round_id].reset_index(drop=True)

        if filtered.empty:
            raise ValueError(f"No data found for round_id: {round_id}")

        return filtered
    
    def extract_transfer(self, display_name: str,selected_season: str, ccode3: str) -> pd.DataFrame:
        """
        Extract transfer market data for a specific league and season.

        This function retrieves transfer information from the FotMob API and
        returns a cleaned DataFrame with player movements between clubs,
        including transfer dates, clubs, and enriched image URLs.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').

        Returns:
            pd.DataFrame: Cleaned transfer dataset including:
                - Player transfer details
                - From/to clubs
                - Transfer dates (split into date and time)
                - Player and club image URLs

        Raises:
            ValueError: If league or season validation fails.
            requests.exceptions.RequestException: If API request fails.
            TypeError: If inputs are not strings.
        """
        if not isinstance(display_name, str) or not isinstance(selected_season, str) or not isinstance(ccode3, str):
            raise TypeError("display_name, selected_season and ccode3 must be strings")

        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league( display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"

        response = requests.get(url_info)
        response.raise_for_status()
        data = response.json()

        df = pd.json_normalize(data["transfers"]["data"])

        df["transferDate"] = pd.to_datetime(df["transferDate"])
        df["transfer_date"] = df["transferDate"].dt.date
        df["transfer_time"] = df["transferDate"].dt.time

        df = df.drop(columns=["position","fee.value","fee", "fee.localizedFeeText","transferText","transferType.localizationKey","transferDate"], errors="ignore")

        df["fromDate"] = df["fromDate"].str.split("T").str[0]
        df["toDate"] = df["toDate"].str.split("T").str[0]

        df["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/"+ df["playerId"].astype(str) + ".png"
        df["logo_url_fromClub"] ="https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["fromClubId"].astype(str) + ".png"

        df["logo_url_toClub"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["toClubId"].astype(str) + ".png"

        return df
    
    def extract_all_matches(self, display_name: str,selected_season: str,ccode3: str) -> pd.DataFrame:
        """
        Extract all matches for a league season.

        This function retrieves all match data from the FotMob API and returns
        a structured DataFrame with match dates, times, status, and URLs.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').

        Returns:
            pd.DataFrame: Dataset containing all matches with:
                - Teams and scores
                - Match status
                - Localized match time
                - Match URLs

        Raises:
            ValueError: If season validation fails.
            requests.exceptions.RequestException: If API request fails.
        """
        if not isinstance(display_name, str) or not isinstance(selected_season, str) or not isinstance(ccode3, str):
            raise TypeError("display_name, selected_season and ccode3 must be strings")

        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league( display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"
        
        response = requests.get(url_info)
        response.raise_for_status()
        data = response.json()

        all_matches = pd.json_normalize(data["fixtures"]["allMatches"])

        all_matches["pageUrl"] = "https://www.fotmob.com" + all_matches["pageUrl"].astype(str)

        all_matches["status.utcTime"] = pd.to_datetime( all_matches["status.utcTime"], utc=True, errors="coerce")
        all_matches["status.localTime"] = all_matches["status.utcTime"].dt.tz_convert("Europe/Madrid")

        all_matches["match_date"] = all_matches["status.localTime"].dt.date
        all_matches["match_time"] = all_matches["status.localTime"].dt.strftime("%H:%M")

        all_matches = all_matches.drop(columns=["roundName","home.shortName","away.shortName","status.timezone","status.reason.shortKey","status.reason.longKey","status.utcTime"  ],errors="ignore")

        return all_matches
    
    def extract_stats_players(self, display_name: str, selected_season: str,ccode3: str) -> pd.DataFrame:
        """
        Extract player statistics for a league season.

        This function retrieves multiple statistical categories for players and
        aggregates them into a single enriched DataFrame using parallel requests.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').

        Returns:
            pd.DataFrame: Player statistics including performance metrics,
            team info, and player images.

        Raises:
            ValueError: If season validation fails.
            requests.exceptions.RequestException: If API request fails.
        """
        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"


        response = requests.get(url_info)
        response.raise_for_status()
        data = response.json()

        info_stats_player = pd.json_normalize(data["stats"]["players"])[["header", "fetchAllUrl"]]

        
        dfs = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_stat, row) for _, row in info_stats_player.iterrows()]

            for future in as_completed(futures):
                dfs.extend(future.result())

        df_final = pd.concat(dfs, ignore_index=True)

        df_final["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/"+ df_final["ParticiantId"].astype(str) + ".png"
        df_final["logo_team"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df_final["TeamId"].astype(str) + ".png"

        df_final = df_final.drop( columns=["StatValueCount", "ParticipantCountryCode", "Positions", "header"],errors="ignore")

        return df_final
    
    def extract_stats_teams(self, display_name: str,selected_season: str,ccode3: str) -> pd.DataFrame:
        """
        Extract team statistics for a league season.

        This function retrieves team-level statistical categories from the FotMob API
        and aggregates them into a unified DataFrame using parallel processing.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').

        Returns:
            pd.DataFrame: Team statistics including performance metrics and team logos.

        Raises:
            ValueError: If season validation fails.
            requests.exceptions.RequestException: If API request fails.
        """
        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"

        response = requests.get(url_info)
        response.raise_for_status()
        data = response.json()

        info_stats_team = pd.json_normalize(data["stats"]["teams"])

        
        dfs = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_stat, row) for _, row in info_stats_team.iterrows()]

            for future in as_completed(futures):
                dfs.extend(future.result())

        df_final = pd.concat(dfs, ignore_index=True)

        df_final["logo_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df_final["TeamId"].astype(str) + ".png"

        df_final = df_final.drop( columns=["ParticiantId", "MinutesPlayed", "StatValueCount", "ParticipantCountryCode", "header"], errors="ignore" )

        return df_final
    

    def extract_history_seasons(self, display_name: str, selected_season: str, ccode3: str) -> pd.DataFrame:
        """
        Extract historical season results for a league.

        This function retrieves past season data from the FotMob API,
        including winners and runner-ups for each season, and returns
        a structured DataFrame enriched with team logo URLs.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').

        Returns:
            pd.DataFrame: Dataset containing historical season results with:
                - Season identifiers
                - Winner team (ID and name)
                - Runner-up team (ID and name)
                - Logo URLs for both winner and runner-up teams

        Raises:
            TypeError: If input arguments are not strings.
            ValueError: If season validation fails.
            requests.exceptions.RequestException: If API request fails.
        """
        if not isinstance(display_name, str) or not isinstance(selected_season, str) or not isinstance(ccode3, str):
            raise TypeError("display_name, selected_season and ccode3 must be strings")

        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_info = f"https://www.fotmob.com/api/data/leagues?id={id_general_league}&ccode3={ccode3}&season={season_in}%2F{season_out}"
        
        response = requests.get(url_info)
        response.raise_for_status()

        df = pd.json_normalize(response.json()['seasons'])

        df.columns = df.columns.str.replace('.', '_', regex=False)

        df = df.rename(columns={'loser_id': 'runner_up_id',    'loser_name': 'runner_up_name'})
        df = df.drop(columns=['winner_seasonName', 'winner_winner','loser_seasonName', 'loser_winner'])

        df["logo_url_winner"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["winner_id"].astype(str)+ ".png"
        df["logo_url_runner_up"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["runner_up_id"].astype(str) + ".png"

        return df

    def extract_standing_all_h_a_form(self, display_name: str,selected_season: str,ccode3: str,type_stand: str = "table.home") -> pd.DataFrame:
        """
        Extract league standings with home/away form and next opponent information.

        This function retrieves standings from FotMob, enriches them with:
        - team form (last matches)
        - next opponent information
        - competition metadata
        - team logos and URLs

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').
            type_stand (str): Standings type (default: 'table.home').

        Returns:
            pd.DataFrame: Enriched standings dataset including form and next match info.

        Raises:
            ValueError: If season validation fails.
            requests.exceptions.RequestException: If API request fails.
        """
        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url_standings = f"https://www.fotmob.com/api/data/tltable?leagueId={id_general_league}"

        response = requests.get(url_standings)
        response.raise_for_status()

        data = response.json()

        row_data = pd.json_normalize(data[0]["data"])

        legend = row_data["legend"].iloc[0]
        color_map = {item["color"]: {"title": item["title"], "tKey": item["tKey"]} for item in legend}

        teams = row_data[type_stand].iloc[0]

        df_standings = pd.DataFrame(teams)

        df_standings[["goals_for", "goals_against"]] = df_standings["scoresStr"].str.split("-", expand=True)

        df_standings = df_standings[ [ "qualColor", "idx", "name", "id", "pageUrl", "played", "wins", "draws", "losses","goals_for", "goals_against", "goalConDiff", "pts"]]

        df_standings["competition"] = df_standings["qualColor"].map(lambda x: color_map.get(x, {}).get("title"))
        df_standings["tKey"] = df_standings["qualColor"].map(lambda x: color_map.get(x, {}).get("tKey"))

        df_standings["team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df_standings["id"].astype(str) + ".png"
        df_standings["pageUrl"] = "https://www.fotmob.com" + df_standings["pageUrl"].astype(str)
        df_standings["id"] = df_standings["id"].astype(str)

        df_form = extract_team_form(data)
        df_standing_form = df_standings.merge(df_form, left_on="id", right_on="team_id", how="left").drop(columns=["team_id"])

        df_next = extract_next_opponent(data)
        df_final = df_standing_form.merge(df_next, left_on="id", right_on="team_id", how="left").drop(columns=["team_id"])

        df_final["team_opponent_logo"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df_final["opponent_id"].astype(str) + ".png"


        return df_final
    
    def extract_standing_xg(self, display_name: str,selected_season: str,ccode3: str,type_stand: str = "table.xg") -> pd.DataFrame:
        """
        Extract expected goals (xG) standings for a league season.

        This function retrieves advanced statistics standings including:
        xG, xPoints, and defensive metrics from FotMob API.

        Args:
            display_name (str): League display name.
            selected_season (str): Season in format 'YYYY/YYYY'.
            ccode3 (str): Country code (e.g., 'ESP').
            type_stand (str): Standings type (default: 'table.xg').

        Returns:
            pd.DataFrame: Standings enriched with xG metrics and team metadata.

        Raises:
            ValueError: If season validation fails.
            requests.exceptions.RequestException: If API request fails.
        """
        valid, message, season_in, season_out, id_general_league = self.validate_season_from_league(display_name, selected_season, ccode3)

        if not valid:
            raise ValueError(message)

        url = f"https://www.fotmob.com/api/data/tltable?leagueId={id_general_league}"

        response = requests.get(url)
        response.raise_for_status()

        data = response.json()

        row_data = pd.json_normalize(data[0]["data"])

        legend = row_data["legend"].iloc[0]
        color_map = {item["color"]: {"title": item["title"], "tKey": item["tKey"]} for item in legend}

        teams = row_data[type_stand].iloc[0]

        df_standings = pd.DataFrame(teams)
        df_standings[["goals_for", "goals_against"]] = df_standings["scoresStr"].str.split("-", expand=True)
        df_standings = df_standings[[ "qualColor", "idx", "xPositionDiff", "name", "id", "pageUrl","played", "wins", "draws", "losses","goals_for", "goals_against", "goalConDiff",
                                        "pts", "xg", "xgDiff", "xgConceded", "xgConcededDiff", "xPoints", "xPointsDiff"]]

        df_standings["competition"] = df_standings["qualColor"].map(lambda x: color_map.get(x, {}).get("title"))
        df_standings["team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df_standings["id"].astype(str) + ".png"
        df_standings["pageUrl"] = "https://www.fotmob.com" + df_standings["pageUrl"].astype(str)
        df_standings["id"] = df_standings["id"].astype(str)

        return df_standings