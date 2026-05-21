import pandas as pd
from typing import Union, Tuple
from datetime import datetime

from football_scraper.providers.sofascore.constants import DEFAULT_HEADERS, BASE_URL
from football_scraper.providers.sofascore.utils import sofascore_requests,extract_tournament_season_available,  safe_expand, expand_coordinates

class SofascorePlayerScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS

    
    def extract_tournament_season_by_player(self, id_player_sofascore: Union[str, int], competition_selected_sofascored: str, season_selected_sofascored: Union[str, int]) -> Tuple[str, str]:
        """
        Get season ID and competition ID for a given player, competition, and season.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.
            competition_selected_sofascored (str):
                Competition name (e.g. "LaLiga").
            season_selected_sofascored (Union[str, int]):
                Season year (e.g. 2023 or "23/24").

        Raises:
            ValueError:
                If no matching competition/season is found.
            KeyError:
                If required columns are missing.

        Returns:
            Tuple[str, str]:
                - season_id
                - competition_id
        """

        df = extract_tournament_season_available(id_player_sofascore)

        if df.empty:
            raise ValueError("No tournament-season data available for player")

        required_cols = ['year', 'name', 'season_id', 'id']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            raise KeyError(f"Missing required columns: {missing_cols}")

        # -----------------------------
        # Filtering (FIX importante)
        # -----------------------------
        mask = (df['year'] == season_selected_sofascored) & (df['name'] == competition_selected_sofascored) 

        filtered = df[mask]

        if filtered.empty:
            raise ValueError(f"No data found for competition='{competition_selected_sofascored}' and season='{season_selected_sofascored}'"
            )

        # -----------------------------
        # Extract IDs
        # -----------------------------
        season_id = str(filtered['season_id'].iloc[0])
        competition_id = str(filtered['id'].iloc[0])

        return season_id, competition_id
    
    def extract_player_info(self, id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract detailed player information from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing in the API response.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - player personal info
                - physical attributes
                - team info
                - country info
                - tournament and team country info
        """

        api = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "player" not in json_data:
            raise KeyError("Missing 'player' in API response")

        player = json_data["player"]

        if not isinstance(player, dict):
            raise ValueError("'player' must be a dictionary")

        # -----------------------------
        # Base DataFrame
        # -----------------------------
        df = pd.DataFrame([player])

        # -----------------------------
        # Date transformation
        # -----------------------------
        if "dateOfBirthTimestamp" not in df.columns:
            raise KeyError("Missing 'dateOfBirthTimestamp' in player data")

        df['dateOfBirth'] = pd.to_datetime(df['dateOfBirthTimestamp'], unit='s', errors='coerce').dt.date

        # -----------------------------
        # Expand team & country
        # -----------------------------
        df = pd.concat([
                df.drop(['team', 'country'], axis=1, errors='ignore'),
                df['team'].apply(pd.Series).add_prefix('team_') if 'team' in df else pd.DataFrame(index=df.index),
                df['country'].apply(pd.Series).add_prefix('country_') if 'country' in df else pd.DataFrame(index=df.index),
            ], axis=1)

        # -----------------------------
        # Expand nested team fields
        # -----------------------------
        df = pd.concat([
                df.drop(['team_tournament', 'team_country'], axis=1, errors='ignore'),
                df['team_tournament'].apply(pd.Series).add_prefix('team_tournament_') if 'team_tournament' in df else pd.DataFrame(index=df.index),
                df['team_country'].apply(pd.Series).add_prefix('team_country_') if 'team_country' in df else pd.DataFrame(index=df.index),
            ], axis=1)

        # -----------------------------
        # Final columns (robusto)
        # -----------------------------
        final_cols = ['id','name',	'slug'	,'shortName','position',	'positionsDetailed',	'jerseyNumber',	'height',	'dateOfBirth',	'preferredFoot', 'proposedMarketValue',	'team_name','team_slug'	,'team_shortName',
                'team_nameCode',	'team_id',	'country_alpha3',	'country_name'	,'country_slug'	,'team_tournament_name'	,'team_tournament_slug',	'team_country_alpha3',	'team_country_name',	'team_country_slug']
        df = df.reindex(columns=final_cols)

        # -----------------------------
        # Cleaning
        # -----------------------------
        if 'positionsDetailed' in df.columns:
            df['positionsDetailed'] = df['positionsDetailed'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x )

        return df
    
    def extract_attributes_summary( self, id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract player attribute overview summary from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - attribute values
                - mapped position
                - relative date (month-year)
        """

        api = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/attribute-overviews"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "playerAttributeOverviews" not in json_data:
            raise KeyError("Missing 'playerAttributeOverviews' in API response")

        data = json_data["playerAttributeOverviews"]

        if not isinstance(data, list):
            raise ValueError("'playerAttributeOverviews' must be a list")

        if len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # -----------------------------
        # Validate required columns
        # -----------------------------
        if "yearShift" not in df.columns:
            raise KeyError("Missing 'yearShift' in data")

        # -----------------------------
        # Date transformation
        # -----------------------------
        now = datetime.now()

        df['date'] = df['yearShift'].apply( lambda x: (now.replace(year=now.year - int(x)).strftime('%B %Y')if pd.notnull(x) else None ))

        # -----------------------------
        # Position mapping
        # -----------------------------
        if "position" in df.columns:
            positions_map = {'G': 'Goalkeeper', 'D': 'Defender','M': 'Midfielder','F': 'Forward' }
            df['position'] = df['position'].map(positions_map)

        # -----------------------------
        # Cleanup
        # -----------------------------
        return df.drop(columns=['yearShift', 'id'], errors='ignore')
    
    def extract_summary_last_year(self,  id_player_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract last year performance summary for a player from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - df_final: detailed match-level data with tournament info
                - df_stats: aggregated stats (appearances and average rating)
        """

        api = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/last-year-summary"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "summary" not in json_data:
            raise KeyError("Missing 'summary' in API response")

        if "uniqueTournamentsMap" not in json_data:
            raise KeyError("Missing 'uniqueTournamentsMap' in API response")

        summary_data = json_data["summary"]

        if not isinstance(summary_data, list):
            raise ValueError("'summary' must be a list")

        if len(summary_data) == 0:
            return pd.DataFrame(), pd.DataFrame()

        # -----------------------------
        # Base DataFrame
        # -----------------------------
        df = pd.DataFrame(summary_data)

        if "timestamp" not in df.columns:
            raise KeyError("Missing 'timestamp' in summary data")

        df['timestamp'] = pd.to_datetime( df['timestamp'], unit='s', errors='coerce').dt.date

        # -----------------------------
        # Tournaments mapping
        # -----------------------------
        tournaments_map = json_data["uniqueTournamentsMap"]

        if not isinstance(tournaments_map, dict):
            raise ValueError("'uniqueTournamentsMap' must be a dictionary")

        unique_tournaments = pd.DataFrame(tournaments_map).transpose()

        required_cols = ['name', 'slug', 'category', 'id']
        missing_cols = [c for c in required_cols if c not in unique_tournaments.columns]
        if missing_cols:
            raise KeyError(f"Missing columns in tournaments map: {missing_cols}")

        unique_tournaments = pd.concat([
                unique_tournaments.drop(['category'], axis=1),
                unique_tournaments['category'].apply(pd.Series).add_prefix('category_'),
            ], axis=1)

        unique_tournaments = unique_tournaments.reindex(columns=['name', 'slug', 'id','category_name', 'category_slug', 'category_flag', 'category_id'])

        # -----------------------------
        # Merge
        # -----------------------------
        if "uniqueTournamentId" not in df.columns:
            raise KeyError("Missing 'uniqueTournamentId' in summary data")

        df_final = df.merge( unique_tournaments,left_on='uniqueTournamentId',right_on='id', how='left')

        # -----------------------------
        # Value cleaning
        # -----------------------------
        if "value" in df_final.columns:
            df_final['value'] = pd.to_numeric(df_final['value'], errors='coerce')

        # -----------------------------
        # Aggregation
        # -----------------------------
        if "name" not in df_final.columns:
            raise KeyError("Missing 'name' column after merge")

        df_stats = df_final.groupby('name').agg(appearances=('value', 'count'),avg_rating=('value', 'mean') ).round({'avg_rating': 2}).reset_index()
        

        return df_final, df_stats
    
    def extract_transfer_history(self, id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract transfer history for a player from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - player info
                - transfer origin/destination
                - transfer date and fee
        """

        api = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/transfer-history"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "transferHistory" not in json_data:
            raise KeyError("Missing 'transferHistory' in API response")

        data = json_data["transferHistory"]

        if not isinstance(data, list):
            raise ValueError("'transferHistory' must be a list")

        if len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # -----------------------------
        # Date
        # -----------------------------
        if "transferDateTimestamp" not in df.columns:
            raise KeyError("Missing 'transferDateTimestamp'")

        df['transferDateTimestamp'] = pd.to_datetime( df['transferDateTimestamp'], unit='s', errors='coerce')
        df['transfer_date'] = df['transferDateTimestamp'].dt.date

        # -----------------------------
        # Expand nested
        # -----------------------------
        df = pd.concat([
                df.drop(['player', 'transferFrom', 'transferTo'], axis=1, errors='ignore'),
                df['player'].apply(pd.Series).add_prefix('player_') if 'player' in df else pd.DataFrame(index=df.index),
                df['transferFrom'].apply(pd.Series).add_prefix('transferFrom_') if 'transferFrom' in df else pd.DataFrame(index=df.index),
                df['transferTo'].apply(pd.Series).add_prefix('transferTo_') if 'transferTo' in df else pd.DataFrame(index=df.index),
            ], axis=1)

        # -----------------------------
        # Final columns
        # -----------------------------
        final_cols = ['player_name', 'player_slug', 'player_shortName', 'player_position', 'player_jerseyNumber', 'player_id', 'transfer_date', 'transferFeeDescription','transferFrom_name','transferFrom_slug','transferFrom_shortName',
                'transferFrom_nameCode','transferFrom_id','transferTo_name','transferTo_slug','transferTo_shortName','transferTo_nameCode', 'transferTo_id']

        return df.reindex(columns=final_cols)
    
    def extract_national_team_stats(self, id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract national team statistics for a player from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required keys are missing.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - national team info
                - debut date
                - performance statistics
        """

        api = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/national-team-statistics"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "statistics" not in json_data:
            raise KeyError("Missing 'statistics' in API response")

        data = json_data["statistics"]

        if not isinstance(data, list):
            raise ValueError("'statistics' must be a list")

        if len(data) == 0:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # -----------------------------
        # Date
        # -----------------------------
        if "debutTimestamp" in df.columns:
            df['match_date'] = pd.to_datetime(df['debutTimestamp'],unit='s', errors='coerce' ).dt.date
            df = df.drop(columns=['debutTimestamp'], errors='ignore')

        # -----------------------------
        # Expand team
        # -----------------------------
        if "team" not in df.columns:
            raise KeyError("Missing 'team' in statistics data")

        team_df = df['team'].apply(pd.Series)

        expected_team_cols = ['name','slug','shortName','nameCode','ranking','id']
        team_df = team_df.reindex(columns=expected_team_cols)
        team_df = team_df.add_prefix('team_')

        # -----------------------------
        # Final merge
        # -----------------------------
        return pd.concat([ team_df,df.drop(columns=['team'], errors='ignore')], axis=1)
    
    def extract_heatmap_season(self, id_player_sofascore: Union[str, int],id_competition_sofascored: Union[str, int],id_season_sofascored: Union[str, int]) -> pd.DataFrame:
        """
        Extract player heatmap data for a given competition and season
        from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.
            id_competition_sofascored (Union[str, int]):
                Competition identifier.
            id_season_sofascored (Union[str, int]):
                Season identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If 'points' field is missing in API response.

        Returns:
            pd.DataFrame:
                DataFrame containing heatmap points (typically x, y coordinates and intensity).
        """

        api =  f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/unique-tournament/{id_competition_sofascored}/season/{id_season_sofascored}/heatmap/overall"
        

        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}, competition={id_competition_sofascored}, season={id_season_sofascored}")

        if "points" not in json_data:
            raise KeyError("Missing 'points' in API response")

        points = json_data["points"]

        if not isinstance(points, list):
            raise ValueError("'points' must be a list")

        if len(points) == 0:
            return pd.DataFrame()

        return pd.DataFrame(points)
    
    def extract_season_ratings(self, id_player_sofascore: Union[str, int], id_competition_sofascored: Union[str, int], id_season_sofascored: Union[str, int]) -> pd.DataFrame:
        """
        Extract match-by-match ratings for a player in a given competition and season
        from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier in SofaScore.
            id_competition_sofascored (Union[str, int]):
                Competition identifier.
            id_season_sofascored (Union[str, int]):
                Season identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required fields are missing in API response.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - match date and time
                - rating per match
                - opponent info
                - match context (teams, score, tournament, status)
        """

        api =  f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/unique-tournament/{id_competition_sofascored}/season/{id_season_sofascored}/ratings/overall"
        

        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}, competition={id_competition_sofascored}, season={id_season_sofascored}")

        if "seasonRatings" not in json_data:
            raise KeyError("Missing 'seasonRatings' in API response")

        data = json_data["seasonRatings"]

        if not isinstance(data, list):
            raise ValueError("'seasonRatings' must be a list")

        if len(data) == 0:
            return pd.DataFrame()

        seasonRatings = pd.DataFrame(data)

        # -----------------------------
        # Date handling
        # -----------------------------
        if "startTimestamp" not in seasonRatings.columns:
            raise KeyError("Missing 'startTimestamp' in seasonRatings")

        dt = pd.to_datetime( seasonRatings['startTimestamp'],unit='s',errors='coerce')
        seasonRatings['match_date'] = dt.dt.date
        seasonRatings['match_time'] = dt.dt.time

        seasonRatings = seasonRatings.drop(columns=['startTimestamp'], errors='ignore')

        # -----------------------------
        # Events expansion
        # -----------------------------
        if "event" not in seasonRatings.columns:
            raise KeyError("Missing 'event' in seasonRatings")

        events = seasonRatings['event'].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)

        expected_event_cols = ['tournament', 'status', 'winnerCode', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore', 'slug' ]
        events = events.reindex(columns=expected_event_cols)

        events_expanded = pd.concat([
                events.drop(['tournament', 'status', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore'], axis=1),
                events['tournament'].apply(pd.Series).add_prefix('tournament_'),
                events['status'].apply(pd.Series).add_prefix('status_'),
                events['homeTeam'].apply(pd.Series).add_prefix('homeTeam_'),
                events['awayTeam'].apply(pd.Series).add_prefix('awayTeam_'),
                events['homeScore'].apply(pd.Series).add_prefix('homeScore_'),
                events['awayScore'].apply(pd.Series).add_prefix('awayScore_')
            ], axis=1)

        final_event_cols = ['winnerCode', 'slug', 'tournament_name', 'tournament_slug', 'tournament_id', 'status_description', 'homeTeam_name', 'homeTeam_slug', 'homeTeam_shortName',
                                        'homeTeam_nameCode','homeTeam_id', 'awayTeam_name', 'awayTeam_slug','awayTeam_shortName', 'awayTeam_nameCode', 'awayTeam_id','homeScore_current', 'homeScore_period1',
                                        'homeScore_period2', 'awayScore_current','awayScore_period1', 'awayScore_period2'  ]
        events_clean = events_expanded.reindex(columns=final_event_cols)

        # -----------------------------
        # Opponent
        # -----------------------------
        if "opponent" in seasonRatings.columns:
            opponents = seasonRatings['opponent'].apply(  lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)
            opponents = opponents.reindex(columns=['name']).rename( columns={'name': 'opponent_name'} )
        else:
            opponents = pd.DataFrame(index=seasonRatings.index)

        # -----------------------------
        # Final merge
        # -----------------------------
        return  pd.concat([events_clean,opponents, seasonRatings.drop(columns=['event', 'opponent'], errors='ignore') ], axis=1)
    
    def extract_stats_season(self, id_player_sofascore: Union[str, int],id_competition_sofascored: Union[str, int],id_season_sofascored: Union[str, int], type_stats: str = "overall") -> pd.DataFrame:
        """
        Extract season statistics for a player in a given competition and season
        from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier.
            id_competition_sofascored (Union[str, int]):
                Competition identifier.
            id_season_sofascored (Union[str, int]):
                Season identifier.
            type_stats (str, optional):
                Type of statistics ('overall', 'home', 'away', etc.). Default is 'overall'.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If 'statistics' field is missing.

        Returns:
            pd.DataFrame:
                DataFrame containing normalized season statistics.
        """

        api =  f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/unique-tournament/{id_competition_sofascored}/season/{id_season_sofascored}/statistics/{type_stats}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}, competition={id_competition_sofascored}, season={id_season_sofascored}")

        if "statistics" not in json_data:
            raise KeyError("Missing 'statistics' in API response")

        stats = json_data["statistics"]

        if not isinstance(stats, dict):
            raise ValueError("'statistics' must be a dictionary")

        df = pd.json_normalize(stats)

        # -----------------------------
        # Cleanup
        # -----------------------------
        drop_cols = [ 'statisticsType.sportSlug','statisticsType.statisticsType']

        return df.drop(columns=drop_cols, errors='ignore')
    
    def extract_info_penalties(self, id_player_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, int, int, float]:
        """
        Extract penalty history and summary statistics for a player
        from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required fields are missing.

        Returns:
            Tuple:
                - penalties (pd.DataFrame): detailed penalty events
                - penalties_attempts (int)
                - penalties_scored (int)
                - conversion_rate (float)
        """

        api = f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/penalty-history/unique-tournament/8/season/77559"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        required_keys = ['penalties', 'attempts', 'scored']
        missing_keys = [k for k in required_keys if k not in json_data]

        if missing_keys:
            raise KeyError(f"Missing keys in API response: {missing_keys}")

        penalties_data = json_data['penalties']

        if not isinstance(penalties_data, list):
            raise ValueError("'penalties' must be a list")

        if len(penalties_data) == 0:
            return pd.DataFrame(), 0, 0, 0.0

        penalties = pd.DataFrame(penalties_data).rename(columns={'id': 'id_event'})

        # -----------------------------
        # Events expansion
        # -----------------------------
        if "event" not in penalties.columns:
            raise KeyError("Missing 'event' in penalties data")

        events = penalties['event'].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series)
        events = events.drop(columns=['eventState', 'customId', 'hasXg', 'finalResultOnly'],errors='ignore')

        events_expanded = pd.concat([
                events.drop(['tournament', 'status', 'homeTeam', 'awayTeam', 'homeScore', 'awayScore'], axis=1, errors='ignore'),
                events['tournament'].apply(pd.Series).add_prefix('tournament_'),
                events['status'].apply(pd.Series).add_prefix('status_'),
                events['homeTeam'].apply(pd.Series).add_prefix('homeTeam_'),
                events['awayTeam'].apply(pd.Series).add_prefix('awayTeam_'),
                events['homeScore'].apply(pd.Series).add_prefix('homeScore_'),
                events['awayScore'].apply(pd.Series).add_prefix('awayScore_')
            ], axis=1)

        final_cols = ['winnerCode', 'slug', 'tournament_name', 'tournament_slug', 'tournament_id', 'status_description', 'homeTeam_name', 'homeTeam_slug', 'homeTeam_shortName',
                    'homeTeam_nameCode','homeTeam_id', 'awayTeam_name', 'awayTeam_slug','awayTeam_shortName', 'awayTeam_nameCode', 'awayTeam_id','homeScore_current', 'homeScore_period1',
                    'homeScore_period2', 'awayScore_current','awayScore_period1', 'awayScore_period2'  ]

        events_clean = events_expanded.reindex(columns=final_cols)

        # -----------------------------
        # Merge
        # -----------------------------
        penalties = pd.concat([events_clean, penalties.drop(columns=['event'], errors='ignore')], axis=1)

        # -----------------------------
        # Summary stats
        # -----------------------------
        attempts = json_data['attempts']
        scored = json_data['scored']

        if not isinstance(attempts, (int, float)) or not isinstance(scored, (int, float)):
            raise ValueError("'attempts' and 'scored' must be numeric")

        conversion_rate = round((scored / attempts * 100) if attempts > 0 else 0.0,2)

        return penalties, int(attempts), int(scored), float(conversion_rate)
    
    def extract_career_stats_all_h_a(self,  id_player_sofascore: Union[str, int], type_stat: str = "overall") -> pd.DataFrame:
        """
        Extract player career statistics split by match type (home/away/overall)
        across all seasons from SofaScore API.

        Args:
            id_player_sofascore (Union[str, int]):
                Player identifier.
            type_stat (str, optional):
                Match type filter ('overall', 'home', 'away'). Default is 'overall'.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required fields are missing.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - season info
                - team info
                - competition info
                - detailed statistics per season
        """

        api =  f"https://www.sofascore.com/api/v1/player/{id_player_sofascore}/statistics/match-type/{type_stat}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for player={id_player_sofascore}")

        if "seasons" not in json_data:
            raise KeyError("Missing 'seasons' in API response")

        seasons = json_data["seasons"]

        if not isinstance(seasons, list):
            raise ValueError("'seasons' must be a list")

        if len(seasons) == 0:
            return pd.DataFrame()

        stats_seasons = pd.DataFrame(seasons)

        # -----------------------------
        # Expand nested
        # -----------------------------
        stats_seasons_expanded = pd.concat([
                stats_seasons.drop(['team', 'uniqueTournament', 'season'], axis=1, errors='ignore'),
                safe_expand(stats_seasons, 'team', 'team_'),
                safe_expand(stats_seasons, 'uniqueTournament', 'uniqueTournament_'),
                safe_expand(stats_seasons, 'season', 'season_'),
            ], axis=1)

        # -----------------------------
        # Safe selection
        # -----------------------------
        base_cols = ['statistics', 'year', 'startYear', 'endYear', 'team_name', 'team_slug','team_shortName', 'team_nameCode','team_national', 
                    'team_id', 'uniqueTournament_name', 'uniqueTournament_slug','uniqueTournament_id',
                    'uniqueTournament_competitionType', 'season_name', 'season_id']

        stats_seasons_clean = stats_seasons_expanded.reindex(columns=base_cols)

        # -----------------------------
        # Expand statistics safely
        # -----------------------------
        stats_final = pd.concat([
            stats_seasons_clean.drop(['statistics'], axis=1, errors='ignore'),
            stats_seasons_clean['statistics'].apply(lambda x: x if isinstance(x, dict) else {}).apply(pd.Series).add_prefix('statistics_')
            ], axis=1)

        return stats_final
    
    def extract_stats_one_match(self, id_one_match_player: Union[str, int],id_player_sofascore: Union[str, int]) -> Tuple[str, pd.DataFrame]:
        """
        Extract match statistics for a specific player from SofaScore API.

        Args:
            id_one_match_player (Union[str, int]):
                Match (event) identifier.
            id_player_sofascore (Union[str, int]):
                Player identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required fields are missing.

        Returns:
            Tuple[str, pd.DataFrame]:
                - position_match: player position (mapped)
                - stats_match: DataFrame with match statistics
        """

        api =  f"https://www.sofascore.com/api/v1/event/{id_one_match_player}/player/{id_player_sofascore}/statistics"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for match={id_one_match_player}, player={id_player_sofascore}")

        if "statistics" not in json_data:
            raise KeyError("Missing 'statistics' in API response")

        # -----------------------------
        # Position mapping
        # -----------------------------
        raw_position = json_data.get("position")

        position_map =  {'G': 'Goalkeeper',  'D': 'Defender','M': 'Midfielder','F': 'Forward' }
        position_match = position_map.get(raw_position, raw_position)

        # -----------------------------
        # Stats DataFrame
        # -----------------------------
        stats = json_data["statistics"]

        if not isinstance(stats, dict):
            raise ValueError("'statistics' must be a dictionary")

        stats_match = pd.json_normalize(stats)

        # -----------------------------
        # Cleanup
        # -----------------------------
        drop_cols = ['statisticsType.sportSlug','statisticsType.statisticsType','ratingVersions.original']
        stats_match = stats_match.drop(columns=drop_cols, errors='ignore')

        return position_match, stats_match
    
    def extract_events_rating_breakdown( self, id_one_match_player: Union[str, int], id_player_sofascore: Union[str, int]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract detailed event breakdown (passes, defensive actions,
        dribbles, ball carries) for a player in a match.

        Args:
            id_one_match_player (Union[str, int]):
                Match (event) identifier.
            id_player_sofascore (Union[str, int]):
                Player identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required sections are missing.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
                - passes
                - defensive
                - dribbles
                - ball_carries
        """

        api =  f"https://www.sofascore.com/api/v1/event/{id_one_match_player}/player/{id_player_sofascore}/rating-breakdown"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(
                f"No API response for match={id_one_match_player}, player={id_player_sofascore}"
            )

        required_keys = ['passes', 'defensive', 'dribbles', 'ball-carries']
        missing_keys = [k for k in required_keys if k not in json_data]

        if missing_keys:
            raise KeyError(f"Missing keys in API response: {missing_keys}")

        # -----------------------------
        # Passes
        # -----------------------------
        passes = pd.DataFrame(json_data['passes'])
        if not passes.empty:
            passes = expand_coordinates(passes, ['playerCoordinates', 'passEndCoordinates'])

        # -----------------------------
        # Defensive
        # -----------------------------
        defensive = pd.DataFrame(json_data['defensive'])
        if not defensive.empty:
            defensive = expand_coordinates(defensive, ['playerCoordinates'])

        # -----------------------------
        # Dribbles
        # -----------------------------
        dribbles = pd.DataFrame(json_data['dribbles'])
        if not dribbles.empty:
            dribbles = expand_coordinates(dribbles, ['playerCoordinates'])

        # -----------------------------
        # Ball carries
        # -----------------------------
        ball_carries = pd.DataFrame(json_data['ball-carries'])
        if not ball_carries.empty:
            ball_carries = expand_coordinates(ball_carries,['playerCoordinates', 'passEndCoordinates'])

        return passes, defensive, dribbles, ball_carries
    
    def extract_shotmap_one_match(self, id_one_match_player: Union[str, int],id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract shotmap data for a player in a specific match from SofaScore API.

        Args:
            id_one_match_player (Union[str, int]):
                Match (event) identifier.
            id_player_sofascore (Union[str, int]):
                Player identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - shot coordinates
                - xG / xGOT
                - shot metadata (type, body part, situation)
                - goalkeeper info
        """

        api = f"https://www.sofascore.com/api/v1/event/{id_one_match_player}/shotmap/player/{id_player_sofascore}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for match={id_one_match_player}, player={id_player_sofascore}")

        shotmap = json_data.get('shotmap')

        if shotmap is None:
            raise KeyError("Missing 'shotmap' in API response")

        if not isinstance(shotmap, list):
            raise ValueError("'shotmap' must be a list")

        if len(shotmap) == 0:
            return pd.DataFrame()

        df_shotmap = pd.DataFrame(shotmap)      

        # -----------------------------
        # Expand nested
        # -----------------------------
        df_shotmap = pd.concat([
                df_shotmap.drop(
                    ['player','playerCoordinates','goalMouthCoordinates','goalkeeper','blockCoordinates'],axis=1,errors='ignore'),
                safe_expand(df_shotmap, 'player', 'player_'),
                safe_expand(df_shotmap, 'playerCoordinates', 'playerCoordinates_'),
                safe_expand(df_shotmap, 'goalMouthCoordinates', 'goalMouthCoordinates_'),
                safe_expand(df_shotmap, 'goalkeeper', 'goalkeeper_'),
                safe_expand(df_shotmap, 'blockCoordinates', 'blockCoordinates_'),
            ], axis=1)

        # -----------------------------
        # Final columns
        # -----------------------------
        final_cols = [
            'player_name','player_slug','player_shortName','player_position','player_jerseyNumber','player_id','playerCoordinates_x','playerCoordinates_y','playerCoordinates_z',
            'goalMouthCoordinates_x','goalMouthCoordinates_y','goalMouthCoordinates_z','blockCoordinates_x','blockCoordinates_y','blockCoordinates_z','isHome','incidentType','shotType','goalType','situation',
            'bodyPart','goalMouthLocation','xg','xgot','id','time','timeSeconds', 'goalkeeper_name','goalkeeper_slug','goalkeeper_shortName','goalkeeper_jerseyNumber','goalkeeper_id','draw'
            ]

        df_shotmap = df_shotmap.reindex(columns=final_cols)

        return df_shotmap
    
    def extract_heatmap_one_match(self,  id_one_match_player: Union[str, int],  id_player_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract heatmap data for a player in a specific match from SofaScore API.

        Args:
            id_one_match_player (Union[str, int]):
                Match (event) identifier.
            id_player_sofascore (Union[str, int]):
                Player identifier.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If 'heatmap' field is missing.

        Returns:
            pd.DataFrame:
                DataFrame containing heatmap points (x, y coordinates and intensity).
        """

        api =   f"https://www.sofascore.com/api/v1/event/{id_one_match_player}/player/{id_player_sofascore}/heatmap"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError( f"No API response for match={id_one_match_player}, player={id_player_sofascore}")

        if "heatmap" not in json_data:
            raise KeyError("Missing 'heatmap' in API response")

        heatmap = json_data["heatmap"]

        if not isinstance(heatmap, list):
            raise ValueError("'heatmap' must be a list")

        if len(heatmap) == 0:
            return pd.DataFrame()

        return pd.DataFrame(heatmap)
