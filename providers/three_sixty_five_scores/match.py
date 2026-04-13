import re
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from PIL import Image
from io import BytesIO
from mplsoccer import PyPizza, add_image, VerticalPitch, Pitch
import matplotlib.pyplot as plt

from providers.three_sixty_five_scores.constants import DEFAULT_HEADERS, BASE_URL
from providers.three_sixty_five_scores.utils import get_ids, get_match_data, process_squad, get_requests_stats, get_match_time_stats

class Scores365MatchScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS
    
    def extract_match_info(self, url_match: str) -> pd.DataFrame:
        """
        Extract structured match information including teams, scores, referee, and stages.

        Args:
            url_match (str): 365Scores match URL.

        Returns:
            pd.DataFrame: Single-row DataFrame with match info.
        """
        match_data = get_match_data(url_match)
        if not match_data:
            return pd.DataFrame()  # Return empty if no data

        # Flatten match data
        df = pd.json_normalize(match_data).copy()

        # Extract date and time
        df['match_date'] = df['startTime'].str.split('T').str[0]
        df['match_time'] = df['startTime'].str.split('T').str[1].str.split('+').str[0]

        # Extract competition info safely
        competition_display = df.get('competitionDisplayName', pd.Series(['']))
        df['nation'] = competition_display.str.split(',').str[0]
        df['competition'] = competition_display.str.split(',').str[-1]

        # Drop unnecessary columns
        drop_cols = [
            'sportId', 'startTime', 'shortStatusText', 'gameTimeAndStatusDisplayType', 'justEnded', 'gameTimeDisplay', 'competitionDisplayName', 'hasLineups', 'hasMissingPlayers',
            'hasFieldPositions', 'winDescription', 'isHomeAwayInverted', 'hasStats', 'hasStandings','standingsName', 'hasBrackets', 'hasPreviousMeetings', 'hasRecentMatches', 'hasVideo',
            'hasShotChart', 'hasBets', 'hasPlayerBets', 'hasPointByPoint', 'gameStageHasTable','hasTrends', 'hasTopTrends', 'hasNews', 'preciseGameTime.minutes', 'preciseGameTime.seconds',
            'preciseGameTime.autoProgress', 'preciseGameTime.clockDirection', 'homeCompetitor.sportId','homeCompetitor.isQualified', 'homeCompetitor.toQualify', 'homeCompetitor.isWinner',
            'homeCompetitor.type', 'homeCompetitor.recentMatches', 'homeCompetitor.lineups.status','widgets', 'homeCompetitor.countryId', 'homeCompetitor.lineups.hasFieldPositions',
            'homeCompetitor.mainCompetitionId', 'homeCompetitor.imageVersion', 'awayCompetitor.imageVersion','events', 'awayCompetitor.sportId', 'awayCompetitor.isQualified', 'awayCompetitor.toQualify',
            'awayCompetitor.isWinner', 'awayCompetitor.type', 'awayCompetitor.recentMatches','awayCompetitor.lineups.status', 'awayCompetitor.countryId', 'awayCompetitor.lineups.hasFieldPositions',
            'awayCompetitor.mainCompetitionId', 'video.id', 'video.type', 'video.url', 'video.source', 'video.isEmbedded', 'video.embedElement', 'venue.googlePlaceId', 'promotedPredictions.predictions',
            'promotedPredictions.playersBetsPredictions', 'playByPlay.feedURL', 'playByPlay.previewFeedUrl','actualPlayTime.title', 'actualPlayTime.actualTime.name', 'actualPlayTime.actualTime.progress',
            'actualPlayTime.totalTime.name', 'actualPlayTime.totalTime.progress', 'topPerformers.categories','lineTypesIds', 'chartEvents.events', 'chartEvents.eventTypes', 'chartEvents.statuses',
            'chartEvents.eventSubTypes', 'homeCompetitor.lineups.statsCategory', 'awayCompetitor.lineups.statsCategory','members', 'homeCompetitor.lineups.members', 'awayCompetitor.lineups.members'
            ]
        df = df.drop(columns=drop_cols, errors='ignore')

        # Add team images
        df['home_image'] = df['homeCompetitor.id'].apply(lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_48,h_48,c_limit,q_auto:eco,dpr_3,d_Competitors:default1.png/v4/Competitors/{x}")
        df['away_image'] = df['awayCompetitor.id'].apply(lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_48,h_48,c_limit,q_auto:eco,dpr_3,d_Competitors:default1.png/v4/Competitors/{x}")

        # Extract referee info
        df_referee = pd.json_normalize(match_data.get('officials', []))
        if not df_referee.empty:
            df_referee = df_referee.drop(columns=['athleteId', 'countryId', 'status'], errors='ignore')
            df_referee = df_referee.rename(columns={'id': 'id_referee', 'name': 'referee_name', 'nameForURL': 'referee_for_url'})
            df = pd.concat([df.drop(columns=['officials'], errors='ignore'), df_referee], axis=1)

        # Extract halftime and fulltime stages
        stages_data = pd.json_normalize(match_data.get('stages', []))
        if not stages_data.empty and len(stages_data) >= 2:
            stages = [{
                'id_halftime': stages_data['id'][0],
                'name_halftime': stages_data['name'][0],
                'home_score_halftime': stages_data['homeCompetitorScore'][0],
                'away_score_halftime': stages_data['awayCompetitorScore'][0],
                'id_end_90min': stages_data['id'][1],
                'name_end_90min': stages_data['name'][1],
                'home_score_end_90min': stages_data['homeCompetitorScore'][1],
                'away_score_end_90min': stages_data['awayCompetitorScore'][1],
            }]
            df_stages = pd.DataFrame(stages)
            df = pd.concat([df.drop(columns=['stages'], errors='ignore'), df_stages], axis=1)

        return df
    
    def extract_top_performers(self, url_match: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract top performers for both teams in a match.

        Args:
            url_match (str): 365Scores match URL.

        Returns:
            tuple[pd.DataFrame, pd.DataFrame]:
                - info_top_performers: General info about top performers including player images.
                - stats_top_performers: Detailed stats for each top performer.
        """
        # Fetch match data
        match_data = get_match_data(url_match)
        top_perf_data = match_data.get('topPerformers', {}).get('categories', [])
        if not top_perf_data:
            return pd.DataFrame(), pd.DataFrame()  # Return empty if no top performers

        row_data_top_performers = pd.json_normalize(top_perf_data)

        dfs = []

        for side in ['home', 'away']:
            col_player = f'{side}Player.name'
            col_stats = f'{side}Player.stats'

            if col_player not in row_data_top_performers.columns or col_stats not in row_data_top_performers.columns:
                continue

            # Explode stats for each player
            df = row_data_top_performers[['name', col_player, col_stats]].explode(col_stats).reset_index(drop=True)

            # Expand stat dictionaries into columns
            df_stats = pd.json_normalize(df[col_stats])
            df = pd.concat([df.drop(columns=[col_stats]), df_stats], axis=1)
            df = df.rename(columns={col_player: 'player'})
            df['team'] = side
            dfs.append(df)

        stats_top_performers = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        stats_top_performers = stats_top_performers.drop(columns=['shortName', 'type'], errors='ignore')

        # Prepare general info with player images
        info_cols_to_drop = ['homePlayer.imageVersion', 'homePlayer.positionShortName', 'homePlayer.createdAt','awayPlayer.positionShortName', 'awayPlayer.createdAt', 'homePlayer.stats', 'awayPlayer.stats','awayPlayer.imageVersion']
        info_top_performers = row_data_top_performers.drop(columns=[c for c in info_cols_to_drop if c in row_data_top_performers.columns], errors='ignore')

        # Add player images safely
        if 'homePlayer.athleteId' in info_top_performers.columns:
            info_top_performers['home_player_image'] = info_top_performers['homePlayer.athleteId'].apply(
                lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_35,h_35,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v26/Athletes/{x}"
            )
        if 'awayPlayer.athleteId' in info_top_performers.columns:
            info_top_performers['away_player_image'] = info_top_performers['awayPlayer.athleteId'].apply(
                lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_35,h_35,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v26/Athletes/{x}"
            )

        return info_top_performers, stats_top_performers
    
    def extract_heatmap_match_player(self, url_match: str, player_id: int):
        """
        Extract the heatmap image of a player for a specific match.

        Args:
            url_match (str): 365Scores match URL.
            player_id (int): Player ID to retrieve the heatmap for.
            headers (dict): Optional HTTP headers for requests.

        Returns:
            PIL.Image.Image or str: Heatmap image of the player, or a message if not available.
        """
        # Fetch match data
        match_data = get_match_data(url_match)

        # Extract lineup members with heatmaps
        home_members = pd.json_normalize(match_data.get('homeCompetitor', {}).get('lineups', {}).get('members', []))
        away_members = pd.json_normalize(match_data.get('awayCompetitor', {}).get('lineups', {}).get('members', []))

        if home_members.empty and away_members.empty:
            return "No lineup or heatmap data available for this match."

        # Keep only relevant columns if they exist
        home = home_members[['id', 'heatMap']] if 'id' in home_members.columns and 'heatMap' in home_members.columns else pd.DataFrame()
        away = away_members[['id', 'heatMap']] if 'id' in away_members.columns and 'heatMap' in away_members.columns else pd.DataFrame()

        heatmaps = pd.concat([home, away], ignore_index=True)

        # Select the player's heatmap
        player_heatmap = heatmaps.loc[heatmaps['id'] == player_id, 'heatMap']

        if player_heatmap.empty or pd.isna(player_heatmap.iloc[0]):
            return "No heatmap available for this player in this match."

        # Fetch and return the heatmap image
        url = player_heatmap.iloc[0]
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        except requests.exceptions.RequestException:
            return "Failed to fetch heatmap image from URL."
        except Exception:
            return "Error opening heatmap image."
        
    def extract_lineups_and_data_match(self, url_match: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Extract lineups and detailed player stats from a match.

        Args:
            url_match (str): 365Scores match URL.

        Returns:
            tuple: (home_squad_info, home_stats, away_squad_info, away_stats)
                All elements are pandas DataFrames.
        """
        # Fetch match data
        match_data = get_match_data(url_match)

        # Process home squad
        home_squad_data = match_data.get('homeCompetitor', {}).get('lineups', {}).get('members', [])
        info_home_squad, df_stats_home = process_squad(home_squad_data)

        # Process away squad
        away_squad_data = match_data.get('awayCompetitor', {}).get('lineups', {}).get('members', [])
        info_away_squad, df_stats_away = process_squad(away_squad_data)

        return info_home_squad, df_stats_home, info_away_squad, df_stats_away
    
    def extract_match_members_squad(self, url_match: str) -> pd.DataFrame:
        """
        Extract all match members (players/staff) from a match and provide basic info with images.

        Args:
            url_match (str): 365Scores match URL.
            headers (Dict): Optional HTTP headers for requests.

        Returns:
            pd.DataFrame: DataFrame containing member info, including a URL for the player image.
        """
        # Fetch match data
        match_data = get_match_data(url_match)

        # Get members list safely
        members = match_data.get('members', [])
        if not members:
            return pd.DataFrame()

        # Normalize member data into a DataFrame
        df = pd.json_normalize(members)

        # Drop unnecessary columns
        df = df.drop(columns=['createdAt', 'imageVersion'], errors='ignore')

        # Add player image URL
        df['player_image'] = df['athleteId'].apply(lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}")

        return df
    
    def extract_shots_data(self, url_match: str) -> pd.DataFrame:
        """
        Extract all shot events from a match, including xG/xGOT and player info.

        Args:
            url_match (str): 365Scores match URL.

        Returns:
            pd.DataFrame: DataFrame containing shot events with calculated xG/xGOT, event types, 
                        match half info, and player images.
        """
        # Fetch match data
        match_data = get_match_data(url_match)

        # Normalize shot events
        df_shots = pd.json_normalize(match_data.get('chartEvents', {}).get('events', []))
        if df_shots.empty:
            return pd.DataFrame()

        # Replace '-' with '0' in xgot and convert to float
        df_shots['xgot'] = df_shots.get('xgot', '').replace('-', '0')
        df_shots[['xg', 'xgot']] = df_shots[['xg', 'xgot']].astype(float)

        # Event subtypes
        event_sub_type = pd.json_normalize(match_data.get('chartEvents', {}).get('eventSubTypes', [{}])[0])
        event_sub_type = event_sub_type.rename(columns={'id': 'id_subtype', 'value': 'subType', 'name': 'name_subtype'})

        # Event types
        event_type = pd.json_normalize(match_data.get('chartEvents', {}).get('eventTypes', []))
        event_type = event_type.rename(columns={'id': 'id_type', 'value': 'type', 'name': 'name_type'})

        # Match half / status info
        info_half = pd.json_normalize(match_data.get('chartEvents', {}).get('statuses', []))
        info_half = info_half.drop(columns=['name', 'sportTypeId', 'isExtraTime', 'isActive', 'isFinished', 'isNotStarted', 'isPenalties', 'isAbnormal', 'gameTimeForStatus','autonomicTime', 'hasEvents'], errors='ignore')
        info_half = info_half.rename(columns={'id': 'id_half', 'symbolName': 'half_symbol', 'aliasName': 'half_name'})

        # Merge shot events with half info, subtypes, and types
        df_merged = df_shots.merge(info_half, how='left', left_on='status', right_on='id_half')
        df_merged = df_merged.merge(event_sub_type, how='left', left_on='subType', right_on='subType')
        df_merged = df_merged.merge(event_type, how='left', left_on='type', right_on='type')

        # Drop redundant columns
        df_merged = df_merged.drop(columns=['status', 'type', 'subType', 'id_half', 'id_subtype', 'id_type'], errors='ignore')

        # Add player image URL
        df_merged['player_image'] = df_merged['playerId'].apply(lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}")

        return df_merged
    
    def plot_match_shotmap(self, match_url: str, save_fig: bool = False) -> None:
        """
        Plot a shot map for a 365Scores match, distinguishing shots and goals for both teams.

        Args:
            match_url (str): 365Scores match URL. Example:
                https://www.365scores.com/football/match/laliga-11/elche-villarreal-133-156-11#id=4469187
            save_fig (bool, optional): If True, saves the figure as PNG. Defaults to False.

        Returns:
            None
        """
        # Extract shots and basic match info
        shotmap = self.extract_shots_data(match_url)
        df_match_info_basic = self.extract_match_info(match_url)

        # Get team colors and names safely
        color_local = df_match_info_basic.get('homeCompetitor.color', ['blue'])[0]
        color_visit = df_match_info_basic.get('awayCompetitor.color', ['red'])[0]
        local = df_match_info_basic.get('homeCompetitor.name', ['Home'])[0]
        visit = df_match_info_basic.get('awayCompetitor.name', ['Away'])[0]

        # Initialize pitch
        fig, ax = plt.subplots(figsize=(10, 7))
        pitch = Pitch(pitch_type='opta', goal_type='box')
        pitch.draw(ax=ax)

        # Separate shots by team and outcome
        comp1 = shotmap[(shotmap['competitorNum'] == 1) & (shotmap['outcome.name'] != 'Goal')].copy()
        comp2 = shotmap[(shotmap['competitorNum'] != 1) & (shotmap['outcome.name'] != 'Goal')].copy()
        gol_comp_1 = shotmap[(shotmap['competitorNum'] == 1) & (shotmap['outcome.name'] == 'Goal')].copy()
        gol_comp_2 = shotmap[(shotmap['competitorNum'] != 1) & (shotmap['outcome.name'] == 'Goal')].copy()

        # Flip local shots to the correct half
        for df_flip in [comp1, gol_comp_1]:
            df_flip['side'] = 100 - df_flip['side']
            df_flip['line'] = 100 - df_flip['line']

        # Plot non-goal shots
        pitch.scatter(comp1.side, comp1.line, s=comp1.xg * 500, c=color_local, alpha=0.95,
                    edgecolor='black', ax=ax, label='Shot')
        pitch.scatter(comp2.side, comp2.line, s=comp2.xg * 500, c=color_visit, alpha=0.95,
                    edgecolor='black', ax=ax)

        # Plot goals
        if len(gol_comp_1) > 0:
            pitch.scatter(gol_comp_1.side, gol_comp_1.line, s=gol_comp_1.xg * 500,
                        marker='football', ax=ax, label='Goal')
        if len(gol_comp_2) > 0:
            pitch.scatter(gol_comp_2.side, gol_comp_2.line, s=gol_comp_2.xg * 500,
                        marker='football',  ax=ax, label='Goal')

        # Customize legend
        handles, labels = ax.get_legend_handles_labels()
        plt.legend(handles, labels, loc='lower center', ncol=2)
        plt.title(f'Shot Map {local} - {visit}', fontsize=12)

        # Save figure if requested
        if save_fig:
            filename = f'Shot_Map_{local}_vs_{visit}.png'
            plt.savefig(filename, bbox_inches='tight', dpi=300)

    def extract_match_events(self, url_match: str) -> pd.DataFrame:
        """
        Extracts and merges match events with player and halftime information from a 365Scores match.

        Args:
            url_match (str): 365Scores match URL.

        Returns:
            pd.DataFrame: Match events with player info, extra players, and halftime info.
        """
        # Get raw match data
        match_data = get_match_data(url_match)

        # Normalize main events
        match_events = pd.json_normalize(match_data.get('events', []))

        # Normalize halftime info
        info_half = pd.json_normalize(match_data.get('chartEvents', {}).get('statuses', []))
        info_half = info_half.drop(columns=['name', 'sportTypeId', 'isExtraTime', 'isActive', 'isFinished', 'isNotStarted','isPenalties', 'isAbnormal', 'gameTimeForStatus', 'autonomicTime', 'hasEvents'], errors='ignore')
        info_half = info_half.rename(columns={'id': 'id_half', 'symbolName': 'half_symbol', 'aliasName': 'half_name'})

        # Merge halftime info into events
        match_events = match_events.merge(info_half, how='left', left_on='statusId', right_on='id_half')

        # Drop unnecessary columns
        match_events = match_events.drop(columns=['statusId', 'stageId', 'gameTimeAndStatusDisplayType', 'gameTime', 'isMajor','num', 'eventType.subTypeId', 'eventType.subTypeName'], errors='ignore')

        # Safely extract first extra player if exists
        match_events['extraPlayers'] = match_events['extraPlayers'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else None)

        # Normalize player lineup info
        df_lineups = pd.json_normalize(match_data.get('members', []))
        df_lineups = df_lineups.drop(columns=['createdAt', 'imageVersion'], errors='ignore')
        df_lineups['player_image'] = df_lineups['athleteId'].apply(
            lambda x: f"https://imagecache.365scores.com/image/upload/f_png,w_66,h_66,c_limit,q_auto:eco,dpr_3,d_Athletes:default.png,r_max,c_thumb,g_face,z_0.65/v79/Athletes/{x}"
            )

        # Keep relevant player columns
        players = df_lineups[['id', 'name', 'shortName', 'jerseyNumber', 'nameForURL', 'player_image']]

        # Merge main player info
        match_events = match_events.merge(players, how='left', left_on='playerId', right_on='id').rename(columns={'name': 'player_name','shortName': 'player_shortName','player_image': 'player_image',
                                                                                                                'jerseyNumber': 'player_jerseyNumber', 'nameForURL': 'player_nameForURL'}).drop(columns='id', errors='ignore')
        # Merge extra player info
        match_events = match_events.merge(players, how='left', left_on='extraPlayers', right_on='id').rename(columns={'name': 'extra_player_name', 'shortName': 'extra_player_shortName','player_image': 'extra_player_image',
                                                                                                        'jerseyNumber': 'extra_player_jerseyNumber', 'nameForURL': 'extra_player_nameForURL'}).drop(columns='id', errors='ignore')

        return match_events
    
    def extract_match_time_stats(self, match_url: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract detailed match time stats and wasted time stats.

        Args:
            match_url (str): 365Scores match URL.

        Returns:
            Tuple[pd.DataFrame, pd.DataFrame]: 
                - DataFrame with general time statistics (playtime, stops, added time, etc.)
                - DataFrame with comparative stats on wasted time
        """
        # Get actual time statistics
        game_data_time = get_match_time_stats(match_url)
        row_data_time = pd.json_normalize(game_data_time)

        # Extract general time info
        all_data = []
        try:
            all_data.append({
                'actual_playtime': row_data_time.get('actualPlayTime.actualTime.name', [''])[0].split(' ')[-1],
                'total_playtime': row_data_time.get('actualPlayTime.totalTime.name', [''])[0].split(' ')[-1],
                'game_stops': row_data_time.get('general', [[]])[0][0].get('value') if row_data_time.get('general', [[]])[0] else None,
                'longest_in_play': row_data_time.get('general', [[]])[0][1].get('value') if len(row_data_time.get('general', [[]])[0]) > 1 else None,
                'added_time_announced': row_data_time.get('addedTime.stats', [[{}]])[0][0].get('value'),
                'added_time_actual_added': row_data_time.get('addedTime.stats', [[{}]])[0][1].get('value'),
                'added_time_played': row_data_time.get('addedTime.stats', [[{}]])[0][2].get('value'),
            })
        except Exception as e:
            print("Warning: Could not extract all general time stats.", e)

        time_dataframe = pd.DataFrame(all_data)

        # Extract comparative wasted time stats
        df_comparative_time_wasted_on = pd.DataFrame()
        try:
            df_comparative_time_wasted_on = pd.json_normalize(row_data_time.get('wastedTime.stats', [])[0])
            df_comparative_time_wasted_on = df_comparative_time_wasted_on.drop(columns=['isMajor', 'isPrimary', 'isTop'], errors='ignore')
        except Exception as e:
            print("Warning: Could not extract comparative wasted time stats.", e)

        return time_dataframe, df_comparative_time_wasted_on
    
    
    def extract_match_stats(self, match_url: str) -> pd.DataFrame:
        """
        Extract match statistics from a 365Scores match URL.

        Args:
            match_url (str): 365Scores match URL.

        Returns:
            pd.DataFrame: DataFrame containing match statistics, with unnecessary columns removed.
        """
        try:
            # Request match stats
            response = get_requests_stats(match_url)
            data = response.json()
            
            # Extract 'statistics' section safely
            statistics = data.get('statistics', [])
            
            # Normalize JSON into DataFrame
            df_stats = pd.json_normalize(statistics)
            
            # Drop unnecessary columns if they exist
            df_stats = df_stats.drop(columns=['isPrimary', 'isMajor'], errors='ignore')
            
            return df_stats
        except Exception as e:
            print(f"Warning: Could not extract match statistics for URL {match_url}. Error: {e}")
            return pd.DataFrame()