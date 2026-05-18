import requests
from bs4 import BeautifulSoup
import pandas as pd
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (NoSuchElementException,TimeoutException, WebDriverException)

from providers.scoresway.utils import _create_response

class ScoreswayPreMatchScraper:
    def __init__(self, session: requests.Session):
        self.session = session
    