import requests
import pandas as pd

from providers.scoresway.utils import _create_response, normalize_label, build_qualifier_mapping
from providers.scoresway.data_opta.loaders import load_events_ids, load_qualifiers

class ScoreswayEventsMatchScraper:
    def __init__(self, session: requests.Session):
        self.session = session,
        self.events_ids = load_events_ids()
        self.qualifiers= load_qualifiers()

        self.event_mapping = dict(
            zip(
                self.events_ids["Code"].astype(str),
                self.events_ids["Event"].apply(normalize_label)
            )
        )

        self.qualifier_mapping = build_qualifier_mapping(self.qualifiers)

    def extract_and_build_events(self, url: str) -> pd.DataFrame:

        """
        Extract and build match events from PerformFeeds API.

        This function retrieves event-level match data using a Scoresway
        post-match URL, maps event types using a reference DataFrame,
        and returns a structured events DataFrame.

        Parameters
        ----------
        url : str
            Scoresway post-match URL used to identify the match.

        Returns
        -------
        pd.DataFrame
            Cleaned events dataset with enriched metadata:
            - team info
            - event type labels
            - period mapping
            - coordinates and qualifiers

        Raises
        ------
        TypeError
            If url is not a string.
        ValueError
            If url is empty or API response is invalid.
        RuntimeError
            If extraction or processing fails.
        """
        try:
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
            
            api= f"https://api.performfeeds.com/soccerdata/matchevent/ft1tiv1inq7v1sk3y9tv12yh5/{match_id}?_rt=c&_lcl=en&_fmt=jsonp&sps=widgets&_clbk=W3093b991cfeafd603690c56bd7caa5b60ffd19bfc"

            # ------------------------
            # REQUEST API RESPONSE
            # ------------------------
            json_data = _create_response(api)
            if not isinstance(json_data, dict):
                raise ValueError("Invalid API response format")
            
            # ------------------------
            # VALIDATE STRUCTURE
            # ------------------------
            if "matchInfo" not in json_data or "contestant" not in json_data["matchInfo"]:
                raise ValueError("matchInfo/contestant not found in API response")

            if "liveData" not in json_data or "event" not in json_data["liveData"]:
                raise ValueError("liveData/event not found in API response")

            # =========================
            # TEAMS
            # =========================
            contestants = pd.DataFrame(json_data['matchInfo']['contestant'])

            id_to_side = dict(zip(contestants['id'], contestants['position']))
            id_to_name = dict(zip(contestants['id'], contestants['name']))

            # -------------------------
            # events
            # -------------------------
            events = pd.json_normalize(json_data['liveData']['event'])

            # team info
            events['teamSide'] = events['contestantId'].map(id_to_side)
            events['teamName'] = events['contestantId'].map(id_to_name)

            # outcome
            events['outcome'] = events['outcome'].replace({0: 'Unsuccessful', 1: 'Successful'})

            # periodos
            events['periodId'] = events['periodId'].replace({1: 'FirstHalf',2: 'SecondHalf',3: 'FirstExtraHalf',4: 'SecondExtraHalf',5: 'PenaltyShootout', 14: 'PostGame', 16: 'PreMatch'})

            # map event types
            events["event_type"] = (events["typeId"].astype(str).map(self.event_mapping) )


            # keep useful cols
            keep_cols = ["id","eventId","event_type","periodId","timeMin","timeSec","contestantId", "teamName", "teamSide", "playerId", "playerName", "outcome", "x", "y", "qualifier"]

            return events[keep_cols].copy()
        
        except Exception as e:
                raise RuntimeError(f"Failed to extract events from URL '{url}': {str(e)}")

    def expand_events(self, events_df: pd.DataFrame, event_type: str) -> pd.DataFrame:
        """
        Expand event qualifiers into structured columns for a specific event type.

        This function filters events by type, decodes qualifier metadata,
        and expands it into a flat tabular structure.

        Parameters
        ----------
        events_df : pd.DataFrame
            Raw events DataFrame.

        event_type : str
            Event type to filter (normalized label).

        Returns
        -------
        pd.DataFrame
            Expanded events DataFrame with qualifiers as columns.

        Raises
        ------
        TypeError
            If inputs are not of expected types.
        ValueError
            If required columns are missing or filtering fails.
        RuntimeError
            If expansion process fails.
        """
        try:
            # ------------------------
            # VALIDATE INPUT
            # ------------------------
            if not isinstance(events_df, pd.DataFrame):
                raise TypeError("events_df must be a pandas DataFrame")

            if not isinstance(event_type, str):
                raise TypeError("event_type must be a string")
            

            # ------------------------
            # FILTER EVENTS
            # ------------------------
            df = events_df[events_df["event_type"] == event_type].copy()
            if df.empty:
                raise ValueError(f"No events found for event_type='{event_type}'")

            # ------------------------
            # PARSE QUALIFIERS
            # ------------------------
            def build_qualifier_dict(lst: list):
                """
                Convert a list of qualifier objects into a flat dictionary.

                This function maps qualifier IDs to human-readable names
                using a provided mapping dictionary, and extracts their values.

                Parameters
                ----------
                lst : list
                    List of qualifier dictionaries from the API.

                Returns
                -------
                dict
                    Flattened dictionary of qualifiers:
                    {qualifier_name: value}
                """
                if not isinstance(lst, list):
                    return {}

                result = {}

                for q in lst:

                    qid = q.get("qualifierId")

                    qname = self.qualifier_mapping.get(qid)

                    if qname:

                        value = q.get("value", True)

                        result[qname] = value

                return result

            # ------------------------
            # EXPAND QUALIFIERS
            # ------------------------
            qual_df = pd.json_normalize(df["qualifier"].apply(build_qualifier_dict) )
            df = pd.concat( [df.drop(columns="qualifier").reset_index(drop=True),qual_df.reset_index(drop=True)],axis=1)

            # ------------------------
            # NUMERIC CONVERSION
            # ------------------------
            numeric_cols = ["x", "y", "timeMin", "timeSec"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            return df
        
        except Exception as e:
            raise RuntimeError(f"Failed to expand events for event_type='{event_type}': {str(e)}")