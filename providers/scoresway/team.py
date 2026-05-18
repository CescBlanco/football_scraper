import requests
import pandas as pd

from providers.scoresway.utils import _create_response

class ScoreswayTeamScraper:
    def __init__(self, session: requests.Session, league_service):
        self.session = session
        self.league_service = league_service
        self._team_squad_cache = {}

    def extract_team_fixtures(self,country_name: str,league_name: str,team_name: str,season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract fixtures for a specific football team.

        This function retrieves all league fixtures and filters
        matches where the selected team plays either as home
        or away team.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name associated with the team.
        team_name : str
            Team name to filter fixtures.
        season : str, optional
            Season name to filter fixtures.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing fixtures for the selected team.

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - no fixtures are found.
            - team is not found in fixtures.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUTS
            # ------------------------
            if not isinstance(country_name, str):
                raise TypeError("country_name must be a string")

            if not isinstance(league_name, str):
                raise TypeError("league_name must be a string")

            if not isinstance(team_name, str):
                raise TypeError("team_name must be a string")

            if not isinstance(season, str):
                raise TypeError("season must be a string")

            if not country_name.strip():
                raise ValueError("country_name cannot be empty")

            if not league_name.strip():
                raise ValueError("league_name cannot be empty")

            if not team_name.strip():
                raise ValueError("team_name cannot be empty")

            if not season.strip():
                raise ValueError("season cannot be empty")

            # ------------------------
            # GET LEAGUE FIXTURES
            # ------------------------
            df_fixtures = self.league_service.extract_fixtures(country_name=country_name, league_name=league_name, season=season)

            if df_fixtures.empty:
                raise ValueError("No fixtures were found")

            # ------------------------
            # FILTER TEAM FIXTURES
            # ------------------------
            df_team = df_fixtures[(df_fixtures["home_name"] == team_name) |(df_fixtures["away_name"] == team_name) ].reset_index(drop=True)

            if df_team.empty:
                raise ValueError( f"Team '{team_name}' was not found in fixtures")

            return df_team

        except Exception as e:
            raise RuntimeError( f"Failed to extract fixtures for team '{team_name}' in league '{league_name}' ({season}): {str(e)}")
        
    def extract_team_results(self,country_name: str, league_name: str, team_name: str, season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract played match results for a specific football team.

        This function retrieves all played league matches and filters
        results where the selected team played either as home
        or away team.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name associated with the team.
        team_name : str
            Team name to filter match results.
        season : str, optional
            Season name to filter results.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing played match results for the selected team.

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - no results are found.
            - team is not found in results.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUTS
            # ------------------------
            if not isinstance(country_name, str):
                raise TypeError("country_name must be a string")

            if not isinstance(league_name, str):
                raise TypeError("league_name must be a string")

            if not isinstance(team_name, str):
                raise TypeError("team_name must be a string")

            if not isinstance(season, str):
                raise TypeError("season must be a string")

            if not country_name.strip():
                raise ValueError("country_name cannot be empty")

            if not league_name.strip():
                raise ValueError("league_name cannot be empty")

            if not team_name.strip():
                raise ValueError("team_name cannot be empty")

            if not season.strip():
                raise ValueError("season cannot be empty")

            # ------------------------
            # GET LEAGUE RESULTS
            # ------------------------
            df_results = self.league_service.extract_results(country_name=country_name,league_name=league_name,season=season)
            if df_results.empty:
                raise ValueError("No match results were found")

            # ------------------------
            # FILTER TEAM RESULTS
            # ------------------------
            df_team = df_results[(df_results["home_name"] == team_name) |(df_results["away_name"] == team_name)].reset_index(drop=True)
            if df_team.empty:
                raise ValueError( f"Team '{team_name}' was not found in results")

            return df_team

        except Exception as e:
            raise RuntimeError(f"Failed to extract results for team '{team_name}' in league '{league_name}' ({season}): {str(e)}")
    
    def extract_squad(self, country_name: str, league_name: str, team_name: str, season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract detailed squad information for a specific football team.

        This function retrieves squad data from the PerformFeeds API,
        expands player information, generates player and team URLs,
        and returns a structured DataFrame containing all players
        belonging to the selected team.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name associated with the team.
        team_name : str
            Team name to retrieve squad information from.
        season : str, optional
            Season name to filter squad data.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - player information
            - team information
            - player image URLs
            - team badge URLs
            - player profile URLs
            - team URLs

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - team is not found.
            - squad data is unavailable.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """

        try:
            # ------------------------
            # VALIDATE INPUTS
            # ------------------------
            if not isinstance(country_name, str):
                raise TypeError("country_name must be a string")

            if not isinstance(league_name, str):
                raise TypeError("league_name must be a string")

            if not isinstance(team_name, str):
                raise TypeError("team_name must be a string")

            if not isinstance(season, str):
                raise TypeError("season must be a string")

            if not country_name.strip():
                raise ValueError("country_name cannot be empty")

            if not league_name.strip():
                raise ValueError("league_name cannot be empty")

            if not team_name.strip():
                raise ValueError("team_name cannot be empty")

            if not season.strip():
                raise ValueError("season cannot be empty")

            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.league_service.extract_season_league_available(country_name, league_name)

            season_filter = df_seasons[df_seasons['season'] == season]
            if season_filter.empty:
                raise ValueError( f"Season '{season}' was not found")

            # Extract season identifier
            id_season = season_filter['id_season'].values[0]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/squads/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={id_season}&_pgSz=200&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W32e1ce8ead468893ac276dde18d30e28441247d50'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "squad" not in json_data:
                raise ValueError( "Squad data was not found in API response")

            # ------------------------
            # NORMALIZE SQUAD DATA
            # ------------------------
            teams_row_data = pd.DataFrame( json_data['squad'])
            if teams_row_data.empty:
                raise ValueError(f"No squad data was found for season '{season}'" )

            # Keep only relevant columns
            teams_row_data = teams_row_data[['contestantId'	,'contestantName', 'competitionName',"tournamentCalendarId", 'tournamentCalendarStartDate',	'tournamentCalendarEndDate','person']]

            # ------------------------
            # EXPLODE PLAYER LIST
            # ------------------------
            df_exploded = teams_row_data.explode('person').reset_index(drop=True)

            # Convert player dictionaries into columns
            players_df = pd.json_normalize(df_exploded['person'])

            # Merge team and player data
            df = pd.concat([df_exploded.drop(columns='person'), players_df],axis=1)

            # ------------------------
            # GENERATE SLUGS
            # ------------------------
            df["slugContestantName"] =  df["contestantName"].str.lower().str.replace(" ", "-", regex=False)
            df["competition_slug"] = df["competitionName"].str.strip().str.lower().str.replace(r"\s+", "-", regex=True)

            # ------------------------
            # BUILD IMAGE URLS
            # ------------------------
            df['player_photo']=  'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df['contestantId'] + '&dimensions=103x155&id=' + df['id']
            df["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df["contestantId"]

            # ------------------------
            # BUILD TEAM URLS
            # ------------------------
            df["teamUrl"] = ("https://www.scoresway.com/en_GB/soccer/"+ df["competition_slug"]+ "-"+ df["tournamentCalendarStartDate"].str.split('-').str[0] + "-"
                                + df["tournamentCalendarEndDate"].str.split('-').str[0] + "/" + df["tournamentCalendarId"] + "/teams/" + df["slugContestantName"]
                                + "/"+ df["contestantId"])

            # ------------------------
            # BUILD PLAYER URLS
            # ------------------------
            df["playerUrl"] = ( "https://www.scoresway.com/en_GB/soccer/" + df["competition_slug"] + "-" + df["tournamentCalendarStartDate"].str.split('-').str[0] + "-" 
                                    + df["tournamentCalendarEndDate"].str.split('-').str[0] + "/" + df["tournamentCalendarId"]+ "/teams/view/"+ df["contestantId"]
                                    + "/player/view/"+ df["id"])
            
            df['startDate'] = df['startDate'].str.replace('Z', '', regex=False)
            df['endDate'] = df['endDate'].str.replace('Z', '', regex=False)

            # ------------------------
            # FILTER TEAM DATA
            # ------------------------
            df_filtered= df[df['contestantName']==team_name].reset_index(drop=True)
            if df_filtered.empty:
                raise ValueError(f"Team '{team_name}' was not found" )

            return df_filtered

        except Exception as e:
            raise RuntimeError(f"Failed to extract squad data for team '{team_name}' in league '{league_name}' ({season}): {str(e)}")
        
    def _get_team_squad_cache( self, country_name: str, league_name: str, team_name: str, season: str ) -> pd.DataFrame:

        cache_key = f"{country_name}_{league_name}_{team_name}_{season}"

        if cache_key not in self._team_squad_cache:

            self._team_squad_cache[cache_key] = self.extract_squad(country_name, league_name, team_name,  season)

        return self._team_squad_cache[cache_key]
        
    def get_team_squad(self, country_name: str, league_name: str, team_name: str, season: str) -> pd.DataFrame:

        return self._get_team_squad_cache( country_name, league_name, team_name, season)