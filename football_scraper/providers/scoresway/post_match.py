import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)

from football_scraper.providers.scoresway.utils import _create_response, _create_driver, extract_team_data, extract_width

class ScoreswayPostMatchScraper:
    def __init__(self, session: requests.Session):
        self.session = session
    
    def extract_match_info(self, url: str) -> pd.DataFrame:
        """
        Extract detailed post-match information for a football match.

        This function retrieves detailed match statistics and metadata
        from the PerformFeeds API using a Scoresway post-match URL.
        The response is normalized into a structured DataFrame including:
        - match information
        - team details
        - attendance
        - match duration
        - scores
        - period timing information

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        pd.DataFrame
            DataFrame containing detailed post-match information including:
            - match metadata
            - contestant information
            - attendance
            - match status
            - winner
            - half-time and full-time scores
            - total scores
            - period start/end times
            - injury time information

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - API response structure is invalid.
            - required match data is missing.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")

        try:
            
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE RESPONSE STRUCTURE
            # ------------------------
            if "matchInfo" not in json_data:
                raise ValueError("matchInfo was not found in API response")

            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            # ------------------------
            # NORMALIZE MATCH INFO
            # ------------------------
            df1 = pd.json_normalize(json_data["matchInfo"])

            if df1.empty:
                raise ValueError("Match information is empty")

            # ------------------------
            # FORMAT DATE COLUMNS
            # ------------------------
            df1['date'] = df1['date'].str.replace('Z', '', regex=False)
            
            # ------------------------
            # REMOVE UNUSED COLUMNS
            # ------------------------
            df1 = df1.drop(columns= ['coverageLevel', 'time', 'localDate', 'postMatch', 'numberOfPeriods',	'periodLength',	'var',	'lastUpdated', 'sport.id' ,'sport.name'	,'ruleset.id',
                                    'ruleset.name', 'competition.sponsorName','tournamentCalendar.startDate',	'tournamentCalendar.endDate',
                                    'stage.id', 'stage.formatId' ,	'stage.startDate',	'stage.endDate'] ,errors='ignore')

            # Rename match identifier column
            df1= df1.rename(columns= {'id': 'id_match'})

            # ------------------------
            # EXPAND CONTESTANT DATA
            # ------------------------
            df_exp = df1.explode("contestant")
            contestant = pd.json_normalize(df_exp["contestant"])
            
            df2 = pd.concat([df_exp.drop(columns='contestant').reset_index(drop=True), contestant.reset_index(drop=True)],axis=1)

            # ------------------------
            # EXTRACT ATTENDANCE DATA
            # ------------------------
            df2['attendance'] = json_data['liveData']['matchDetailsExtra']['attendance']

            # ------------------------
            # EXTRACT MATCH STATUS
            # ------------------------
            df2["status"] = json_data["liveData"]["matchDetails"]["winner"]
            df2["winner"] = json_data["liveData"]["matchDetails"]["matchStatus"]
            df2["matchLengthMin"] = json_data["liveData"]["matchDetails"]["matchLengthMin"]
            df2["matchLengthSec"] = json_data["liveData"]["matchDetails"]["matchLengthSec"]

            # ------------------------
            # EXTRACT SCORE INFORMATION
            # ------------------------
            scores = json_data["liveData"]["matchDetails"]["scores"]

            # Half-time scores
            df2["ht_home"] = scores["ht"]["home"]
            df2["ht_away"] = scores["ht"]["away"]

            # Full-time scores
            df2["ft_home"] = scores["ft"]["home"]
            df2["ft_away"] = scores["ft"]["away"]

            # Total scores
            df2["total_home"] = scores["total"]["home"]
            df2["total_away"] = scores["total"]["away"]

            # ------------------------
            # EXTRACT PERIOD INFORMATION
            # ------------------------
            periods = json_data["liveData"]["matchDetails"]["period"]

            if len(periods) < 2:
                raise ValueError("Incomplete match period information")

            # First half
            df2["p1_start"] = periods[0]["start"].split("T")[1].replace("Z", "")
            df2["p1_end"] = periods[0]["end"].split("T")[1].replace("Z", "")
            df2["p1_minutes"] = periods[0]["lengthMin"]
            df2["p1_added_minutes"] = periods[0]["announcedInjuryTime"] / 60

            # Second half
            df2["p2_start"] = periods[1]["start"].split("T")[1].replace("Z", "")
            df2["p2_end"] = periods[1]["end"].split("T")[1].replace("Z", "")
            df2["p2_minutes"] = periods[1]["lengthMin"]
            df2["p2_added_minutes"] = periods[1]["announcedInjuryTime"] / 60

            return df2

        except Exception as e:
            raise RuntimeError( f"Failed to extract match information from URL '{url}': {str(e)}")
    
    def extract_match_summary_ux(self, url: str) -> pd.DataFrame:
        """
        Extract match event summary data from a Scoresway match page.

        This function uses Selenium to load the dynamic match page,
        parses the rendered HTML using BeautifulSoup, extracts match
        events for both home and away teams, and returns a structured
        DataFrame containing timeline event information.

        Parameters
        ----------
        url : str
            Scoresway match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - team side
            - event type
            - player name
            - player identifier
            - player profile URL
            - match minute

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - no match events are found.
            - page content cannot be loaded.
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
            
            # ------------------------
            # CREATE SELENIUM DRIVER
            # ------------------------
            driver = _create_driver()

            # ------------------------
            # LOAD MATCH PAGE
            # ------------------------
            driver.get(url)

            # ------------------------
            # SCROLL PAGE
            # ------------------------
            driver.execute_script( "window.scrollTo(0, document.body.scrollHeight);")

            time.sleep(5)

            # ------------------------
            # PARSE RENDERED HTML
            # ------------------------
            soup = BeautifulSoup( driver.page_source, "html.parser")

            # ------------------------
            # CLOSE DRIVER
            # ------------------------
            driver.quit()

            # ------------------------
            # INITIALIZE STORAGE
            # ------------------------
            events = []
            block = []

            # ------------------------
            # LOCATE EVENT CONTAINERS
            # ------------------------
            event_lists = soup.select("ul.Opta-Events")
            if not event_lists:
                raise ValueError("No event containers were found")

            # ------------------------
            # FILTER HOME/AWAY EVENTS
            # ------------------------
            for ul in event_lists:

                clases = ul.get("class", [])

                # Skip empty event containers
                if not ul.select(".Opta-MatchEvent"):
                    continue

                if "Opta-Home" in clases:

                    block.append(("home", ul))

                elif "Opta-Away" in clases:

                    block.append(("away", ul))

            # ------------------------
            # EXTRACT MATCH EVENTS
            # ------------------------
            for team, bloque in block:

                if not bloque:
                    continue

                for ev in bloque.select(".Opta-MatchEvent"):

                    # ------------------------
                    # EXTRACT EVENT TYPE
                    # ------------------------
                    icon = ev.select_one(".Opta-Icon")

                    event_type = icon.get("title") if icon  else None
                    

                    # ------------------------
                    # EXTRACT PLAYER DATA
                    # ------------------------
                    player_tag = ev.select_one( ".Opta-Event-Player")

                    if player_tag:

                        player = player_tag.text.strip()
                        player_url = player_tag.get("href")

                        # ------------------------
                        # EXTRACT PLAYER ID
                        # ------------------------
                        player_id = None

                        if player_url:

                            match = re.search( r"/player/view/([^/]+)", player_url)
                            if match:
                                player_id = match.group(1)

                    else:

                        player = None
                        player_url = None
                        player_id = None

                    # ------------------------
                    # EXTRACT MATCH MINUTE
                    # ------------------------
                    time_tag = ev.select_one(".Opta-Event-Time")
                    if time_tag:

                        raw_time = time_tag.get_text()

                        # Remove invisible characters
                        raw_time = raw_time .replace("\u200e", "") .replace("\u200f", "") 

                        # Extract values like:
                        # 45
                        # 90+2
                        match = re.search( r"\d+\+?\d*", raw_time)
                        minute =  match.group(0) if match else None
                    

                    else:

                        minute = None

                    # ------------------------
                    # STORE EVENT DATA
                    # ------------------------
                    events.append({
                        "team": team,
                        "event_type": event_type,
                        "player": player,
                        "player_id": player_id,
                        "player_url": player_url,
                        "minute": minute
                    })

            # ------------------------
            # VALIDATE OUTPUT
            # ------------------------
            if not events:
                raise ValueError("No match events were extracted")

            return pd.DataFrame(events)

        except Exception as e:
            raise RuntimeError( f"Failed to extract match summary from URL '{url}': {str(e)}")
        
    def extract_key_events(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract key post-match events from the PerformFeeds API.

        This function retrieves match event information including:
        - goals
        - cards
        - substitutions

        It also generates image URLs for teams and players,
        and returns three structured DataFrames containing
        the extracted event data.

        Parameters
        ----------
        url : str
            Scoresway post-match URL.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
            Tuple containing:

            1. Goals DataFrame
                - goal information
                - scorer details
                - assist details
                - team images
                - player images

            2. Cards DataFrame
                - card events
                - player details
                - team images
                - player images

            3. Substitutions DataFrame
                - substitution events
                - incoming player details
                - outgoing player details
                - team images
                - player images

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - API response structure is invalid.
            - key event data is unavailable.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")
        
        try:
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'
            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE LIVE DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError( "liveData was not found in API response")

            # ==================================================
            # GOALS DATA
            # ==================================================
            goals_data = json_data["liveData"].get("goal", [])
            df1 = pd.DataFrame(goals_data)

            # ------------------------
            # BUILD GOAL IMAGE URLS
            # ------------------------
            if not df1.empty:

                df1["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df1["contestantId"]
                df1['scorer_player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df1['contestantId']+ '&dimensions=103x155&id=' + df1['scorerId']
                df1['assist_player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df1['contestantId']+ '&dimensions=103x155&id=' + df1['assistPlayerId']

            # ==================================================
            # CARDS DATA
            # ==================================================
            cards_data = json_data["liveData"].get("card", [])
            df2 = pd.DataFrame(cards_data)

            # ------------------------
            # BUILD CARD IMAGE URLS
            # ------------------------
            if not df2.empty:

                df2["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df2["contestantId"]
                df2['player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df2['contestantId']+ '&dimensions=103x155&id=' + df2['playerId']

            # ==================================================
            # SUBSTITUTIONS DATA
            # ==================================================
            substitutions_data = json_data["liveData"].get( "substitute", [])
            df3 = pd.DataFrame(substitutions_data)

            # ------------------------
            # BUILD SUBSTITUTION IMAGE URLS
            # ------------------------
            if not df3.empty:

                df3["team_photo"] = 'https://omo.akamai.opta.net/image.php?h=www.scoresway.com&sport=football&entity=team&description=badges&dimensions=150&id=' + df3["contestantId"]
                df3['player_on_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df3['contestantId']+ '&dimensions=103x155&id=' + df3['playerOnId']
                df3['player_off_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df3['contestantId']+ '&dimensions=103x155&id=' + df3['playerOffId']

            # ------------------------
            # VALIDATE OUTPUT
            # ------------------------
            if  df1.empty and df2.empty and df3.empty:
                raise ValueError( "No key events were found for this match")

            return  df1, df2,  df3
            

        except Exception as e:
            raise RuntimeError(f"Failed to extract key events from URL '{url}': {str(e)}")
    
    def extract_referees(self, url: str) -> pd.DataFrame:
        """
        Extract referee information for a football post-match event.

        This function retrieves referee and match official information
        from the PerformFeeds API using a Scoresway post-match URL
        and returns a structured DataFrame containing officiating data.

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        pd.DataFrame
            DataFrame containing referee and match official information.

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - API response structure is invalid.
            - referee information is unavailable.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")

        try:
            
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'
            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE REFEREE DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            officials = json_data["liveData"]["matchDetailsExtra"]["matchOfficial"]
            if not officials:
                raise ValueError("No referee information was found")

            return pd.DataFrame(officials)

        except Exception as e:
            raise RuntimeError( f"Failed to extract referee information from URL '{url}': {str(e)}")
    
    def extract_home_formation(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract home team formation and player statistics
        for a football post-match event.

        This function retrieves lineup and formation data
        for the home team from the PerformFeeds API,
        expands player statistics, and returns:
        - a complete lineup DataFrame
        - a normalized statistics DataFrame

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            Tuple containing:
            - Complete home lineup DataFrame.
            - Expanded player statistics DataFrame.

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - lineup information is unavailable.
            - API response structure is invalid.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")
        
        try:
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE LINEUP DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            if "lineUp" not in json_data["liveData"]:
                raise ValueError("lineUp data was not found")

            lineup_home = json_data["liveData"]["lineUp"][0]

            # ------------------------
            # NORMALIZE PLAYER DATA
            # ------------------------
            df = pd.DataFrame(lineup_home["player"])
            if df.empty:
                raise ValueError("Home lineup data is empty")

            # ------------------------
            # ADD TEAM INFORMATION
            # ------------------------
            df["contestantId"] = lineup_home["contestantId"]
            df["formationUsed"] = lineup_home["formationUsed"]
            df["averageAge"] = lineup_home["averageAge"]

            # ------------------------
            # BUILD PLAYER IMAGE URLS
            # ------------------------
            df['player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df['contestantId']+ '&dimensions=103x155&id=' + df['playerId']

            # Identify team side
            df["side"] = "home"

            # ------------------------
            # SELECT BASE COLUMNS
            # ------------------------
            df_base= df[['playerId','matchName' , 'position'	,'positionSide'	,'formationPlace', 'captain', 'side', 'player_photo', 'stat' ]]

            # ------------------------
            # EXPAND PLAYER STATISTICS
            # ------------------------
            stats_expanded = df_base['stat'].apply( lambda stats: {   item['type']: item['value']  for item in stats} if isinstance(stats, list) else {})

            # Convert statistics into columns
            df_stats = pd.json_normalize(stats_expanded)

            return  df.drop(columns=['stat']), pd.concat([df_base.drop(columns=['stat']), df_stats],axis=1)

        except Exception as e:
            raise RuntimeError( f"Failed to extract home formation information from URL '{url}': {str(e)}")
    
    def extract_away_formation(self, url: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract away team formation and player statistics
        for a football post-match event.

        This function retrieves lineup and formation data
        for the away team from the PerformFeeds API,
        expands player statistics, and returns:
        - a complete lineup DataFrame
        - a normalized statistics DataFrame

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        tuple[pd.DataFrame, pd.DataFrame]
            Tuple containing:
            - Complete away lineup DataFrame.
            - Expanded player statistics DataFrame.

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - lineup information is unavailable.
            - API response structure is invalid.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")
        
        try:
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'
            

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE LINEUP DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            if "lineUp" not in json_data["liveData"]:
                raise ValueError("lineUp data was not found")

            lineup_away = json_data["liveData"]["lineUp"][1]

            # ------------------------
            # NORMALIZE PLAYER DATA
            # ------------------------
            df = pd.DataFrame(lineup_away["player"])
            if df.empty:
                raise ValueError("Away lineup data is empty")

            # ------------------------
            # ADD TEAM INFORMATION
            # ------------------------
            df["contestantId"] = lineup_away["contestantId"]
            df["formationUsed"] = lineup_away["formationUsed"]
            df["averageAge"] = lineup_away["averageAge"]

            # ------------------------
            # BUILD PLAYER IMAGE URLS
            # ------------------------
            df['player_photo']=  f'https://omo.akamai.opta.net/image.php?secure=true&h=omo.akamai.opta.net&sport=football&entity=player&description=' + df['contestantId']+ '&dimensions=103x155&id=' + df['playerId']

            # Identify team side
            df["side"] = "away"

            # ------------------------
            # SELECT BASE COLUMNS
            # ------------------------
            df_base= df[['playerId','matchName' , 'position'	,'positionSide'	,'formationPlace', 'captain', 'side', 'player_photo', 'stat' ]]

            # ------------------------
            # EXPAND PLAYER STATISTICS
            # ------------------------
            stats_expanded = df_base['stat'].apply( lambda stats: {   item['type']: item['value']  for item in stats} if isinstance(stats, list) else {})

            # Convert statistics into columns
            df_stats = pd.json_normalize(stats_expanded)

            return df.drop(columns=['stat']), pd.concat([df_base.drop(columns=['stat']), df_stats],axis=1)

        except Exception as e:
            raise RuntimeError(f"Failed to extract away formation information from URL '{url}': {str(e)}" )
        
    def extract_player_stats_match_ux(self, url: str) -> pd.DataFrame:
        """
        Extract detailed player statistics from the Scoresway
        player-stats page.

        This function uses Selenium to load the dynamic
        player statistics page, interacts with tabs and
        navigation elements, parses the rendered HTML using
        BeautifulSoup, and extracts player statistics for
        both home and away teams.

        Parameters
        ----------
        url : str
            Scoresway match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - player names
            - team side
            - individual player statistics

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - player-stats page cannot be generated.
            - no player statistics are found.
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
        
            # ------------------------
            # CREATE SELENIUM DRIVER
            # ------------------------
            driver = _create_driver()

            wait = WebDriverWait(driver, 10)

            # =========================
            # BUILD PLAYER-STATS URL
            # =========================
            parts = url.rstrip("/").split("/")

            if len(parts) < 2:
                raise ValueError("Invalid match URL structure")

            url = "/".join(parts[:-1]) + "/player-stats"

            # ------------------------
            # LOAD PAGE
            # ------------------------
            driver.get(url)

            # =========================
            # INITIAL PAGE SCROLL
            # =========================
            driver.execute_script( "window.scrollTo(0, document.body.scrollHeight);")

            time.sleep(3)

            # =========================
            # CLICK AWAY TAB
            # =========================
            away_button = wait.until( EC.element_to_be_clickable( ( By.XPATH,  "//div[contains(@class,'statspagenav')]//a[text()='Away']" )) )

            driver.execute_script( "arguments[0].scrollIntoView({block: 'center'});", away_button)

            time.sleep(1)

            driver.execute_script( "arguments[0].click();", away_button)

            time.sleep(3)

            # =========================
            # CLICK ALL STATISTIC TABS
            # =========================
            tabs = driver.find_elements( By.CSS_SELECTOR, ".Opta-Nav ul li a")
            for tab in tabs:

                try:

                    driver.execute_script("arguments[0].click();", tab)

                    time.sleep(1.5)

                except Exception:
                    continue

            # =========================
            # WAIT FOR TABLE CONTENT
            # =========================
            wait.until( EC.presence_of_element_located( (By.CSS_SELECTOR, "table") ))

            # =========================
            # PARSE RENDERED HTML
            # =========================
            soup = BeautifulSoup( driver.page_source, "html.parser")

            # ------------------------
            # EXTRACT TEAM DATA
            # ------------------------
            home_data = extract_team_data( soup, "home")
            away_data = extract_team_data( soup, "away" )

            # =========================
            # CLOSE DRIVER
            # =========================
            driver.quit()

            # ------------------------
            # VALIDATE OUTPUT
            # ------------------------
            all_data = home_data + away_data

            if not all_data:
                raise ValueError( "No player statistics were extracted")

            return pd.DataFrame(all_data)

        except Exception as e:
            raise RuntimeError( f"Failed to extract player statistics from URL '{url}': {str(e)}")
        
    def extract_team_kits(self, url: str) -> pd.DataFrame:
        """
        Extract team kit information for a football post-match event.

        This function retrieves kit information for both home
        and away teams from the PerformFeeds API using a
        Scoresway post-match URL.

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - team kit information
            - kit colors
            - side identifier (home/away)

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - kit information is unavailable.
            - API response structure is invalid.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")
        
        try:
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)

            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE KIT DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            if "lineUp" not in json_data["liveData"]:
                raise ValueError("lineUp data was not found")

            # ------------------------
            # EXTRACT HOME KIT
            # ------------------------
            home_team_kit = pd.json_normalize( json_data["liveData"]["lineUp"][0]["kit"])
            home_team_kit["side"] = "home"

            # ------------------------
            # EXTRACT AWAY KIT
            # ------------------------
            away_team_kit = pd.json_normalize(json_data["liveData"]["lineUp"][1]["kit"] )
            away_team_kit["side"] = "away"

            # ------------------------
            # MERGE KIT DATA
            # ------------------------
            return pd.concat( [home_team_kit, away_team_kit],axis=0)

        except Exception as e:
            raise RuntimeError(f"Failed to extract team kits information from URL '{url}': {str(e)}")
    
    def extract_match_stats(self, url: str) -> pd.DataFrame:
        """
        Extract team match statistics for a football post-match event.

        This function retrieves statistical match data for both
        home and away teams from the PerformFeeds API using
        a Scoresway post-match URL.

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - team statistics
            - statistical categories
            - values
            - side identifier (home/away)

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - statistics data is unavailable.
            - API response structure is invalid.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")
        
        try:  
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE STATISTICS DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            if "lineUp" not in json_data["liveData"]:
                raise ValueError("lineUp data was not found")

            # ------------------------
            # EXTRACT HOME STATS
            # ------------------------
            match_stats_home = pd.DataFrame( json_data["liveData"]["lineUp"][0]["stat"] )
            match_stats_home["side"] = "home"

            # ------------------------
            # EXTRACT AWAY STATS
            # ------------------------
            match_stats_away = pd.DataFrame( json_data["liveData"]["lineUp"][1]["stat"])
            match_stats_away["side"] = "away"

            # ------------------------
            # MERGE MATCH STATISTICS
            # ------------------------
            return pd.concat( [match_stats_home, match_stats_away],axis=0)

        except Exception as e:
            raise RuntimeError( f"Failed to extract match statistics from URL '{url}': {str(e)}")
        
    def extract_match_stats_ux(self, url: str) -> pd.DataFrame:
        """
        Extract visual match statistics from the Scoresway match-stats page.

        This function uses Selenium to load the dynamic match statistics
        page, parses the rendered HTML using BeautifulSoup, extracts
        statistical categories and values for both teams, and returns
        a structured DataFrame containing match statistics.

        Parameters
        ----------
        url : str
            Scoresway match URL.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - statistics category
            - statistic name
            - home team value
            - away team value
            - home percentage width
            - away percentage width

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match-stats page cannot be generated.
            - statistics container is not found.
            - no statistics data is available.
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
            # ------------------------
            # CREATE SELENIUM DRIVER
            # ------------------------
            driver = _create_driver()

            # =========================
            # BUILD MATCH-STATS URL
            # =========================
            parts = url.rstrip("/").split("/")
            if len(parts) < 2:
                raise ValueError("Invalid match URL structure")

            url = "/".join(parts[:-1]) + "/match-stats"

            # ------------------------
            # LOAD PAGE
            # ------------------------
            driver.get(url)

            # =========================
            # WAIT FOR DYNAMIC CONTENT
            # =========================
            wait = WebDriverWait(driver, 20)

            wait.until(EC.presence_of_element_located((By.ID, "Opta_1")))
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#Opta_1 table") ))

            # =========================
            # PARSE RENDERED HTML
            # =========================
            soup = BeautifulSoup(driver.page_source, "html.parser")

            # Close browser session
            driver.quit()

            # ------------------------
            # LOCATE MAIN CONTAINER
            # ------------------------
            container = soup.select_one("#Opta_1")
            if container is None:
                raise ValueError("Statistics container '#Opta_1' was not found")

            # ------------------------
            # EXTRACT STATISTIC TABS
            # ------------------------
            tabs = container.select( "ul.Opta-TabbedContent > li")
            if not tabs:
                raise ValueError("No statistic tabs were found")

            # =========================
            # EXTRACT MATCH STATISTICS
            # =========================
            data = []

            for tab in tabs:

                # ------------------------
                # EXTRACT CATEGORY
                # ------------------------
                category_tag = tab.select_one("h3 span")
                category = category_tag.get_text(strip=True) if category_tag else "Unknown"

                # ------------------------
                # EXTRACT ROWS
                # ------------------------
                rows = tab.select("table tbody tr")

                stat_name = None

                for row in rows:

                    th = row.select_one("th")
                    tds = row.find_all("td")

                    # ------------------------
                    # DETECT NEW STATISTIC
                    # ------------------------
                    if th:
                        stat_name = th.get_text(strip=True)
                        continue

                    # ------------------------
                    # EXTRACT VALUES
                    # ------------------------
                    if len(tds) >= 1 and stat_name:

                        home = tds[0].get_text(strip=True)   if len(tds) > 0   else None
                        away = tds[2].get_text(strip=True)   if len(tds) > 2   else None

                        # ------------------------
                        # EXTRACT BAR PERCENTAGES
                        # ------------------------
                        bar = row.select_one(".Opta-Bars-Full")

                        home_width = None
                        away_width = None

                        if bar:

                            home_span = bar.select_one( ".Opta-Percent.Opta-Home")
                            away_span = bar.select_one( ".Opta-Percent.Opta-Away")

                            home_width = extract_width(home_span)
                            away_width = extract_width(away_span)

                        # ------------------------
                        # STORE ROW DATA
                        # ------------------------
                        data.append({
                            "category": category,
                            "stat": stat_name,
                            "home": home,
                            "away": away,
                            "home_width": home_width,
                            "away_width": away_width
                        })

            # ------------------------
            # VALIDATE OUTPUT
            # ------------------------
            if not data:
                raise ValueError("No match statistics were extracted")

            return pd.DataFrame(data)

        except Exception as e:
            raise RuntimeError(
                f"Failed to extract UX match statistics from URL '{url}': {str(e)}")
        
    def extract_managers( self, url: str) -> pd.DataFrame:
        """
        Extract manager and team official information
        for a football post-match event.

        This function retrieves manager and coaching staff
        information for both home and away teams from the
        PerformFeeds API using a Scoresway post-match URL.

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        pd.DataFrame
            DataFrame containing:
            - manager information
            - coaching staff details
            - side identifier (home/away)

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If:
            - url is empty.
            - match identifier cannot be extracted.
            - manager information is unavailable.
            - API response structure is invalid.
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

        # ------------------------
        # EXTRACT MATCH IDENTIFIER
        # ------------------------
        match_id = url.split("/")[-2]
        if not match_id:
            raise ValueError("Could not extract match identifier from URL")
        
        try:
            # ------------------------
            # BUILD API URL
            # ------------------------
            api= f'https://api.performfeeds.com/soccerdata/matchstats/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&detailed=yes&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3fb0132f43b518abcb701afbe7e1ab3cf0cfac9ee'

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")

            # ------------------------
            # VALIDATE MANAGER DATA
            # ------------------------
            if "liveData" not in json_data:
                raise ValueError("liveData was not found in API response")

            if "lineUp" not in json_data["liveData"]:
                raise ValueError("lineUp data was not found")

            # ------------------------
            # EXTRACT HOME MANAGERS
            # ------------------------
            df_manager_home = pd.DataFrame(json_data["liveData"]["lineUp"][0]["teamOfficial"])
            df_manager_home["side"] = "home"

            # ------------------------
            # EXTRACT AWAY MANAGERS
            # ------------------------
            df_manager_away = pd.DataFrame(json_data["liveData"]["lineUp"][1]["teamOfficial"])
            df_manager_away["side"] = "away"

            # ------------------------
            # MERGE MANAGER DATA
            # ------------------------
            return pd.concat( [df_manager_home, df_manager_away],axis=0 )

        except Exception as e:
            raise RuntimeError(f"Failed to extract manager information from URL '{url}': {str(e)}")