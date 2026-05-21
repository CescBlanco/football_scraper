import pandas as pd
from typing import Union

from football_scraper.providers.sofascore.constants import DEFAULT_HEADERS, BASE_URL
from football_scraper.providers.sofascore.utils import sofascore_requests, safe_expand

class SofascoreManagerScraper:
    def __init__(self, session,  headers=None):
        self.session = session
        self.headers = headers if headers else DEFAULT_HEADERS

    def extract_manager_details(self, id_manager_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract detailed information for a manager from SofaScore API.

        Args:
            id_manager_sofascore (Union[str, int]):
                Manager identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If 'manager' field is missing in API response.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - personal info
                - nationality and country
                - team info
                - performance stats
        """

        api = f"https://www.sofascore.com/api/v1/manager/{id_manager_sofascore}"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for manager={id_manager_sofascore}")

        if "manager" not in json_data:
            raise KeyError("Missing 'manager' in API response")

        manager = json_data.get("manager", {})

        if not isinstance(manager, dict):
            raise ValueError("'manager' must be a dictionary")

        details_row = pd.DataFrame([manager])

        base_cols = [ 'id','name','slug','shortName','country','preferredFormation','team','nationality','performance','dateOfBirthTimestamp']

        details_clean = details_row.reindex(columns=base_cols).copy()

        # -----------------------------
        # Date
        # -----------------------------
        if 'dateOfBirthTimestamp' in details_clean.columns:
            details_clean['birthdate'] = pd.to_datetime(details_clean['dateOfBirthTimestamp'], unit='s', errors='coerce').dt.date

        # -----------------------------
        # Expand nested
        # -----------------------------
        details_clean = pd.concat([
                details_clean.drop(['country','team','performance'], axis=1, errors='ignore'),
                safe_expand(details_clean, 'country', 'country_'),
                safe_expand(details_clean, 'team', 'team_'),
                safe_expand(details_clean, 'performance', 'performance_'),
            ], axis=1)

        # -----------------------------
        # Final columns
        # -----------------------------
        final_cols = [
            'id','name','slug','shortName','birthdate','country_name','nationality','country_alpha2','preferredFormation',
            'team_name','team_slug','team_shortName','team_nameCode','team_id','performance_total','performance_wins','performance_draws',
            'performance_losses','performance_goalsScored','performance_goalsConceded','performance_totalPoints'
            ]

        details_clean = details_clean.reindex(columns=final_cols)
        details_clean['manager_photo'] = f"https://img.sofascore.com/api/v1/manager/" + str(details_clean['id']) +'/image'
        return details_clean   

    def extract_career_history_manager(self, id_manager_sofascore: Union[str, int]) -> pd.DataFrame:
        """
        Extract career history for a manager from SofaScore API.

        Args:
            id_manager_sofascore (Union[str, int]):
                Manager identifier in SofaScore.

        Raises:
            ValueError:
                If API response is empty or invalid.
            KeyError:
                If required fields are missing.

        Returns:
            pd.DataFrame:
                DataFrame containing:
                - team history
                - performance stats
                - start and end dates
        """

        api = f"https://www.sofascore.com/api/v1/manager/{id_manager_sofascore}/career-history"
        json_data = sofascore_requests(api)

        # -----------------------------
        # Hard failure
        # -----------------------------
        if not json_data:
            raise ValueError(f"No API response for manager={id_manager_sofascore}")

        if "careerHistory" not in json_data:
            raise KeyError("Missing 'careerHistory' in API response")

        data = json_data["careerHistory"]

        if not isinstance(data, list):
            raise ValueError("'careerHistory' must be a list")

        if len(data) == 0:
            return pd.DataFrame()

        careerHistory = pd.DataFrame(data)

        # -----------------------------
        # Expand nested
        # -----------------------------
        careerHistory = pd.concat([
                careerHistory.drop(['team','performance'], axis=1, errors='ignore'),
                safe_expand(careerHistory, 'team', 'team_'),
                safe_expand(careerHistory, 'performance', 'performance_'),
            ], axis=1)

        # -----------------------------
        # Dates
        # -----------------------------
        if 'startTimestamp' in careerHistory.columns:
            careerHistory['start_period'] = pd.to_datetime(careerHistory['startTimestamp'], unit='s', errors='coerce').dt.date

        if 'endTimestamp' in careerHistory.columns:
            careerHistory['end_period'] = pd.to_datetime( careerHistory['endTimestamp'], unit='s', errors='coerce').dt.date

        # -----------------------------
        # Final columns
        # -----------------------------
        final_cols = ['team_name','team_slug','team_shortName','team_nameCode','team_id','team_ranking','performance_total',
                    'performance_wins','performance_draws','performance_losses','performance_totalPoints','start_period','end_period']

        return careerHistory.reindex(columns=final_cols)    