import pandas as pd
from pathlib import Path

BASE_PATH = Path(__file__).resolve().parent


def load_events_ids():
    return pd.read_excel(BASE_PATH / "Opta Events.xlsx")


def load_qualifiers():
    return pd.read_excel(BASE_PATH / "Opta Qualifiers.xlsx")