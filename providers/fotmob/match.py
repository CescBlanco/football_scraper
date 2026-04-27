import asyncio
import re
import os
import json
import time
import pandas as pd
from patchright.async_api import async_playwright

from providers.fotmob.utils import flatten_stats, extract_stats

COOKIES_FILE = "fotmob_cookies.json"

class FotmobMatchService:
    def __init__(self, headless=True):
        self.headless = headless

    async def fetch_match_json(self, url):
        match_id = re.search(r"#(\d+)", url).group(1)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome"
            )
            context = await browser.new_context()

            if os.path.exists(COOKIES_FILE):
                mod_time = os.path.getmtime(COOKIES_FILE)
                if (time.time() - mod_time) / 3600 > 1:
                    os.remove(COOKIES_FILE)
                    print("🗑️  Cookies expiradas")
                else:
                    with open(COOKIES_FILE) as f:
                        cookies = json.load(f)
                    await context.add_cookies(cookies)
                    print("🍪 Cookies cargadas")

            page = await context.new_page()

            # Captura todas las respuestas de matchDetails en una lista
            captured = []

            async def handle_response(response):
                if "matchDetails" in response.url and f"matchId={match_id}" in response.url:
                    print(f"🔥 DETECTADO: {response.url}")
                    try:
                        data = await response.json()
                        captured.append(data)
                    except Exception as e:
                        print(f"⚠️ Error leyendo JSON: {e}")

            page.on("response", handle_response)

            try:
                print("\n🌐 Navegando...")
                await page.goto(url, wait_until="domcontentloaded")

                # Espera hasta 60s a que aparezca la respuesta
                # (después de resolver Turnstile, la página recarga y dispara la API)
                print("⏳ Esperando matchDetails (resuelve el Turnstile si aparece)...")
                for _ in range(600):  # 60 segundos
                    if captured:
                        break
                    await asyncio.sleep(0.1)

                if not captured:
                    raise Exception("No se capturó matchDetails en 60s")

                # Guardar cookies
                cookies = await context.cookies()
                with open(COOKIES_FILE, "w") as f:
                    json.dump(cookies, f, indent=2)
                print("🍪 Cookies guardadas")

                print("✅ DATA LISTA")
                return captured[0]

            finally:
                await browser.close()

    def extract_match_details(self,url):
        json_data = asyncio.run(self.fetch_match_json(url))

        general_details = pd.json_normalize(json_data['general'])
    
        general_details['datetime'] = pd.to_datetime(general_details['matchTimeUTCDate'],utc=True)

        # Convertir a tu zona (ejemplo)
        general_details['datetime_local'] = general_details['datetime'].dt.tz_convert('Europe/Madrid')

        general_details['match_date'] = general_details['datetime_local'].dt.date
        general_details['match_time'] = general_details['datetime_local'].dt.strftime('%H:%M:%S')
        general_details['match_day'] = general_details['datetime_local'].dt.day_name()

        general_details = general_details.drop(columns=['matchName', 'datetime','datetime_local','leagueRoundName', 'coverageLevel', 'parentLeagueId', 
                                                'matchTimeUTC','matchTimeUTCDate'])

        df_teams= pd.DataFrame(json_data['header']['teams'])
        df_teams["pageUrl"] = "https://www.fotmob.com"+ df_teams["pageUrl"].astype(str)
        df = general_details.merge(df_teams,left_on="homeTeam.id",right_on="id",how="left")
        df = df.rename(columns={"score": "home_team_score","imageUrl": "home_team_image","pageUrl": "home_team_page"}).drop(columns=["id", "name"])
        df = df.merge( df_teams,left_on="awayTeam.id",right_on="id",how="left")
        df = df.rename(columns={  "score": "away_team_score", "imageUrl": "away_team_image", "pageUrl": "away_team_page"}).drop(columns=["id", "name"])
        df = df.drop(columns=['started',	'finished'])


        df_status= pd.json_normalize(json_data['header']['status'])
        df_status = df_status.drop(columns=["utcTime", "numberOfHomeRedCards", "numberOfAwayRedCards", 'scoreStr', 'whoLostOnAggregated', 'reason.shortKey',
                                            'reason.longKey'])


        box_info= pd.json_normalize(json_data['content']['matchFacts']['infoBox'])
        box_info = box_info.drop(columns=['legInfo', 'Match Date.utcTime',	'Match Date.isDateCorrect', 'Tournament.id'	,'Tournament.parentLeagueId',
                                    'Tournament.link',	'Tournament.leagueName',	'Tournament.roundName',	'Tournament.round' ])
        
        weather_match= pd.json_normalize(json_data['content']['weather'])

        return pd.concat((df,df_status, box_info, weather_match), axis=1)
    
    def extract_head_to_head(self, url):
        json_data = asyncio.run(self.fetch_match_json(url))

        head_to_head_data = json_data['content']['h2h']['summary']
        head_to_head_summary = pd.DataFrame([{
            'match_home_wins': head_to_head_data[0],
            'match_draws': head_to_head_data[1],
            'match_away_wins': head_to_head_data[2]
            }])
        
        df= pd.json_normalize(json_data['content']['h2h']['matches'])
        df["matchUrl"] = "https://www.fotmob.com"+ df["matchUrl"].astype(str)
        df['datetime'] = pd.to_datetime(df['time.utcTime'], utc=True)

        # Convertir a tu zona (ejemplo: Madrid)
        df['datetime_local'] = df['datetime'].dt.tz_convert('Europe/Madrid')

        df['match_date'] = df['datetime_local'].dt.date
        df['match_time'] = df['datetime_local'].dt.strftime('%H:%M:%S')
        df = df.drop(columns= ['finished', 'time.utcTime','datetime_local', 'league.pageUrl', 'status.utcTime', 'status.reason.shortKey', 'status.reason.longKey'])
        return head_to_head_summary , df
    
    def extract_info_lineups(self, url):

        json_data = asyncio.run(self.fetch_match_json(url))
        row_data_lineup_home= pd.json_normalize(json_data['content']['lineup']['homeTeam'])
        data_lineup_home = row_data_lineup_home.drop(columns=['starters','subs', 'unavailable', 'coach.isCoach', 'coach.usualPlayingPositionId', 'coach.primaryTeamName'], 
                                                     errors='ignore')

        row_data_lineup_away= pd.json_normalize(json_data['content']['lineup']['awayTeam'])
        data_lineup_away = row_data_lineup_away.drop(columns=['starters','subs', 'unavailable', 'coach.isCoach', 'coach.usualPlayingPositionId', 'coach.primaryTeamName'], 
                                                     errors='ignore')

        starters_home= pd.json_normalize(row_data_lineup_home['starters'][0])
        starters_home['isStarter'] = True

        subs_home= pd.json_normalize(row_data_lineup_home['subs'][0])
        subs_home['isStarter'] = False

        df_lineup_home= pd.concat([starters_home, subs_home]).reset_index(drop=True)
        df_lineup_home = df_lineup_home.drop(columns=['performance.seasonRating', 'shortName', 'rankings'], errors='ignore')

        starters_away= pd.json_normalize(row_data_lineup_away['starters'][0])
        starters_away['isStarter'] = True

        subs_away= pd.json_normalize(row_data_lineup_away['subs'][0])
        subs_away['isStarter'] = False

        df_lineup_away= pd.concat([starters_away, subs_home]).reset_index(drop=True)
        df_lineup_away = df_lineup_away.drop(columns=['performance.seasonRating', 'shortName', 'rankings'], errors='ignore')

        unavaible_home= pd.json_normalize(row_data_lineup_home['unavailable'][0])
        unavaible_away= pd.json_normalize(row_data_lineup_away['unavailable'][0])
        return data_lineup_home,data_lineup_away , df_lineup_home, df_lineup_away,unavaible_home,  unavaible_away 
    
    def extract_events(self, url):

        json_data = asyncio.run(self.fetch_match_json(url))
        match_events= pd.json_normalize(json_data['content']['matchFacts']['events']['events'])
        match_events= match_events.drop(columns=['reactKey', 'overloadTimeStr','time', 'nameStr'	,'firstName',	'lastName', 'player.id',
                                        'player.name',	'player.profileUrl', 'goalDescriptionKey', 'suffix',	'suffixKey'])

        swap_expanded = (match_events['swap'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else {}).apply(pd.Series).add_prefix('substitution_'))

        match_events = pd.concat([match_events.drop(columns=['swap']), swap_expanded], axis=1)
        match_events["profileUrl"] = "https://www.fotmob.com"+ match_events["profileUrl"].astype(str)
        match_events["assistProfileUrl"] = "https://www.fotmob.com"+ match_events["assistProfileUrl"].astype(str)
        match_events["substitution_profileUrl"] = "https://www.fotmob.com"+ match_events["substitution_profileUrl"].astype(str)
        return match_events
    
    def extract_player_of_the_match(self, url):

        json_data = asyncio.run(self.fetch_match_json(url))

        df_player_of_match_row_data= pd.json_normalize(json_data['content']['matchFacts']['playerOfTheMatch'])
        stats_expanded = df_player_of_match_row_data['stats'].apply(flatten_stats).apply(pd.Series)
        df = pd.concat([df_player_of_match_row_data.drop(columns=['stats']), stats_expanded], axis=1)

        df =df.drop(columns=['name.firstName',	'name.lastName', 'teamData.home.id', 'rating.num', 'minutesPlayed'])

        df["pageUrl"] = "https://www.fotmob.com"+ df["pageUrl"].astype(str)
        df["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + df["id"].astype(str) + ".png"

        df_player_of_match_clean =df.drop(columns=['shotmap'])
        return df, df_player_of_match_clean
    
    def extract_shotmap_player_of_the_match(self, url, player_id):

        df, df_player_of_match_clean = self.extract_player_of_the_match(url)

        filtered = df[df['id'] == int(player_id)]

        if filtered.empty:
            return f"No data found for player_id={player_id}. Check if this player is the Player of the Match."

        shots = filtered['shotmap'].iloc[0]

        if shots is not None and len(shots) > 0:
            df_shots_match = pd.json_normalize(shots)
            return df_shots_match
        else:
            return "The player did not take any shots in this match."
        
    def extract_home_away_form(self, url):
        
        json_data = asyncio.run(self.fetch_match_json(url))

        home_form = pd.json_normalize(json_data['content']['matchFacts']['teamForm'][0])
        home_form["linkToMatch"] = "https://www.fotmob.com"+ home_form["linkToMatch"].astype(str)
        home_form['datetime'] = pd.to_datetime(home_form['date.utcTime'], utc=True)
        home_form['datetime_local'] = home_form['datetime'].dt.tz_convert('Europe/Madrid')

        home_form['match_date'] = home_form['datetime_local'].dt.date
        home_form['match_time'] = home_form['datetime_local'].dt.strftime('%H:%M:%S')
        home_form = home_form.drop(columns=['result','score', 'teamPageUrl', 'tooltipText.utcTime', 'datetime','datetime_local', 'tooltipText.homeTeam',
                                            'tooltipText.homeTeamId', 'tooltipText.awayTeam',	'tooltipText.awayTeamId','home.isOurTeam', 'away.isOurTeam', 'date.utcTime'],
                                             errors='ignore')
        
        away_form= pd.json_normalize(json_data['content']['matchFacts']['teamForm'][1])
        away_form["linkToMatch"] = "https://www.fotmob.com"+ away_form["linkToMatch"].astype(str)
        away_form['datetime'] = pd.to_datetime(away_form['date.utcTime'], utc=True)
        away_form['datetime_local'] = away_form['datetime'].dt.tz_convert('Europe/Madrid')

        away_form['match_date'] = away_form['datetime_local'].dt.date
        away_form['match_time'] = away_form['datetime_local'].dt.strftime('%H:%M:%S')
        away_form = away_form.drop(columns=['result','score', 'teamPageUrl', 'tooltipText.utcTime',  'datetime','datetime_local','tooltipText.homeTeam',
                                            'tooltipText.homeTeamId', 'tooltipText.awayTeam',	'tooltipText.awayTeamId','home.isOurTeam', 'away.isOurTeam', 'date.utcTime'],
                                             errors='ignore')

        return home_form, away_form  
    
    def extract_top_players_home_away(self, url):
        
        json_data = asyncio.run(self.fetch_match_json(url))

        homeTopPlayers= pd.json_normalize(json_data['content']['matchFacts']['topPlayers']['homeTopPlayers'])
        homeTopPlayers = homeTopPlayers.drop(columns=['playerRatingRounded', 'name.firstName',	'name.lastName'], errors='ignore')
        homeTopPlayers["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + homeTopPlayers["playerId"].astype(str) + ".png"

        awayTopPlayers= pd.json_normalize(json_data['content']['matchFacts']['topPlayers']['awayTopPlayers'])
        awayTopPlayers = awayTopPlayers.drop(columns=['playerRatingRounded', 'name.firstName',	'name.lastName', 'positionLabel'], errors='ignore')
        awayTopPlayers["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + awayTopPlayers["playerId"].astype(str) + ".png"

        return homeTopPlayers, awayTopPlayers
    
    def extract_top_scores_home_away(self, url):
    
        json_data = asyncio.run(self.fetch_match_json(url))

        try:
            top_scorers_home = pd.json_normalize(json_data['content']['matchFacts']['topScorers']['homePlayer'])
            top_scorers_home = top_scorers_home.drop(columns=['lastName'])
            top_scorers_home["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + top_scorers_home["playerId"].astype(str) + ".png"

            top_scorers_away = pd.json_normalize(json_data['content']['matchFacts']['topScorers']['awayPlayer'])
            top_scorers_away = top_scorers_away.drop(columns=['lastName'])
            top_scorers_away["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + top_scorers_away["playerId"].astype(str) + ".png"

        except KeyError:
            # fallback mínimo
            top_scorers_home = pd.DataFrame()
            top_scorers_away = pd.DataFrame()

        return top_scorers_home, top_scorers_away

    def extract_match_momentum(self, url):
        
        json_data = asyncio.run(self.fetch_match_json(url))

        return pd.DataFrame(json_data['content']['momentum']['main']['data'])
    
    def extract_player_stats(self, url):
        
        json_data = asyncio.run(self.fetch_match_json(url))

        df = pd.DataFrame.from_dict(json_data['content']['playerStats'], orient='index')
        df = df.reset_index().rename(columns={'index': 'player_id'})

        
        stats_expanded = df['stats'].apply(flatten_stats).apply(pd.Series)
        df = pd.concat([df.drop(columns=['stats']), stats_expanded], axis=1)
        df_stats= df.drop(columns=['isPotm']) 
        df_stats_clean= df.drop(columns=['isPotm','shotmap']) 
        return df_stats_clean, df_stats
    
    def extract_shot_map_player(self, url, player_id):
        
        df_stats_clean, df_stats = self.extract_player_stats(url)

        # Asegurar tipo consistente
        df_stats['player_id'] = df_stats['player_id'].astype(int)
        player_id = int(player_id)

        filtered = df_stats[df_stats['player_id'] == player_id]

        if filtered.empty:
            return f"No data found for player_id= {player_id}"

        shots = filtered['shotmap'].iloc[0]

        if shots is not None and len(shots) > 0:
            return pd.json_normalize(shots)
        else:
            return "The player did not take any shots in this match."
        
    def extract_shots_map_all(self, url):

        json_data = asyncio.run(self.fetch_match_json(url))

        shots = pd.DataFrame(json_data['content']['shotmap']['Periods']['All'])
        shots[['x_onGoalShot', 'y_onGoalShot', 'zoomRatio_onGoalShot']] = shots['onGoalShot'].apply(lambda d: pd.Series(d))
        return shots.drop(columns=['onGoalShot'])
    
    def extract_match_stats(self, url):

        json_data = asyncio.run(self.fetch_match_json(url))

        periods = {
            "All": json_data['content']['stats']['Periods']['All']['stats'],
            "FirstHalf": json_data['content']['stats']['Periods']['FirstHalf']['stats'],
            "SecondHalf": json_data['content']['stats']['Periods']['SecondHalf']['stats']
            }

        dfs = []

        for period_name, stats_data in periods.items():
            
            df = pd.DataFrame(stats_data)

            df1 = df.explode('stats', ignore_index=True)
            lvl1 = pd.json_normalize(df1['stats']).add_prefix('lvl1_')

            df2 = df1.drop(columns=['stats']).join(lvl1)
            df2 = df2.copy()

            df2 = df2[df2['lvl1_stats'].apply( lambda x: isinstance(x, list) and len(x) > 0 and x != [None, None])]

            df2[['stat_home', 'stat_away']] = df2['lvl1_stats'].apply( lambda x: pd.Series(extract_stats(x)) )
            df2['period'] = period_name  # 👈 clave

            df_final_part = df2[['title', 'lvl1_title', 'stat_home', 'stat_away', 'lvl1_highlighted', 'period']]
            df_final_part = df_final_part.rename(columns={
                                                        'title': 'type_stat',
                                                        'lvl1_title': 'stat',
                                                        'lvl1_highlighted': 'highlighted'
                                                    })

            dfs.append(df_final_part)

        return  pd.concat(dfs, ignore_index=True)