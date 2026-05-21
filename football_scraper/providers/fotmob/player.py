import asyncio
import re
import os
import json
import time
import random
import pandas as pd


COOKIES_FILE = "fotmob_player_cookies.json"

class FotmobPlayerService:
    def __init__(self, headless=False):
        self.headless = headless

    async def _simulate_human_mouse(self, page):
        """
        Simulate human-like mouse movements on a Playwright page.

        This helper function performs random mouse movements across the page
        to mimic human interaction behavior, which can help bypass bot detection
        mechanisms on some websites.

        Args:
            page (playwright.async_api.Page): Playwright page instance where
                the mouse movements will be simulated.

        Returns:
            None

        Raises:
            TypeError: If the provided page is not a valid Playwright Page object.
            RuntimeError: If mouse interaction fails during execution.
        """

        if page is None:
            raise TypeError("page must be a valid Playwright Page instance")


        for _ in range(10):
            try:
                x = random.randint(0, 1280)
                y = random.randint(0, 720)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            except Exception as e:
                raise RuntimeError(f"Mouse simulation failed: {e}")

    async def fetch_player_details(self, url):
        from patchright.async_api import async_playwright
        """
        Fetch detailed player data from a given URL using Playwright.

        This function launches a Chromium browser instance, navigates to the
        provided player URL, listens for network responses containing player data,
        and extracts the relevant JSON payload. It also manages cookies to
        maintain session persistence and reduce bot detection.

        Args:
            url (str): URL of the player's page.

        Returns:
            dict | None: A dictionary containing player data if successfully captured,
            otherwise None if the process fails or no data is retrieved.

        Raises:
            TypeError: If the URL is not a string.
            ValueError: If the player ID cannot be extracted from the URL.
            RuntimeError: If the browser fails to launch or navigation fails.
            Exception: If no player data is captured within the expected time.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")
        
        player_id = re.search(r"/(\d+)/", url)
        player_id = player_id.group(1) if player_id else None

        if not player_id:
            raise ValueError("Could not extract player ID from URL")
    
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=False,channel="chrome")
            except Exception as e:
                raise RuntimeError(f"Failed to launch browser: {e}")
            
            context = await browser.new_context()

            # Load cookies if available and not expired
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
            captured = []

            async def handle_response(response):
                """
                Handle network responses and capture player data JSON.

                Args:
                    response (playwright.async_api.Response): Network response object.

                Returns:
                    None
                """
                
                is_player_data = "playerData" in response.url
                matches_id = player_id and f"id={player_id}" in response.url 
                is_ok = response.status == 200                           

                if is_player_data and matches_id and is_ok:
                    print(f"🔥 DETECTED: {response.url}")
                    try:
                        data = await response.json()
                        captured.append(data)
                    except Exception as e:
                        print(f"⚠️ Error reading JSON: {e}")

            page.on("response", handle_response)

            try:
                print("\n🌐 Surfing the internet...")
                await page.goto(url, wait_until="domcontentloaded")
                await self._simulate_human_mouse(page)

                print("⏳ Waiting for playerData (resolves the Turnstile if it appears)...")
                # Wait up to ~60 seconds for player data
                for _ in range(600):
                    if captured:
                        break
                    await asyncio.sleep(0.1)

                if not captured:
                    raise Exception("Player data was not captured within 60 seconds")

                # Save cookies
                cookies = await context.cookies()
                with open(COOKIES_FILE, "w") as f:
                    json.dump(cookies, f, indent=2)
                print("🍪 Save Cookies")

                print("✅ DATA READY")
                return captured[0]

            except Exception as e:
                print(f"❌ Error: {e}")
                return None

            finally:
                await browser.close()

    def extract_player_info(self, url):
        """
        Extract detailed player information and metadata.

        This function retrieves player data from the API and converts it into
        a structured pandas DataFrame. It includes personal details, contract info,
        injury status, team metadata, and generated image URLs.

        Args:
            url (str): Player URL used to fetch data.

        Returns:
            pd.DataFrame: A single-row DataFrame containing player information.

        Raises:
            TypeError: If url is not a string.
            ValueError: If player data cannot be retrieved.
            KeyError: If expected fields are missing in the response.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize player information
            df_row = pd.json_normalize(json_data_player['playerInformation'])

            # 🔹 Transform key-value structure into dictionary
            new_data = {}
            for _, row in df_row.iterrows():
                title = row['title']

                if title == "Contract end":
                    new_data[title] = row['value.fallback.utcTime'].split('T')[0]
                else:
                    new_data[title] = row['value.fallback']

            df = pd.DataFrame(new_data, index=[0])

            # 🔹 Add additional player metadata
            df['Weight'] = json_data_player['meta']['personJSONLD']['weight']['value'] + ' kg'
            df['Birthday'] = json_data_player['birthDate']['utcTime'].split('T')[0]
            df['player'] = json_data_player['name']
            df['gender'] = json_data_player['gender']
            df['id'] = json_data_player['id']
            df['player_url'] = json_data_player['meta']['personJSONLD']['url']

            # 🔹 Injury information (safe access)
            injury_info = json_data_player.get('injuryInformation', None)
            if injury_info:
                df['injury_name'] = injury_info.get('name')
                df['injury_expectedReturnDate'] = injury_info.get('expectedReturn', {}).get('expectedReturnDateParam')
                df['injury_expectedReturnFallback'] = injury_info.get('expectedReturn', {}).get('expectedReturnFallback')
                df['lastUpdated_injury'] = injury_info.get('lastUpdated', {}).get('utcTime')

                if df['lastUpdated_injury'].notnull().any():
                    df['lastUpdated_injury'] = df['lastUpdated_injury'].str.split('T').str[0]
            else:
                df[['injury_name',
                    'injury_expectedReturnDate',
                    'injury_expectedReturnFallback',
                    'lastUpdated_injury']] = None

            # 🔹 Add images and team info
            df["player_photo"] = (
                "https://images.fotmob.com/image_resources/playerimages/"
                + df["id"].astype(str) + ".png"
            )

            df['isCaptain'] = json_data_player['isCaptain']
            df['isCoach'] = json_data_player['isCoach']
            df['teamName'] = json_data_player['primaryTeam']['teamName']
            df['teamId'] = json_data_player['primaryTeam']['teamId']

            df["logo_url_team"] = (
                "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"
                + df["teamId"].astype(str) + ".png"
            )

            df['onLoan'] = json_data_player['primaryTeam']['onLoan']
            df['teamColors_home'] = json_data_player['primaryTeam']['teamColors']['color']
            df['teamColors_home_alternative'] = json_data_player['primaryTeam']['teamColors']['colorAlternate']
            df['teamColors_away'] = json_data_player['primaryTeam']['teamColors']['colorAway']
            df['teamColors_away_alternative'] = json_data_player['primaryTeam']['teamColors']['colorAwayAlternate']
            df['status'] = json_data_player['status']

            return df

        except KeyError as e:
            raise KeyError(f"Missing expected field in player data: {e}")
    
    def extract_career_stats_senior(self, url):
        """
        Extract senior career statistics for a player.

        Args:
            url (str): Player URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                Season/tournament stats and team history.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If required fields are missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize season entries
            df = pd.json_normalize(json_data_player['careerHistory']['careerItems']['senior']['seasonEntries']).drop(columns=['seasonName'])

            # 🔹 Explode tournament stats
            df_exploded = df.explode('tournamentStats').reset_index(drop=True)

            # 🔹 Ensure valid dicts
            df_exploded['tournamentStats'] = df_exploded['tournamentStats'].apply( lambda x: x if isinstance(x, dict) else {})

            # 🔹 Normalize tournament stats
            tournament_df = pd.json_normalize(df_exploded['tournamentStats']).add_prefix('tournament_')
            df1 = pd.concat([df_exploded.drop(columns=['tournamentStats']), tournament_df],axis=1).reset_index(drop=True)

            # 🔹 Rename and clean columns
            df1 = df1.rename(columns={ 'appearances': 'total_appearances','goals': 'total_goals','assists': 'total_assists','rating.rating': 'rating_promed',
                        'tournament_rating.rating': 'tournament_rating'}).drop(columns=['showTeamGender', 'transferType', 'tournament_isFriendly', 'teamGender'])
            # 🔹 Team history
            df2 = pd.json_normalize(json_data_player['careerHistory']['careerItems']['senior']['teamEntries'] )
            df2['startDate'] = pd.to_datetime(df2['startDate'])
            df2['endDate'] = pd.to_datetime(df2['endDate'])
            df2 = df2.drop(columns=['teamGender', 'showTeamGender', 'transferType', 'hasUncertainData'])

            return df1, df2

        except KeyError as e:
            raise KeyError(f"Missing expected senior career field: {e}")
    
    def extract_career_stats_youth(self, url):
        """
        Extract youth career statistics for a player.

        This function retrieves youth-level career data from the API, including
        season-level statistics and team history, and transforms it into structured
        pandas DataFrames.

        Args:
            url (str): Player URL used to fetch data.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - First DataFrame: Season and tournament statistics.
                - Second DataFrame: Team history with start and end dates.

        Raises:
            TypeError: If url is not a string.
            ValueError: If player data cannot be retrieved.
            KeyError: If 'careerHistory.careerItems.youth' is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize youth season entries
            df_career_youth = pd.json_normalize( json_data_player['careerHistory']['careerItems']['youth']['seasonEntries'])

            # 🔹 Remove unnecessary columns
            df_career_youth = df_career_youth.drop(columns=['seasonName'])

            # 🔹 Explode tournament stats into separate rows
            df_exploded = df_career_youth.explode('tournamentStats').reset_index(drop=True)

            # 🔹 Ensure all entries are dictionaries
            df_exploded['tournamentStats'] = df_exploded['tournamentStats'].apply( lambda x: x if isinstance(x, dict) else {})

            # 🔹 Normalize tournament stats
            tournament_df = pd.json_normalize(df_exploded['tournamentStats']).add_prefix('tournament_')

            # 🔹 Merge base stats with tournament stats
            df1 = pd.concat([df_exploded.drop(columns=['tournamentStats']), tournament_df],axis=1).reset_index(drop=True)

            # 🔹 Rename columns for clarity
            df1 = df1.rename(columns={ 'appearances': 'total_appearances','goals': 'total_goals','assists': 'total_assists', 'rating.rating': 'rating_promed',
                                     'tournament_rating.rating': 'tournament_rating'})

            # 🔹 Drop irrelevant columns
            df1 = df1.drop(columns=['showTeamGender', 'transferType', 'tournament_isFriendly', 'teamGender'])

            # 🔹 Extract team history
            df2 = pd.json_normalize(json_data_player['careerHistory']['careerItems']['youth']['teamEntries'] )

            # 🔹 Convert date columns
            df2['startDate'] = pd.to_datetime(df2['startDate'])
            df2['endDate'] = pd.to_datetime(df2['endDate'])

            # 🔹 Drop irrelevant columns
            df2 = df2.drop(columns=['teamGender', 'showTeamGender', 'transferType', 'hasUncertainData'])

            return df1, df2

        except KeyError as e:
            raise KeyError(f"Missing expected youth career field: {e}")
    
    def extract_career_stats_national_team(self, url):
        """
            Extract national team career statistics for a player.

            This function retrieves national team data including seasonal performance
            and team participation history.

            Args:
                url (str): Player URL used to fetch data.

            Returns:
                tuple[pd.DataFrame, pd.DataFrame]:
                    - First DataFrame: Season and tournament statistics.
                    - Second DataFrame: Team history.

            Raises:
                TypeError: If url is not a string.
                ValueError: If player data cannot be retrieved.
                KeyError: If 'careerHistory.careerItems.national team' is missing.
            """

            # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")
        
        json_data_player= asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize national team season entries
            df_career_nat = pd.json_normalize(json_data_player['careerHistory']['careerItems']['national team']['seasonEntries'])
            df_career_nat = df_career_nat.drop(columns=['seasonName'])

            # 🔹 Explode tournament stats
            df_exploded = df_career_nat.explode('tournamentStats').reset_index(drop=True)

            # 🔹 Ensure valid dict format
            df_exploded['tournamentStats'] = df_exploded['tournamentStats'].apply(
                lambda x: x if isinstance(x, dict) else {}
            )

            # 🔹 Normalize tournament stats
            tournament_df = pd.json_normalize(df_exploded['tournamentStats']).add_prefix('tournament_')

            df1 = pd.concat([df_exploded.drop(columns=['tournamentStats']), tournament_df],axis=1).reset_index(drop=True)

            # 🔹 Rename columns
            df1 = df1.rename(columns={ 'appearances': 'total_appearances', 'goals': 'total_goals', 'assists': 'total_assists',
                                        'rating.rating': 'rating_promed','tournament_rating.rating': 'tournament_rating'})

            # 🔹 Drop unnecessary columns
            df1 = df1.drop(columns=['showTeamGender', 'transferType', 'tournament_isFriendly', 'teamGender'])

            # 🔹 Extract team history
            df2 = pd.json_normalize( json_data_player['careerHistory']['careerItems']['national team']['teamEntries'])

            df2['startDate'] = pd.to_datetime(df2['startDate'])
            df2['endDate'] = pd.to_datetime(df2['endDate'])

            df2 = df2.drop(columns=['teamGender', 'showTeamGender', 'transferType', 'hasUncertainData'])

            return df1, df2

        except KeyError as e:
            raise KeyError(f"Missing expected national team career field: {e}")
    
    def extract_club_national_teammates(self, url):
        """
        Extract club and national team teammates for a player.

        This function retrieves teammate data from both club and national team
        contexts and converts them into pandas DataFrames.

        Args:
            url (str): Player URL used to fetch data.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - First DataFrame: Club teammates.
                - Second DataFrame: National team teammates.

        Raises:
            TypeError: If url is not a string.
            ValueError: If player data cannot be retrieved.
            KeyError: If 'relatedLinksData' is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Extract club teammates
            club_mates = json_data_player['relatedLinksData']['teammates']
            club_mates = pd.json_normalize(club_mates)

            # 🔹 Extract national team teammates
            national_team = json_data_player['relatedLinksData']['mensNationalTeam']
            national_team = pd.json_normalize(national_team)

            return club_mates, national_team

        except KeyError as e:
            raise KeyError(f"Missing teammates data: {e}")
    
    def extract_market_values(self, url):
        """
        Extract historical market values for a player.

        This function retrieves market value data over time, formats dates,
        and enriches the dataset with team logo URLs.

        Args:
            url (str): Player URL used to fetch data.

        Returns:
            pd.DataFrame: DataFrame containing market value history.

        Raises:
            TypeError: If url is not a string.
            ValueError: If player data cannot be retrieved.
            KeyError: If 'marketValues.values' is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize market values
            values = pd.json_normalize(json_data_player['marketValues']['values'])

            # 🔹 Convert and format dates
            values['date'] = pd.to_datetime(values['date'])
            values['value_date'] = values['date'].dt.date

            # 🔹 Add team logo URL
            values["logo_url_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ values["teamId"].astype(str) + ".png"

            # 🔹 Drop unnecessary columns
            return values.drop(columns=['date', 'source'])

        except KeyError as e:
            raise KeyError(f"Missing market values data: {e}")
    
    def extract_stats_section_season(self, url):
        """
        Extract season statistics section for a player.

        This function retrieves detailed season statistics grouped by sections
        and sub-statistics, transforming nested structures into a flat DataFrame.

        Args:
            url (str): Player URL used to fetch data.

        Returns:
            pd.DataFrame: DataFrame containing structured season statistics.

        Raises:
            TypeError: If url is not a string.
            ValueError: If player data cannot be retrieved.
            KeyError: If 'firstSeasonStats.statsSection.items' is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize stats section
            row_stats_section = pd.json_normalize(json_data_player['firstSeasonStats']['statsSection']['items'])
            stats_section = row_stats_section[['title', 'localizedTitleId', 'items']]

            # 🔹 Explode nested items
            df_exploded = stats_section.explode('items').reset_index(drop=True)

            # 🔹 Ensure valid dict format
            df_exploded['items'] = df_exploded['items'].apply( lambda x: x if isinstance(x, dict) else {})

            # 🔹 Normalize sub-statistics
            substats = pd.json_normalize(df_exploded['items']).add_prefix('substat_')

            # 🔹 Merge main stats with substats
            df_stats_section = pd.concat( [df_exploded.drop(columns=['items']), substats],  axis=1).reset_index(drop=True)

            # 🔹 Select relevant columns
            df_stats_section = df_stats_section[['title', 'localizedTitleId', 'substat_title','substat_localizedTitleId', 'substat_statValue',
                                                      'substat_percentileRank', 'substat_per90', 'substat_percentileRankPer90']]

            return df_stats_section

        except KeyError as e:
            raise KeyError(f"Missing season stats section data: {e}")
        
    def extract_shotmap(self, url, is_goalkeeper= True):
        """
        Extract shotmap data for a player.

        This function retrieves shotmap data for either goalkeepers or outfield players,
        formats datetime fields, and returns structured shot-level data.

        Args:
            url (str): Player URL used to fetch data.
            is_goalkeeper (bool, optional): Whether to extract goalkeeper shotmap.
                Defaults to True.

        Returns:
            pd.DataFrame: DataFrame containing shotmap data.

        Raises:
            TypeError: If url is not a string or is_goalkeeper is not a boolean.
            ValueError: If player data cannot be retrieved.
            KeyError: If shotmap data is missing.
        """

        # 🔹 Input validation
        if not isinstance(url, str):
            raise TypeError("url must be a string")

        if not isinstance(is_goalkeeper, bool):
            raise TypeError("is_goalkeeper must be a boolean")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Select correct shotmap type
            key = 'keeperShotmap' if is_goalkeeper else 'shotmap'

            row_shotmap = pd.json_normalize( json_data_player['firstSeasonStats'][key])

            # 🔹 Convert datetime fields
            row_shotmap['datetime'] = pd.to_datetime(row_shotmap['matchDate'], utc=True)
            row_shotmap['datetime_local'] = row_shotmap['datetime'].dt.tz_convert('Europe/Madrid')

            row_shotmap['match_date'] = row_shotmap['datetime_local'].dt.date
            row_shotmap['match_time'] = row_shotmap['datetime_local'].dt.strftime('%H:%M:%S')

            # 🔹 Drop unnecessary columns
            df_shotmap = row_shotmap.drop(columns=['matchDate', 'datetime', 'datetime_local'])

            return df_shotmap

        except KeyError as e:
            raise KeyError(f"Missing shotmap data: {e}")
    
    def extract_heatmap_season_stats(self, url):
        """
        Extract heatmap coordinates for a player's season.

        Args:
            url (str): Player URL used to fetch data.

        Returns:
            pd.DataFrame: DataFrame containing heatmap coordinates.

        Raises:
            TypeError: If url is not a string.
            ValueError: If player data cannot be retrieved.
            KeyError: If heatmap data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            return pd.json_normalize(json_data_player['firstSeasonStats']['heatmap']['coordinates'])

        except KeyError as e:
            raise KeyError(f"Missing heatmap data: {e}")
    
    def extract_next_match(self, url):
        """
        Extract next match information for a player.

        Args:
            url (str): Player URL.

        Returns:
            pd.DataFrame: DataFrame containing next match details.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If 'nextMatch' data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            next_match = pd.json_normalize(json_data_player['nextMatch'])

            # 🔹 Build full URL
            next_match["matchUrl"] = "https://www.fotmob.com" + next_match["matchUrl"].astype(str)

            # 🔹 Convert datetime
            next_match['datetime'] = pd.to_datetime(next_match['matchDate'], utc=True)
            next_match['datetime_local'] = next_match['datetime'].dt.tz_convert('Europe/Madrid')

            next_match['match_date'] = next_match['datetime_local'].dt.date
            next_match['match_time'] = next_match['datetime_local'].dt.strftime('%H:%M:%S')

            # 🔹 Add logos
            next_match["logo_url_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ next_match["homeId"].astype(str) + ".png"
          

            next_match["logo_url_opponent_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ next_match["awayId"].astype(str) + ".png"
         

            return next_match.drop(columns=[ 'matchDate', 'datetime', 'datetime_local','statusId', 'parentLeagueId', 'status.utcTime'])

        except KeyError as e:
            raise KeyError(f"Missing next match data: {e}")
    
    def extract_player_traits(self, url):
        """
        Extract player traits and description.

        Args:
            url (str): Player URL.

        Returns:
            tuple[str, pd.DataFrame]: Trait description and traits DataFrame.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If traits data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            description = pd.json_normalize(json_data_player)['traits.title'].iloc[0]
            traits_raw = pd.json_normalize(json_data_player)['traits.items'].iloc[0]

            traits = pd.json_normalize(traits_raw).drop(columns=['key'])

            return description, traits

        except KeyError as e:
            raise KeyError(f"Missing player traits data: {e}")
    
    def extract_actual_data_mainleague(self, url):
        """
        Extract main league statistics for the current season.

        Args:
            url (str): Player URL.

        Returns:
            pd.DataFrame: DataFrame containing league statistics.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If main league data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            row_data = pd.json_normalize(json_data_player)['mainLeague.stats'].iloc[0]
            df = pd.json_normalize(row_data).drop(columns=['localizedTitleId'])

            df['leagueName'] = json_data_player['mainLeague']['leagueName']
            df['leagueId'] = json_data_player['mainLeague']['leagueId']
            df['season'] = json_data_player['mainLeague']['season']

            return df

        except KeyError as e:
            raise KeyError(f"Missing main league data: {e}")
    
    def extract_position(self, url):
        """
        Extract player positions.

        Args:
            url (str): Player URL.

        Returns:
            pd.DataFrame: DataFrame containing player positions.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If position data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            row_positions = pd.json_normalize(json_data_player)['positionDescription.positions'].iloc[0]
            positions = pd.json_normalize(row_positions)

            return positions.drop(columns=['pitchPositionData', 'strPosShort.key'])

        except KeyError as e:
            raise KeyError(f"Missing position data: {e}")
    
    def extract_all_matches_stats(self, url):
        """
        Extract statistics for all recent matches.

        Args:
            url (str): Player URL.

        Returns:
            pd.DataFrame: DataFrame containing match-by-match statistics.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If match data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            df_recent = pd.json_normalize(json_data_player)['recentMatches'].iloc[0]
            df = pd.json_normalize(df_recent)

            # 🔹 Build URLs
            df["matchPageUrl"] = "https://www.fotmob.com" + df["matchPageUrl"].astype(str)

            # 🔹 Convert datetime
            df['matchDate.utcTime'] = pd.to_datetime(df['matchDate.utcTime'], utc=True)
            df['datetime_local'] = df['matchDate.utcTime'].dt.tz_convert('Europe/Madrid')

            df['match_date'] = df['datetime_local'].dt.date
            df['match_time'] = df['datetime_local'].dt.strftime('%H:%M:%S')

            # 🔹 Add logos
            df["logo_url_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["teamId"].astype(str) + ".png"
            df["logo_url_opponent_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["opponentTeamId"].astype(str) + ".png"

            return df.drop(columns=['ratingProps.isTopRating', 'matchDate.utcTime', 'datetime_local'])

        except KeyError as e:
            raise KeyError(f"Missing match stats data: {e}")
        
    def extract_trophies(self, url):
        """
        Extract player trophies and tournaments.

        Args:
            url (str): Player URL.

        Returns:
            pd.DataFrame: DataFrame containing trophies and tournament details.

        Raises:
            TypeError: If url is not a string.
            ValueError: If data retrieval fails.
            KeyError: If trophies data is missing.
        """

        if not isinstance(url, str):
            raise TypeError("url must be a string")

        json_data_player = asyncio.run(self.fetch_player_details(url))

        if json_data_player is None:
            raise ValueError("Failed to retrieve player data")

        try:
            # 🔹 Normalize trophies
            df = pd.json_normalize(json_data_player['trophies']['playerTrophies'])

            # 🔹 Ensure tournaments is a list
            df['tournaments'] = df['tournaments'].apply(lambda x: x if isinstance(x, list) else [])

            # 🔹 Explode tournaments
            df_expanded = df.explode('tournaments', ignore_index=True)

            # 🔹 Normalize tournament details
            df_tournaments = pd.json_normalize(df_expanded['tournaments'])

            # 🔹 Merge results
            return df_expanded.drop('tournaments', axis=1).join( df_tournaments, rsuffix='_tournament' )

        except KeyError as e:
            raise KeyError(f"Missing trophies data: {e}")