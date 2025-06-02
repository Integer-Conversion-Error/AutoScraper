import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException # Added for more specific exception handling

import time
import datetime # Added for generating unique names

# Configuration
APP_URL = "http://localhost:5000"  # Adjust if your app runs on a different URL
LOGIN_URL = APP_URL + "/login"
TEST_USER_EMAIL = "example@example.ca"
TEST_USER_PASSWORD = "esad123"
# The user dropdown seems to display "esad" for this user.
LOGGED_IN_USER_IDENTIFIER = "esad"


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

def test_page_title(driver):
    """I.1. Verify that the page title is 'AutoScraper Web Interface'."""
    # The driver fixture now handles login and ensures we are on the main page.
    # So, this assertion should pass if login was successful and title is correct.
    WebDriverWait(driver, 10).until(EC.title_contains("AutoScraper Web Interface"))
    assert "AutoScraper Web Interface" in driver.title

def test_main_sections_presence(driver):
    """I.2. Verify main sections are present in the DOM."""
    wait = WebDriverWait(driver, 20) # Keep increased wait time

    # Search Parameters Card - Using normalize-space() for robustness
    search_params_header = wait.until(EC.presence_of_element_located((By.XPATH, "//h5[contains(normalize-space(.), 'Search Parameters')]/ancestor::div[contains(@class, 'card-header')][1]")))
    assert search_params_header is not None # If found, it's not None

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

# To run these tests:
# 1. Make sure you have pytest and selenium installed:
#    pip install pytest selenium
# 2. Download ChromeDriver (or your browser's driver) and ensure it's in your PATH
#    or specify its path in webdriver.Chrome().
# 3. Navigate to the directory containing this file and run:
#    pytest
#
# Note: These tests assume the application is running and accessible at APP_URL.
# For tests requiring a logged-in state (like verifying a specific username),
# you would typically add a login fixture or steps.

def test_makes_dropdown_populated(driver):
    """I.4. Verify that the 'Make' dropdown is populated with options."""
    wait = WebDriverWait(driver, 20) # Increased wait time for dynamic content

    # Locate the 'Make' select element
    make_dropdown = wait.until(EC.presence_of_element_located((By.ID, "makeSelect")))
    
    # Wait for the options to be populated (more than just the default "Select Make")
    # We expect at least one actual make to be loaded in addition to the placeholder.
    # A common pattern is to have a default "Select..." option, so > 1 means it's populated.
    wait.until(lambda d: len(make_dropdown.find_elements(By.TAG_NAME, "option")) > 1)
    
    # Assert that there is more than one option (i.e., it's populated beyond the default)
    options = make_dropdown.find_elements(By.TAG_NAME, "option")
    assert len(options) > 1
    
    # Optional: You could also check if the first option is "Select Make"
    # and that subsequent options have non-empty values.
    assert options[0].text == "Select Make"
    # Example: Check if there's at least one make with a non-empty value
    assert any(opt.get_attribute("value") != "" for opt in options[1:])
    print(f"DEBUG: Found {len(options)} options in 'Make' dropdown. First option: '{options[0].text}'.")
    print("DEBUG: Makes dropdown content:")
    for option in options:
        print(f"  - Text: '{option.text}', Value: '{option.get_attribute('value')}'")

def test_models_dropdown_populates_after_make_selection(driver):
    """I.5. Verify that the 'Model' dropdown populates after selecting a 'Make'."""
    wait = WebDriverWait(driver, 20)

    # Locate the 'Make' select element and ensure it's populated
    make_dropdown = wait.until(EC.presence_of_element_located((By.ID, "makeSelect")))
    wait.until(lambda d: len(make_dropdown.find_elements(By.TAG_NAME, "option")) > 1)
    
    # Select a specific make (e.g., "Acura"). This relies on "Acura" being an option.
    # If "Acura" is not available, this test will fail, which is acceptable.
    try:
        make_select = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "makeSelect"))
        )
        # Iterate through options to find and click "Acura"
        # Using Select class is more robust for dropdowns
        from selenium.webdriver.support.ui import Select
        select_make = Select(make_select)
        select_make.select_by_visible_text("Acura") 
        print(f"DEBUG: Selected 'Acura' from Make dropdown.")
    except Exception as e:
        print(f"DEBUG: Could not select 'Acura'. Available makes:")
        options = make_dropdown.find_elements(By.TAG_NAME, "option")
        for opt in options:
            print(f"  - Text: '{opt.text}', Value: '{opt.get_attribute('value')}'")
        pytest.fail(f"Failed to select 'Acura' from Make dropdown: {e}")

    # Locate the 'Model' select element
    model_dropdown = wait.until(EC.presence_of_element_located((By.ID, "modelSelect")))
    
    # Wait for the 'Model' dropdown to be populated (more than just "Select Model")
    # The 'change' event on 'makeSelect' should trigger loading models.
    wait.until(lambda d: len(model_dropdown.find_elements(By.TAG_NAME, "option")) > 1)
    
    # Assert that there is more than one option in the 'Model' dropdown
    model_options = model_dropdown.find_elements(By.TAG_NAME, "option")
    assert len(model_options) > 1
    
    # Optional: Check that the first option is "Select Model"
    assert model_options[0].text == "Select Model"
    # Example: Check if there's at least one model with a non-empty value
    assert any(opt.get_attribute("value") != "" for opt in model_options[1:])
    
    print(f"DEBUG: Found {len(model_options)} options in 'Model' dropdown after selecting a Make.")
    print("DEBUG: Models dropdown content:")
    for option in model_options:
        print(f"  - Text: '{option.text}', Value: '{option.get_attribute('value')}'")

def test_trim_and_color_dropdowns_populate_after_model_selection(driver):
    """I.6. Verify that 'Trim' and 'Color' dropdowns populate after selecting a 'Model'."""
    wait = WebDriverWait(driver, 20)
    from selenium.webdriver.support.ui import Select
    select_helper = Select  

    # --- Step 1: Select a Make ---
    make_dropdown_element = wait.until(EC.presence_of_element_located((By.ID, "makeSelect")))
    wait.until(lambda d: len(make_dropdown_element.find_elements(By.TAG_NAME, "option")) > 1)
    
    try:
        make_select = select_helper(make_dropdown_element)
        make_select.select_by_visible_text("Acura") # Assuming "Acura" is a valid make
        print(f"DEBUG: Selected 'Acura' from Make dropdown.")
    except Exception as e:
        options = make_dropdown_element.find_elements(By.TAG_NAME, "option")
        available_makes = [opt.text for opt in options]
        print(f"DEBUG: Could not select 'Acura'. Available makes: {available_makes}")
        pytest.fail(f"Failed to select 'Acura' from Make dropdown: {e}. Available: {available_makes}")

    # --- Step 2: Select a Model ---
    model_dropdown_element = wait.until(EC.presence_of_element_located((By.ID, "modelSelect")))
    # Wait for models to populate after make selection
    wait.until(lambda d: len(model_dropdown_element.find_elements(By.TAG_NAME, "option")) > 1)
    
    try:
        model_select = select_helper(model_dropdown_element)
        # Attempt to select a common Acura model. If "ILX" isn't present, the test might need adjustment
        # or a more dynamic way to pick a model. For now, we'll assume "ILX" or a similar common model exists.
        # Let's try to pick the first available model that isn't the placeholder
        model_options_list = model_dropdown_element.find_elements(By.TAG_NAME, "option")
        first_valid_model_text = next((opt.text for opt in model_options_list if opt.get_attribute("value") != ""), None)
        
        if not first_valid_model_text:
            pytest.fail("No valid model found to select after choosing 'Acura'.")
            
        model_select.select_by_visible_text(first_valid_model_text)
        print(f"DEBUG: Selected '{first_valid_model_text}' from Model dropdown.")
    except Exception as e:
        options = model_dropdown_element.find_elements(By.TAG_NAME, "option")
        available_models = [opt.text for opt in options]
        print(f"DEBUG: Could not select a model for 'Acura'. Available models: {available_models}")
        pytest.fail(f"Failed to select a model from Model dropdown: {e}. Available: {available_models}")

    # --- Step 3: Verify Trim Dropdown Populates ---
    # Assuming the ID for the trim dropdown is 'trimSelect'
    trim_dropdown_element = wait.until(EC.presence_of_element_located((By.ID, "trimSelect")))
    
    # Wait for the 'Trim' dropdown to be populated (more than just "Select Trim" or "Any Trim")
    wait.until(lambda d: len(trim_dropdown_element.find_elements(By.TAG_NAME, "option")) > 1)
    
    trim_options = trim_dropdown_element.find_elements(By.TAG_NAME, "option")
    assert len(trim_options) > 1, "Trim dropdown did not populate with more than one option."
    
    # Check that the first option is a placeholder like "Select Trim" or "Any Trim"
    # and that subsequent options have non-empty values if applicable.
    # The exact text of the placeholder might vary.
    # assert trim_options[0].text in ["Select Trim", "Any Trim"] 
    print(f"DEBUG: Found {len(trim_options)} options in 'Trim' dropdown. First option: '{trim_options[0].text}'.")
    print("DEBUG: Trim dropdown content:")
    for option in trim_options:
        print(f"  - Text: '{option.text}', Value: '{option.get_attribute('value')}'")
    assert any(opt.get_attribute("value") != "" for opt in trim_options if opt.text not in ["Select Trim", "Any Trim", "All Trims"]), "No valid trim options found."


    # --- Step 4: Verify Color Dropdown Populates ---
    # Assuming the ID for the color dropdown is 'colorSelect'
    color_dropdown_element = wait.until(EC.presence_of_element_located((By.ID, "colorSelect")))
    
    # Wait for the 'Color' dropdown to be populated (more than just "Select Color" or "Any Color")
    wait.until(lambda d: len(color_dropdown_element.find_elements(By.TAG_NAME, "option")) > 1)
    
    color_options = color_dropdown_element.find_elements(By.TAG_NAME, "option")
    assert len(color_options) > 1, "Color dropdown did not populate with more than one option."
    
    # Similar check for placeholder and valid options
    # assert color_options[0].text in ["Select Color", "Any Color"]
    print(f"DEBUG: Found {len(color_options)} options in 'Color' dropdown. First option: '{color_options[0].text}'.")
    print("DEBUG: Color dropdown content:")
    for option in color_options:
        print(f"  - Text: '{option.text}', Value: '{option.get_attribute('value')}'")
    assert any(opt.get_attribute("value") != "" for opt in color_options if opt.text not in ["Select Color", "Any Color", "All Colors"]), "No valid color options found."

# --- Helper Functions for Payload Tests ---

def generate_unique_name(base_name):
    """Generates a unique name by appending a timestamp."""
    return f"{base_name}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def check_notification(driver, expected_text, timeout=10):
    """Waits for and verifies the notification message."""
    try:
        notification_content = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.ID, "notification-content"))
        )
        # Wait for text to be present in the element
        WebDriverWait(driver, timeout).until(
            EC.text_to_be_present_in_element((By.ID, "notification-content"), expected_text)
        )
        actual_text = notification_content.text
        assert expected_text in actual_text, f"Notification text '{actual_text}' did not contain '{expected_text}'"
        print(f"DEBUG: Notification found: '{actual_text}'")
    except TimeoutException:
        print(f"DEBUG: Notification with text '{expected_text}' not found within {timeout}s. Current notification: {driver.find_element(By.ID, 'notification-content').text if EC.visibility_of_element_located((By.ID, 'notification-content')) else 'not visible'}")
        raise

def check_option_in_select(driver, select_id, option_text, should_exist=True, timeout=10):
    """Checks if an option with specific text exists (or not) in a select dropdown."""
    try:
        select_element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.ID, select_id))
        )
        
        if not should_exist:
            # Poll for the option to disappear
            start_time = time.time()
            while time.time() - start_time < timeout:
                current_options = select_element.find_elements(By.TAG_NAME, "option")
                still_found = any(option.text.strip() == option_text.strip() for option in current_options)
                if not still_found:
                    print(f"DEBUG: Option '{option_text}' correctly not found in '{select_id}' after polling.")
                    assert not still_found # This will pass, confirming absence
                    return # Successfully verified absence
                time.sleep(0.5) # Polling interval
            # If loop finishes, option was still there, get final list for error message
            final_options_texts = [o.text.strip() for o in select_element.find_elements(By.TAG_NAME, "option")]
            pytest.fail(f"Option '{option_text}' was still present in select '{select_id}' after {timeout}s. Options: {final_options_texts}")
        else:
            # Original logic for should_exist=True (option should be present)
            # Wait a bit for options to populate if they are dynamically loaded.
            time.sleep(1) # Consider if this fixed delay is always needed or if a WebDriverWait for options > 1 is better.
                          # For now, keeping it as it was for this specific case.
            options = select_element.find_elements(By.TAG_NAME, "option")
            found = any(option.text.strip() == option_text.strip() for option in options)
            assert found, f"Option '{option_text}' not found in select '{select_id}'. Options: {[o.text for o in options]}"
            print(f"DEBUG: Option '{option_text}' found in '{select_id}'.")
            
    except TimeoutException:
        # If the select element itself is not found.
        # If we expected the option *not* to exist, and the whole select is gone, that could be valid in some contexts.
        # However, this function's purpose is to check *options within a select*.
        # If should_exist was True, it's a clear fail.
        # If should_exist was False, it's ambiguous: option is gone, but because parent is gone.
        # For now, failing consistently if select_id is not found.
        pytest.fail(f"Select element with ID '{select_id}' not found within {timeout}s.")
    except Exception as e:
        pytest.fail(f"Error checking option in select '{select_id}': {e}")

# --- End Helper Functions ---

def test_payload_lifecycle(driver):
    """II.1. Test payload creation, saving, loading, renaming, and deletion."""
    wait = WebDriverWait(driver, 20)
    unique_payload_name_1 = generate_unique_name("TestPayload")
    unique_payload_name_2 = generate_unique_name("TestPayloadRenamed")

    # --- 1. Define and Create Payload (Client-Side) ---
    print(f"DEBUG: Starting payload lifecycle test. Initial name: {unique_payload_name_1}, Renamed name: {unique_payload_name_2}")

    # Section: Vehicle Selection (Accordion ID: #collapseVehicle, open by default)
    # This section contains Make, Model, Trim, Color, condition checkboxes, Drivetrain, Transmission, Body Type, Doors, Seats.
    print("DEBUG: Filling 'Vehicle Selection' section (Accordion: #collapseVehicle - open by default)...")

    make_dropdown_select = Select(wait.until(EC.element_to_be_clickable((By.ID, "makeSelect"))))
    make_dropdown_select.select_by_visible_text("Acura")
    print("DEBUG: Selected Make: Acura")
    time.sleep(1) # Allow models to load

    model_dropdown_element = wait.until(EC.presence_of_element_located((By.ID, "modelSelect")))
    wait.until(lambda d: len(model_dropdown_element.find_elements(By.TAG_NAME, "option")) > 1, "Model dropdown did not populate")
    model_dropdown_select = Select(model_dropdown_element)
    selected_model_value_for_verification = ""
    try:
        model_dropdown_select.select_by_value("ILX")
        selected_model_value_for_verification = "ILX"
        print(f"DEBUG: Selected Model by value: ILX. Stored value for verification: {selected_model_value_for_verification}")
    except NoSuchElementException:
        model_options_elements = [opt for opt in model_dropdown_select.options if opt.get_attribute("value") != ""]
        if model_options_elements:
            model_to_select_value = model_options_elements[0].get_attribute("value")
            model_dropdown_select.select_by_value(model_to_select_value)
            selected_model_value_for_verification = model_to_select_value
            print(f"DEBUG: Selected Model (fallback by value): {model_to_select_value}. Stored value for verification: {selected_model_value_for_verification}")
        else:
            pytest.fail("No models found for Acura to select in test_payload_lifecycle")
    time.sleep(1) # Allow trims/colors to load

    trim_select_element = wait.until(EC.presence_of_element_located((By.ID, "trimSelect")))
    selected_trim_value_for_verification = "" # Default if no trim selected
    try:
        wait.until(lambda d: len(trim_select_element.find_elements(By.TAG_NAME, "option")) > 1, "Trim dropdown did not populate for selected Make/Model")
        trim_select = Select(trim_select_element)
        # Select the first valid trim option (index 1, as index 0 is often a placeholder)
        if len(trim_select.options) > 1 and trim_select.options[1].get_attribute("value") != "":
            trim_select.select_by_index(1)
            selected_trim_value_for_verification = trim_select.first_selected_option.get_attribute("value")
            print(f"DEBUG: Selected Trim: {trim_select.first_selected_option.text}, Stored value for verification: {selected_trim_value_for_verification}")
        else:
            print("DEBUG: No valid trims to select for selected Make/Model.")
    except TimeoutException:
        print("DEBUG: Trim dropdown did not populate in time for selected Make/Model.")
    
    # Color select (similar logic for selecting first available if populated)
    # For brevity, we'll assume it might not always populate or be critical for this test's core payload functionality

    is_used_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "isUsed")))
    if not is_used_checkbox.is_selected():
        is_used_checkbox.click()
    print("DEBUG: Checked 'IsUsed'")
    # is_damaged_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "isDamaged"))) # Assuming it's in the first accordion
    # if is_damaged_checkbox.is_selected(): # Ensure it's not checked for this test
    #     is_damaged_checkbox.click()
    # print("DEBUG: Ensured 'IsDamaged' is not checked.")

    # Helper function to click accordion if collapsed
    def click_accordion_if_collapsed(driver, wait_obj, target_id_fragment):
        print(f"DEBUG: Checking accordion for target '{target_id_fragment}'...")
        try:
            # Construct CSS selector for the button targeting the collapse div
            # e.g., button[data-bs-target="#collapseLocation"]
            button_selector = f"button[data-bs-target='#{target_id_fragment}']"
            accordion_button = wait_obj.until(EC.presence_of_element_located((By.CSS_SELECTOR, button_selector)))
            
            # Scroll into view if necessary
            driver.execute_script("arguments[0].scrollIntoView(true);", accordion_button)
            time.sleep(0.2) # Brief pause after scroll

            # Check if it's collapsed
            if "collapsed" in accordion_button.get_attribute("class") or accordion_button.get_attribute("aria-expanded") == "false":
                print(f"DEBUG: Accordion '{target_id_fragment}' is collapsed, clicking to expand.")
                # Use JS click if direct click is problematic
                driver.execute_script("arguments[0].click();", accordion_button)
                time.sleep(0.5) # Wait for animation
                # Verify it expanded by checking aria-expanded attribute using a lambda
                wait_obj.until(
                    lambda d: d.find_element(By.CSS_SELECTOR, button_selector).get_attribute("aria-expanded") == "true",
                    message=f"Accordion {target_id_fragment} did not set aria-expanded='true' after click."
                )
                print(f"DEBUG: Accordion '{target_id_fragment}' expanded (aria-expanded='true').")
            else:
                print(f"DEBUG: Accordion '{target_id_fragment}' is already expanded.")
        except TimeoutException:
            # This timeout could be for finding the button OR for the attribute change via lambda
            pytest.fail(f"Timeout interacting with accordion '{target_id_fragment}'. Button not found or aria-expanded attribute did not become 'true'.")
        except Exception as e:
            pytest.fail(f"Error interacting with accordion '{target_id_fragment}': {e}")

    # Section: Location (Accordion ID: #collapseLocation)
    click_accordion_if_collapsed(driver, wait, "collapseLocation")
    address_input = wait.until(EC.visibility_of_element_located((By.ID, "address")))
    address_input.clear()
    address_input.send_keys("Toronto, ON")
    print("DEBUG: Entered Address: Toronto, ON")
    proximity_input = wait.until(EC.visibility_of_element_located((By.ID, "proximity")))
    proximity_input.clear()
    proximity_input.send_keys("150")
    print("DEBUG: Entered Proximity: 150")

    # Section: Year Range (Accordion ID: #collapseYear)
    click_accordion_if_collapsed(driver, wait, "collapseYear")
    year_min_input = wait.until(EC.visibility_of_element_located((By.ID, "yearMin")))
    year_min_input.clear()
    year_min_input.send_keys("2015")
    print("DEBUG: Entered YearMin: 2015")
    year_max_input = wait.until(EC.visibility_of_element_located((By.ID, "yearMax")))
    year_max_input.clear()
    year_max_input.send_keys("2023")
    print("DEBUG: Entered YearMax: 2023")

    # Section: Price Range (Accordion ID: #collapsePrice)
    click_accordion_if_collapsed(driver, wait, "collapsePrice")
    price_min_input = wait.until(EC.visibility_of_element_located((By.ID, "priceMin")))
    price_min_input.clear()
    price_min_input.send_keys("10000")
    print("DEBUG: Entered PriceMin: 10000")
    price_max_input = wait.until(EC.visibility_of_element_located((By.ID, "priceMax")))
    price_max_input.clear()
    price_max_input.send_keys("35000")
    print("DEBUG: Entered PriceMax: 35000")

    # Section: Mileage (Accordion ID: #collapseMileage)
    click_accordion_if_collapsed(driver, wait, "collapseMileage")
    odometer_min_input = wait.until(EC.visibility_of_element_located((By.ID, "odometerMin")))
    odometer_min_input.clear()
    odometer_min_input.send_keys("50000")
    print("DEBUG: Entered OdometerMin: 50000")
    odometer_max_input = wait.until(EC.visibility_of_element_located((By.ID, "odometerMax")))
    odometer_max_input.clear()
    odometer_max_input.send_keys("150000")
    print("DEBUG: Entered OdometerMax: 150000")

    # Section: Keyword Filtering (Accordion ID: #collapseKeywords)
    click_accordion_if_collapsed(driver, wait, "collapseKeywords")
    exclusion_keywords_to_add = ["accident", "rebuilt", "salvage"]
    exclusion_input = wait.until(EC.visibility_of_element_located((By.ID, "exclusionKeyword")))
    add_exclusion_btn = wait.until(EC.element_to_be_clickable((By.ID, "addExclusionBtn")))
    print("DEBUG: Adding exclusion keywords...")
    for keyword in exclusion_keywords_to_add:
        exclusion_input.clear()
        exclusion_input.send_keys(keyword)
        add_exclusion_btn.click()
        wait.until(EC.visibility_of_element_located((By.XPATH, f"//div[@id='exclusionsList']/span[contains(normalize-space(.), '{keyword}')]")))
        print(f"DEBUG: Added exclusion keyword: {keyword}")
        time.sleep(0.2)
    
    inclusion_input = wait.until(EC.visibility_of_element_located((By.ID, "inclusion")))
    inclusion_input.clear()
    inclusion_input.send_keys("sunroof")
    print("DEBUG: Entered Inclusion: sunroof")

    # Click "Create Payload" (client-side)
    print("DEBUG: All form fields filled. Attempting to click 'Create Payload' (client-side).")
    print("DEBUG: All form fields filled. Attempting to click 'Create Payload' (client-side).")
    create_payload_btn = wait.until(EC.element_to_be_clickable((By.ID, "createPayloadBtn")))
    create_payload_btn.click()
    print("DEBUG: Clicked 'Create Payload' (client-side)")
    time.sleep(1) # Allow client-side JS to process

    # --- 2. Save Payload to Server ---
    print(f"DEBUG: Attempting to save payload as '{unique_payload_name_1}'")
    save_payload_btn = wait.until(EC.element_to_be_clickable((By.ID, "savePayloadBtn")))
    save_payload_btn.click()

    # Wait for modal to be visible and input field to be present
    name_payload_modal = wait.until(EC.visibility_of_element_located((By.ID, "namePayloadModal")))
    payload_name_input = wait.until(EC.visibility_of_element_located((By.ID, "payloadName")))
    payload_name_input.clear()
    payload_name_input.send_keys(unique_payload_name_1)
    print(f"DEBUG: Entered payload name '{unique_payload_name_1}' in modal")

    save_named_payload_btn = wait.until(EC.element_to_be_clickable((By.ID, "saveNamedPayloadBtn")))
    save_named_payload_btn.click()
    print("DEBUG: Clicked 'Save' in modal")

    # Wait for modal to disappear
    wait.until(EC.invisibility_of_element_located((By.ID, "namePayloadModal")))
    print("DEBUG: Save modal closed")
    check_notification(driver, f'Payload saved as "{unique_payload_name_1}"')
    
    # Verification: Check dropdown for the new payload name
    # Need a slight delay for the dropdown to refresh via API call
    time.sleep(3) # Increased delay for payload list to refresh, was 2
    check_option_in_select(driver, "payloadSelect", unique_payload_name_1, should_exist=True)
    print(f"DEBUG: Verified '{unique_payload_name_1}' is in payloadSelect dropdown.")

    # --- Click Clear Filters before loading ---
    print("DEBUG: Attempting to click 'Clear Filters' button.")
    # Assuming the clear filters button has ID "clearFiltersBtn"
    # And that it shows a notification "Filters cleared"
    try:
        clear_filters_btn = wait.until(EC.element_to_be_clickable((By.ID, "clearFiltersBtn")))
        clear_filters_btn.click()
        print("DEBUG: Clicked 'Clear Filters' button.")
        time.sleep(0.5) # Brief pause for UI to react
        check_notification(driver, "Filters cleared", timeout=5) # Shorter timeout for quick notification
        print("DEBUG: 'Filters cleared' notification verified.")
    except TimeoutException:
        print("DEBUG: 'Clear Filters' button or its notification not found as expected. Proceeding without it for this run.")
        # This allows the test to continue if the button/notification isn't there,
        # but it's a point to check if the feature is expected.
    time.sleep(1) # Allow UI to fully reset after clearing

    # --- 3. Load the Saved Payload ---
    print(f"DEBUG: Attempting to load payload '{unique_payload_name_1}'")
    payload_select_dropdown = Select(wait.until(EC.element_to_be_clickable((By.ID, "payloadSelect"))))
    
    # Robustly select the option by text
    selected_successfully = False
    for option in payload_select_dropdown.options:
        if option.text.strip() == unique_payload_name_1.strip():
            payload_select_dropdown.select_by_visible_text(unique_payload_name_1)
            selected_successfully = True
            break
    if not selected_successfully:
        pytest.fail(f"Could not select payload '{unique_payload_name_1}' by visible text for loading.")
    print(f"DEBUG: Selected '{unique_payload_name_1}' in dropdown for loading.")
    
    load_payload_btn = wait.until(EC.element_to_be_clickable((By.ID, "loadPayloadBtn")))
    load_payload_btn.click()
    print("DEBUG: Clicked 'Load Payload'")

    check_notification(driver, "Payload loaded successfully")
    print("DEBUG: 'Payload loaded successfully' notification verified.")
    time.sleep(3) # Allow form to populate, was 2

    # Verification: Check all originally entered form fields
    print("DEBUG: Verifying all form fields after loading payload...")
    assert wait.until(lambda d: d.find_element(By.ID, "makeSelect").get_attribute("value") == "Acura"), "Make not loaded correctly"
    print("DEBUG: Verified Make: Acura")

    assert wait.until(lambda d: d.find_element(By.ID, "modelSelect").get_attribute("value") == selected_model_value_for_verification), \
        f"Model not loaded correctly. Expected '{selected_model_value_for_verification}', got '{driver.find_element(By.ID, 'modelSelect').get_attribute('value')}'"
    print(f"DEBUG: Verified Model: {selected_model_value_for_verification}")

    if selected_trim_value_for_verification:
        assert wait.until(lambda d: d.find_element(By.ID, "trimSelect").get_attribute("value") == selected_trim_value_for_verification), \
            f"Trim not loaded correctly. Expected '{selected_trim_value_for_verification}', got '{driver.find_element(By.ID, 'trimSelect').get_attribute('value')}'"
        print(f"DEBUG: Verified Trim: {selected_trim_value_for_verification}")
    else:
        # If no trim was selected during creation, verify it's still not selected (e.g., value is empty for placeholder)
        loaded_trim_value = driver.find_element(By.ID, "trimSelect").get_attribute("value")
        assert loaded_trim_value == "", f"Trim should be empty/placeholder if not set in payload, but got '{loaded_trim_value}'"
        print("DEBUG: Verified Trim is correctly unselected/placeholder as per payload.")

    assert wait.until(lambda d: d.find_element(By.ID, "isUsed").is_selected()), "'IsUsed' checkbox not loaded correctly"
    print("DEBUG: Verified 'IsUsed' checkbox is selected.")

    assert wait.until(lambda d: d.find_element(By.ID, "address").get_attribute("value") == "Toronto, ON"), "Address not loaded correctly"
    print("DEBUG: Verified Address: Toronto, ON")
    assert wait.until(lambda d: d.find_element(By.ID, "proximity").get_attribute("value") == "150"), "Proximity not loaded correctly"
    print("DEBUG: Verified Proximity: 150")

    assert wait.until(lambda d: d.find_element(By.ID, "yearMin").get_attribute("value") == "2015"), "YearMin not loaded correctly"
    print("DEBUG: Verified YearMin: 2015")
    assert wait.until(lambda d: d.find_element(By.ID, "yearMax").get_attribute("value") == "2023"), "YearMax not loaded correctly"
    print("DEBUG: Verified YearMax: 2023")

    assert wait.until(lambda d: d.find_element(By.ID, "priceMin").get_attribute("value") == "10000"), "PriceMin not loaded correctly"
    print("DEBUG: Verified PriceMin: 10000")
    assert wait.until(lambda d: d.find_element(By.ID, "priceMax").get_attribute("value") == "35000"), "PriceMax not loaded correctly"
    print("DEBUG: Verified PriceMax: 35000")

    assert wait.until(lambda d: d.find_element(By.ID, "odometerMin").get_attribute("value") == "50000"), "OdometerMin not loaded correctly"
    print("DEBUG: Verified OdometerMin: 50000")
    assert wait.until(lambda d: d.find_element(By.ID, "odometerMax").get_attribute("value") == "150000"), "OdometerMax not loaded correctly"
    print("DEBUG: Verified OdometerMax: 150000")

    # Verify exclusion keywords
    expected_exclusions = ["accident", "rebuilt", "salvage"]
    for keyword in expected_exclusions:
        wait.until(EC.visibility_of_element_located((By.XPATH, f"//div[@id='exclusionsList']/span[contains(normalize-space(.), '{keyword}')]")))
        print(f"DEBUG: Verified exclusion keyword '{keyword}' is present.")
    
    # Verify inclusion keyword
    assert wait.until(lambda d: d.find_element(By.ID, "inclusion").get_attribute("value") == "sunroof"), "Inclusion keyword not loaded correctly"
    print("DEBUG: Verified inclusion keyword 'sunroof'.")
    print("DEBUG: All payload fields verified successfully after loading.")

    # --- 4. Rename the Payload ---
    print(f"DEBUG: Attempting to rename payload to '{unique_payload_name_2}'")
    # Ensure the correct payload is still selected (it should be after loading)
    print(f"DEBUG: Verifying '{unique_payload_name_1}' is selected before renaming...")
    payload_select_dropdown = Select(driver.find_element(By.ID, "payloadSelect")) # Re-fetch to avoid staleness
    # Strip text for comparison to handle potential leading/trailing whitespace from browser rendering
    selected_option_text_before_rename = payload_select_dropdown.first_selected_option.text.strip()
    assert selected_option_text_before_rename == unique_payload_name_1.strip(), \
        f"Incorrect payload selected before rename. Expected '{unique_payload_name_1}', got '{selected_option_text_before_rename}'"
    print(f"DEBUG: Confirmed '{unique_payload_name_1}' is selected.")

    rename_payload_btn = wait.until(EC.element_to_be_clickable((By.ID, "renamePayloadBtn")))
    rename_payload_btn.click()

    rename_modal = wait.until(EC.visibility_of_element_located((By.ID, "renameModal")))
    new_name_input = wait.until(EC.visibility_of_element_located((By.ID, "newItemName")))
    new_name_input.clear()
    new_name_input.send_keys(unique_payload_name_2)
    print(f"DEBUG: Entered new name '{unique_payload_name_2}' in rename modal")

    save_rename_btn = wait.until(EC.element_to_be_clickable((By.ID, "saveRenameBtn")))
    save_rename_btn.click()
    print("DEBUG: Clicked 'Save Changes' in rename modal")

    wait.until(EC.invisibility_of_element_located((By.ID, "renameModal")))
    print("DEBUG: Rename modal closed")
    check_notification(driver, "Payload renamed successfully")
    print("DEBUG: 'Payload renamed successfully' notification verified.")
    
    time.sleep(3) # Allow dropdown to refresh, was 2
    check_option_in_select(driver, "payloadSelect", unique_payload_name_2, should_exist=True)
    print(f"DEBUG: Verified new name '{unique_payload_name_2}' exists in dropdown.")
    check_option_in_select(driver, "payloadSelect", unique_payload_name_1, should_exist=False)
    print(f"DEBUG: Verified old name '{unique_payload_name_1}' does not exist in dropdown.")
    print(f"DEBUG: Payload renamed to '{unique_payload_name_2}' and verified in dropdown.")

    # --- 5. Delete the Payload ---
    print(f"DEBUG: Attempting to delete payload '{unique_payload_name_2}'")
    payload_select_dropdown = Select(wait.until(EC.element_to_be_clickable((By.ID, "payloadSelect"))))
    
    selected_successfully_for_delete = False
    for option in payload_select_dropdown.options:
        if option.text.strip() == unique_payload_name_2.strip():
            payload_select_dropdown.select_by_visible_text(unique_payload_name_2)
            selected_successfully_for_delete = True
            break
    if not selected_successfully_for_delete:
        pytest.fail(f"Could not select payload '{unique_payload_name_2}' by visible text for deletion.")
    print(f"DEBUG: Selected '{unique_payload_name_2}' for deletion.")

    delete_payload_btn = wait.until(EC.element_to_be_clickable((By.ID, "deletePayloadBtn")))
    print("DEBUG: Delete button is clickable.")
    
    # Using JavaScript click for potentially more robust interaction if overlays interfere
    driver.execute_script("arguments[0].click();", delete_payload_btn)
    print("DEBUG: Clicked 'Delete Payload' using JavaScript.")
        
    check_notification(driver, "Payload deleted successfully")
    print("DEBUG: 'Payload deleted successfully' notification verified.")
    
    time.sleep(3) # Allow dropdown to refresh, was 2
    check_option_in_select(driver, "payloadSelect", unique_payload_name_2, should_exist=False)
    print(f"DEBUG: Payload '{unique_payload_name_2}' deleted and verified as not in dropdown.")
    print("DEBUG: Payload lifecycle test completed successfully.")
