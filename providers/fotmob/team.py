import requests
import pandas as pd

from typing import Dict, List, Union, Tuple ,Literal, Any, Optional
from providers.fotmob.utils import flatten_stats, process_block, validate_season_competition_team_context, extract_stats_available

class FotmobTeamService:
    def __init__(self, session: requests.Session):
        self.session = session

    def extract_last_starting_eleven(self, url_team: str,ccode3: str = "ESP") -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract the last starting lineup and related player events for a given team.

        This function retrieves team data from the FotMob API and processes:
        - Starting XI and substitutes
        - Substitution events
        - General lineup metadata

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]:
                - DataFrame with player-level data including substitution events
                - DataFrame with general lineup information (match context)

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "overview" not in data or "lastLineupStats" not in data["overview"]:
            raise KeyError("Missing 'lastLineupStats' in API response")

        lineup_data = data["overview"]["lastLineupStats"]

        # 🔹 General lineup info
        row_data_last_starting_info = pd.json_normalize(lineup_data)
        last_starting_info = row_data_last_starting_info.drop( columns=["starters", "subs", "unavailable", "coach.usualPlayingPositionId"], errors="ignore" )

        # 🔹 Starters and subs
        df_starters = pd.json_normalize(lineup_data["starters"]).drop(columns="rankings", errors="ignore")
        df_subs = pd.json_normalize(lineup_data["subs"]).drop(columns="rankings", errors="ignore")

        df_starters["isStarter"] = True
        df_subs["isStarter"] = False

        df_all = pd.concat([df_starters, df_subs], ignore_index=True)

        # 🔹 Substitution events
        df_subs_events = df_all.explode("performance.substitutionEvents")
        df_subs_events = pd.concat([ df_subs_events.drop(columns=["performance.substitutionEvents"], errors="ignore"),df_subs_events["performance.substitutionEvents"].apply(pd.Series)],axis=1)
        df_subs_events = df_subs_events.drop(columns=["firstName", "lastName", 0, "performance.events", "shortName"], errors="ignore")

        return df_subs_events, last_starting_info
    
    def extract_fixture_difficulty(self, url_team: str,url_league: str) -> pd.DataFrame:
        """
        Extract upcoming fixture difficulty data for a specific team.

        This function retrieves fixture difficulty metrics from the FotMob API,
        expands nested structures, and filters the results for the given team.

        Args:
            url_team (str): Team page URL from FotMob.
            url_league (str): League page URL from FotMob.

        Returns:
            pd.DataFrame: Dataset containing upcoming fixtures with:
                - Opponent information
                - Match dates
                - Difficulty-related metadata
                - Match URLs

        Raises:
            TypeError: If inputs are not strings.
            ValueError: If IDs cannot be extracted from URLs.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        if not isinstance(url_team, str) or not isinstance(url_league, str):
            raise TypeError("url_team and url_league must be strings")

        try:
            id_team = url_team.split("/")[-3]
            id_league = url_league.split("/")[-3]
        except Exception:
            raise ValueError("Invalid URL format")

        url_api = f"https://www.fotmob.com/api/data/fixtureDifficulty?id={id_league}"

        response = requests.get(url_api)
        response.raise_for_status()
        data = response.json()

        if "teams" not in data:
            raise KeyError("Missing 'teams' in API response")

        df_all = pd.DataFrame(data["teams"])

        df_fixtures = df_all.explode("fixtures").reset_index(drop=True)
        df_fixtures = pd.concat( [df_fixtures.drop(columns=["fixtures"], errors="ignore"), df_fixtures["fixtures"].apply(pd.Series) ],  axis=1)

        df_final = df_fixtures.join( df_fixtures.pop("opponent").apply(pd.Series).add_prefix("opponent_"))
        df_final["url"] = "https://www.fotmob.com" + df_final["url"].astype(str)
        df_final["matchDateUtc"] = pd.to_datetime(df_final["matchDateUtc"],utc=True,errors="coerce")
        df_final["matchDateLocal"] = df_final["matchDateUtc"].dt.tz_convert("Europe/Madrid")
        df_final["match_date"] = df_final["matchDateLocal"].dt.date
        df_final["match_time"] = df_final["matchDateLocal"].dt.time

        df_final = df_final.drop(columns=["matchDateUtc", "totalNextFive", "matchDateLocal", "averageNextFive"],errors="ignore")

        df_final = df_final[df_final["teamId"] == int(id_team)]

        return df_final.reset_index(drop=True)
    
    def extract_team_form(self, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract recent match form for a specific team.

        This function retrieves the latest match results for a team from the FotMob API,
        including match outcomes, scores, dates, and enriched metadata such as match URLs
        and team logos.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Dataset containing recent matches with:
                - Match result (W/D/L)
                - Scores (home and away)
                - Match date and time (UTC converted)
                - Match URL
                - Team logos (home and away)

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[ -3 ]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()

        data = response.json()

        if "overview" not in data or "teamForm" not in data["overview"]:
            raise KeyError("Missing 'teamForm' in API response")

        df = pd.json_normalize(data["overview"]["teamForm"])

        # 🔹 Enrich URLs
        df["linkToMatch"] = "https://www.fotmob.com" + df["linkToMatch"].astype(str)

        # 🔹 Datetime parsing
        df["date.utcTime"] = pd.to_datetime(df["date.utcTime"],utc=True,errors="coerce")
        df["matchDateLocal"] = df["date.utcTime"].dt.tz_convert("Europe/Madrid")
        df["match_date"] = df["matchDateLocal"].dt.date
        df["match_time"] = df["matchDateLocal"].dt.time

        # 🔹 Drop unnecessary columns
        df = df.drop(columns= ['tooltipText.utcTime', 'date.utcTime', 'matchDateLocal', 'away.isOurTeam', 'home.isOurTeam', 'tooltipText.awayTeamId', 'tooltipText.homeTeamId', 'imageUrl', 'result', 'score', 
                                        'tooltipText.homeTeam', 'tooltipText.awayTeam', 'teamPageUrl'])
        # 🔹 Rename columns
        df= df.rename(columns={'resultString':'result', 'linkToMatch': 'mathc_url', 'tooltipText.homeScore': 'home_score' , 'tooltipText.awayScore' : 'away_score'})

        # 🔹 Add team logos
        df["home_team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["home.id"].astype(str) + ".png"
        df["away_team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["away.id"].astype(str) + ".png"
        
        return df
    
    def extract_data_details(self, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract detailed team information including metadata, venue, and team colors.

        This function retrieves team-level details from the FotMob API and returns
        a flattened and cleaned dataset combining:
        - General team information
        - Venue details (including capacity, surface, and location)
        - Team colors

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Single-row DataFrame containing:
                - Team metadata
                - Venue information (name, city, capacity, surface, coordinates)
                - Team colors

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()

        data = response.json()

        # 🔹 Validate structure
        if "details" not in data or "overview" not in data:
            raise KeyError("Missing required keys in API response")

        # 🔹 Team details
        row_data_team = pd.json_normalize(data["details"])

        clean_data_team = row_data_team.drop(columns=[
            'canSyncCalendar', 'details.faqJSONLD', 'faqJSONLD.@context',	'faqJSONLD.@type',	'faqJSONLD.mainEntity',	'sportsTeamJSONLD.@context',	'sportsTeamJSONLD.@type',
            'sportsTeamJSONLD.name', 'sportsTeamJSONLD.sport',	'sportsTeamJSONLD.gender','sportsTeamJSONLD.athlete',	'sportsTeamJSONLD.location.@type','sportsTeamJSONLD.location.address.@type',
            'sportsTeamJSONLD.location.geo.@type','sportsTeamJSONLD.memberOf.@type', 'sportsTeamJSONLD.memberOf.name', 'breadcrumbJSONLD.@context',	'breadcrumbJSONLD.@type', 
            'breadcrumbJSONLD.itemListElement','sportsTeamJSONLD.memberOf.url', 'sportsTeamJSONLD.location.name', 'sportsTeamJSONLD.location.address.addressLocality', 'sportsTeamJSONLD.location.geo.latitude',
            'sportsTeamJSONLD.location.geo.longitude'], errors='ignore') 

        # 🔹 Venue
        if "venue" not in data["overview"]:
            raise KeyError("Missing 'venue' in API response")

        df_venue = pd.json_normalize(data["overview"]["venue"])

        # Convert statPairs to columns
        stats_dict = dict(df_venue.loc[0, "statPairs"])
        df_stats = pd.DataFrame([stats_dict])

        df_venue = pd.concat([df_venue.drop(columns=["statPairs"], errors="ignore"), df_stats],axis=1)

        # Extract location
        df_venue[["location_latitude", "location_longitude"]] = pd.DataFrame( df_venue["widget.location"].tolist(),index=df_venue.index)
        df_venue = df_venue.drop(columns=["widget.location"], errors="ignore")
        df_venue= df_venue.rename(columns={'widget.name':'name_venue', 'widget.city': 'city_venue','Surface': 'surface_venue', 'Capacity': 'capacity_venue' , 'Opened' : 'opened_venue'})

        # 🔹 Team colors
        if "teamColors" not in data["overview"]:
            raise KeyError("Missing 'teamColors' in API response")

        colors = pd.json_normalize(data["overview"]["teamColors"])

        return pd.concat([clean_data_team, df_venue, colors], axis=1)
    
    def extract_next_match(self, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract upcoming match information for a given team.

        This function retrieves the next scheduled match from the FotMob API,
        including match metadata, date/time (localized), team logos, and
        optionally match statistics if available.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Single-row DataFrame containing:
                - Match metadata (teams, competition, URL)
                - Localized match date and time
                - Team logos (home and away)
                - Flattened match statistics (if available)

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If required keys are missing in API response.
        """

        
        # 🔹 Validate input
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "overview" not in data or "nextMatch" not in data["overview"]:
            raise KeyError("Missing 'nextMatch' in API response")

        # 🔹 Base match data
        next_match = pd.json_normalize(data["overview"]["nextMatch"])
        next_match["pageUrl"] = "https://www.fotmob.com" + next_match["pageUrl"].astype(str)

        # 🔹 Datetime conversion
        next_match["status.utcTime"] = pd.to_datetime( next_match["status.utcTime"], utc=True, errors="coerce")
        next_match["matchDateLocal"] = next_match["status.utcTime"].dt.tz_convert("Europe/Madrid")
        next_match["match_date"] = next_match["matchDateLocal"].dt.date
        next_match["match_time"] = next_match["matchDateLocal"].dt.time

        # 🔹 Drop noisy columns
        next_match = next_match.drop(columns=['displayTournament','matchDateLocal', 'odds','startDay', 'tournament.stage', 'liveTime.short',  'status.utcTime', 'opponent.id',
                                    'opponent.name','opponent.score', 'liveTime.shortKey', 'liveTime.long',	'liveTime.longKey', 'stats.leagueIds',	'stats.leagueNames',
                                    'stats.teamColors.fontDarkMode.home',	'stats.teamColors.fontDarkMode.away', 'stats.teamColors.fontLightMode.home',	'stats.teamColors.fontLightMode.away'], errors='ignore')

        # 🔹 Logos
        next_match["team_home_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + next_match["home.id"].astype(str) + ".png"
        next_match["team_away_logo"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + next_match["away.id"].astype(str) + ".png"

        # 🔹 Match stats (optional)
        try:
            stats_raw = data["overview"]["nextMatch"]["stats"]["stats"]
            stats_next_match = pd.json_normalize(stats_raw).drop(columns=["localizedTitle", "type", "decimals"],errors="ignore")

            flat_dict = flatten_stats(stats_next_match)
            stats_df = pd.DataFrame([flat_dict])

            next_match = pd.concat([next_match, stats_df], axis=1)
            next_match = next_match.drop(columns=['stats.stats','odds.persistentKey',	'odds.providerId'	,'odds.logoUrl'	,'odds.promoText.lang',	'odds.promoText.text',	
                        'odds.promoText.text2',	'odds.promoText.link','odds.promoText.linkIOS',	'odds.promoText.linkWeb',	'odds.promoText.callToAction',	'odds.ongoing',
                        'odds.callToActionLink',	'odds.betBoostMarkets',	'odds.odds.matchfactMarkets',	'odds.odds.oddsTabMarkets',	'odds.odds.matchCouponKey',
                        'odds.odds.oddsType',	'odds.odds.provider.id',	'odds.odds.resolvedOddsMarket','odds.restrictions.country'	,'odds.restrictions.disableLiveOdds',	
                        'odds.restrictions.gambleAwareMsg',	'odds.restrictions.showAgeGate',	'odds.restrictions.ageLimit','odds.restrictions.showOddsTab',	
                        'odds.restrictions.excludedLeagueIds',	'odds.restrictions.excludedMatchIds'],errors='ignore')
            
        except (KeyError, TypeError):
            # No stats available
            pass

        return next_match
    
    def extract_last_match(self, url_team: str, ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract the most recent match played by a given team.

        This function retrieves the last match information from the FotMob API,
        including match metadata, date/time (localized), match URL, and team logos.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Single-row DataFrame containing:
                - Match metadata (teams, score, status)
                - Match date and time (localized to Europe/Madrid)
                - Match URL
                - Team logos (home and away)

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        # 🔹 Validate input
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "fixtures" not in data or "allFixtures" not in data["fixtures"]:
            raise KeyError("Missing 'lastMatch' data in API response")

        # 🔹 Normalize last match
        df = pd.json_normalize(data["fixtures"]["allFixtures"]["lastMatch"])

        # 🔹 Enrich URL
        df["pageUrl"] = "https://www.fotmob.com" + df["pageUrl"].astype(str)

        # 🔹 Datetime conversion
        df["status.utcTime"] = pd.to_datetime(df["status.utcTime"], utc=True, errors="coerce")
        df["matchDateLocal"] = df["status.utcTime"].dt.tz_convert("Europe/Madrid")
        df["match_date"] = df["matchDateLocal"].dt.date
        df["match_time"] = df["matchDateLocal"].dt.time

        # 🔹 Drop unnecessary columns
        df = df.drop(columns=['displayTournament', 'tournament.stage', 'status.utcTime', 'matchDateLocal', 'opponent.id',	'opponent.name',	'opponent.score', 
                                            'status.reason.longKey', 'status.reason.shortKey'], errors='ignore')

        # 🔹 Add team logos
        df["team_home_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["home.id"].astype(str)+ ".png"
        df["team_away_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["away.id"].astype(str)+ ".png"

        return df
    
    def extract_top_players(self, url_team: str, ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract top players for a given team across multiple performance categories.

        This function retrieves top players from the FotMob API, including:
        - Top scorers (goals)
        - Top assist providers
        - Top rated players

        Each category is normalized into a consistent structure and combined
        into a single DataFrame.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Dataset containing top players with:
                - Player identifiers and metadata
                - Statistic name (e.g., goals, assists, rating)
                - Statistic value
                - Team color information (dark/light mode)

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        # 🔹 Validate input
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "overview" not in data or "topPlayers" not in data["overview"]:
            raise KeyError("Missing 'topPlayers' in API response")

        # 🔹 Extract each category
        top_players = data["overview"]["topPlayers"]

        df_assists = process_block(top_players.get("byAssists", {}).get("players", []))
        df_goals = process_block(top_players.get("byGoals", {}).get("players", []))
        df_rating = process_block(top_players.get("byRating", {}).get("players", []))

        # 🔹 Combine all
        df_final = pd.concat([df_assists, df_goals, df_rating], axis=0, ignore_index=True)

        return df_final
    
    def extract_standing_all_h_a_form(self, url_team: str,type_stand: str = "data.table.all",ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract full standings (all/home/away) including team form and next opponent.

        This function retrieves league standings for the team’s competition,
        enriches them with:
        - Team form (recent results)
        - Next opponent information
        - Competition metadata

        Args:
            url_team (str): Team page URL from FotMob.
            type_stand (str, optional): Type of standings
                (e.g., 'data.table.all', 'data.table.home', 'data.table.away').
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Standings DataFrame enriched with:
                - Team stats (points, wins, losses, etc.)
                - Form string
                - Next opponent info (id, name, match date/time)
                - Logos and URLs

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID extraction fails.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "table" not in data:
            raise KeyError("Missing 'table' in API response")

        row_data_standings = pd.json_normalize(data["table"][0])
        legend = row_data_standings["data.legend"].iloc[0]

        color_map = {item["color"]: {"title": item["title"], "tKey": item["tKey"]}for item in legend}

        teams = row_data_standings[type_stand].iloc[0]
        df_standings = pd.DataFrame(list(teams))

        df_standings[["goals_for", "goals_against"]] = df_standings["scoresStr"].str.split("-", expand=True)

        df_standings = df_standings[ ["qualColor", "idx", "name", "id", "pageUrl", "played", "wins", "draws", "losses","goals_for", "goals_against", "goalConDiff", "pts"] ]

        df_standings["competition"] = df_standings["qualColor"].map(lambda x: color_map.get(x, {}).get("title"))
        df_standings["tKey"] = df_standings["qualColor"].map(lambda x: color_map.get(x, {}).get("tKey"))
        df_standings["team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df_standings["id"].astype(str) + ".png"
        df_standings["pageUrl"] = "https://www.fotmob.com" + df_standings["pageUrl"].astype(str)
        df_standings["id"] = df_standings["id"].astype(str)

        # 🔹 FORM
        df_form = pd.json_normalize(data["table"][0]["teamForm"]).T.rename_axis("team_id").reset_index()
        df_form["form"] = df_form[0].apply( lambda x: ",".join([m["resultString"] for m in x]) if isinstance(x, list) else None)
        df_form["team_id"] = df_form["team_id"].astype(str)
        df_standing_form = df_standings.merge(df_form[["team_id", "form"]], left_on="id", right_on="team_id").drop(columns="team_id")

        # 🔹 NEXT OPPONENT
        df_next = pd.json_normalize(data["table"][0]["nextOpponent"]).T.rename_axis("team_id").reset_index()

        df_next["opponent_id"] = df_next[0].apply(lambda x: x[0] if isinstance(x, list) else None)
        df_next["opponent_name"] = df_next[0].apply(lambda x: x[1] if isinstance(x, list) else None)
        df_next["match_id"] = df_next[0].apply(lambda x: x[2] if isinstance(x, list) else None)
        df_next["match_date"] = pd.to_datetime(df_next[0].apply(lambda x: x[5] if isinstance(x, list) else None))

        df_next["match_time"] = df_next["match_date"].dt.time
        df_next["match_day"] = df_next["match_date"].dt.date

        df_next["team_id"] = df_next["team_id"].astype(str)

        df_final = df_standing_form.merge(df_next, left_on="id", right_on="team_id").drop(columns="team_id")
        df_final["team_opponent_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df_final["opponent_id"].astype(str) + ".png"
        
        df_final = df_final.drop(columns= [0, 'match_date'])
        return df_final
    
    def extract_standings_xg(self, url_team: str,type_stand: str = "xg",ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract expected goals (xG) standings for a team’s competition.

        Args:
            url_team (str): Team page URL.
            type_stand (str, optional): Standings type (default: 'xg').
            ccode3 (str, optional): Country code.

        Returns:
            pd.DataFrame: Standings including xG metrics.

        Raises:
            TypeError, ValueError, RequestException, KeyError
        """
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        id_team = url_team.split("/")[-3]

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        row_data = pd.json_normalize(data["table"][0])
        legend = row_data["data.legend"].iloc[0]
        color_map = {i["color"]: i["title"] for i in legend}

        df = pd.json_normalize(row_data[type_stand][0])

        df[["goals_for", "goals_against"]] = df["scoresStr"].str.split("-", expand=True)
        df = df[['qualColor', 'idx', 'xPositionDiff' , 'name', 'id', 'pageUrl', 'played', 'wins', 'draws', 'losses','goals_for', 'goals_against', 
                                    'goalConDiff',  'pts', 'xg', 'xgDiff', 'xgConceded', 'xgConcededDiff', 'xPoints', 'xPointsDiff']]
        df["competition"] = df["qualColor"].map(color_map)
        df["team_logo"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["id"].astype(str) + ".png"
        df["pageUrl"] = "https://www.fotmob.com" + df["pageUrl"].astype(str)
        df['id'] = df['id'].astype(str)

        return df
    
    def extract_standings_champions_all_h_a(self, url_team: str, type_standing: str = "all", ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract Champions League-style standings including form and next opponent.

        Args:
            url_team (str): Team URL.
            type_standing (str): 'all', 'home', or 'away'.
            ccode3 (str): Country code.

        Returns:
            pd.DataFrame: Enriched standings.

        Raises:
            Standard validation and request errors.
        """
        id_team = url_team.split("/")[-3]

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        row_data = pd.json_normalize(data["table"][1])
        legend = row_data["data.legend"].iloc[0]

        color_map = {i["color"]: { "title": i["title"],"tKey": i["tKey"]}for i in legend}

        teams = pd.json_normalize(row_data["data.tables"][0][0]["table"][type_standing])
        teams[['goals_for', 'goals_against']] = teams['scoresStr'].str.split('-', expand=True)
        teams = teams[['qualColor', 'idx', 'name', 'id', 'pageUrl', 'played', 'wins', 'draws', 'losses','goals_for', 'goals_against', 'goalConDiff',  'pts']]
        teams['competition'] = teams['qualColor'].map(lambda x: color_map.get(x, {}).get('title'))
        teams['tKey'] = teams['qualColor'].map(lambda x: color_map.get(x, {}).get('tKey'))
        teams["team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + teams["id"].astype(str)+ ".png"
        teams["pageUrl"] = "https://www.fotmob.com"+ teams["pageUrl"].astype(str)
        teams['id'] = teams['id'].astype(str)

        df_form = (pd.json_normalize(data['table'][1]['teamForm']).T.rename_axis('team_id').reset_index())
        df_form['form'] = df_form[0].apply(lambda x: ','.join([match['resultString'] for match in x]) if isinstance(x, list) else None)
        df_form_final= df_form[['team_id', 'form' ]].copy()
        df_form_final['team_id'] = df_form_final['team_id'].astype(str)
        df_standing_form = teams.merge(df_form_final, left_on='id', right_on='team_id', how='left').drop(columns= ['team_id'])

        df_next = (pd.json_normalize(data['table'][1]['nextOpponent']).T.rename_axis('team_id').reset_index())

        df_next['opponent_id'] = df_next[0].apply(lambda x: x[0] if isinstance(x, list) else None)
        df_next['opponent_name'] = df_next[0].apply(lambda x: x[1] if isinstance(x, list) else None)
        df_next['match_id'] = df_next[0].apply(lambda x: x[2] if isinstance(x, list) else None)
        df_next['match_date'] = df_next[0].apply(lambda x: x[5] if isinstance(x, list) else None)

        df_next['match_date'] = pd.to_datetime(df_next['match_date'])

        df_next['match_time'] = df_next['match_date'].dt.time
        df_next['match_day'] = df_next['match_date'].dt.date
        df_next= df_next[['team_id', 'opponent_id' , 'opponent_name', 'match_id', 'match_time'	,'match_day']]

        df_next['team_id'] = df_next['team_id'].astype(str)

        df_final = df_standing_form.merge(df_next, left_on='id', right_on='team_id', how='left').drop(columns= ['team_id'])
        df_final["team_opponent_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df_final["opponent_id"].astype(str)+ ".png"

        return df_final
    
    def extract_standings_champions_xg(self, url_team: str,type_stand: str = "xg",ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract Champions League standings with xG metrics.

        Args:
            url_team (str): Team URL.
            type_stand (str): xG table type.
            ccode3 (str): Country code.

        Returns:
            pd.DataFrame: xG standings.

        Raises:
            Standard validation and request errors.
        """
        id_team = url_team.split("/")[-3]

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        row_data = pd.json_normalize(data["table"][1])
        legend = row_data["data.legend"].iloc[0]
        color_map = {item['color']: {'title': item['title'], 'tKey': item['tKey']} for item in legend}

        df = pd.json_normalize(row_data["data.tables"][0][0]["table"][type_stand])

        df[['goals_for', 'goals_against']] = df['scoresStr'].str.split('-', expand=True)
        df = df[['qualColor', 'idx', 'xPositionDiff' , 'name', 'id', 'pageUrl', 'played', 'wins', 'draws', 'losses','goals_for', 'goals_against', 
                                    'goalConDiff',  'pts', 'xg', 'xgDiff', 'xgConceded', 'xgConcededDiff', 'xPoints', 'xPointsDiff']]
        df['competition'] = df['qualColor'].map(lambda x: color_map.get(x, {}).get('title'))
        df["team_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["id"].astype(str)+ ".png"
        df["pageUrl"] = "https://www.fotmob.com"+ df["pageUrl"].astype(str)
        df['id'] = df['id'].astype(str)
        return df
    
    def extract_all_fixtures(self, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract all fixtures (past and upcoming matches) for a given team.

        This function retrieves the complete fixture list from the FotMob API,
        including match metadata, match date, URLs, and team logos.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: DataFrame containing:
                - Match metadata (teams, scores, status)
                - Match date
                - Match URL
                - Home and away team logos

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        # 🔹 Validate input
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        # 🔹 API request
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "fixtures" not in data or "allFixtures" not in data["fixtures"]:
            raise KeyError("Missing 'fixtures' data in API response")

        # 🔹 Normalize fixtures
        all_fixtures = pd.json_normalize(data["fixtures"]["allFixtures"]["fixtures"])

        # 🔹 Enrich URL
        all_fixtures["pageUrl"] = "https://www.fotmob.com" + all_fixtures["pageUrl"].astype(str)

        # 🔹 Datetime handling
        all_fixtures["status.utcTime"] = pd.to_datetime(all_fixtures["status.utcTime"],utc=True,errors="coerce")
        all_fixtures["matchDateLocal"] = all_fixtures["status.utcTime"].dt.tz_convert("Europe/Madrid")
        all_fixtures["match_date"] = all_fixtures["matchDateLocal"].dt.date
        all_fixtures["match_time"] = all_fixtures["matchDateLocal"].dt.strftime("%H:%M")
        
        # 🔹 Drop unnecessary columns
        all_fixtures = all_fixtures.drop(columns=['result', 'displayTournament', 'matchDateLocal','tournament.stage', 'status.utcTime', 'opponent.id',	'opponent.name',	'opponent.score',
                                                        'status.matchDateTbd',	'status.matchTimeTbd', 'status.reason.shortKey', 'status.reason.longKey'], errors='ignore')

        # 🔹 Add logos
        all_fixtures["team_home_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + all_fixtures["home.id"].astype(str)+ ".png"
        all_fixtures["team_away_logo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + all_fixtures["away.id"].astype(str)+ ".png"

        return all_fixtures
    
    def extract_squad(self, url_team: str, ccode3: str = "USA_CA") -> pd.DataFrame:
        """
        Extract the full squad (players) of a given team.

        This function retrieves squad data from the FotMob API, expands
        nested player structures, and returns a flat DataFrame containing
        player-level information.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'USA_CA').

        Returns:
            pd.DataFrame: DataFrame containing squad players with:
                - Player metadata (id, name, position, etc.)
                - Player role information
                - Player photo URL

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected keys are missing in API response.
        """
        # 🔹 Validate input
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        # 🔹 API request
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "squad" not in data or "squad" not in data["squad"]:
            raise KeyError("Missing 'squad' data in API response")

        # 🔹 Normalize squad structure
        df = pd.json_normalize(data["squad"]["squad"])

        if df.empty:
            return df

        # 🔹 Expand players list
        df = df.explode("members").reset_index(drop=True)

        # 🔹 Normalize player dictionaries
        players = pd.json_normalize(df["members"])

        # 🔹 Combine with squad metadata (position group, etc.)
        final_df = pd.concat([df[["title"]], players], axis=1)

        # 🔹 Clean columns
        final_df = final_df.drop(columns=["title", "role.key", "injury", "excludeFromRanking"], errors="ignore")

        # 🔹 Add player photo
        final_df["member_photo"] =  "https://images.fotmob.com/image_resources/playerimages/"+ final_df["id"].astype(str) + ".png"

        return final_df
    




    def extract_transfers(self, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract all transfer activity for a given team.

        This function retrieves transfer data from the FotMob API, including:
        - Incoming transfers
        - Outgoing transfers
        - Contract extensions

        It combines all transfer types into a single unified DataFrame.

        Args:
            url_team (str): Team page URL from FotMob.
            ccode3 (str, optional): Country code (default: 'ESP').

        Returns:
            pd.DataFrame: Transfer dataset containing:
                - Player information
                - Transfer type (in, out, extension)
                - Contract dates
                - Transfer timestamps
                - Player and club logos

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from URL.
            requests.exceptions.RequestException: If API request fails.
            KeyError: If expected transfer sections are missing in API response.
        """
        # 🔹 Validate input
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "transfers" not in data or "data" not in data["transfers"]:
            raise KeyError("Missing 'transfers' data in API response")

        transfers_data = data["transfers"]["data"]

        # 🔹 Normalize each transfer type
        contract_extension = pd.json_normalize(transfers_data.get("Contract extension", []))
        contract_extension["player_out"] = False

        player_in = pd.json_normalize(transfers_data.get("Players in", []))
        player_in["player_out"] = False

        players_out = pd.json_normalize(transfers_data.get("Players out", []))
        players_out["player_out"] = True

        # 🔹 Combine all
        df_transfers = pd.concat([contract_extension, player_in, players_out], axis=0).reset_index(drop=True)

        # 🔹 Rename columns
        df_transfers = df_transfers.rename(columns={"fromDate": "contract_from_date","toDate": "contract_to_date" })

        # 🔹 Datetime processing
        df_transfers["transferDate"] = pd.to_datetime(df_transfers["transferDate"], errors="coerce")

        df_transfers["transfer_date"] = df_transfers["transferDate"].dt.date
        df_transfers["transfer_time"] = df_transfers["transferDate"].dt.time

        # 🔹 Clean contract dates
        df_transfers["contract_from_date"] = df_transfers["contract_from_date"].astype(str).str.split("T").str[0]
        df_transfers["contract_to_date"] = df_transfers["contract_to_date"].astype(str).str.split("T").str[0]

        # 🔹 Drop unnecessary columns
        df_transfers= df_transfers.drop(columns=['transferText','position',	'fee' , 'transferType.localizationKey', 'fee.localizedFeeText', 'transferDate'])

        # 🔹 Add images
        df_transfers["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/"+ df_transfers["playerId"].astype(str)+ ".png"
        df_transfers["logo_url_fromClub"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df_transfers["fromClubId"].astype(str)+ ".png"
        df_transfers["logo_url_toClub"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df_transfers["toClubId"].astype(str) + ".png"

        return df_transfers
    
    def extract_history_trophies(self, url_team: str, ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract historical trophies for a football team.

        This function retrieves the trophy history of a team from the FotMob API,
        including all competitions won or achieved by the club.

        It also cleans nested list structures and generates a competition logo URL.

        Args:
            url_team (str): FotMob team URL.
            ccode3 (str, optional): Country code for the API request (default is 'ESP').

        Returns:
            pd.DataFrame: DataFrame containing trophy history and competition metadata,
            including a generated competition image URL.

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from the URL.
            requests.exceptions.RequestException: If the API request fails.
            KeyError: If 'history.trophyList' is missing in the response.
        """

        # 🔹 Input validation
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        # 🔹 Validate structure
        if "history" not in data or "trophyList" not in data["history"]:
            raise KeyError("Missing 'history.trophyList' in API response")

        # 🔹 Normalize data
        df = pd.json_normalize(data["history"]["trophyList"])

        # 🔹 Clean single-item lists
        df = df.apply( lambda col: col.map(   lambda x: x[0] if isinstance(x, list) and len(x) == 1 else x ))

        # 🔹 Add competition image
        df["competition_photo"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["tournamentTemplateId"].astype(str)+ ".png"

        return df
    
    def extract_historical_table_position(self, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract historical league positions for a football team.

        This function retrieves historical ranking data and division metadata
        from the FotMob API and merges both datasets into a single DataFrame.

        Args:
            url_team (str): FotMob team URL.
            ccode3 (str, optional): Country code for API request (default is 'ESP').

        Returns:
            pd.DataFrame: Merged DataFrame containing historical ranks and division info.

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from the URL.
            requests.exceptions.RequestException: If the API request fails.
            KeyError: If expected historical data is missing in the response.
        """

        # 🔹 Input validation
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        # 🔹 Validate structure
        try:
            historical = data["history"]["historicalTableData"]
        except KeyError:
            raise KeyError("Missing 'history.historicalTableData' in API response")

        # 🔹 Normalize data
        division = pd.json_normalize(historical["divisions"])
        ranks = pd.json_normalize(historical["ranks"])

        # 🔹 Merge datasets
        df_ranks = ranks.merge(division,on="templateId", how="left")

        return df_ranks
    
    def extract_coach_history(señf, url_team: str,ccode3: str = "ESP") -> pd.DataFrame:
        """
        Extract coaching history for a football team.

        This function retrieves the historical list of coaches for a team
        from the FotMob API and enriches the dataset with coach image URLs.

        Args:
            url_team (str): FotMob team URL.
            ccode3 (str, optional): Country code for API request (default is 'ESP').

        Returns:
            pd.DataFrame: DataFrame containing coach history and metadata,
            including generated coach image URLs.

        Raises:
            TypeError: If url_team is not a string.
            ValueError: If team ID cannot be extracted from the URL.
            requests.exceptions.RequestException: If the API request fails.
            KeyError: If 'history.coachHistory' is missing in the response.
        """

        # 🔹 Input validation
        if not isinstance(url_team, str):
            raise TypeError("url_team must be a string")

        try:
            id_team = url_team.split("/")[-3]
        except Exception:
            raise ValueError("Invalid team URL format")

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"

        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        # 🔹 Validate structure
        if "history" not in data or "coachHistory" not in data["history"]:
            raise KeyError("Missing 'history.coachHistory' in API response")

        # 🔹 Normalize data
        coach_history = pd.json_normalize(data["history"]["coachHistory"])

        # 🔹 Add coach image
        coach_history["coach_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + coach_history["id"].astype(str) + ".png"

        return coach_history
    
    def extract_players_stats(self, url_team, season, league, ccode3='ESP', stat='Top scorer'):
        """
        Extract player statistics for a specific team, season, and competition.

        This function validates the team-season-league context and the requested
        statistical category, then retrieves detailed player statistics from the
        FotMob API. It enriches the dataset with metadata and image URLs, and
        filters results for the specified team only.

        Args:
            url_team (str): FotMob team URL.
            season (str): Season in format 'YYYY/YYYY'.
            league (str): League name.
            ccode3 (str, optional): Country code (default is 'ESP').
            stat (str, optional): Statistic type to extract (default is 'Top scorer').

        Returns:
            pd.DataFrame: DataFrame containing player statistics for the team, including:
                - Player performance stats
                - Category, title, and subtitle metadata
                - Player image URLs
                - Team logo URLs
                - Filtered results for the specified team only

        Raises:
            ValueError: If season/league validation or stat validation fails.
            requests.exceptions.RequestException: If API request fails.
        """

        # Validate team, season and competition context
        valid, msg, row, id_team, data = validate_season_competition_team_context(url_team, season, league, ccode3)

        if not valid:
            raise ValueError(msg)
        
        # Validate that the requested stat is available
        valid_stat, msg_stat, players_stat, teams_stat = extract_stats_available(url_team, stat=stat)

        if not valid_stat:
            raise ValueError(
                f"{msg_stat}\n\n"
                f"Available player stats:\n{players_stat}\n\n"
            )

        # Normalize player stats metadata
        df_stats_info = pd.json_normalize(data['stats']['players'])
        df_stats_info = df_stats_info[['header', 'name']]

        # Get API slug for the selected stat
        slug_stat = df_stats_info[df_stats_info['header'] == stat]['name'].iloc[0]

        parent_league_id = row['parentLeagueId']
        tournament_id = row['tournamentId']

        # Fetch stat-specific data from FotMob API
        url_stat = f"https://data.fotmob.com/stats/{parent_league_id}/season/{tournament_id}/{slug_stat}.json"
        response = requests.get(url_stat)
        response.raise_for_status()
        data_stat = response.json()
        
        # Extract general top list metadata
        df_top = pd.json_normalize(data_stat['TopLists'][0])
        info = df_top.iloc[0].to_dict()

        # Extract player stat list
        df = pd.json_normalize(data_stat['TopLists'][0]['StatList'])

        # Add metadata columns
        df['Category'] = info.get('Category')
        df['Title'] = info.get('Title')
        df['Subtitle'] = info.get('Subtitle')

        # Build player image and team logo URLs
        df["player_photo"] = "https://images.fotmob.com/image_resources/playerimages/" + df["ParticiantId"].astype(str) + ".png"
        df["logo_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" +  df["TeamId"].astype(str) + ".png"

        # Remove unnecessary columns
        df = df.drop(columns=['StatValueCount', 'ParticipantCountryCode', 'Positions', 'header'],errors='ignore')

        return df[df['TeamId'] == int(id_team)].reset_index(drop=True)
    
    def extract_team_stats(self, url_team, season, league, ccode3='ESP', stat='Top scorer'):
        """
        Extract team-level statistics for a specific team, season, and competition.

        This function validates the team-season-league context and the requested
        team statistic, then retrieves detailed team statistics from the FotMob API.
        It enriches the dataset with metadata and logo URLs, and returns the
        processed statistics for the specified team.

        Args:
            url_team (str): FotMob team URL.
            season (str): Season in format 'YYYY/YYYY'.
            league (str): League name.
            ccode3 (str, optional): Country code (default is 'ESP').
            stat (str, optional): Statistic type to extract (default is 'Top scorer').

        Returns:
            pd.DataFrame: DataFrame containing team statistics, including:
                - Team performance stats
                - Category, title, and subtitle metadata
                - Team logo URLs
                - Filtered and cleaned stat list

        Raises:
            ValueError: If season/league validation or stat validation fails.
            requests.exceptions.RequestException: If API request fails.
        """

        # Validate team, season and competition context
        valid, msg, row, id_team, data = validate_season_competition_team_context(url_team, season, league, ccode3)

        if not valid:
            raise ValueError(msg)
        
        # Validate that the requested stat is available
        valid_stat, msg_stat, players_stat, teams_stat = extract_stats_available(url_team, stat=stat)

        if not valid_stat:
            raise ValueError(
                f"{msg_stat}\n\n"
                f"Available team stats:\n{teams_stat}\n\n"
            )

        # Extract team ID from URL
        id_team = url_team.split('/')[-3]

        # Fetch team data from FotMob API
        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        # Normalize available team stats metadata
        df_stats_info = pd.json_normalize(data['stats']['teams'])
        df_stats_info = df_stats_info[['header', 'stat']]

        # Get API slug for the selected stat
        slug_stat = df_stats_info[df_stats_info['header'] == stat]['stat'].iloc[0]

        parent_league_id = row['parentLeagueId']
        tournament_id = row['tournamentId']

        # Build stats API URL
        url_stat = f"https://data.fotmob.com/stats/{parent_league_id}/season/{tournament_id}/{slug_stat}.json"
        response = requests.get(url_stat)
        response.raise_for_status()
        data_stat = response.json()

        # Extract general metadata from top list
        df_top = pd.json_normalize(data_stat['TopLists'][0])
        info = df_top.iloc[0].to_dict()

        # Extract stat list
        df = pd.json_normalize(data_stat['TopLists'][0]['StatList'])

        # Add metadata columns
        df['Category'] = info.get('Category')
        df['Title'] = info.get('Title')
        df['Subtitle'] = info.get('Subtitle')

        # Build team logo URLs
        df["logo_team"] =  "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/" + df["TeamId"].astype(str) + ".png"

        # Clean unnecessary columns
        return df.drop(columns=['StatValueCount', 'ParticiantId', 'Positions', 'header'],errors='ignore')
