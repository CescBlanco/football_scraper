from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

import re
import requests
import json

from providers.scoresway.constants import DEFAULT_HEADERS

#----------------------------------------------DRIVE SELENIUM---------------------------------------------
def _create_driver():
    """
    Create and configure a Selenium Chrome WebDriver instance.

    This function initializes a Chrome browser in headless mode with
    anti-detection configurations commonly used for web scraping tasks.

    Returns
    -------
    webdriver.Chrome
        Configured Selenium Chrome WebDriver instance.

    Raises
    ------
    RuntimeError
        If the Chrome WebDriver cannot be initialized.
    """

    try:
        # Configure Chrome browser options
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")

        # Prevent Selenium detection by websites
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Set a realistic browser user-agent
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # Automatically install and configure ChromeDriver
        service = Service(ChromeDriverManager().install())

        # Create WebDriver instance
        driver = webdriver.Chrome(service=service, options=options)

        # Hide webdriver property from browser detection scripts
        driver.execute_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
        """)

        return driver

    except Exception as e:
        raise RuntimeError(f"Failed to create Chrome WebDriver: {str(e)}")
    
#----------------------------------------------RESPONSE BEAUTIFUL---------------------------------------------
def _create_response(url_api: str):
    """
    Send a request to the PerformFeeds API and parse the JSONP response.

    This function performs an HTTP GET request to the provided API URL,
    extracts the JSON object from the JSONP wrapper, and converts it
    into a Python dictionary.

    Parameters
    ----------
    url_api : str
        Complete API endpoint URL.

    Returns
    -------
    dict
        Parsed JSON response as a Python dictionary.

    Raises
    ------
    TypeError
        If url_api is not a string.
    ValueError
        If:
        - url_api is empty.
        - the API response format is invalid.
        - JSON data cannot be extracted.
    RuntimeError
        If the HTTP request or JSON parsing fails.
    """

    try:
        # ------------------------
        # VALIDATE INPUT
        # ------------------------
        if not isinstance(url_api, str):
            raise TypeError("url_api must be a string")

        if not url_api.strip():
            raise ValueError("url_api cannot be empty")

        # ------------------------
        # SEND API REQUEST
        # ------------------------
        r = requests.get(url_api, headers=DEFAULT_HEADERS)
        if r.status_code != 200:
            raise RuntimeError(f"API request failed with status code {r.status_code}")
        text = r.text

        # ------------------------
        # EXTRACT JSON FROM JSONP
        # ------------------------
        match = re.search(r'\((.*)\)', text)
        if not match:
            raise ValueError("Invalid JSONP response format")

        data = match.group(1)

        # ------------------------
        # PARSE JSON DATA
        # ------------------------
        json_data = json.loads(data)
        if not isinstance(json_data, dict):
            raise ValueError("Parsed response is not a valid JSON object")

        return json_data

    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to decode JSON response: {str(e)}")

    except requests.RequestException as e:
        raise RuntimeError(f"HTTP request failed: {str(e)}")

    except Exception as e:
        raise RuntimeError( f"Failed to create API response: {str(e)}")
    
#----------------------------------------------PLAYER---------------------------------------------

