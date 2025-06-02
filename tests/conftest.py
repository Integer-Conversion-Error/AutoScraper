import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Configuration
APP_URL = "http://localhost:5000"  # Adjust if your app runs on a different URL
LOGIN_URL = APP_URL + "/login"
TEST_USER_EMAIL = "barack.obama@us.gov"
TEST_USER_PASSWORD = "test123"
LOGGED_IN_USER_IDENTIFIER = "Obama Barack"

@pytest.fixture(scope="module")
def driver():
    # Setup WebDriver (Chrome in this example)
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Temporarily removed for visual debugging
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,800")
    
    _driver = webdriver.Chrome(options=options)
    
    # Perform login
    _driver.get(LOGIN_URL)
    wait = WebDriverWait(_driver, 20) # Increased wait time for login page elements

    # Wait for email field and enter email
    email_field = wait.until(EC.visibility_of_element_located((By.ID, "signinEmail")))
    email_field.send_keys(TEST_USER_EMAIL)

    # Wait for password field and enter password
    password_field = wait.until(EC.visibility_of_element_located((By.ID, "signinPassword")))
    password_field.send_keys(TEST_USER_PASSWORD)

    # Wait for sign-in button to be clickable and click it
    signin_button = wait.until(EC.element_to_be_clickable((By.ID, "signinBtn")))
    signin_button.click()

    # After clicking login, Firebase auth happens client-side, then a form is submitted.
    # We need to wait for the redirect to the main app page.
    # A good indicator of successful login and redirect is the presence of an element
    # from the main app page, e.g., the "Search Parameters" card header or the page title.
    # Or, wait for the URL to change from /login.
    wait.until(EC.url_changes(LOGIN_URL)) # Wait for URL to change from login page
    
    # Explicitly wait for the URL to become the app interface URL
    wait.until(EC.url_to_be(APP_URL + "/app"))
    
    # Add a small fixed delay to allow client-side JS to settle after redirect
    time.sleep(5) # Increased sleep to 5 seconds

    # Additional wait to ensure the main app page (e.g., /app_interface) is loaded
    # We'll check for the title of the main app page.
    wait.until(EC.title_contains("AutoScraper Web Interface"))
    
    print(f"DEBUG: Current URL before checking element: {_driver.current_url}")
    print(f"DEBUG: Page title before checking element: {_driver.title}")
    # Try to get page source for debugging
    try:
        print("DEBUG: Attempting to get page source...")
        page_source = _driver.page_source
        if "Search Parameters" in page_source:
            print("DEBUG: 'Search Parameters' found in page source.")
        else:
            print("DEBUG: 'Search Parameters' NOT found in page source. Dumping source (first 2000 chars):")
            print(page_source[:2000])
        if "Payload Management" in page_source: # Check for another key element
            print("DEBUG: 'Payload Management' found in page source.")
        else:
            print("DEBUG: 'Payload Management' NOT found in page source.")
        if "Saved Results Management" in page_source:
            print("DEBUG: 'Saved Results Management' found in page source.")
        else:
            print("DEBUG: 'Saved Results Management' NOT found in page source.")
    except Exception as e:
        print(f"DEBUG: Could not get page source: {e}")

    # Also, wait for a key element of the main page to be present in the DOM
    # Using contains(., 'text') which checks the string value of the node (including descendants)
    # Increased timeout for this specific crucial element
    WebDriverWait(_driver, 30).until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Search Parameters')]")))
    print("DEBUG: Element whose string value contains 'Search Parameters' found in DOM by presence check.")

    yield _driver
    # Teardown
    _driver.quit()
