import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import datetime

# The driver fixture is now in conftest.py and will be automatically discovered by pytest.

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
    
    is_used_checkbox = wait.until(EC.element_to_be_clickable((By.ID, "isUsed")))
    if not is_used_checkbox.is_selected():
        is_used_checkbox.click()
    print("DEBUG: Checked 'IsUsed'")

    # Helper function to click accordion if collapsed
    def click_accordion_if_collapsed(driver, wait_obj, target_id_fragment):
        print(f"DEBUG: Checking accordion for target '{target_id_fragment}'...")
        try:
            button_selector = f"button[data-bs-target='#{target_id_fragment}']"
            accordion_button = wait_obj.until(EC.presence_of_element_located((By.CSS_SELECTOR, button_selector)))
            
            driver.execute_script("arguments[0].scrollIntoView(true);", accordion_button)
            time.sleep(0.2)

            if "collapsed" in accordion_button.get_attribute("class") or accordion_button.get_attribute("aria-expanded") == "false":
                print(f"DEBUG: Accordion '{target_id_fragment}' is collapsed, clicking to expand.")
                driver.execute_script("arguments[0].click();", accordion_button)
                time.sleep(0.5)
                wait_obj.until(
                    lambda d: d.find_element(By.CSS_SELECTOR, button_selector).get_attribute("aria-expanded") == "true",
                    message=f"Accordion {target_id_fragment} did not set aria-expanded='true' after click."
                )
                print(f"DEBUG: Accordion '{target_id_fragment}' expanded (aria-expanded='true').")
            else:
                print(f"DEBUG: Accordion '{target_id_fragment}' is already expanded.")
        except TimeoutException:
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
    time.sleep(3)
    check_option_in_select(driver, "payloadSelect", unique_payload_name_1, should_exist=True)
    print(f"DEBUG: Verified '{unique_payload_name_1}' is in payloadSelect dropdown.")

    # --- Click Clear Filters before loading ---
    print("DEBUG: Attempting to click 'Clear Filters' button.")
    try:
        clear_filters_btn = wait.until(EC.element_to_be_clickable((By.ID, "clearFiltersBtn")))
        clear_filters_btn.click()
        print("DEBUG: Clicked 'Clear Filters' button.")
        time.sleep(0.5)
        check_notification(driver, "Filters cleared", timeout=5)
        print("DEBUG: 'Filters cleared' notification verified.")
    except TimeoutException:
        print("DEBUG: 'Clear Filters' button or its notification not found as expected. Proceeding without it for this run.")
    time.sleep(1)

    # --- 3. Load the Saved Payload ---
    print(f"DEBUG: Attempting to load payload '{unique_payload_name_1}'")
    payload_select_dropdown = Select(wait.until(EC.element_to_be_clickable((By.ID, "payloadSelect"))))
    
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
    time.sleep(3)

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
    print(f"DEBUG: Verifying '{unique_payload_name_1}' is selected before renaming...")
    payload_select_dropdown = Select(driver.find_element(By.ID, "payloadSelect"))
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
    
    time.sleep(3)
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
    
    driver.execute_script("arguments[0].click();", delete_payload_btn)
    print("DEBUG: Clicked 'Delete Payload' using JavaScript.")
        
    check_notification(driver, "Payload deleted successfully")
    print("DEBUG: 'Payload deleted successfully' notification verified.")
    
    time.sleep(3)
    check_option_in_select(driver, "payloadSelect", unique_payload_name_2, should_exist=False)
    print(f"DEBUG: Payload '{unique_payload_name_2}' deleted and verified as not in dropdown.")
    print("DEBUG: Payload lifecycle test completed successfully.")
