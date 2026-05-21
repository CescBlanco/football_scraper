import pandas as pd
import requests
from typing import List, Dict, Any,Tuple, Optional
from football_scraper.providers.sofascore.constants import BASE_URL

#-----------------------------------------------COMPETITIONS---------------------------------------------------

def flatten_leagues(leagues_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """
            Flatten league data from a nested structure.

            Args:
                leagues_list (List[Dict[str, Any]]): List of country or international league data.

            Returns:
                List[Dict[str, Any]]: Flattened list of league dictionaries.
            """
            flattened: List[Dict[str, Any]] = []

            for item in leagues_list:
                name: str = item.get("name") or item.get("displayName", "Unknown")

                if "leagues" not in item:
                    raise KeyError("Missing 'leagues' key in data item")

                for league in item.get("leagues", []):
                    league_id = league.get("id")

                    flattened.append({
                        "country": name,
                        "league_id": league_id,
                        "league_name": league.get("name"),
                        "display_name": f"{league.get('name')} - {name}",
                        "localized_name": league.get("localizedName"),
                        "pageUrl": BASE_URL + league.get("pageUrl", ""),
                        "logoURL": f"https://images.fotmob.com/image_resources/logo/leaguelogo/dark/{league_id}.png"
                    })

            return flattened

#-----------------------------------------------LEAGUE---------------------------------------------------
def fetch_stat(row):
    header = row["header"]
    url = row["fetchAllUrl"]

    if isinstance(url, list):
        url = url[0]

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "TopLists" not in data:
            return []

        dfs = []

        for block in data["TopLists"]:
            df = pd.json_normalize(block["StatList"])
            df["category"] = block.get("Category")
            df["stat"] = block.get("Title")
            df["substat"] = block.get("Subtitle")
            df["header"] = header
            dfs.append(df)

        return dfs

    except Exception:
        return []


def extract_next_opponent(df: Any) -> pd.DataFrame:
    """
    Extract next opponent information for teams from a nested FotMob dataset.

    This function flattens the "nextOpponent" structure and extracts opponent
    metadata such as opponent name, match ID, and match date/time.

    Args:
        df (Any): Raw FotMob API response containing team data.

    Returns:
        pd.DataFrame: Flattened dataset with:
            - team_id
            - opponent_id
            - opponent_name
            - match_id
            - match_date
            - match_time

    Raises:
        KeyError: If expected keys are missing in the input structure.
        TypeError: If input format is invalid.
    """
    df_next = pd.json_normalize(df[0]["nextOpponent"]).T.rename_axis("team_id").reset_index()

    df_next["opponent_id"] = df_next[0].apply(lambda x: x[0] if isinstance(x, list) else None)
    df_next["opponent_name"] = df_next[0].apply(lambda x: x[1] if isinstance(x, list) else None)
    df_next["match_id"] = df_next[0].apply(lambda x: x[2] if isinstance(x, list) else None)
    df_next["match_date"] = df_next[0].apply(lambda x: x[5] if isinstance(x, list) else None)

    df_next["match_datetime"] = pd.to_datetime(df_next["match_date"], utc=True, errors="coerce")

    df_next["match_date"] = df_next["match_datetime"].dt.strftime("%Y-%m-%d")
    df_next["match_time"] = df_next["match_datetime"].dt.strftime("%H:%M")

    df_next = df_next[ ["team_id", "opponent_id", "opponent_name", "match_id", "match_time", "match_date"]]
    df_next["team_id"] = df_next["team_id"].astype(str)

    return df_next

def extract_team_form(df: Any) -> pd.DataFrame:
    """
    Extract recent team form information from a nested FotMob dataset.

    This function parses the "teamForm" structure and returns a compact
    representation of match results per team.

    Args:
        df (Any): Raw FotMob API response containing team data.

    Returns:
        pd.DataFrame: Dataset with:
            - team_id
            - form (comma-separated match results)

    Raises:
        KeyError: If expected keys are missing.
    """
    df_form = pd.json_normalize(df[0]["teamForm"]).T.rename_axis("team_id").reset_index()

    df_form["form"] = df_form[0].apply(lambda x: ",".join([m["resultString"] for m in x]) if isinstance(x, list) else None)

    df_form_final = df_form[["team_id", "form"]].copy()
    df_form_final["team_id"] = df_form_final["team_id"].astype(str)

    return df_form_final

#-----------------------------------------------TEAM---------------------------------------------------
 
def flatten_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Flatten match statistics into a single dictionary.

    Args:
        df (pd.DataFrame): Raw stats DataFrame.

    Returns:
        Dict[str, Any]: Flattened key-value stats.
    """
    result = {}

    for _, row in df.iterrows():
        key = str(row.get("title", "")).lower().replace(" ", "_")
        stats = row.get("stats")

        if isinstance(stats, list) and len(stats) == 2:
            result[f"{key}_home"] = stats[0]
            result[f"{key}_away"] = stats[1]

        result[f"{key}_highlighted"] = row.get("highlighted")

    return result

def process_block(players: list) -> pd.DataFrame:
    """
    Normalize a top players block (goals, assists, rating).
    """
    df = pd.DataFrame(players)

    if df.empty:
        return df

    df[["stat_name", "stat_value"]] = df["stat"].apply(lambda x: pd.Series([x.get("name"), x.get("value")]) if isinstance(x, dict) else pd.Series([None, None]))
    df[["team_colors_darkMode", "team_colors_lightMode"]] = df["teamColors"].apply( lambda x: pd.Series([x.get("darkMode"), x.get("lightMode")]) if isinstance(x, dict) else pd.Series([None, None]))
    df = df.drop(columns=["stat", "teamColors", "value"], errors="ignore")

    return df

def validate_season_competition_team_context(url_team: str, season: str, league: str, ccode3: str = "ESP"):
    """
    Validate whether a team participated in a specific league season context.

    This function extracts the team ID from a FotMob URL, retrieves the team's
    historical tournament seasons, and checks if the given season and league
    combination exists for that team.

    Args:
        url_team (str): FotMob team URL.
        season (str): Season in format 'YYYY/YYYY' or similar string representation.
        league (str): League name to validate against.
        ccode3 (str, optional): Country code (default is 'ESP').

    Returns:
        tuple:
            - bool: Whether the season + league context is valid.
            - str: Validation message.
            - pd.Series or None: Matching row of tournament season data if valid.
            - str or None: Team ID extracted from URL.
            - dict or None: Raw API response data.

    Raises:
        requests.exceptions.RequestException: If the API request fails.
    """
    try:
        id_team = url_team.split('/')[-3]

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        df = pd.json_normalize(data['stats']['tournamentSeasons'])

        if df.empty:
            return False, "No tournament data available", None, None, None

        df['season'] = df['season'].astype(str).str.strip()
        df['leagueName'] = df['leagueName'].astype(str).str.strip()

        row = df[(df['season'] == str(season)) & (df['leagueName'] == league)]

        if row.empty:
            return False, "Season + league not found", None, None, None

        return True, "Valid", row.iloc[0], id_team, data

    except requests.exceptions.RequestException as e:
        return False, f"API error: {e}", None, None, None

def extract_stats_available(url_team: str, stat: Optional[str] = None, ccode3: str = "ESP") -> Tuple[bool, str, List[str], List[str]]:
    """
    Extract available player and team statistics for a given team.

    This function retrieves statistical categories from the FotMob API
    and returns lists of available player and team stats. Optionally,
    it validates whether a specific stat exists.

    Args:
        url_team (str): FotMob team URL.
        stat (Optional[str], optional): Specific stat to validate (default is None).
        ccode3 (str, optional): Country code (default is 'ESP').

    Returns:
        tuple:
            - bool: Whether stats are valid and available.
            - str: Status message.
            - List[str]: Available player stats headers.
            - List[str]: Available team stats headers.

    Raises:
        requests.exceptions.RequestException: If the API request fails.
    """

    try:
        id_team = url_team.split('/')[-3]

        url_data = f"https://www.fotmob.com/api/data/teams?id={id_team}&ccode3={ccode3}"
        response = requests.get(url_data)
        response.raise_for_status()
        data = response.json()

        if "stats" not in data:
            return False, "Stats not found", [], []

        df_players = pd.json_normalize(data['stats']['players'])
        df_teams = pd.json_normalize(data['stats']['teams'])

        if df_players.empty or df_teams.empty:
            return False, "Stats empty", [], []

        player_stats = df_players['header'].astype(str).tolist()
        team_stats = df_teams['header'].astype(str).tolist()

        # 🔥 validación opcional de stat
        if stat is not None:
            if stat not in player_stats and stat not in team_stats:
                return (
                    False,
                    f"Stat '{stat}' not available",
                    player_stats,
                    team_stats
                )

        return True, "Valid stats available", player_stats, team_stats

    except requests.exceptions.RequestException as e:
        return False, f"API error: {e}", [], []
    
#----------------------------------------------------------PLAYER---------------------------------------------------------------------------
    
#----------------------------------------------------------MATCH---------------------------------------------------------------------------

def flatten_stats(stats_list):
        flat = {}
        
        for section in stats_list:  # top_stats, attack, defense...
            stats_dict = section.get('stats', {})
            
            for stat_name, stat_info in stats_dict.items():
                stat_data = stat_info.get('stat', {})
                
                # coger el valor principal
                value = stat_data.get('value')
                
                # guardar
                flat[stat_name] = value
                
                # opcional: si quieres también el total (para %)
                if 'total' in stat_data:
                    flat[f"{stat_name}_total"] = stat_data.get('total')
        
        return flat
   
def extract_stats(x):
    if isinstance(x, list):
        if len(x) >= 2:
            home = x[0].get('value') if isinstance(x[0], dict) else x[0]
            away = x[1].get('value') if isinstance(x[1], dict) else x[1]
            return home, away
        elif len(x) == 1:
            val = x[0].get('value') if isinstance(x[0], dict) else x[0]
            return val, None
    return None, None
