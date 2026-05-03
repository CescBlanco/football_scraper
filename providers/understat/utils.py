import pandas as pd
from bs4 import BeautifulSoup
import re

from providers.understat.constants import BASE_URL

#-------------------------------LEAGUE------------------------------------------------------------
def parse_standings_table(data: dict) -> pd.DataFrame:
    """
    Parse team standings and match history data into a structured DataFrame,
    including calculated PPDA and OPPDA metrics.

    Args:
        data (dict): Raw data dictionary containing team information and match history.
            Expected format:
                {
                    "teams": {
                        team_id: {
                            "title": str,
                            "history": list[dict]
                        }
                    }
                }

    Returns:
        pd.DataFrame: A DataFrame where each row represents a match entry with:
            - team_id (str)
            - team (str)
            - match statistics (various fields from history)
            - PPDA (float or None)
            - OPPDA (float or None)

    Raises:
        KeyError: If expected keys ("teams", "title", "history") are missing.
        TypeError: If data structure is not iterable or not a dict.
    """

    # List to store all processed rows
    rows = []

    # Iterate through each team in the dataset
    for team_id, team_data in data["teams"].items():
        team_name = team_data["title"]

        # Iterate through each match in the team's history
        for match in team_data["history"]:
            row = match.copy()

            # Add team metadata to each row
            row["team_id"] = team_id
            row["team"] = team_name

            # Compute PPDA (Passes Allowed Per Defensive Action)
            if "ppda" in row and isinstance(row["ppda"], dict):
                att = float(row["ppda"].get("att", 0))
                deff = float(row["ppda"].get("def", 1))  # avoid division by zero
                row["PPDA"] = att / deff
            else:
                row["PPDA"] = None

            # Compute OPPDA (Opponent PPDA)
            if "ppda_allowed" in row and isinstance(row["ppda_allowed"], dict):
                att = float(row["ppda_allowed"].get("att", 0))
                deff = float(row["ppda_allowed"].get("def", 1))
                row["OPPDA"] = att / deff
            else:
                row["OPPDA"] = None

            # Append processed row
            rows.append(row)

    # Convert list of dictionaries into a DataFrame
    return pd.DataFrame(rows)

def extract_standings_total(data: dict, season: str) -> pd.DataFrame:
    """
    Extract total standings statistics (home + away combined)
    from Understat match data.

    Args:
        data (dict): Raw Understat data containing teams and match history.
        season (str): The season for which to extract standings.

    Returns:
        pd.DataFrame: A DataFrame containing aggregated season-wide performance metrics.

    Raises:
        KeyError: If expected keys are missing in the input data.
        TypeError: If input data is not structured as expected.
    """

    # Parse raw standings into structured DataFrame
    df = parse_standings_table(data)

    # Columns to aggregate by sum
    sum_columns = ["xG", "xGA", "npxG", "npxGA", "deep", "deep_allowed" , "scored", "missed", 'xpts', 'wins', 'draws', 'loses', 'pts', 'npxGD']

    # Columns to aggregate by mean
    mean_columns = ["PPDA", "OPPDA"]

    # Ensure numeric conversion
    for col in sum_columns + mean_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Aggregate metrics
    df_sum = df.groupby("team")[sum_columns].sum().round(2)
    df_mean = df.groupby("team")[mean_columns].mean().round(2)
    df_matches = df.groupby("team").size().to_frame("matches")

    # Combine results
    df_total = pd.concat([df_sum, df_mean, df_matches], axis=1)

    # Reset index
    df_total = df_total.reset_index()

    # Reorder columns
    df_total = df_total[['team', 'matches' ,'wins',	'draws'	,'loses', 'scored',	'missed', 'pts', 'xG', 'npxG' ,'xGA' ,'npxGA', 'npxGD', 'PPDA',	'OPPDA', 'deep',	'deep_allowed',	'xpts']]

    # Sort by points
    df_total.sort_values("pts", ascending=False, inplace=True)

    # Create ranking
    df_total["position"] = range(1, len(df_total) + 1)

    # Rename columns
    df_total.columns = ['team' , 'matches', 'wins', 'draws', 'loses', 'goals', 'goals_against', 'pts', 'xG', 'npxG','xGA',  'npxGA' , 'npxGDif', 'ppda', 'oppda', 'passes_completed', 'opp_passes_completed', 'xpts', 'position']
    # Build team URLs
    df_total["team_url"] = BASE_URL + 'team/' +   df_total['team'].str.replace(' ', '_') + f"/{season}"

    return df_total

def extract_standings_home(data: dict, season: str) -> pd.DataFrame:
    """
    Extract home standings statistics from Understat match data.

    The function processes raw team match history, filters home games,
    aggregates performance metrics, and computes rankings.

    Args:
        data (dict): Raw Understat data containing teams and match history.
        season (str): The season for which to extract standings.


    Returns:
        pd.DataFrame: A DataFrame containing aggregated home performance metrics per team:
            - team (str)
            - matches (int)
            - wins, draws, loses (int)
            - goals, goals_against (int)
            - pts (int)
            - xG, npxG, xGA, npxGA (float)
            - npxGDif (float)
            - ppda, oppda (float)
            - passes_completed, opp_passes_completed (float)
            - xpts (float)
            - position (int)
            - team_url (str)

    Raises:
        KeyError: If expected columns or keys are missing in the input data.
        TypeError: If input data is not structured as expected.
    """

    # Parse raw standings into a structured DataFrame
    df = parse_standings_table(data)

    # Filter only home matches
    df_home = df[df["h_a"] == "h"].copy()

    # Columns to aggregate by sum
    sum_cols = ["xG", "xGA", "npxG", "npxGA", "deep", "deep_allowed" , "scored", "missed", 'xpts', 'wins', 'draws', 'loses', 'pts', 'npxGD']

    # Columns to aggregate by mean
    mean_columns = ["PPDA", "OPPDA"]

    # Ensure numeric conversion for aggregation columns
    for col in sum_cols + mean_columns:
        if col in df_home.columns:
            df_home[col] = pd.to_numeric(df_home[col], errors="coerce")

    # Aggregate metrics
    df_sum = df_home.groupby("team")[sum_cols].sum().round(2)
    df_mean = df_home.groupby("team")[mean_columns].mean().round(2)
    df_matches = df_home.groupby("team").size().to_frame("matches")

    # Combine all aggregated metrics
    df_home = pd.concat([df_sum, df_mean, df_matches], axis=1)

    # Reset index to turn team into a column
    df_home = df_home.reset_index()

    # Reorder columns for readability
    df_home = df_home[['team', 'matches' ,'wins',	'draws'	,'loses', 'scored',	'missed', 'pts', 'xG', 'npxG' ,'xGA' ,'npxGA', 'npxGD', 'PPDA',	'OPPDA', 'deep',	'deep_allowed',	'xpts']]
    
    # Sort teams by points
    df_home.sort_values("pts", ascending=False, inplace=True)

    # Create ranking position
    df_home["position"] = range(1, len(df_home) + 1)

    # Rename columns for final output standardization
    df_home.columns = ['team', 'matches' ,'wins',	'draws'	,'loses', 'goals',	'goals_against', 'pts', 'xG', 'npxG' ,'xGA' ,'npxGA', 'npxGD', 'PPDA',	'OPPDA', 'passes_completed','opp_passes_completed',	'xpts', 'position']

    # Build team URLs
    df_home['team_url'] = BASE_URL + 'team/' +   df_home['team'].str.replace(' ', '_') + f"/{season}"

    return df_home

def extract_standings_away(data: dict, season: str) -> pd.DataFrame:
    """
    Extract away standings statistics from Understat match data.

    The function processes raw team match history, filters away games,
    aggregates performance metrics, and computes rankings.

    Args:
        data (dict): Raw Understat data containing teams and match history.
        season (str): The season for which to extract standings.

    Returns:
        pd.DataFrame: A DataFrame containing aggregated away performance metrics per team.

    Raises:
        KeyError: If expected keys are missing in the input data.
        TypeError: If input data is not structured as expected.
    """

    # Parse raw standings into structured DataFrame
    df = parse_standings_table(data)

    # Filter only away matches
    df_away = df[df["h_a"] == "a"].copy()

    # Columns to aggregate by sum
    sum_cols = ["xG", "xGA", "npxG", "npxGA", "deep", "deep_allowed" , "scored", "missed", 'xpts', 'wins', 'draws', 'loses', 'pts', 'npxGD']

    # Columns to aggregate by mean
    mean_columns = ["PPDA", "OPPDA"]

    # Ensure numeric conversion
    for col in sum_cols + mean_columns:
        if col in df_away.columns:
            df_away[col] = pd.to_numeric(df_away[col], errors="coerce")

    # Aggregate metrics
    df_sum = df_away.groupby("team")[sum_cols].sum().round(2)
    df_mean = df_away.groupby("team")[mean_columns].mean().round(2)
    df_matches = df_away.groupby("team").size().to_frame("matches")

    # Combine results
    df_away = pd.concat([df_sum, df_mean, df_matches], axis=1)

    # Reset index
    df_away = df_away.reset_index()

    # Reorder columns
    df_away = df_away[['team', 'matches' ,'wins',	'draws'	,'loses', 'scored',	'missed', 'pts', 'xG', 'npxG' ,'xGA' ,'npxGA', 'npxGD', 'PPDA',	'OPPDA', 'deep',	'deep_allowed',	'xpts']]

    # Sort by points
    df_away.sort_values("pts", ascending=False, inplace=True)

    # Create ranking
    df_away["position"] = range(1, len(df_away) + 1)

    # Rename columns
    df_away.columns = ['team' , 'matches', 'wins', 'draws', 'loses', 'goals', 'goals_against', 'pts', 'xG', 'npxG','xGA',  'npxGA' , 'npxGDif', 'ppda', 'oppda', 'passes_completed', 'opp_passes_completed', 'xpts', 'position']

    # Build team URLs
    df_away['team_url'] = BASE_URL + 'team/' +  df_away['team'].str.replace(' ', '_') + f"/{season}"

    return df_away

#-------------------------------MATCH------------------------------------------------------------

def extract_team_info(html: str) -> dict:

    """
    Extract team name and URL from Understat HTML snippet.

    Args:
        html (str): Raw HTML containing team information.

    Returns:
        dict: Dictionary with:
            - name (str): Team name.
            - url (str): Team URL.

    Raises:
        AttributeError: If expected HTML structure is not found.
    """

    soup = BeautifulSoup(html, "html.parser")

    element = soup.find("h3").find("a")

    return { "name": element.text.strip(),"url": element["href"]}

def parse_data_squads_match(data: dict,team_side: str = "h") -> pd.DataFrame:
    """
    Parse match squad data (lineups and player stats) for a given team side.

    Args:
        data (dict): Raw match JSON from Understat API.
        team_side (str): Team side to extract ('h' for home, 'a' for away).

    Returns:
        pd.DataFrame: Player-level match statistics.

    Raises:
        KeyError: If expected structure is missing in JSON.
    """

    stats = data["rosters"][team_side]

    rows = []

    for player_id, values in stats.items():
        rows.append({
            "positionOrder": values.get("positionOrder", 0),
            "h_a": values.get("h_a", 0),
            "team_id": values.get("team_id", 0),
            "player_id": values.get("player_id", 0),
            "player": values.get("player", 0),
            "position": values.get("position", 0),
            "time": values.get("time", 0),
            "goals": values.get("goals", 0),
            "shots": values.get("shots", 0),
            "assists": values.get("assists", 0),
            "own_goals": values.get("own_goals", 0),
            "key_passes": values.get("key_passes", 0),
            "xG": values.get("xG", 0),
            "xA": values.get("xA", 0),
            "xGChain": values.get("xGChain", 0),
            "xGBuildup": values.get("xGBuildup", 0),
            "yellow_card": values.get("yellow_card", 0),
            "red_card": values.get("red_card", 0),
            "roster_in": values.get("roster_in", 0),
            "roster_out": values.get("roster_out", 0),
            "id": player_id
        })

    df = pd.DataFrame(rows)

    numeric_cols = ["xG", "xA", "xGChain", "xGBuildup"]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[numeric_cols] = df[numeric_cols].round(2)

    return df

# Extract numeric value inside progress bar
def extract_value(el):
    if not el:
        return None
    text = el.select_one(".progress-value")
    return text.get_text(strip=True) if text else None

# Extract percentage from inline style
def extract_pct(el, side):
    if not el:
        return None
    style = el.get("style", "")
    match = re.search(rf"{side}:\s*([\d\.]+)%", style)
    return round(float(match.group(1)), 2) if match else None