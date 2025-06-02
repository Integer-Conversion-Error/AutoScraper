import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# The driver fixture is now in conftest.py and will be automatically discovered by pytest.

def test_page_title(driver):
    """I.1. Verify that the page title is 'AutoScraper Web Interface'."""
    WebDriverWait(driver, 10).until(EC.title_contains("AutoScraper Web Interface"))
    assert "AutoScraper Web Interface" in driver.title

def test_main_sections_presence(driver):
    """I.2. Verify main sections are present in the DOM."""
    wait = WebDriverWait(driver, 20)

    # Search Parameters Card - Using normalize-space() for robustness
    search_params_header = wait.until(EC.presence_of_element_located((By.XPATH, "//h5[contains(normalize-space(.), 'Search Parameters')]/ancestor::div[contains(@class, 'card-header')][1]")))
    assert search_params_header is not None

    # Payload Management Card - Using normalize-space()
    payload_mgmt_header = wait.until(EC.presence_of_element_located((By.XPATH, "//h5[contains(normalize-space(.), 'Payload Management')]/ancestor::div[contains(@class, 'card-header')][1]")))
    assert payload_mgmt_header is not None
    
    # Saved Results Management Card - Using normalize-space()
    saved_results_header = wait.until(EC.presence_of_element_located((By.XPATH, "//h5[contains(normalize-space(.), 'Saved Results Management')]/ancestor::div[contains(@class, 'card-header')][1]")))
    assert saved_results_header is not None

    # Current Search Results Card - Using normalize-space()
    current_results_header = wait.until(EC.presence_of_element_located((By.XPATH, "//h5[contains(normalize-space(.), 'Current Search Results')]/ancestor::div[contains(@class, 'card-header')][1]")))
    assert current_results_header is not None

def test_navbar_elements_presence(driver):
    """I.3. Verify navbar elements are present."""
    wait = WebDriverWait(driver, 10)
    LOGGED_IN_USER_IDENTIFIER = "Obama Barack" # Defined here for this test file

    # Navbar Brand/Logo
    navbar_brand = wait.until(EC.visibility_of_element_located((By.XPATH, "//a[@class='navbar-brand' and contains(., 'AutoScraper Web')]")))
    assert navbar_brand.is_displayed()
    assert "AutoScraper Web" in navbar_brand.text

    # User Dropdown (checking for the dropdown toggle itself)
    user_dropdown_toggle = wait.until(EC.visibility_of_element_located((By.ID, "userDropdown")))
    assert user_dropdown_toggle.is_displayed()
    # Verify the logged-in user's identifier (email in this case) is in the dropdown text
    assert LOGGED_IN_USER_IDENTIFIER in user_dropdown_toggle.text

    # Tokens Display
    token_display = wait.until(EC.visibility_of_element_located((By.ID, "tokenCountDisplay")))
    assert token_display.is_displayed()
    assert "Tokens:" in token_display.text
    token_value_span = driver.find_element(By.ID, "tokenValue")
    assert token_value_span.is_displayed()
