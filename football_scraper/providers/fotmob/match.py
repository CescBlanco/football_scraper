import asyncio
import re
import os
import json
import time
import pandas as pd


from football_scraper.providers.fotmob.utils import flatten_stats, extract_stats

COOKIES_FILE = "fotmob_cookies.json"

class FotmobMatchService:
    def __init__(self, headless=True):
        self.headless = headless

    async def fetch_match_json(self, url):
        from patchright.async_api import async_playwright
        """
        Fetch match details JSON data using Playwright.

        This function navigates to a match URL, listens for network responses
        containing match details data, and captures the corresponding JSON payload.
        It also manages cookies to maintain session persistence.

        Args:
            url (str): Match URL containing the match ID.

        Returns:
            dict: JSON data containing match details.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match ID cannot be extracted from the URL.
            RuntimeError: If browser launch or navigation fails.
            Exception: If match data is not captured within the expected time.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")
        

        match_id_match = re.search(r"#(\d+)", url).group(1)

        if not match_id_match:
            raise ValueError("Could not extract match ID from URL")
    
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch( headless=False, channel="chrome")

            except Exception as e:
                raise RuntimeError(f"Failed to launch browser: {e}")
            
            context = await browser.new_context()

            # 🔹 Load cookies if available and valid
            if os.path.exists(COOKIES_FILE):

                mod_time = os.path.getmtime(COOKIES_FILE)

                if (time.time() - mod_time) / 3600 > 1:
                    os.remove(COOKIES_FILE)
                    print("🗑️ Cookies expired")

                else:
                    with open(COOKIES_FILE) as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    print("🍪 Cookies loaded")

            page = await context.new_page()

            # 🔹 Store captured responses
            captured = []

            async def handle_response(response):
                """
                Capture matchDetails responses from network traffic.
                """
                if "matchDetails" in response.url and f"matchId={match_id_match}" in response.url:
                    print(f"🔥 DETECTED: {response.url}")
                    try:
                        data = await response.json()
                        captured.append(data)
                    except Exception as e:
                        print(f"⚠️ Error reading JSON: {e}")

            page.on("response", handle_response)

            try:
                print("\n🌐 Surfing the internet...")
                 # 🔹 Navigate to match page
                await page.goto(url, wait_until="domcontentloaded")

                # 🔹 Wait up to 60 seconds for matchDetails response
                print("⏳ Waiting for matchDetails (resolves the Turnstile if it appears)...")
                for _ in range(600):  # 60 segundos
                    if captured:
                        break
                    await asyncio.sleep(0.1)

                if not captured:
                    raise Exception("Match data was not captured within 60 seconds")

                # 🔹 Save cookies
                cookies = await context.cookies()
                with open(COOKIES_FILE, "w") as f:
                    json.dump(cookies, f, indent=2)
                print("🍪 Save Cookies")

                print("✅ DATA READY")
                return captured[0]

            finally:
                # 🔹 Ensure browser is closed
                await browser.close()

    def extract_match_details(self, url):
        """
        Extract structured match details from match JSON data.

        This function retrieves match data and transforms it into a structured
        pandas DataFrame, including general match info, teams, status, match facts,
        and weather conditions.

        Args:
            url (str): Match URL used to fetch data.

        Returns:
            pd.DataFrame: DataFrame containing detailed match information.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If required fields are missing in the response.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Normalize general match details
            general_details = pd.json_normalize(json_data['general'])

            # 🔹 Convert datetime fields
            general_details['datetime'] = pd.to_datetime( general_details['matchTimeUTCDate'], utc=True)
            general_details['datetime_local'] = general_details['datetime'].dt.tz_convert('Europe/Madrid')
            general_details['match_date'] = general_details['datetime_local'].dt.date
            general_details['match_time'] = general_details['datetime_local'].dt.strftime('%H:%M:%S')
            general_details['match_day'] = general_details['datetime_local'].dt.day_name()

            # 🔹 Drop unnecessary columns
            general_details = general_details.drop(columns=['matchName', 'datetime', 'datetime_local', 'leagueRoundName','coverageLevel', 'parentLeagueId', 'matchTimeUTC',
                                                             'matchTimeUTCDate'])

            # 🔹 Extract teams data
            df_teams = pd.DataFrame(json_data['header']['teams'])
            df_teams["pageUrl"] = "https://www.fotmob.com" + df_teams["pageUrl"].astype(str)

            # 🔹 Merge home team
            df = general_details.merge(df_teams, left_on="homeTeam.id", right_on="id", how="left" )
            df = df.rename(columns={ "score": "home_team_score","imageUrl": "home_team_image", "pageUrl": "home_team_page"}).drop(columns=["id", "name"])

            # 🔹 Merge away team
            df = df.merge(df_teams, left_on="awayTeam.id", right_on="id", how="left" )
            df = df.rename(columns={"score": "away_team_score","imageUrl": "away_team_image","pageUrl": "away_team_page" }).drop(columns=["id", "name"])

            # 🔹 Drop redundant flags
            df = df.drop(columns=['started', 'finished'])

            # 🔹 Match status
            df_status = pd.json_normalize(json_data['header']['status'])
            df_status = df_status.drop(columns=["utcTime", "numberOfHomeRedCards", "numberOfAwayRedCards", 'scoreStr', 'whoLostOnAggregated', 
                                                'reason.shortKey', 'reason.longKey'])

            # 🔹 Match facts info box
            box_info = pd.json_normalize(json_data['content']['matchFacts']['infoBox'])
            box_info = box_info.drop(columns=['legInfo', 'Match Date.utcTime', 'Match Date.isDateCorrect', 'Tournament.id', 'Tournament.parentLeagueId',
                                             'Tournament.link', 'Tournament.leagueName', 'Tournament.roundName', 'Tournament.round'])

            # 🔹 Weather data
            weather_match = pd.json_normalize(json_data['content']['weather'])

            # 🔹 Combine all components
            return pd.concat((df, df_status, box_info, weather_match), axis=1)

        except KeyError as e:
            raise KeyError(f"Missing match details field: {e}")
    
    def extract_head_to_head(self, url):
        """
        Extract head-to-head statistics and historical matches.

        This function retrieves head-to-head summary statistics and past match data
        between two teams, formatting dates and URLs into a structured format.

        Args:
            url (str): Match URL used to fetch data.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - First DataFrame: Summary (home wins, draws, away wins).
                - Second DataFrame: Historical match details.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If head-to-head data is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Extract summary
            head_to_head_data = json_data['content']['h2h']['summary']
            head_to_head_summary = pd.DataFrame([{ 'match_home_wins': head_to_head_data[0], 'match_draws': head_to_head_data[1],'match_away_wins': head_to_head_data[2] }])

            # 🔹 Normalize match list
            df = pd.json_normalize(json_data['content']['h2h']['matches'])

            # 🔹 Build URLs
            df["matchUrl"] = "https://www.fotmob.com" + df["matchUrl"].astype(str)

            # 🔹 Convert datetime
            df['datetime'] = pd.to_datetime(df['time.utcTime'], utc=True)
            df['datetime_local'] = df['datetime'].dt.tz_convert('Europe/Madrid')
            df['match_date'] = df['datetime_local'].dt.date
            df['match_time'] = df['datetime_local'].dt.strftime('%H:%M:%S')

            # 🔹 Drop unnecessary columns
            df = df.drop(columns=[ 'finished', 'time.utcTime', 'datetime_local','league.pageUrl', 'status.utcTime', 'status.reason.shortKey', 'status.reason.longKey'])

            return head_to_head_summary, df

        except KeyError as e:
            raise KeyError(f"Missing head-to-head data: {e}")
        
    def extract_info_lineups(self, url):
        """
        Extract lineup information for both teams.

        This function retrieves lineup data including starters, substitutes,
        and unavailable players for both home and away teams.

        Args:
            url (str): Match URL.

        Returns:
            tuple:
                - Home team info
                - Away team info
                - Home lineup DataFrame
                - Away lineup DataFrame
                - Home unavailable players
                - Away unavailable players

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If lineup data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Normalize team data
            row_home = pd.json_normalize(json_data['content']['lineup']['homeTeam'])
            row_away = pd.json_normalize(json_data['content']['lineup']['awayTeam'])

            data_home = row_home.drop(columns=['starters', 'subs', 'unavailable', 'coach.isCoach', 'coach.usualPlayingPositionId', 'coach.primaryTeamName' ], errors='ignore')
            data_away = row_away.drop(columns=[ 'starters', 'subs', 'unavailable', 'coach.isCoach', 'coach.usualPlayingPositionId', 'coach.primaryTeamName' ], errors='ignore')

            # 🔹 Home lineup
            starters_home = pd.json_normalize(row_home['starters'][0])
            starters_home['isStarter'] = True

            subs_home = pd.json_normalize(row_home['subs'][0])
            subs_home['isStarter'] = False

            df_home = pd.concat([starters_home, subs_home]).reset_index(drop=True)
            df_home = df_home.drop(columns=['performance.seasonRating', 'shortName', 'rankings'], errors='ignore')

            # 🔹 Away lineup
            starters_away = pd.json_normalize(row_away['starters'][0])
            starters_away['isStarter'] = True

            subs_away = pd.json_normalize(row_away['subs'][0])
            subs_away['isStarter'] = False

            df_away = pd.concat([starters_away, subs_away]).reset_index(drop=True)
            df_away = df_away.drop(columns=['performance.seasonRating', 'shortName', 'rankings'], errors='ignore')

            # 🔹 Unavailable players
            unavailable_home = pd.json_normalize(row_home['unavailable'][0])
            unavailable_away = pd.json_normalize(row_away['unavailable'][0])

            return data_home, data_away, df_home, df_away, unavailable_home, unavailable_away

        except KeyError as e:
            raise KeyError(f"Missing lineup data: {e}")
        
    def extract_events(self, url):
        """
        Extract match events.

        This function retrieves all match events such as goals, substitutions,
        and cards, and normalizes nested structures.

        Args:
            url (str): Match URL.

        Returns:
            pd.DataFrame: DataFrame containing match events.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If events data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            match_events = pd.json_normalize(json_data['content']['matchFacts']['events']['events'])

            # 🔹 Drop unnecessary columns
            match_events = match_events.drop(columns=['reactKey', 'overloadTimeStr', 'time', 'nameStr', 'firstName', 'lastName', 'player.id', 'player.name',
                                                      'player.profileUrl', 'goalDescriptionKey', 'suffix', 'suffixKey'])

            # 🔹 Expand substitutions
            swap_expanded = ( match_events['swap'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else {}).apply(pd.Series).add_prefix('substitution_') )
            match_events = pd.concat([match_events.drop(columns=['swap']), swap_expanded],  axis=1)

            # 🔹 Build URLs
            match_events["profileUrl"] = "https://www.fotmob.com" + match_events["profileUrl"].astype(str)
            match_events["assistProfileUrl"] = "https://www.fotmob.com" + match_events["assistProfileUrl"].astype(str)
            match_events["substitution_profileUrl"] = "https://www.fotmob.com" + match_events["substitution_profileUrl"].astype(str)

            return match_events

        except KeyError as e:
            raise KeyError(f"Missing events data: {e}")
    
    def extract_player_of_the_match(self, url):
        """
        Extract Player of the Match data.

        Args:
            url (str): Match URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - Full data including shotmap.
                - Cleaned data without shotmap.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If player of the match data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            df_raw = pd.json_normalize( json_data['content']['matchFacts']['playerOfTheMatch'])

            # 🔹 Expand stats
            stats_expanded = df_raw['stats'].apply(flatten_stats).apply(pd.Series)
            df = pd.concat([df_raw.drop(columns=['stats']), stats_expanded], axis=1)

            # 🔹 Clean columns
            df = df.drop(columns=['name.firstName', 'name.lastName','teamData.home.id', 'rating.num', 'minutesPlayed'])

            # 🔹 Add URLs
            df["pageUrl"] = "https://www.fotmob.com" + df["pageUrl"].astype(str)
            df["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + df["id"].astype(str) + ".png"
            df_clean = df.drop(columns=['shotmap'])

            return df, df_clean

        except KeyError as e:
            raise KeyError(f"Missing player of the match data: {e}")
    
    def extract_shotmap_player_of_the_match(self, url, player_id):
        """
        Extract shotmap for the Player of the Match.

        Args:
            url (str): Match URL.
            player_id (int | str): Player ID.

        Returns:
            pd.DataFrame | str: Shotmap data or message if no data is found.

        Raises:
            TypeError: If inputs are invalid.
            ValueError: If match data cannot be retrieved.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not isinstance(player_id, (int, str)):
            raise TypeError("player_id must be int or string")

        df, _ = self.extract_player_of_the_match(url)

        filtered = df[df['id'] == int(player_id)]

        if filtered.empty:
            return f"No data found for player_id={player_id}. Check if this player is the Player of the Match."

        shots = filtered['shotmap'].iloc[0]

        if shots and len(shots) > 0:
            return pd.json_normalize(shots)
        else:
            return "The player did not take any shots in this match."
        
    def extract_home_away_form(self, url):
        """
        Extract recent form for home and away teams.

        Args:
            url (str): Match URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                Home team form and away team form.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If form data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Home form
            home = pd.json_normalize(json_data['content']['matchFacts']['teamForm'][0])
            home["linkToMatch"] = "https://www.fotmob.com" + home["linkToMatch"].astype(str)

            home['datetime'] = pd.to_datetime(home['date.utcTime'], utc=True)
            home['datetime_local'] = home['datetime'].dt.tz_convert('Europe/Madrid')

            home['match_date'] = home['datetime_local'].dt.date
            home['match_time'] = home['datetime_local'].dt.strftime('%H:%M:%S')

            home = home.drop(columns=[ 'result', 'score', 'teamPageUrl', 'tooltipText.utcTime','datetime', 'datetime_local', 'tooltipText.homeTeam','tooltipText.homeTeamId',
                                        'tooltipText.awayTeam','tooltipText.awayTeamId', 'home.isOurTeam','away.isOurTeam', 'date.utcTime' ], errors='ignore')

            # 🔹 Away form
            away = pd.json_normalize(json_data['content']['matchFacts']['teamForm'][1])
            away["linkToMatch"] = "https://www.fotmob.com" + away["linkToMatch"].astype(str)

            away['datetime'] = pd.to_datetime(away['date.utcTime'], utc=True)
            away['datetime_local'] = away['datetime'].dt.tz_convert('Europe/Madrid')

            away['match_date'] = away['datetime_local'].dt.date
            away['match_time'] = away['datetime_local'].dt.strftime('%H:%M:%S')

            away = away.drop(columns=['result', 'score', 'teamPageUrl', 'tooltipText.utcTime','datetime', 'datetime_local', 'tooltipText.homeTeam','tooltipText.homeTeamId',
                                       'tooltipText.awayTeam','tooltipText.awayTeamId', 'home.isOurTeam', 'away.isOurTeam', 'date.utcTime' ], errors='ignore')

            return home, away

        except KeyError as e:
            raise KeyError(f"Missing team form data: {e}")
    
    def extract_top_players_home_away(self, url):
        """
        Extract top players for home and away teams.

        This function retrieves the best-performing players for both teams
        and enriches the data with player image URLs.

        Args:
            url (str): Match URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - Home top players.
                - Away top players.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If top players data is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Home top players
            home = pd.json_normalize(json_data['content']['matchFacts']['topPlayers']['homeTopPlayers'])
            home = home.drop(columns=[ 'playerRatingRounded', 'name.firstName', 'name.lastName'], errors='ignore')

            home["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/"  + home["playerId"].astype(str) + ".png"

            # 🔹 Away top players
            away = pd.json_normalize(json_data['content']['matchFacts']['topPlayers']['awayTopPlayers'] )
            away = away.drop(columns=[ 'playerRatingRounded', 'name.firstName', 'name.lastName', 'positionLabel'], errors='ignore')

            away["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + away["playerId"].astype(str) + ".png"

            return home, away

        except KeyError as e:
            raise KeyError(f"Missing top players data: {e}")
    
    def extract_top_scores_home_away(self, url):
        """
        Extract top scorers for home and away teams.

        Args:
            url (str): Match URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - Home top scorers.
                - Away top scorers.
                Returns empty DataFrames if data is not available.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Home scorers
            home = pd.json_normalize(json_data['content']['matchFacts']['topScorers']['homePlayer'])

            home = home.drop(columns=['lastName'])
            home["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/"+ home["playerId"].astype(str) + ".png"

            # 🔹 Away scorers
            away = pd.json_normalize(json_data['content']['matchFacts']['topScorers']['awayPlayer'])

            away = away.drop(columns=['lastName'])
            away["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/" + away["playerId"].astype(str) + ".png"

        except KeyError:
            # 🔹 Graceful fallback if data is missing
            home = pd.DataFrame()
            away = pd.DataFrame()

        return home, away

    def extract_match_momentum(self, url):
        """
        Extract match momentum data.

        Args:
            url (str): Match URL.

        Returns:
            pd.DataFrame: DataFrame containing momentum values over time.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If momentum data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            return pd.DataFrame( json_data['content']['momentum']['main']['data'])

        except KeyError as e:
            raise KeyError(f"Missing momentum data: {e}")
    
    def extract_player_stats(self, url):
        """
        Extract player statistics for a match.

        Args:
            url (str): Match URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - Clean DataFrame without shotmap.
                - Full DataFrame including shotmap.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If player stats are missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            # 🔹 Normalize player stats
            df = pd.DataFrame.from_dict( json_data['content']['playerStats'], orient='index')
            df = df.reset_index().rename(columns={'index': 'player_id'})

            # 🔹 Expand stats
            stats_expanded = df['stats'].apply(flatten_stats).apply(pd.Series)

            df = pd.concat([df.drop(columns=['stats']), stats_expanded], axis=1)

            df_stats = df.drop(columns=['isPotm'])
            df_clean = df.drop(columns=['isPotm', 'shotmap'])

            return df_clean, df_stats

        except KeyError as e:
            raise KeyError(f"Missing player stats data: {e}")
    
    def extract_shot_map_player(self, url, player_id):
        """
        Extract shotmap for a specific player.

        Args:
            url (str): Match URL.
            player_id (int | str): Player ID.

        Returns:
            pd.DataFrame | str: Shotmap data or message if not available.

        Raises:
            TypeError: If inputs are invalid.
            ValueError: If match data cannot be retrieved.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not isinstance(player_id, (int, str)):
            raise TypeError("player_id must be int or string")

        df_clean, df_stats = self.extract_player_stats(url)

        df_stats['player_id'] = df_stats['player_id'].astype(int)
        player_id = int(player_id)

        filtered = df_stats[df_stats['player_id'] == player_id]

        if filtered.empty:
            return f"No data found for player_id={player_id}"

        shots = filtered['shotmap'].iloc[0]

        if shots and len(shots) > 0:
            return pd.json_normalize(shots)
        else:
            return "The player did not take any shots in this match."
        
    def extract_shots_map_all(self, url):
        """
        Extract all shots from a match.

        Args:
            url (str): Match URL.

        Returns:
            pd.DataFrame: DataFrame containing all shots.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If shotmap data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            shots = pd.DataFrame( json_data['content']['shotmap']['Periods']['All'])

            # 🔹 Expand nested shot data
            shots[['x_onGoalShot', 'y_onGoalShot', 'zoomRatio_onGoalShot']] = shots['onGoalShot'].apply(lambda d: pd.Series(d))

            return shots.drop(columns=['onGoalShot'])

        except KeyError as e:
            raise KeyError(f"Missing shotmap data: {e}")
    
    def extract_match_stats(self, url):
        """
        Extract match statistics by period.

        This function processes match statistics for all periods
        (full match, first half, second half) and returns a unified DataFrame.

        Args:
            url (str): Match URL.

        Returns:
            pd.DataFrame: DataFrame containing structured match statistics.

        Raises:
            TypeError: If url is not a string.
            ValueError: If match data cannot be retrieved.
            KeyError: If stats data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data = asyncio.run(self.fetch_match_json(url))

        if json_data is None:
            raise ValueError("Failed to retrieve match data")

        try:
            periods = {
                "All": json_data['content']['stats']['Periods']['All']['stats'],
                "FirstHalf": json_data['content']['stats']['Periods']['FirstHalf']['stats'],
                "SecondHalf": json_data['content']['stats']['Periods']['SecondHalf']['stats']
            }

            dfs = []

            for period_name, stats_data in periods.items():

                # 🔹 Normalize stats
                df = pd.DataFrame(stats_data)

                df1 = df.explode('stats', ignore_index=True)
                lvl1 = pd.json_normalize(df1['stats']).add_prefix('lvl1_')

                df2 = df1.drop(columns=['stats']).join(lvl1)

                # 🔹 Filter valid stats
                df2 = df2[df2['lvl1_stats'].apply(lambda x: isinstance(x, list) and len(x) > 0 and x != [None, None] )]

                # 🔹 Extract home/away values
                df2[['stat_home', 'stat_away']] = df2['lvl1_stats'].apply(lambda x: pd.Series(extract_stats(x)))
                df2['period'] = period_name
                
                df_final = df2[['title', 'lvl1_title', 'stat_home', 'stat_away', 'lvl1_highlighted', 'period']]

                df_final = df_final.rename(columns={'title': 'type_stat', 'lvl1_title': 'stat', 'lvl1_highlighted': 'highlighted' })

                dfs.append(df_final)

            return pd.concat(dfs, ignore_index=True)

        except KeyError as e:
            raise KeyError(f"Missing match stats data: {e}")