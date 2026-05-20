import requests
import pandas as pd
import numpy as np

from providers.scoresway.utils import _create_response

class ScoreswayPreMatchScraper:
    def __init__(self, session: requests.Session):
        self.session = session
    
    def extract_match_details(self, url: str) -> pd.DataFrame:
        """
        Extract pre-match details for a football match.

        This function retrieves match preview information from the
        PerformFeeds API, expands contestant information, and returns
        a structured DataFrame containing match metadata and team details.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - match information
            - competition details
            - contestant/team details
            - match metadata

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - match information is unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError("url cannot be empty")
        
        url_parts = url.split('/')
        if len(url_parts) < 2:
            raise ValueError("Invalid match URL format")
        
        try:
            match_id = url_parts[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/matchpreview/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&fx={match_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e98937ac605a685165acfd6281b9bffff556850e'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "matchInfo" not in json_data:
                raise ValueError("Match information was not found")

            # ------------------------
            # NORMALIZE MATCH DATA
            # ------------------------
            df = pd.json_normalize(json_data['matchInfo'])

            if df.empty:
                raise ValueError("No match details were found")

            # Clean datetime values
            df['date'] = df['date'].str.replace('Z', '', regex=False)

            # Remove unnecessary columns
            df = df.drop(columns= ['coverageLevel', 'time', 'localDate', 'numberOfPeriods',	'periodLength',	'var',	'lastUpdated', 'sport.id' ,'sport.name'	,'ruleset.id',
                                'ruleset.name', 'competition.sponsorName','tournamentCalendar.startDate',	'tournamentCalendar.endDate',
                                'stage.id', 'stage.formatId' ,	'stage.startDate',	'stage.endDate'] ,errors='ignore')

            # Rename match identifier
            df = df.rename(columns={'id': 'id_match' })

            # ------------------------
            # EXPAND CONTESTANT DATA
            # ------------------------
            df_exp = df.explode('contestant')

            contestant = pd.json_normalize( df_exp['contestant'])

            final_df = pd.concat([df_exp.drop(columns='contestant').reset_index(drop=True), contestant.reset_index(drop=True)],axis=1)

            final_df["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + final_df["id"]

            return final_df

        except Exception as e:
            raise RuntimeError( f"Failed to extract pre-match details from URL '{url}': {str(e)}")
    
    def extract_info_previous_meeting_mainleague(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract previous meetings information in the main league.

        This function retrieves historical meetings between two teams
        in the same competition, including summary information,
        match details, and goal events.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
            Tuple containing:
            - summary DataFrame
            - match details DataFrame
            - goal events DataFrame

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - previous meeting information is unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError("url cannot be empty")
        
        try:
            match_id = url.split('/')[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/matchpreview/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&fx={match_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e98937ac605a685165acfd6281b9bffff556850e'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "previousMeetings" not in json_data:
                raise ValueError("Previous meetings data was not found")

            # ------------------------
            # SUMMARY INFORMATION
            # ------------------------
            data = json_data['previousMeetings']
            data_sin_match = { k: v for k, v in data.items() if k != 'match'}
            summary_df = pd.DataFrame([data_sin_match])

            # ------------------------
            # MATCH INFORMATION
            # ------------------------
            df = pd.DataFrame(json_data['previousMeetings']['match'])
            if df.empty:
                raise ValueError("No previous matches were found" )

            df = df.rename(columns={'id': 'id_match'})
            contestants = pd.json_normalize( df['contestants'])
            df2 =pd.concat([df.drop(columns='contestants').reset_index(drop=True), contestants.reset_index(drop=True)],axis=1)
            df2['date'] = df2['date'].str.replace('Z', '', regex=False)
            
            # ------------------------
            # GOAL INFORMATION
            # ------------------------
            matches = df2.copy()

            goals = matches.explode('goal')
            goals = goals[goals['goal'].apply(lambda x: isinstance(x, dict))]

            if goals.empty:
                goals_df = pd.DataFrame()
            else:
                goal_detail = pd.json_normalize(goals['goal'])
                meta_cols = ['id_match','date','homeContestantId','homeContestantName','awayContestantId', 'awayContestantName',	'homeScore'	,'awayScore']
                goals_df = pd.concat([goals[meta_cols].reset_index(drop=True),goal_detail.reset_index(drop=True)], axis=1)

            return summary_df, df2.drop(columns='goal'), goals_df

        except Exception as e:
            raise RuntimeError(f"Failed to extract previous meetings from URL '{url}': {str(e)}")
        
    def extract_info_previous_meeting_anycomp(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract previous meetings information across all competitions.

        This function retrieves historical meetings between two teams
        across any competition, including summary information,
        match details, and goal events.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
            Tuple containing:
            - summary DataFrame
            - match details DataFrame
            - goal events DataFrame

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - previous meeting information is unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError("url cannot be empty")
        
        try:
            match_id = url.split('/')[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/matchpreview/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&fx={match_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e98937ac605a685165acfd6281b9bffff556850e'

            json_data = _create_response(api)
            if "previousMeetingsAnyComp" not in json_data:
                raise ValueError("Previous meetings data was not found")

            # Summary information
            data = json_data['previousMeetingsAnyComp']
            data_sin_match = {  k: v for k, v in data.items() if k != 'match'}
            summary_df = pd.DataFrame([data_sin_match])

            # Match information
            df = pd.DataFrame(json_data['previousMeetingsAnyComp']['match'])
            df = df.rename(columns={'id': 'id_match'})
            contestants = pd.json_normalize(df['contestants'])

            df2 =pd.concat([df.drop(columns='contestants').reset_index(drop=True), contestants.reset_index(drop=True)],axis=1)
            df2['date'] = df2['date'].str.replace('Z', '', regex=False)
            
            # Goal information
            matches = df2.copy()
            goals = matches.explode('goal')
            goals = goals[goals['goal'].apply(lambda x: isinstance(x, dict))]

            if goals.empty:
                goals_df = pd.DataFrame()
            else:
                goal_detail = pd.json_normalize(goals['goal'])
                meta_cols = ['id_match','date','homeContestantId','homeContestantName','awayContestantId','awayContestantName','homeScore','awayScore']
                goals_df = pd.concat([ goals[meta_cols].reset_index(drop=True), goal_detail.reset_index(drop=True)],axis=1)

            return summary_df, df2.drop(columns='goal'), goals_df
            

        except Exception as e:
            raise RuntimeError(f"Failed to extract cross-competition meetings from URL '{url}': {str(e)}")
    
    def extract_last6match_form_main_league(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract last 6 matches form for teams in the main league.

        This function retrieves recent match form data from the
        PerformFeeds API, expands match and goal-level information,
        and returns structured DataFrames.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            - DataFrame with match form data
            - DataFrame with goal-level details

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - form data is unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError("url cannot be empty")

        try:
            
            match_id = url.split('/')[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/matchpreview/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&fx={match_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e98937ac605a685165acfd6281b9bffff556850e'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "form" not in json_data:
                raise ValueError( "Form data was not found in API response")

            # ------------------------
            # NORMALIZE DATA
            # ------------------------
            df = pd.DataFrame(json_data['form'])
            if df.empty:
                raise ValueError("No form data found")

            # ------------------------
            # ASSIGN SIDE (HOME/AWAY)
            # ------------------------
            df['side'] = np.where( df.index % 2 == 0,'home','away' )

            # ------------------------
            # EXPAND MATCH DATA
            # ------------------------
            df_exp = df.explode('match')
            match_exp = pd.json_normalize(df_exp['match'])
            resultado = pd.concat([df_exp.drop(columns='match') .reset_index(drop=True), match_exp.reset_index(drop=True)], axis=1)

            resultado['date'] = resultado['date'].str.replace('Z', '', regex=False) 

            # ------------------------
            # EXPAND GOALS DATA
            # ------------------------
            matches = resultado.copy()
            goals = matches.explode('goal')
            goal_detail = pd.json_normalize(goals['goal'])
            meta_cols = ['id','date','contestantId','side','contestants.homeContestantName','contestants.awayContestantName','contestants.homeScore','contestants.awayScore']

            goals_df = pd.concat([ goals[meta_cols].reset_index(drop=True), goal_detail.reset_index(drop=True)], axis=1)

            return resultado.drop(columns='goal'), goals_df

        except Exception as e:
            raise RuntimeError(f"Failed to extract last 6 match form (main league) from URL '{url}': {str(e)}" )
        
    def extract_last6match_form_anycomp(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract last 6 matches form across all competitions.

        This function retrieves recent match form data from the
        PerformFeeds API for all competitions, expands match
        and goal-level information, and returns structured DataFrames.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            - DataFrame with match form data
            - DataFrame with goal-level details

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - form data is unavailable.
        RuntimeError
            If the extraction process fails.
        """
        
        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError("url cannot be empty")

        try:
            
            match_id = url.split('/')[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/matchpreview/ft1tiv1inq7v1sk3y9tv12yh5/?_rt=c&fx={match_id}&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3e98937ac605a685165acfd6281b9bffff556850e'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)

            if "formAnyComp" not in json_data:
                raise ValueError("Form (any competition) data was not found in API response")

            # ------------------------
            # NORMALIZE DATA
            # ------------------------
            df = pd.DataFrame(json_data['formAnyComp'])
            if df.empty:
                raise ValueError("No form (any competition) data found")

            # ------------------------
            # ASSIGN SIDE (HOME/AWAY)
            # ------------------------
            df['side'] = np.where( df.index % 2 == 0, 'home', 'away')

            # ------------------------
            # EXPAND MATCH DATA
            # ------------------------
            df_exp = df.explode('match')
            match_exp = pd.json_normalize(df_exp['match'])

            resultado = pd.concat([df_exp.drop(columns='match').reset_index(drop=True),match_exp.reset_index(drop=True)], axis=1)
            resultado['date'] = (resultado['date'].str.replace('Z', '', regex=False))

            # ------------------------
            # EXPAND GOALS DATA
            # ------------------------
            matches = resultado.copy()

            goals = matches.explode('goal')
            goal_detail = pd.json_normalize(goals['goal'])
            meta_cols = ['id','date','contestantId','side','contestants.homeContestantName','contestants.awayContestantName','contestants.homeScore','contestants.awayScore']
            goals_df = pd.concat([goals[meta_cols].reset_index(drop=True),goal_detail.reset_index(drop=True)], axis=1)

            return resultado.drop(columns='goal'), goals_df

        except Exception as e:
            raise RuntimeError(f"Failed to extract last 6 match form (any competition) from URL '{url}': {str(e)}")
        
    def extract_win_probability(self, url: str) -> pd.DataFrame:
        """
        Extract pre-match win probability predictions.

        This function retrieves pre-match prediction probabilities
        from the PerformFeeds API and returns them as a DataFrame.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - home win probability
            - draw probability
            - away win probability

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - prediction data is unavailable.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError( "url cannot be empty")
        
        try:
            
            match_id = url.split('/')[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/matchlivewinprobability/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W370035dd8c91380e1d4c3d382668707c5a76ed6c5'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)

            predictions = json_data['liveData']['preMatchPredictions'][0]['prediction']
            if not predictions:
                raise ValueError("No prediction data was found" )

            return pd.DataFrame(predictions)

        except Exception as e:
            raise RuntimeError(f"Failed to extract win probabilities from URL '{url}': {str(e)}")
        

    def extract_extra_prematch_details(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract extra pre-match details including highlights and contextual insights.

        This function retrieves additional pre-match information such as messages,
        form guides, head-to-head stats, top scorers, and upcoming fixtures
        from the PerformFeeds API.

        Parameters
        ----------
        url : str
            Full Scoresway pre-match URL.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]
            - Messages DataFrame
            - Form guide DataFrame
            - Head-to-head DataFrame
            - Top scorers DataFrame
            - Upcoming home fixtures DataFrame
            - Upcoming away fixtures DataFrame

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - API response is invalid or missing expected fields.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not url.strip():
            raise ValueError("url cannot be empty")

        try:
            
            match_id = url.split('/')[-2]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api = f'https://api.performfeeds.com/soccerdata/nlgmatchpreview/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&_lcl=en-gb&_fmt=jsonp&_clbk=W32b2a213776a44ff18b2b03f8babe5eac7a9d9afb'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)

            if "highlights" not in json_data:
                raise ValueError("Highlights data was not found in API response")

            # ------------------------
            # PARSE SECTIONS
            # ------------------------
            df_messages = pd.DataFrame(json_data['messages']['messages'])
            df_form_guide = pd.json_normalize(json_data['highlights']['formGuide'])
            df_h2h = pd.json_normalize(json_data['highlights']['headToHead'])
            df_top_scorers = pd.json_normalize(json_data['highlights']['topScorers'])
            df_up_next_home = pd.json_normalize(json_data['highlights']['upNext']['home']).rename(columns={'contestant': 'fixtures_home','competition': 'competition_home'})
            df_up_next_away = pd.json_normalize(json_data['highlights']['upNext']['away']).rename(columns={'contestant': 'fixtures_away','competition': 'competition_away'})

            return  df_messages, df_form_guide, df_h2h, df_top_scorers, df_up_next_home, df_up_next_away

        except Exception as e:
            raise RuntimeError(f"Failed to extract extra pre-match details from URL '{url}': {str(e)}")
    
    def extract_home_squad(self, url: str) -> pd.DataFrame:
        """
        Extract home team squad for a pre-match context.

        This function retrieves home team squad data using the match
        information DataFrame and expands player-level details.

        Parameters
        ----------
        url : str
      

        Returns
        -------
        pd.DataFrame
            DataFrame containing home team players with:
            - player information
            - team metadata
            - player image URLs
            - nationality flag URLs
            - team badge URLs

        Raises
        ------
        TypeError
            If input is not a DataFrame or missing required fields.
        ValueError
            If:
            - DataFrame is empty.
            - required team ID is missing.
            - API response is invalid.
        RuntimeError
            If the extraction process fails.
        """

        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        df_match_details_prematch= self.extract_match_details(url)
        if not isinstance(df_match_details_prematch, pd.DataFrame):
            raise TypeError("df_match_details_prematch must be a DataFrame")

        if df_match_details_prematch.empty:
            raise ValueError("Input DataFrame cannot be empty")
        
        try:
        
            home_id = df_match_details_prematch['id'].values[0]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/squads/ft1tiv1inq7v1sk3y9tv12yh5?tmcl=80zg2v1cuqcfhphn56u4qpyqc&ctst={home_id}&_fmt=jsonp&_clbk=TM3_{home_id}'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if "squad" not in json_data:
                raise ValueError("Squad data was not found in API response")

            df= pd.DataFrame(json_data['squad'])[['contestantId','contestantName', 'person']]

            # ------------------------
            # EXTRACT PLAYERS
            # ------------------------
            df_home = pd.DataFrame(df.loc[0, 'person']).assign(contestantId=df.loc[0, 'contestantId'],contestantName=df.loc[0, 'contestantName'])

            # ------------------------
            # IMAGE URLS
            # ------------------------
            df_home['player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df_home['contestantId']+ '&dimensions=103x155&id=' + df_home['id']
            df_home['nation_photo']=  "https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=flags&description=countries&dimensions=21x21&id=" + df_home['nationalityId']
            df_home["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df_home["contestantId"]

            return df_home

        except Exception as e:
            raise RuntimeError( "Failed to extract home squad pre-match: " f"{str(e)}")
        
    def extract_away_squad(self, url: str) -> pd.DataFrame:
        """
        Extract away team squad for a pre-match context.

        This function retrieves away team squad data using the match
        information DataFrame and expands player-level details.

        Parameters
        ----------
        url : str

        Returns
        -------
        pd.DataFrame
            DataFrame containing away team players with:
            - player information
            - team metadata
            - player image URLs
            - nationality flag URLs
            - team badge URLs

        Raises
        ------
        TypeError
            If input is not a DataFrame or missing required fields.
        ValueError
            If:
            - DataFrame is empty.
            - required team ID is missing.
            - API response is invalid.
        RuntimeError
            If the extraction process fails.
        """
        
        # ------------------------
        # VALIDATE INPUT
        # ------------------------

        df_match_details_prematch= self.extract_match_details(url)
        if not isinstance(df_match_details_prematch, pd.DataFrame):
            raise TypeError( "df_match_details_prematch must be a DataFrame")

        if df_match_details_prematch.empty:
            raise ValueError("Input DataFrame cannot be empty")
        
        try:
            away_id = df_match_details_prematch['id'].values[1]

            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/squads/ft1tiv1inq7v1sk3y9tv12yh5?tmcl=80zg2v1cuqcfhphn56u4qpyqc&ctst={away_id}&_fmt=jsonp&_clbk=TM3_{away_id}'
            json_data = _create_response(api)

            if "squad" not in json_data:
                raise ValueError("Squad data was not found in API response")

            df= pd.DataFrame(json_data['squad'])[['contestantId','contestantName', 'person']]

            df_away = pd.DataFrame(df.loc[0, 'person'] ).assign( contestantId=df.loc[0, 'contestantId'], contestantName=df.loc[0, 'contestantName'])

            df_away['player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df_away['contestantId']+ '&dimensions=103x155&id=' + df_away['id']
            df_away['nation_photo']=  "https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=flags&description=countries&dimensions=21x21&id=" + df_away['nationalityId']
            df_away["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df_away["contestantId"]

            return df_away

        except Exception as e:
            raise RuntimeError( "Failed to extract away squad pre-match: " f"{str(e)}")
                

    