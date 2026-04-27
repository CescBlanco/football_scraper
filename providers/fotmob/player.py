import asyncio
import re
import os
import json
import time
import random
import pandas as pd
from patchright.async_api import async_playwright

COOKIES_FILE = "fotmob_player_cookies.json"

class FotmobPlayerService:
    def __init__(self, headless=False):
        self.headless = headless

    async def _simulate_human_mouse(self, page):
        for _ in range(10):
            x = random.randint(0, 1280)
            y = random.randint(0, 720)
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

    async def fetch_player_details(self, url):
        player_id = re.search(r"/(\d+)/", url)
        player_id = player_id.group(1) if player_id else None

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                channel="chrome"
            )
            context = await browser.new_context()

            # Cargar cookies si existen y son recientes
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
            captured = []

            async def handle_response(response):
                
                is_player_data = "playerData" in response.url
                matches_id = player_id and f"id={player_id}" in response.url  # ← era playerId=, es id=
                is_ok = response.status == 200                                  # ← ignorar 403

                if is_player_data and matches_id and is_ok:
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
                await self._simulate_human_mouse(page)

                print("⏳ Esperando playerData (resuelve el Turnstile si aparece)...")
                for _ in range(600):  # 60 segundos
                    if captured:
                        break
                    await asyncio.sleep(0.1)

                if not captured:
                    raise Exception("No se capturó playerData en 60s")

                # Guardar cookies
                cookies = await context.cookies()
                with open(COOKIES_FILE, "w") as f:
                    json.dump(cookies, f, indent=2)
                print("🍪 Cookies guardadas")

                print("✅ DATA LISTA")
                return captured[0]

            except Exception as e:
                print(f"❌ Error: {e}")
                return None

            finally:
                await browser.close()

    def extract_player_info(self, url):

        json_data_player= asyncio.run(self.fetch_player_details(url))

        df_row = pd.json_normalize(json_data_player['playerInformation'])
        # Crear un diccionario vacío para almacenar los valores
        new_data = {}

        # Recorremos las filas del DataFrame
        for _, row in df_row.iterrows():
            title = row['title']
            
            # Para el "Contract end", tomar el valor de "value.fallback.utcTime"
            if title == "Contract end":
                new_data[title] = row['value.fallback.utcTime'].split('T')[0]
            else:
                new_data[title] = row['value.fallback']

        # Convertir el diccionario de datos en un nuevo DataFrame
        df = pd.DataFrame(new_data, index=[0])
        df['Weight'] = json_data_player['meta']['personJSONLD']['weight']['value'] + ' ' + 'kg'
        df['Birthday'] = json_data_player['birthDate']['utcTime'].split('T')[0]
        df['player']= json_data_player['name']
        df['gender']= json_data_player['gender']
        df['id']= json_data_player['id']
        df['player_url']= json_data_player['meta']['personJSONLD']['url']
        # Información de lesión (segura si no hay injuryInformation)
        injury_info = json_data_player.get('injuryInformation', None)
        if injury_info:
            df['injury_name'] = injury_info.get('name', None)
            df['injury_expectedReturnDate'] = injury_info.get('expectedReturn', {}).get('expectedReturnDateParam', None)
            df['injury_expectedReturnFallback'] = injury_info.get('expectedReturn', {}).get('expectedReturnFallback', None)
            df['lastUpdated_injury'] = injury_info.get('lastUpdated', {}).get('utcTime', None)
            if df['lastUpdated_injury'].notnull().any():
                df['lastUpdated_injury'] = df['lastUpdated_injury'].str.split('T').str[0]
        else:
            df['injury_name'] = None
            df['injury_expectedReturnDate'] = None
            df['injury_expectedReturnFallback'] = None
            df['lastUpdated_injury'] = None
        df["player_photo"] =  "https://images.fotmob.com/image_resources/playerimages/" + df["id"].astype(str) + ".png"
        df['isCaptain']= json_data_player['isCaptain']
        df['isCoach']= json_data_player['isCoach']
        df['teamName']= json_data_player['primaryTeam']['teamName']
        df['teamId']= json_data_player['primaryTeam']['teamId']
        df["logo_url_team"] = "https://images.fotmob.com/image_resources/logo/leaguelogo/dark/"+ df["teamId"].astype(str)+ ".png"
        df['onLoan']= json_data_player['primaryTeam']['onLoan']
        df['teamColors_home']= json_data_player['primaryTeam']['teamColors']['color']
        df['teamColors_home_alternative']= json_data_player['primaryTeam']['teamColors']['colorAlternate']
        df['teamColors_away']= json_data_player['primaryTeam']['teamColors']['colorAway']
        df['teamColors_away_alternative']= json_data_player['primaryTeam']['teamColors']['colorAwayAlternate']

        df['status']= json_data_player['status']
        return df 
    
    def extract_career_stats_senior(self, url):

        json_data_player= asyncio.run(self.fetch_player_details(url))

        df= pd.json_normalize(json_data_player['careerHistory']['careerItems']['senior']['seasonEntries'])
        df = df.drop(columns= [	'seasonName'])

        # 2️⃣ Explode de 'tournamentStats' y reset del índice
        df_exploded = df.explode('tournamentStats').reset_index(drop=True)

        # 3️⃣ Asegurar que no haya None para evitar errores
        df_exploded['tournamentStats'] = df_exploded['tournamentStats'].apply(lambda x: x if isinstance(x, dict) else {})

        # 4️⃣ Normalizar los diccionarios del torneo con prefijo '_tournament'
        tournament_df = pd.json_normalize(df_exploded['tournamentStats']).add_prefix('tournament_')

        # 5️⃣ Concatenar columnas de temporada + torneo
        df1 = pd.concat([df_exploded.drop(columns=['tournamentStats']), tournament_df], axis=1).reset_index(drop=True)
        df1 = df1.rename(columns={'appearances': 'total_appearances'	, 'goals': 'total_goals', 'assists': 'total_assists', 'rating.rating': 'rating_promed',
                                            'tournament_rating.rating': 'tournament_rating'})
        df1 = df1.drop(columns= [	'showTeamGender', 'transferType', 'tournament_isFriendly', 'teamGender' ])


        df2= pd.json_normalize(json_data_player['careerHistory']['careerItems']['senior']['teamEntries'])
        df2['startDate'] = pd.to_datetime(df2['startDate'])
        df2['endDate'] = pd.to_datetime(df2['endDate'])
        df2 = df2.drop(columns= ['teamGender', 'showTeamGender', 'transferType', 'hasUncertainData' ])

        return df1, df2
    
    def extract_career_stats_youth(self, url):
        
        json_data_player= asyncio.run(self.fetch_player_details(url))

        df_career_younth= pd.json_normalize(json_data_player['careerHistory']['careerItems']['youth']['seasonEntries'])
        df_career_younth = df_career_younth.drop(columns= [	'seasonName'])

        # 2️⃣ Explode de 'tournamentStats' y reset del índice
        df_exploded = df_career_younth.explode('tournamentStats').reset_index(drop=True)

        # 3️⃣ Asegurar que no haya None para evitar errores
        df_exploded['tournamentStats'] = df_exploded['tournamentStats'].apply(lambda x: x if isinstance(x, dict) else {})

        # 4️⃣ Normalizar los diccionarios del torneo con prefijo '_tournament'
        tournament_df = pd.json_normalize(df_exploded['tournamentStats']).add_prefix('tournament_')

        # 5️⃣ Concatenar columnas de temporada + torneo
        df1 = pd.concat([df_exploded.drop(columns=['tournamentStats']), tournament_df], axis=1).reset_index(drop=True)
        df1 = df1.rename(columns={'appearances': 'total_appearances'	, 'goals': 'total_goals', 'assists': 'total_assists', 'rating.rating': 'rating_promed',
                                            'tournament_rating.rating': 'tournament_rating'})
        df1 = df1.drop(columns= [	'showTeamGender', 'transferType', 'tournament_isFriendly', 'teamGender' ])

        df2= pd.json_normalize(json_data_player['careerHistory']['careerItems']['youth']['teamEntries'])
        df2['startDate'] = pd.to_datetime(df2['startDate'])
        df2['endDate'] = pd.to_datetime(df2['endDate'])

        df2 = df2.drop(columns= [	'teamGender', 'showTeamGender', 'transferType', 'hasUncertainData' ])

        return df1, df2
    
    def extract_career_stats_national_team(self, url):

        json_data_player= asyncio.run(self.fetch_player_details(url))
        
        df_career_nationalteam= pd.json_normalize(json_data_player['careerHistory']['careerItems']['national team']['seasonEntries'])
        df_career_nationalteam = df_career_nationalteam.drop(columns= [	'seasonName'])

        # 2️⃣ Explode de 'tournamentStats' y reset del índice
        df_exploded = df_career_nationalteam.explode('tournamentStats').reset_index(drop=True)

        # 3️⃣ Asegurar que no haya None para evitar errores
        df_exploded['tournamentStats'] = df_exploded['tournamentStats'].apply(lambda x: x if isinstance(x, dict) else {})

        # 4️⃣ Normalizar los diccionarios del torneo con prefijo '_tournament'
        tournament_df = pd.json_normalize(df_exploded['tournamentStats']).add_prefix('tournament_')

        # 5️⃣ Concatenar columnas de temporada + torneo
        df1 = pd.concat([df_exploded.drop(columns=['tournamentStats']), tournament_df], axis=1).reset_index(drop=True)
        df1 = df1.rename(columns={'appearances': 'total_appearances'	, 'goals': 'total_goals', 'assists': 'total_assists', 'rating.rating': 'rating_promed',
                                            'tournament_rating.rating': 'tournament_rating'})
        df1 = df1.drop(columns= [	'showTeamGender', 'transferType', 'tournament_isFriendly', 'teamGender' ])



        df2= pd.json_normalize(json_data_player['careerHistory']['careerItems']['national team']['teamEntries'])
        df2['startDate'] = pd.to_datetime(df2['startDate'])
        df2['endDate'] = pd.to_datetime(df2['endDate'])
        df2 = df2.drop(columns= [	'teamGender', 'showTeamGender', 'transferType', 'hasUncertainData' ])

        return df1, df2
