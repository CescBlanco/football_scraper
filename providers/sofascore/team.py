import pandas as pd
from typing import Union, Tuple

from concurrent.futures import ThreadPoolExecutor

from providers.sofascore.constants import DEFAULT_HEADERS, BASE_URL
from providers.sofascore.utils import sofascore_requests, clear_data_transfers, extract_start_year,get_all_next_events_fast, clean_events,process_players, extract_top_players_stats_available

class SofascoreTeamScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_info_details(self, id_team_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract detailed team information from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing in the API response.

        Returns:
            pd.DataFrame:
                DataFrame with flattened team information, including:
                - basic team info
                - tournament data
                - manager data
                - venue data
                - country data
                - team colors
                - foundation date (parsed)
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        if "team" not in json_data:
            raise KeyError("Missing 'team' in API response")

        team_data = json_data["team"]

        # -----------------------------
        # Required keys validation
        # -----------------------------
        required_keys = ['name', 'slug', 'shortName', 'tournament', 'manager','venue', 'nameCode', 'country', 'id','fullName', 'teamColors', 'foundationDateTimestamp']
        missing_keys = [key for key in required_keys if key not in team_data]
        if missing_keys:
            raise KeyError(f"Missing keys in team data: {missing_keys}")

        # -----------------------------
        # Base DataFrame
        # -----------------------------
        row_info = pd.DataFrame([team_data])
        row_info = row_info[required_keys]

        # -----------------------------
        # First flattening
        # -----------------------------
        row_info = pd.concat([
                row_info.drop(['tournament', 'manager', 'venue', 'country', 'teamColors'], axis=1),
                row_info['tournament'].apply(pd.Series).add_prefix('tournament_'),
                row_info['manager'].apply(pd.Series).add_prefix('manager_'),
                row_info['venue'].apply(pd.Series).add_prefix('venue_'),
                row_info['country'].apply(pd.Series).add_prefix('country_'),
                row_info['teamColors'].apply(pd.Series).add_prefix('teamColors_')
            ], axis=1)

        # -----------------------------
        # Column selection
        # -----------------------------
        row_info=row_info[['name',	'slug','shortName',  'nameCode',  'id', 'fullName', 'foundationDateTimestamp' , 'tournament_name', 'tournament_slug',
                            'manager_name', 'manager_slug', 'manager_shortName', 'manager_country', 'manager_id', 'venue_venueCoordinates', 'venue_slug', 'venue_name', 'venue_capacity', 'venue_id', 'venue_city',
                            'country_alpha3', 'country_name', 'country_slug', 'teamColors_primary', 'teamColors_secondary', 'teamColors_text']]

        # -----------------------------
        # Second flattening
        # -----------------------------
        row_info = pd.concat([
                    row_info.drop(['manager_country', 'venue_venueCoordinates', 'venue_city'], axis=1),
                    row_info['manager_country'].apply(pd.Series).add_prefix('manager_country_'),
                    row_info['venue_venueCoordinates'].apply(pd.Series).add_prefix('venue_venueCoordinates_'),
                    row_info['venue_city'].apply(pd.Series).add_prefix('venue_city_'),
                ], axis=1)

        # -----------------------------
        # Date transformation
        # -----------------------------
        if 'foundationDateTimestamp' not in row_info:
            raise KeyError("Missing 'foundationDateTimestamp' after processing")

        row_info['foundation_date'] = pd.to_datetime(row_info['foundationDateTimestamp'], unit='s',errors='coerce').dt.date

        # -----------------------------
        # Final cleanup
        # -----------------------------
        return row_info.drop(columns=['manager_country_alpha2', 'fullName', 'foundationDateTimestamp'],errors='ignore')
    
    def extract_transfers(self, id_team_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract inbound and outbound transfers for a team from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required transfer sections are missing.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - transfers_in: DataFrame with incoming transfers
                - transfers_out: DataFrame with outgoing transfers
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/transfers"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        # -----------------------------
        # Validate required keys
        # -----------------------------
        if 'transfersIn' not in json_data:
            raise KeyError("Missing 'transfersIn' in API response")

        if 'transfersOut' not in json_data:
            raise KeyError("Missing 'transfersOut' in API response")

        # -----------------------------
        # Extract data
        # -----------------------------
        df_transfers_in = clear_data_transfers(json_data, type_transfer='in')
        df_transfers_out = clear_data_transfers(json_data, type_transfer='out')

        return df_transfers_in, df_transfers_out
    
    def extract_info_featured_match(self, id_team_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract featured match information for a team from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing in the API response.

        Returns:
            pd.DataFrame:
                DataFrame containing next match information, including:
                - match id, date and time (Europe/Madrid timezone)
                - tournament info
                - match status
                - home and away team data
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/featured-event"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        if "featuredEvent" not in json_data:
            raise KeyError("Missing 'featuredEvent' in API response")

        event_data = json_data["featuredEvent"]

        # -----------------------------
        # Required keys validation
        # -----------------------------
        required_keys = [ 'tournament', 'status', 'homeTeam','awayTeam', 'id', 'slug', 'startTimestamp']

        missing_keys = [key for key in required_keys if key not in event_data]
        if missing_keys:
            raise KeyError(f"Missing keys in featuredEvent: {missing_keys}")

        # -----------------------------
        # Base DataFrame
        # -----------------------------
        featured_match = pd.DataFrame([event_data])
        featured_match = featured_match[required_keys]

        # -----------------------------
        # Flatten nested fields
        # -----------------------------
        featured_match = pd.concat([
                featured_match.drop(['tournament', 'status', 'homeTeam', 'awayTeam'], axis=1),
                featured_match['tournament'].apply(pd.Series).add_prefix('tournament_'),
                featured_match['status'].apply(pd.Series).add_prefix('status_'),
                featured_match['homeTeam'].apply(pd.Series).add_prefix('homeTeam_'),
                featured_match['awayTeam'].apply(pd.Series).add_prefix('awayTeam_'),
            ], axis=1)

        # -----------------------------
        # Datetime transformation
        # -----------------------------
        if 'startTimestamp' not in featured_match:
            raise KeyError("Missing 'startTimestamp' after processing")

        dt = pd.to_datetime(featured_match['startTimestamp'],unit='s', utc=True, errors='coerce' ).dt.tz_convert('Europe/Madrid')
        featured_match['match_date'] = dt.dt.date
        featured_match['match_time'] = dt.dt.time

        # -----------------------------
        # Final column selection
        # -----------------------------
        final_cols = ['id', 'match_date' , 'match_time', 'slug', 'tournament_name', 'tournament_slug', 'status_description', 'homeTeam_name', 'homeTeam_slug', 'homeTeam_shortName', 'homeTeam_nameCode', 'homeTeam_id', 
                                'awayTeam_name', 'awayTeam_slug', 'awayTeam_shortName', 'awayTeam_nameCode', 'awayTeam_id']

        missing_final_cols = [col for col in final_cols if col not in featured_match.columns]
        if missing_final_cols:
            raise KeyError(f"Missing expected columns after transformation: {missing_final_cols}")

        featured_match = featured_match[final_cols]

        return featured_match
    
    def extract_recent_form(self, id_team_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract recent match performance (form) for a team from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys or fields are missing in the API response.

        Returns:
            pd.DataFrame:
                DataFrame containing recent matches with:
                - match metadata (id, slug, date, time)
                - tournament and round info
                - home and away team info
                - scores (current, period, aggregated)
                - winner info
                - points obtained in each match
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/performance"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        if "events" not in json_data:
            raise KeyError("Missing 'events' in API response")

        if "points" not in json_data:
            raise KeyError("Missing 'points' in API response")

        events_raw = json_data["events"]

        if not isinstance(events_raw, list):
            raise ValueError("'events' must be a list")

        if len(events_raw) == 0:
            return pd.DataFrame()  # válido: sin partidos

        # -----------------------------
        # Base DataFrame
        # -----------------------------
        events = pd.DataFrame(events_raw)

        required_cols = ['tournament', 'season', 'roundInfo', 'winnerCode', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore','id', 'slug', 'startTimestamp','aggregatedWinnerCode', 'previousLegEventId' ]

        missing_cols = [col for col in required_cols if col not in events.columns]
        if missing_cols:
            raise KeyError(f"Missing columns in events data: {missing_cols}")

        events = events[required_cols]

        # -----------------------------
        # Points normalization
        # -----------------------------
        points_raw = json_data["points"]

        if not isinstance(points_raw, dict):
            raise ValueError("'points' must be a dictionary")

        points_match = pd.json_normalize(points_raw).transpose()
        points_match =  points_match.rename(columns={0: 'points'}).reset_index().rename(columns={'index': 'id'})
        points_match['id'] = pd.to_numeric(points_match['id'], errors='coerce')

        # -----------------------------
        # Merge points
        # -----------------------------
        events = events.merge(points_match, on='id', how='left')

        # -----------------------------
        # Datetime transformation
        # -----------------------------
        if 'startTimestamp' not in events:
            raise KeyError("Missing 'startTimestamp' in events")

        dt = pd.to_datetime(events['startTimestamp'],unit='s',utc=True,errors='coerce').dt.tz_convert('Europe/Madrid')
        events['match_date'] = dt.dt.date
        events['match_time'] = dt.dt.time

        # -----------------------------
        # Flatten nested fields
        # -----------------------------
        events = pd.concat([
                events.drop(['tournament', 'season', 'roundInfo', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore'], axis=1),
                events['tournament'].apply(pd.Series).add_prefix('tournament_'),
                events['season'].apply(pd.Series).add_prefix('season_'),
                events['roundInfo'].apply(pd.Series).add_prefix('roundInfo_'),
                events['homeTeam'].apply(pd.Series).add_prefix('homeTeam_'),
                events['awayTeam'].apply(pd.Series).add_prefix('awayTeam_'),
                events['homeScore'].apply(pd.Series).add_prefix('homeScore_'),
                events['awayScore'].apply(pd.Series).add_prefix('awayScore_'),
            ], axis=1)

        # -----------------------------
        # Final column selection
        # -----------------------------
        final_cols = ['id', 'slug','winnerCode',    'match_date' , 'match_time', 'tournament_name', 'tournament_slug', 'roundInfo_round', 'roundInfo_name',	'roundInfo_slug', 
                        'homeTeam_name', 'homeTeam_slug', 'homeTeam_shortName', 'homeTeam_nameCode', 'homeTeam_id', 'awayTeam_name', 'awayTeam_slug', 'awayTeam_shortName', 
                        'awayTeam_nameCode', 'awayTeam_id', 'homeScore_current', 'homeScore_period1', 'homeScore_period2','awayScore_current', 'awayScore_period1',
                        'awayScore_period2', 'homeScore_aggregated','awayScore_aggregated', 'aggregatedWinnerCode','previousLegEventId','points']
    
        missing_final_cols = [col for col in final_cols if col not in events.columns]
        if missing_final_cols:
            raise KeyError(f"Missing expected columns after transformation: {missing_final_cols}")

        return events[final_cols]
    
    def extract_trophies(self, id_team_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, int]:
        """
        Extract team trophies and achievements from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing in the API response.

        Returns:
            Tuple[pd.DataFrame, int]:
                - trophies: DataFrame with trophies per competition
                - total_trophies: total number of trophies won
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/achievements"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        if "achievements" not in json_data:
            raise KeyError("Missing 'achievements' in API response")

        if "totalTrophies" not in json_data:
            raise KeyError("Missing 'totalTrophies' in API response")

        achievements = json_data["achievements"]

        if not isinstance(achievements, list):
            raise ValueError("'achievements' must be a list")

        if len(achievements) == 0:
            return pd.DataFrame(), json_data["totalTrophies"]

        # -----------------------------
        # Base DataFrame
        # -----------------------------
        trophies = pd.DataFrame(achievements)

        required_cols = ['uniqueTournament', 'trophiesWon']
        missing_cols = [col for col in required_cols if col not in trophies.columns]

        if missing_cols:
            raise KeyError(f"Missing columns in achievements data: {missing_cols}")

        # -----------------------------
        # First flattening
        # -----------------------------
        trophies = pd.concat([trophies.drop(['uniqueTournament'], axis=1),trophies['uniqueTournament'].apply(pd.Series).add_prefix('uniqueTournament_'),], axis=1)

        # -----------------------------
        # Validate intermediate columns
        # -----------------------------
        intermediate_cols = ['uniqueTournament_name', 'uniqueTournament_slug','uniqueTournament_id', 'uniqueTournament_competitionType','uniqueTournament_category', 'trophiesWon']

        missing_intermediate = [col for col in intermediate_cols if col not in trophies.columns]
        if missing_intermediate:
            raise KeyError(f"Missing expected columns after first flattening: {missing_intermediate}")

        trophies = trophies[intermediate_cols]

        # -----------------------------
        # Second flattening (category)
        # -----------------------------
        trophies = pd.concat([trophies.drop(['uniqueTournament_category'], axis=1),trophies['uniqueTournament_category'].apply(pd.Series).add_prefix('uniqueTournament_category_'),], axis=1)

        # -----------------------------
        # Final column selection
        # -----------------------------
        final_cols = ['uniqueTournament_name', 'uniqueTournament_slug','uniqueTournament_id', 'uniqueTournament_competitionType','uniqueTournament_category_name', 'uniqueTournament_category_slug','trophiesWon']

        missing_final_cols = [col for col in final_cols if col not in trophies.columns]
        if missing_final_cols:
            raise KeyError(f"Missing expected columns after transformation: {missing_final_cols}")

        trophies = trophies[final_cols]

        # -----------------------------
        # Total trophies
        # -----------------------------
        total_trophies = json_data["totalTrophies"]

        if not isinstance(total_trophies, int):
            raise ValueError("'totalTrophies' must be an integer")

        return trophies, total_trophies
    
    def extract_competitions_now(self, id_team_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract all seasons and current season competitions for a team.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing in the API response.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - seasons_league: DataFrame with all seasons
                - seasons_current: DataFrame with current season(s)
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/team-statistics/seasons"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        if "uniqueTournamentSeasons" not in json_data:
            raise KeyError("Missing 'uniqueTournamentSeasons' in API response")

        uts = json_data["uniqueTournamentSeasons"]

        if not isinstance(uts, list):
            raise ValueError("'uniqueTournamentSeasons' must be a list")

        if len(uts) == 0:
            return pd.DataFrame(), pd.DataFrame()

        # -----------------------------
        # Expand JSON
        # -----------------------------
        df = pd.DataFrame(uts)

        if "seasons" not in df.columns:
            raise KeyError("Missing 'seasons' in uniqueTournamentSeasons")

        seasons_league = df["seasons"].explode().reset_index(drop=True)

        if seasons_league.isnull().all():
            return pd.DataFrame(), pd.DataFrame()

        seasons_league = seasons_league.apply(pd.Series)

        # -----------------------------
        # Validate required columns
        # -----------------------------
        if "year" not in seasons_league.columns:
            raise KeyError("Missing 'year' in seasons data")

        # -----------------------------
        # Clean unnecessary columns
        # -----------------------------
        seasons_league = seasons_league.drop( columns=['editor', 'seasonCoverageInfo'],errors='ignore')

        # -----------------------------
        # Create comparable year
        # -----------------------------
        seasons_league['year_start'] = seasons_league['year'].apply(extract_start_year)

        if seasons_league['year_start'].isnull().all():
            raise ValueError("All 'year_start' values are null")

        # -----------------------------
        # Get current season
        # -----------------------------
        current_year = seasons_league['year_start'].max()

        if pd.isna(current_year):
            raise ValueError("Unable to determine current season")

        seasons_current = seasons_league[seasons_league['year_start'] == current_year].reset_index(drop=True)

        return seasons_league, seasons_current
    
    def extract_performance_graph(self, id_team_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract team performance graph data from SofaScore API, including
        match events and weekly position.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys or fields are missing in the API response.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - match info (id, slug, date, time)
                - tournament and status info
                - home and away team data
                - match scores
                - weekly position (week, position)
        """

        api = f"https://www.sofascore.com/api/v1/unique-tournament/8/season/77559/team/{id_team_sofascore}/team-performance-graph-data"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        if "graphData" not in json_data:
            raise KeyError("Missing 'graphData' in API response")

        graph_data = json_data["graphData"]

        if not isinstance(graph_data, list):
            raise ValueError("'graphData' must be a list")

        if len(graph_data) == 0:
            return pd.DataFrame()

        # -----------------------------
        # Normalize base DataFrame
        # -----------------------------
        df = pd.json_normalize(graph_data)

        required_cols = ['events', 'week', 'position']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise KeyError(f"Missing columns in graphData: {missing_cols}")

        # -----------------------------
        # Extract positions
        # -----------------------------
        df_positions = df[['week', 'position']].reset_index(drop=True)

        # -----------------------------
        # Extract events
        # -----------------------------
        events_series = df['events'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None)

        if events_series.isnull().all():
            raise ValueError("No valid events found in graphData")

        events = events_series.apply(pd.Series)

        # -----------------------------
        # Validate required event fields
        # -----------------------------
        required_event_cols = [ 'id', 'slug', 'winnerCode', 'startTimestamp','tournament', 'status', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore']

        missing_event_cols = [col for col in required_event_cols if col not in events.columns]
        if missing_event_cols:
            raise KeyError(f"Missing event fields: {missing_event_cols}")

        # -----------------------------
        # Datetime transformation
        # -----------------------------
        dt = pd.to_datetime( events['startTimestamp'], unit='s',utc=True, errors='coerce').dt.tz_convert('Europe/Madrid')
        events['match_date'] = dt.dt.date
        events['match_time'] = dt.dt.time

        # -----------------------------
        # Select and flatten
        # -----------------------------
        events = events[['id', 'slug', 'winnerCode', 'match_date', 'match_time','tournament', 'status', 'homeTeam', 'awayTeam','homeScore', 'awayScore']]
        events = pd.concat([
                events.drop(['tournament', 'status', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore'], axis=1),
                events['tournament'].apply(pd.Series).add_prefix('tournament_'),
                events['status'].apply(pd.Series).add_prefix('status_'),
                events['homeTeam'].apply(pd.Series).add_prefix('homeTeam_'),
                events['awayTeam'].apply(pd.Series).add_prefix('awayTeam_'),
                events['homeScore'].apply(pd.Series).add_prefix('homeScore_'),
                events['awayScore'].apply(pd.Series).add_prefix('awayScore_'),
            ], axis=1)

        # -----------------------------
        # Final column selection
        # -----------------------------
        final_cols = ['id',	'slug',	'winnerCode',	'match_date', 'match_time',	'tournament_name',	'tournament_slug' ,'status_description', 'homeTeam_name',	'homeTeam_slug',	'homeTeam_shortName', 'homeTeam_nameCode', 'homeTeam_id',
                        'awayTeam_name','awayTeam_slug',	'awayTeam_shortName', 'awayTeam_nameCode', 'awayTeam_id', 'homeScore_current', 'homeScore_period1', 'homeScore_period2', 'awayScore_current', 'awayScore_period1', 
                        'awayScore_period2']

        missing_final_cols = [col for col in final_cols if col not in events.columns]
        if missing_final_cols:
            raise KeyError(f"Missing expected columns after transformation: {missing_final_cols}")

        events = events[final_cols].reset_index(drop=True)

        # -----------------------------
        # Merge with positions
        # -----------------------------
        if len(events) != len(df_positions):
            raise ValueError("Mismatch between events and positions length")

        df_performance_graph_team = pd.concat([events, df_positions], axis=1)

        return df_performance_graph_team
    
    def extract_all_next_matches(self, id_team_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract all upcoming matches for a team from SofaScore API
        (handling pagination with parallel requests).

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API responses are empty or invalid.
            KeyError:
                If required fields are missing in the events data.

        Returns:
            pd.DataFrame:
                DataFrame containing all upcoming matches with:
                - match metadata (id, slug, date, time)
                - tournament and round info
                - match status
                - home and away team data
                - previous leg reference (if applicable)
        """

        events_list = get_all_next_events_fast(id_team_sofascore)

        if not events_list:
            return pd.DataFrame()

        df_cleaned = clean_events(events_list)

        return df_cleaned
    
    def extract_players(self, id_team_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract squad, national players, and foreign players for a team
        from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Unique identifier of the team in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required player sections are missing.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
                - df_squad: full squad
                - df_national_players: players with national team involvement
                - df_foreign_players: foreign players
        """

        api = f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/players"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}")

        required_keys = ['players', 'nationalPlayers', 'foreignPlayers']
        missing_keys = [key for key in required_keys if key not in json_data]

        if missing_keys:
            raise KeyError(f"Missing keys in API response: {missing_keys}")

        # -----------------------------
        # Process data
        # -----------------------------
        df_squad = process_players(json_data['players'])
        df_national_players = process_players(json_data['nationalPlayers'])
        df_foreign_players = process_players(json_data['foreignPlayers'])

        return df_squad, df_national_players, df_foreign_players
    
    def extract_top_players_stat(self, id_team_sofascore: Union[str, int], id_league_selected: Union[str, int], id_season_selected: Union[str, int],stat_selected: str) -> pd.DataFrame:
        """
        Extract top players for a specific statistic in a given team/competition/season.

        Args:
            id_team_sofascore (Union[str, int]):
                Team identifier in SofaScore.
            id_league_selected (Union[str, int]):
                League identifier.
            id_season_selected (Union[str, int]):
                Season identifier.
            stat_selected (str):
                Statistic key to extract (e.g. goals, assists, etc.).

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If requested statistic does not exist.

        Returns:
            pd.DataFrame:
                DataFrame with top players and their statistics.
        """

        stat_names, json_data = extract_top_players_stats_available(id_team_sofascore,id_league_selected, id_season_selected)

        # -----------------------------
        # Validate stat
        # -----------------------------
        if stat_selected not in json_data.get('topPlayers', {}):
            raise KeyError( f"Statistic '{stat_selected}' not found. "f"Available: {stat_names}" )

        data = json_data['topPlayers'][stat_selected]

        if not isinstance(data, list):
            raise ValueError(f"Invalid format for stat '{stat_selected}'")

        if len(data) == 0:
            return pd.DataFrame()

        # -----------------------------
        # Normalize
        # -----------------------------
        df = pd.DataFrame(data)

        required_cols = ['player', 'statistics']
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            raise KeyError(f"Missing columns in stat data: {missing_cols}")

        df = pd.concat([df.drop(['player', 'statistics'], axis=1),
                df['player'].apply(pd.Series).add_prefix('player_'),
                df['statistics'].apply(pd.Series).add_prefix('statistics_'),
            ], axis=1)

        # -----------------------------
        # Cleanup
        # -----------------------------
        drop_cols = ['playedEnough','team','player_fieldTranslations', 'player_gender', 'statistics_id', 'statistics_statisticsType' ]

        df = df.drop(columns=drop_cols, errors='ignore')

        return df
    
    def extract_season_stats(self, id_team_sofascore: Union[str, int],id_league_selected: Union[str, int],id_season_selected: Union[str, int]) -> pd.DataFrame:
        """
        Extract season overall statistics for a team from SofaScore API.

        Args:
            id_team_sofascore (Union[str, int]):
                Team identifier in SofaScore.
            id_league_selected (Union[str, int]):
                League identifier.
            id_season_selected (Union[str, int]):
                Season identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required 'statistics' field is missing in API response.

        Returns:
            pd.DataFrame:
                DataFrame containing overall season statistics for the team.
        """

        api =  f"https://www.sofascore.com/api/v1/team/{id_team_sofascore}/unique-tournament/{id_league_selected}/season/{id_season_selected}/statistics/overall"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure: API response
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for team={id_team_sofascore}, league={id_league_selected}, season={id_season_selected}")

        if "statistics" not in json_data:
            raise KeyError("Missing 'statistics' in API response")

        stats = json_data["statistics"]

        if not isinstance(stats, dict):
            raise ValueError("'statistics' must be a dictionary")

        # -----------------------------
        # Return DataFrame
        # -----------------------------
        return pd.DataFrame([stats])