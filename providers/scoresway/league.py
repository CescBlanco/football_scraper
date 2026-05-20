import requests
import pandas as pd
import time

from urllib.parse import quote
from bs4 import BeautifulSoup

from providers.scoresway.utils import  _create_driver, _create_response
from providers.scoresway.constants import BASE_URL

class ScoreswayLeagueScraper:
    def __init__(self, session: requests.Session, competition_service):
        self.session = session
        self.competition_service = competition_service
        self._league_teams_cache = {}

    def extract_season_league_available(self, country_name: str, league_name: str):
        """
        Extract all available seasons for a specific football league.

        This function retrieves the league URL using the country and league
        name, navigates to the league page, parses the season selector,
        and extracts season-related information.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve seasons from.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - season : str
            - id_season : str
            - season_url : str

        Raises
        ------
        TypeError
            If country_name or league_name is not a string.
        ValueError
            If:
            - country_name or league_name is empty.
            - league information is not found.
            - season selector is not found on the page.
            - no seasons are available.
        RuntimeError
            If the scraping process fails.
        """

        driver = None

        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")
        
        try:
            
            # ------------------------
            # GET LEAGUE INFORMATION
            # ------------------------
            league = self.competition_service.get_league_by_country_and_name(country_name,league_name)

            if league is None or league.empty:
                raise ValueError(f"League '{league_name}' was not found for country '{country_name}'")

            # Extract league URL
            url_league = league[league["league"] == league_name]["league_url"].iloc[0]
            # ------------------------
            # OPEN LEAGUE PAGE
            # ------------------------
            driver = _create_driver()

            driver.get(url_league)

            # Wait for dynamic content to load
            time.sleep(3)

            # Parse HTML content
            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # ------------------------
            # FIND SEASON SELECTOR
            # ------------------------
            select = soup.find("select", id="season-select")

            if select is None:
                raise ValueError(
                    "Season selector was not found on the league page"
                )

            # ------------------------
            # EXTRACT SEASONS
            # ------------------------
            seasons_data = []

            for option in select.find_all("option"):

                # Season display name
                season_text = option.text.strip()

                # Build absolute season URL
                season_url = BASE_URL.rstrip("/") + option["value"]

                # Extract season identifier from URL
                parts = option["value"].strip("/").split("/")

                id_season =  parts[-2]  if len(parts) >= 2  else None

                seasons_data.append({
                    "season": season_text,
                    "id_season": id_season,
                    "season_url": season_url
                })

            if not seasons_data:
                raise ValueError(f"No seasons were found for league '{league_name}'")

            return pd.DataFrame(seasons_data)

        except Exception as e:
            raise RuntimeError(f"Failed to extract seasons for league '{league_name}' in country '{country_name}': {str(e)}")

        finally:
            # Always close the browser session
            if driver:
                driver.quit()
    
    def extract_fixtures(self, country_name: str, league_name: str, season: str = "2025/2026")-> pd.DataFrame:
        """
        Extract fixture matches for a specific football league season.

        This function retrieves season information for a league, calls the
        PerformFeeds API, processes the JSON response, and returns only
        upcoming fixture matches.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve fixtures from.
        season : str, optional
            Season name to filter fixtures.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing fixture match information including:
            - match details
            - home and away teams
            - team badge URLs
            - match preview URL

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - no fixtures are available.
            - API response format is invalid.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")

        if not season.strip():
            raise ValueError("season cannot be empty")
        
        try:
            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available( country_name, league_name)
            season_filter = df_seasons[df_seasons["season"] == season]

            if season_filter.empty:
                raise ValueError(f"Season '{season}' was not found for league '{league_name}'")

            # Extract season identifier
            id_season = season_filter["id_season"].values[0]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/match/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={id_season}&live=yes&_pgSz=400&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W38c46802b1808b1f7876d1903445d1c709bb717a6'
            # ------------------------
            # REQUEST API DATA
            # ------------------------
            json_data= _create_response(api)

            # ------------------------
            # NORMALIZE JSON DATA
            # ------------------------
            df = pd.json_normalize(json_data["match"])

            # Remove unnecessary columns
            df = df.drop(columns= ['matchInfo.coverageLevel','matchInfo.date',	'matchInfo.time', 'matchInfo.numberOfPeriods',	'matchInfo.periodLength',	'matchInfo.var'	,'matchInfo.lastUpdated' ,'matchInfo.sport.id',
                                'matchInfo.sport.name',	'matchInfo.ruleset.id', 'matchInfo.ruleset.name', 'matchInfo.competition.sponsorName', 'matchInfo.stage.id',	'matchInfo.stage.formatId',
                                'matchInfo.competition.competitionCode', 'matchInfo.tournamentCalendar.startDate','matchInfo.tournamentCalendar.endDate' ,'liveData.matchDetails.matchLengthMin',	
                                'liveData.matchDetails.matchLengthSec', 'matchInfo.stage.startDate'	,'matchInfo.stage.endDate',	'matchInfo.stage.name','liveData.matchDetails.periodId'], errors='ignore')

            # ------------------------
            # FILTER FIXTURE MATCHES
            # ------------------------
            df_fix= df[df['liveData.matchDetails.matchStatus']=='Fixture'].reset_index(drop=True)
            if df_fix.empty:
                raise ValueError( f"No fixture matches were found for season '{season}'")
            
            # Remove unnecessary fixture columns
            df_fix = df_fix.drop(columns= ['liveData.matchDetails.winner',	'liveData.matchDetails.period'	,'liveData.matchDetails.scores.ht.home',	'liveData.matchDetails.scores.ht.away',
                                            'liveData.matchDetails.scores.ft.home',	'liveData.matchDetails.scores.ft.away',	'liveData.matchDetails.scores.total.home',
                                            'liveData.matchDetails.scores.total.away',	'liveData.goal','liveData.card',	'liveData.substitute',	'liveData.VAR',
                                            'liveData.matchDetailsExtra.attendance',	'liveData.missedPen'], errors= 'ignore') 

            # Rename contestant column for easier manipulation
            df_fix= df_fix.rename(columns= {'matchInfo.contestant': 'matchInfo_contestant'})

            # ------------------------
            # EXPAND HOME/AWAY TEAMS
            # ------------------------
            df_expanded = pd.concat([pd.json_normalize(df_fix.matchInfo_contestant.str[i]).add_prefix(f'{side}_') for i, side in enumerate(['home', 'away'])], axis=1)

            # Merge expanded team information
            df_final = pd.concat([df_fix.drop(columns='matchInfo_contestant'), df_expanded], axis=1)

            # ------------------------
            # BUILD TEAM IMAGE URLS
            # ------------------------
            df_final['home_photo']= f"https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=" + df_final["home_id"]
            df_final['away_photo']= f"https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=" + df_final["away_id"] 

            # ------------------------
            # BUILD MATCH PREVIEW URL
            # ------------------------
            df_final['match_url'] = ( "https://www.scoresway.com/en_GB/soccer/" + df_final['matchInfo.competition.name'].apply(quote) + "-"+ df_final['matchInfo.tournamentCalendar.name'].str.replace('/', '-', regex=False)+
                                "/"+ df_final['matchInfo.tournamentCalendar.id']+ "/match/view/"+ df_final['matchInfo.id']+ "/match-preview")

            return df_final

        except Exception as e:
            raise RuntimeError(f"Failed to extract fixtures for league '{league_name}' ({season}) in country '{country_name}': {str(e)}")
        
    def extract_results(self, country_name: str,league_name: str,season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract played match results for a specific football league season.

        This function retrieves completed matches from the PerformFeeds API,
        processes the response data, expands home and away team information,
        and returns a structured DataFrame containing match results.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve results from.
        season : str, optional
            Season name to filter results.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing played match information including:
            - match details
            - scores
            - home and away teams
            - team badge URLs
            - match summary URL

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - no played matches are available.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """
        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")

        if not season.strip():
            raise ValueError("season cannot be empty")

        try:
            
            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available(country_name,league_name)

            season_filter =  df_seasons[df_seasons["season"] == season] 
            if season_filter.empty:
                raise ValueError(f"Season '{season}' was not found for league '{league_name}'")

            # Extract season identifier
            id_season = season_filter["id_season"].values[0]
            
            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/match/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={id_season}&live=yes&_pgSz=400&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W38c46802b1808b1f7876d1903445d1c709bb717a6'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)

            if "match" not in json_data:
                raise ValueError("Match data was not found in API response")

            # ------------------------
            # NORMALIZE JSON DATA
            # ------------------------
            df = pd.json_normalize(json_data["match"])

            # Remove unnecessary columns
            df = df.drop(columns= ['matchInfo.coverageLevel',	'matchInfo.date',	'matchInfo.time', 'matchInfo.numberOfPeriods',	'matchInfo.periodLength',	'matchInfo.var'	,'matchInfo.lastUpdated' ,'matchInfo.sport.id',
                                'matchInfo.sport.name',	'matchInfo.ruleset.id', 'matchInfo.ruleset.name', 'matchInfo.competition.sponsorName', 'matchInfo.stage.id',	'matchInfo.stage.formatId',
                                'matchInfo.competition.competitionCode', 'matchInfo.tournamentCalendar.startDate','matchInfo.tournamentCalendar.endDate' ,'liveData.matchDetails.matchLengthMin',	
                                'liveData.matchDetails.matchLengthSec', 'matchInfo.stage.startDate'	,'matchInfo.stage.endDate',	'matchInfo.stage.name','liveData.matchDetails.periodId'], errors='ignore')
        
            # ------------------------
            # FILTER PLAYED MATCHES
            # ------------------------
            df_res = df[df['liveData.matchDetails.matchStatus']== 'Played'].reset_index(drop=True)

            if df_res.empty:
                raise ValueError(f"No played matches were found for season '{season}'")

            # Rename nested contestant column
            df_res = df_res.rename(columns={'matchInfo.contestant': 'matchInfo_contestant'})

            # ------------------------
            # EXPAND HOME/AWAY TEAMS
            # ------------------------
            df_expanded = pd.concat([pd.json_normalize(df_res.matchInfo_contestant.str[i]).add_prefix(f'{side}_') for i, side in enumerate(['home', 'away'])], axis=1)

            # Merge expanded team information
            df_final_res = pd.concat([ df_res.drop(columns='matchInfo_contestant'),df_expanded], axis=1)

            # ------------------------
            # BUILD TEAM IMAGE URLS
            # ------------------------
            df_final_res['home_photo']= f"https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=" + df_final_res["home_id"]
            df_final_res['away_photo']= f"https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=" + df_final_res["away_id"] 

            # ------------------------
            # BUILD MATCH SUMMARY URL
            # ------------------------
            df_final_res['match_url'] = ( "https://www.scoresway.com/en_GB/soccer/" + df_final_res['matchInfo.competition.name'].apply(quote) + "-"+ 
                                        df_final_res['matchInfo.tournamentCalendar.name'].str.replace('/', '-', regex=False)+ "/"+ df_final_res['matchInfo.tournamentCalendar.id']+ 
                                        "/match/view/"+ df_final_res['matchInfo.id']+ "/match-summary")

            return df_final_res

        except Exception as e:
            raise RuntimeError( f"Failed to extract results for league '{league_name}' ({season}) in country '{country_name}': {str(e)}")
        
    def extract_standings_by_type(self,country_name: str,league_name: str,season: str = "2025/2026",type_table: str = "total") -> pd.DataFrame:
        """
        Extract league standing table information for a specific football season.

        This function retrieves standings data from the PerformFeeds API,
        processes the selected table type, formats the standings structure,
        and returns a DataFrame containing ranking statistics for teams.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve standings from.
        season : str, optional
            Season name to filter standings.
            Default is "2025/2026".
        type_table : str, optional
            Type of standings table to extract.

            Supported values include:
            - "total"
            - "home"
            - "away"
            - "form-total"
            - "form-home"
            - "form-away"
            - "half-time-total"
            - "half-time-home"
            - "half-time-away"

            Default is "total".

        Returns
        -------
        pd.DataFrame
            DataFrame containing standings information including:
            - ranking position
            - team information
            - points
            - match statistics
            - goals statistics
            - recent form (for total table)
            - team badge URLs

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - type_table is invalid.
            - standings data is unavailable.
            - API response structure is invalid.
        RuntimeError
            If the standings extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not isinstance(type_table, str):
            raise TypeError("type_table must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")

        if not season.strip():
            raise ValueError("season cannot be empty")

        if not type_table.strip():
            raise ValueError("type_table cannot be empty")
    
        try:
            # ------------------------
            # VALID TABLE TYPES
            # ------------------------
            valid_table_types = ["total","home","away","form-total","form-home","form-away","half-time-total","half-time-home","half-time-away", 'attendance', "over-under"]
            if type_table not in valid_table_types:
                raise ValueError(f"Invalid type_table '{type_table}'. Valid options are: {valid_table_types}")

            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available( country_name, league_name)

            season_filter = df_seasons[df_seasons["season"] == season]
            if season_filter.empty:
                raise ValueError(f"Season '{season}' was not found for league '{league_name}'")

            # Extract season identifier
            id_season = season_filter["id_season"].values[0]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/standings/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={id_season}&live=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3aa9e03622598d4e7dc5f62e1cb756bac91893570'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "stage" not in json_data:
                raise ValueError("Stage data was not found in API response")

            if not json_data["stage"]:
                raise ValueError("Stage information is empty")

            if "division" not in json_data["stage"][0]:
                raise ValueError("Division data was not found in API response")

            # ------------------------
            # NORMALIZE STANDINGS DATA
            # ------------------------
            df_tables = pd.DataFrame(json_data["stage"][0]["division"])
            if df_tables.empty:
                raise ValueError("No standings tables were found")

            # Filter selected table type
            df_selected = df_tables[df_tables["type"] == type_table]
            if df_selected.empty:
                raise ValueError( f"No standings data found for type_table '{type_table}'")

            # Convert ranking information to DataFrame
            standing = pd.DataFrame(df_selected["ranking"].iloc[0])
            if standing.empty:
                raise ValueError("Ranking information is empty")

            # -----------------------------
            # TABLE STRUCTURE DEFINITIONS
            # -----------------------------
            total_types = ["total"]
            medium_types = ['home','away','form-total','form-home','form-away','half-time-total','half-time-home','half-time-away']

            # -----------------------------
            # COLUMN DEFINITIONS
            # -----------------------------
            total_columns = ['rank','rankStatus','rankId','lastRank','contestantId','contestantName','contestantShortName','contestantClubName','contestantCode','points','matchesPlayed',
                        'matchesWon','matchesLost','matchesDrawn','goalsFor','goalsAgainst','goaldifference','lastSix']
            medium_columns = [ 'rank', 'contestantId', 'contestantName', 'contestantShortName', 'contestantClubName', 'contestantCode', 'points', 'matchesPlayed', 'matchesWon',
                        'matchesLost','matchesDrawn','goalsFor','goalsAgainst','goaldifference']
            # -----------------------------
            # APPLY TABLE STRUCTURE
            # -----------------------------
            if type_table in total_types:

                standing = standing[total_columns]
                # Format recent form results
                standing["lastSix"] = standing["lastSix"].apply( lambda x: ",".join(x) if isinstance(x, list) else x)

            elif type_table in medium_types:

                standing = standing[medium_columns]

            # -----------------------------
            # BUILD TEAM IMAGE URLS
            # -----------------------------
            standing['team_photo'] = f"https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=" + standing["contestantId"]

            return standing

        except Exception as e:
            raise RuntimeError(f"Failed to extract standings table '{type_table}' for league '{league_name}' ({season}) in country '{country_name}': {str(e)}")    

    def extract_squads_info(self, country_name: str,league_name: str,season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract squad and team information for a specific football league season.

        This function retrieves squad data from the PerformFeeds API,
        processes team-related information, generates team URLs and
        badge image URLs, and returns a structured DataFrame.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve squad information from.
        season : str, optional
            Season name to filter squad data.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing team and squad information including:
            - contestantId
            - contestantName
            - competitionName
            - teamUrl
            - teamPhoto
            - tournamentCalendarId

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - squad data is unavailable.
            - API response structure is invalid.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")

        if not season.strip():
            raise ValueError("season cannot be empty")
        
        try:
            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available( country_name, league_name)

            season_filter = df_seasons[df_seasons['season'] == season]
            if season_filter.empty:
                raise ValueError(
                    f"Season '{season}' was not found for league '{league_name}'")

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
                raise ValueError("Squad data was not found in API response")

            # ------------------------
            # NORMALIZE JSON DATA
            # ------------------------
            teams_row_data = pd.DataFrame(json_data['squad'])

            if teams_row_data.empty:
                raise ValueError(f"No squad information was found for season '{season}'")

            # Remove unnecessary columns
            df = teams_row_data.drop(columns=['person', 'teamKits'],errors='ignore')

            # ------------------------
            # GENERATE TEAM SLUGS
            # ------------------------
            df["slugContestantName"] =  df["contestantName"].str.lower().str.replace(" ", "-", regex=False)
            df["competition_slug"] = df["competitionName"].str.strip().str.lower().str.replace(r"\s+", "-", regex=True)

            # ------------------------
            # BUILD TEAM URLS
            # ------------------------
            df["teamUrl"] = ( "https://www.scoresway.com/en_GB/soccer/" + df["competition_slug"] + "-" + df["tournamentCalendarStartDate" ].str.split('-').str[0] + "-" +  df["tournamentCalendarEndDate" ].str.split('-').str[0] 
                            + "/"+ df["tournamentCalendarId"] + "/teams/"+ df["slugContestantName"] + "/"+ df["contestantId"])

            # ------------------------
            # BUILD TEAM IMAGE URLS
            # ------------------------
            df["teamPhoto"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df["contestantId"]

            return df

        except Exception as e:
            raise RuntimeError( f"Failed to extract squad information for league '{league_name}' ({season}) in country '{country_name}': {str(e)}")            

    def _get_league_teams_cache(self,country_name: str,league_name: str,season: str = "2025/2026") -> pd.DataFrame:

        if league_name not in self._league_teams_cache:

            self._league_teams_cache[league_name] = self.extract_squads_info( country_name, league_name,season)

        return self._league_teams_cache[league_name]
    
    def get_teams(self,country_name: str,league_name: str,season: str = "2025/2026") -> pd.DataFrame:

        return self._get_league_teams_cache(country_name,league_name,season)
    
    def extract_team_kits(self,country_name: str,league_name: str,team_name: str,season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract kit information for a specific football team.

        This function retrieves team kit data from the PerformFeeds API
        and returns a DataFrame containing the available kits for the
        selected team and season.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name associated with the team.
        team_name : str
            Team name to retrieve kits from.
        season : str, optional
            Season name to filter data.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing team kit information.

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - team is not found.
            - kit information is unavailable.
        RuntimeError
            If the extraction process fails.
        """

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
        
        try:
            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available( country_name, league_name)

            season_filter =df_seasons[df_seasons['season'] == season]
            if season_filter.empty:
                raise ValueError(f"Season '{season}' was not found")

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
                raise ValueError("Squad data was not found in API response")

            teams = pd.DataFrame(json_data['squad'])

            team_filter = teams[teams['contestantClubName'] == team_name]
            if team_filter.empty:
                raise ValueError( f"Team '{team_name}' was not found")

            # ------------------------
            # EXTRACT TEAM KITS
            # ------------------------
            df = pd.DataFrame( team_filter['teamKits'].values[0])

            if df.empty:
                raise ValueError(f"No kit information was found for team '{team_name}'")

            # Expand nested kit information
            df = df.kit.apply(pd.Series)

            return df

        except Exception as e:
            raise RuntimeError( f"Failed to extract kits for team '{team_name}' in league '{league_name}' ({season}): {str(e)}")
        
    def extract_teams_stats(self, country_name: str,league_name: str,season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract team statistics for a specific football league season.

        This function retrieves ranking and statistical data for all teams
        in a league season and returns a structured DataFrame.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve statistics from.
        season : str, optional
            Season name to filter data.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing team statistics and team badge URLs.

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - team statistics are unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")

        if not season.strip():
            raise ValueError("season cannot be empty")

        try:   
            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available( country_name,league_name)

            season_filter =  df_seasons[df_seasons['season'] == season]
            

            if season_filter.empty:
                raise ValueError(f"Season '{season}' was not found")

            id_season =  season_filter['id_season'].values[0]
            

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/rankings/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={id_season}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e773861460895e7a6cee9aa5e2bd83f25b28c7bb'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)

            if "team" not in json_data:
                raise ValueError("Team statistics were not found ""in API response")

            # ------------------------
            # NORMALIZE TEAM DATA
            # ------------------------
            df = pd.DataFrame(json_data['team'] )[['name', 'id', 'stat']]

            if df.empty:
                raise ValueError(f"No team statistics were found for season '{season}'")

            # Convert stats list into dictionary
            team_stats_dict = df['stat'].apply(lambda x: {d['type']: d['value']  for d in x })

            # Expand statistics into columns
            df2 = pd.json_normalize(team_stats_dict)

            # Merge base team information with stats
            df_final = pd.concat([ df.drop(columns='stat').reset_index(drop=True), df2.reset_index(drop=True)],axis=1).rename(columns={'name': 'team', 'id': 'id_team'})

            # ------------------------
            # BUILD TEAM IMAGE URLS
            # ------------------------
            df_final["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df_final["id_team"]

            return df_final

        except Exception as e:
            raise RuntimeError(f"Failed to extract team statistics for league '{league_name}' ({season}): {str(e)}")
        
    def extract_players_stats(self,country_name: str,league_name: str,season: str = "2025/2026") -> pd.DataFrame:
        """
        Extract player statistics for a specific football league season.

        This function retrieves player ranking and statistical data from
        the PerformFeeds API, expands nested player information, and
        returns a structured DataFrame with player and team details.

        Parameters
        ----------
        country_name : str
            Country name associated with the league.
        league_name : str
            League name to retrieve player statistics from.
        season : str, optional
            Season name to filter data.
            Default is "2025/2026".

        Returns
        -------
        pd.DataFrame
            DataFrame containing player statistics, player photos,
            and team badge URLs.

        Raises
        ------
        TypeError
            If input parameters are not strings.
        ValueError
            If:
            - input values are empty.
            - season is not found.
            - player statistics are unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUTS
        # ------------------------
        if not isinstance(country_name, str):
            raise TypeError("country_name must be a string")

        if not isinstance(league_name, str):
            raise TypeError("league_name must be a string")

        if not isinstance(season, str):
            raise TypeError("season must be a string")

        if not country_name.strip():
            raise ValueError("country_name cannot be empty")

        if not league_name.strip():
            raise ValueError("league_name cannot be empty")

        if not season.strip():
            raise ValueError("season cannot be empty")
        
        try:
            # ------------------------
            # GET SEASON INFORMATION
            # ------------------------
            df_seasons = self.extract_season_league_available( country_name, league_name)

            season_filter =  df_seasons[df_seasons['season'] == season]
            if season_filter.empty:
                raise ValueError(f"Season '{season}' was not found" )

            id_season = season_filter['id_season'].values[0]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/rankings/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&tmcl={id_season}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e773861460895e7a6cee9aa5e2bd83f25b28c7bb'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "team" not in json_data:
                raise ValueError("Player statistics were not found in API response")

            # ------------------------
            # NORMALIZE TEAM DATA
            # ------------------------
            df1 = pd.DataFrame(json_data['team'])[['name', 'id', 'player']]

            if df1.empty:
                raise ValueError( f"No player statistics were found for season '{season}'")

            # ------------------------
            # EXPLODE PLAYERS
            # ------------------------
            df2 = df1[['name', 'id','player']].explode('player').reset_index(drop=True).rename(columns= {'name': 'team', 'id': 'id_team'})

            # Expand player dictionary
            df3 = df2['player'].apply(pd.Series).reset_index(drop=True)

            # Expand player statistics
            df4 = df3['stat'].apply(lambda x: {d['type']: d['value'] for d in x}).pipe(pd.json_normalize).reset_index(drop=True)

            # ------------------------
            # BUILD FINAL DATAFRAME
            # ------------------------
            df_final = pd.concat([df2[['team','id_team']].reset_index(drop=True), df3.drop(columns='stat'), df4], axis=1)

            # Rename player name column
            df_final = df_final.rename(columns={'name': 'player_name'})

            # ------------------------
            # BUILD PLAYER IMAGE URLS
            # ------------------------
            df_final['player_photo']=  'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df_final['id_team'] + '&dimensions=103x155&id=' + df_final['id']

            # Build team badge URLs
            df_final["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df_final["id_team"]
            
            return df_final

        except Exception as e:
            raise RuntimeError(f"Failed to extract player statistics for league '{league_name}' ({season}): {str(e)}")
    