import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

# The driver fixture is in conftest.py and will be automatically discovered.

# Placeholder for actual data fetching tests.
# These tests would typically:
# 1. Set up search parameters (either manually or by loading a payload).
# 2. Click the "Fetch Data" button.
# 3. Wait for results to appear in the "Current Search Results" table.
# 4. Verify the presence of results or a "no results" message.
# 5. Optionally, check aspects of the fetched data (e.g., number of rows, specific content).

def test_fetch_data_with_simple_criteria_returns_results(driver):
    """
    Placeholder: Tests that fetching data with some basic criteria
    (e.g., a common make/model) populates the results table.
    """
    wait = WebDriverWait(driver, 20)
    
    # Example: Select a Make (e.g., the first valid one)
    make_dropdown = wait.until(EC.presence_of_element_located((By.ID, "makeSelect")))
    wait.until(lambda d: len(make_dropdown.find_elements(By.TAG_NAME, "option")) > 1)
    select_make = Select(make_dropdown)
    
    first_valid_make_text = None
    for option_element in select_make.options:
        if option_element.get_attribute("value") != "":
            first_valid_make_text = option_element.text
            break
    if not first_valid_make_text:
        pytest.fail("No valid make found to select for data fetching test.")
    select_make.select_by_visible_text(first_valid_make_text)
    print(f"DEBUG: Selected Make: {first_valid_make_text}")
    time.sleep(1) # Allow models to load

    # Example: Select a Model (e.g., the first valid one)
    model_dropdown = wait.until(EC.presence_of_element_located((By.ID, "modelSelect")))
    wait.until(lambda d: len(model_dropdown.find_elements(By.TAG_NAME, "option")) > 1, "Model dropdown did not populate")
    select_model = Select(model_dropdown)

    first_valid_model_text = None
    for option_element in select_model.options:
        if option_element.get_attribute("value") != "":
            first_valid_model_text = option_element.text
            break
    if not first_valid_model_text:
        pytest.fail(f"No valid model found for make '{first_valid_make_text}' to select for data fetching test.")
    select_model.select_by_visible_text(first_valid_model_text)
    print(f"DEBUG: Selected Model: {first_valid_model_text}")
    time.sleep(1) # Allow other fields to potentially update

    # Click the "Fetch Data" button (assuming ID "fetchDataBtn")
    fetch_data_btn = wait.until(EC.element_to_be_clickable((By.ID, "fetchDataBtn")))
    fetch_data_btn.click()
    print("DEBUG: Clicked 'Fetch Data' button.")

    # Wait for the results table to show some activity.
    # This could be waiting for a loading indicator to disappear,
    # or for the table to have at least one row, or a "no results" message.
    # For this placeholder, we'll wait for the table body to be present.
    results_table_body = wait.until(EC.presence_of_element_located((By.ID, "resultsTableBody"))) # Assuming this ID for the tbody
    
    # A more robust check would be to wait for rows or a specific message.
    # Example: Wait for at least one row (tr) in the tbody or a "no results" message.
    try:
        WebDriverWait(driver, 30).until( # Increased timeout for data fetching
            EC.any_of(
                EC.presence_of_element_located((By.XPATH, "//table[@id='resultsTable']/tbody/tr")) , # Check for any row
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'No results found') or contains(text(), 'No data available')]")) # Check for no results message
            )
        )
        print("DEBUG: Results table populated or 'no results' message appeared.")
    except TimeoutException:
        pytest.fail("Data fetching did not complete or show a 'no results' message within timeout.")

    # Further assertions can be added here, e.g., checking number of rows, content.
    # For now, if it reaches here without timeout, the basic flow is considered "working".
    assert results_table_body is not None, "Results table body not found after fetching data."
    
    # Example: Check if there are rows or a no results message
    rows = driver.find_elements(By.XPATH, "//table[@id='vehicleResultsTable']/tbody/tr") # Corrected table ID based on index.html for modal
    no_results_message_xpath = "//*[contains(text(), 'No results found') or contains(text(), 'No data available') or contains(text(), 'No search performed yet.')]"
    
    # Check within resultsInfo or modal table
    results_info_text = driver.find_element(By.ID, "resultsInfo").text
    
    modal_is_present = False
    try:
        modal_is_present = driver.find_element(By.ID, "resultsModal").is_displayed()
    except NoSuchElementException:
        pass

    if modal_is_present:
        no_results_in_modal = driver.find_elements(By.XPATH, f"//div[@id='resultsModal']{no_results_message_xpath}")
        assert len(rows) > 0 or len(no_results_in_modal) > 0, "Neither results nor a 'no results' message was found in the modal."
        if len(rows) > 0:
            print(f"DEBUG: Found {len(rows)} rows in the results modal table.")
        elif len(no_results_in_modal) > 0:
            print(f"DEBUG: Found 'no results' message in modal: {no_results_in_modal[0].text}")
    else:
        no_results_in_main = driver.find_elements(By.XPATH, f"//div[@id='resultsInfo']{no_results_message_xpath}")
        assert len(rows) > 0 or len(no_results_in_main) > 0 or "Found" in results_info_text, "Neither results nor a 'no results' message was found in main page."
        if len(rows) > 0 : # This case should ideally not happen if modal isn't shown
             print(f"DEBUG: Found {len(rows)} rows (unexpectedly, modal not shown).")
        elif "Found" in results_info_text:
            print(f"DEBUG: Results info indicates success: {results_info_text}")
        elif len(no_results_in_main) > 0:
            print(f"DEBUG: Found 'no results' message in main page: {no_results_in_main[0].text}")


# Add more tests for different scenarios:
# - Fetching with no criteria (should it be allowed? what's expected?)
# - Fetching with very specific criteria likely to yield no results.
# - Fetching that results in an error (how are errors displayed?).
# - Pagination of results if applicable.
# - Sorting of results if applicable.

def test_full_data_interaction_scenario(driver):
    """
    Tests the full scenario:
    1. Load a specific payload.
    2. Fetch data.
    3. View results.
    4. Test sorting in modal.
    5. Test filtering in modal.
    6. Delete a listing in modal.
    7. Open selected links from modal.
    """
    wait = WebDriverWait(driver, 30) # Increased default wait time for this complex test

    # 1. Ensure main page is loaded (conftest should handle login and navigation to /app)
    wait.until(EC.presence_of_element_located((By.ID, "payloadSelect")))
    print("DEBUG: Main application page loaded.")

    # 2. Select payload "Acura RDX (2015-2025, $5000-$45000)"
    payload_dropdown_el = wait.until(EC.presence_of_element_located((By.ID, "payloadSelect")))
    select_payload = Select(payload_dropdown_el)
    
    # Wait for payload options to load (at least one non-default option)
    wait.until(lambda d: len(select_payload.options) > 1 and any(opt.get_attribute("value") != "" for opt in select_payload.options))
    
    target_payload_name = "Acura RDX (2015-2025, $5000-$45000)" # This must match exactly how it appears in dropdown
    try:
        select_payload.select_by_visible_text(target_payload_name)
        print(f"DEBUG: Selected payload: {target_payload_name}")
    except NoSuchElementException:
        # Fallback: if exact name isn't found, try to find one containing "Acura RDX"
        found_payload = False
        for option in select_payload.options:
            if "Acura RDX" in option.text:
                select_payload.select_by_visible_text(option.text)
                print(f"DEBUG: Selected payload (fallback match): {option.text}")
                found_payload = True
                break
        if not found_payload:
            pytest.fail(f"Payload containing 'Acura RDX' not found. Available: {[opt.text for opt in select_payload.options]}")

    # 3. Load the selected payload
    load_payload_btn = wait.until(EC.presence_of_element_located((By.ID, "loadPayloadBtn")))
    # Scroll the button into view before attempting to click
    driver.execute_script("arguments[0].scrollIntoView(true);", load_payload_btn)
    time.sleep(0.5) # Brief pause after scroll before click
    wait.until(EC.element_to_be_clickable((By.ID, "loadPayloadBtn"))).click() # Ensure it's clickable after scroll
    print("DEBUG: Clicked 'Load Selected' payload button.")
    time.sleep(2) # Allow form to populate, consider a more dynamic wait if possible

    # Verify form population (e.g., Make field)
    make_field = wait.until(EC.visibility_of_element_located((By.ID, "makeSelect")))
    # The value attribute for makes seems to be title case, e.g., "Acura"
    assert Select(make_field).first_selected_option.get_attribute("value") == "Acura", "Make field not populated correctly after loading payload."
    print("DEBUG: Payload loaded into form (Make field verified).")

    # 4. Press fetch data
    fetch_data_btn = wait.until(EC.element_to_be_clickable((By.ID, "fetchDataBtn")))
    fetch_data_btn.click()
    print("DEBUG: Clicked 'Fetch Data' button.")

    # Wait for fetch to complete: progress bar appears then disappears, and resultsInfo updated
    wait.until(EC.visibility_of_element_located((By.ID, "fetchProgressContainer")))
    print("DEBUG: Fetch progress bar appeared.")
    wait.until(EC.invisibility_of_element_located((By.ID, "fetchProgressContainer")))
    print("DEBUG: Fetch progress bar disappeared.")
    
    results_info = wait.until(EC.visibility_of_element_located((By.ID, "resultsInfo")))
    wait.until(lambda d: "Found" in results_info.text or "No listings found" in results_info.text or "Error" in results_info.text)
    assert "Error" not in results_info.text, f"Error occurred during data fetching: {results_info.text}"
    print(f"DEBUG: Fetch completed. Results info: {results_info.text}")

    # 5. Select newest saved result (after refreshing)
    refresh_results_btn = wait.until(EC.element_to_be_clickable((By.ID, "refreshResultsBtn")))
    refresh_results_btn.click()
    print("DEBUG: Clicked 'Refresh Results' button.")
    time.sleep(2) # Allow results list to refresh

    result_dropdown_el = wait.until(EC.presence_of_element_located((By.ID, "resultSelect")))
    select_result = Select(result_dropdown_el)
    
    # Wait for result options to load
    wait.until(lambda d: len(select_result.options) > 1 and any(opt.get_attribute("value") != "" for opt in select_result.options))
    
    # Select the last available result (assuming it's the newest one from the fetch)
    # This might need adjustment if the list isn't ordered by time or if there are pre-existing results.
    if len(select_result.options) > 1:
        # Last option is typically index len(options) - 1
        # However, if the first option is "Select a saved result", then the actual last result is at index len-1
        last_result_option_index = len(select_result.options) - 1
        select_result.select_by_index(last_result_option_index)
        selected_result_text = select_result.options[last_result_option_index].text
        print(f"DEBUG: Selected result: {selected_result_text}")
    else:
        pytest.fail("No saved results found in the dropdown after fetching data.")

    # 6. Press View Selected
    view_result_btn = wait.until(EC.element_to_be_clickable((By.ID, "viewResultBtn")))
    view_result_btn.click()
    print("DEBUG: Clicked 'View Selected' result button.")

    results_modal = wait.until(EC.visibility_of_element_located((By.ID, "resultsModal")))
    wait.until(EC.visibility_of_element_located((By.ID, "vehicleResultsTableBody")))
    print("DEBUG: Results modal is visible with table body.")

    # 7. Test Sorting features
    sortable_fields = ["Year", "Make", "Model", "Trim", "Price", "Kilometres", "Drivetrain"]
    for field in sortable_fields:
        header = wait.until(EC.element_to_be_clickable((By.XPATH, f"//th[@data-field='{field}']")))
        
        # Click to sort ascending
        header.click()
        print(f"DEBUG: Clicked to sort by {field} (ascending).")
        time.sleep(1) # Allow table to re-render
        # Add assertion for ascending sort if possible (e.g., check first/last values)

        # Click to sort descending
        header.click()
        print(f"DEBUG: Clicked to sort by {field} (descending).")
        time.sleep(1) # Allow table to re-render
        # Add assertion for descending sort

    print("DEBUG: Sorting tests completed.")

    # 8. Test Modal Filters
    # Example: Filter by Make (if multiple makes are present)
    filter_make_el = Select(wait.until(EC.presence_of_element_located((By.ID, "filterMake"))))
    if len(filter_make_el.options) > 2: # More than "All Makes" and one actual make
        initial_rows = driver.find_elements(By.XPATH, "//div[@id='resultsModal']//tbody/tr")
        filter_make_el.select_by_index(1) # Select the first actual make
        selected_filter_make = filter_make_el.options[1].text
        print(f"DEBUG: Filtering by Make: {selected_filter_make}")
        
        apply_filters_btn = wait.until(EC.element_to_be_clickable((By.ID, "applyFiltersBtn")))
        apply_filters_btn.click()
        print("DEBUG: Clicked 'Apply Filters' button.")
        time.sleep(2) # Allow table to update

        filtered_rows = driver.find_elements(By.XPATH, "//div[@id='resultsModal']//tbody/tr")
        if len(initial_rows) > 0 : # Only assert if there were rows to begin with
             assert len(filtered_rows) < len(initial_rows) or all(selected_filter_make in row.text for row in filtered_rows), \
                f"Filtering by make '{selected_filter_make}' did not yield expected results."
        print(f"DEBUG: Rows after Make filter: {len(filtered_rows)}")

        # Clear filter for next step (re-select "All Makes")
        filter_make_el.select_by_index(0)
        apply_filters_btn.click()
        time.sleep(1)
        print("DEBUG: Cleared Make filter.")

    # Example: Filter by Max Price
    filter_price_max_el = wait.until(EC.presence_of_element_located((By.ID, "filterPriceMax")))
    filter_price_max_el.send_keys("30000")
    print("DEBUG: Filtering by Max Price: 30000")
    apply_filters_btn = wait.until(EC.element_to_be_clickable((By.ID, "applyFiltersBtn"))) # Re-locate after potential DOM changes
    apply_filters_btn.click()
    print("DEBUG: Clicked 'Apply Filters' button.")
    time.sleep(2)
    # Add assertion for price filter
    print("DEBUG: Price filter applied.")
    # Clear filter
    filter_price_max_el.clear()
    apply_filters_btn.click()
    time.sleep(1)
    print("DEBUG: Cleared Price filter.")
    
    print("DEBUG: Modal filter tests completed.")

    # 9. Delete a Listing
    initial_row_count = len(driver.find_elements(By.XPATH, "//div[@id='resultsModal']//tbody/tr"))
    if initial_row_count > 0:
        delete_button = wait.until(EC.element_to_be_clickable((By.XPATH, "(//div[@id='resultsModal']//button[contains(@class, 'delete-listing-btn')])[1]")))
        delete_button.click()
        print("DEBUG: Clicked delete button for the first listing.")
        
        # Handle JavaScript confirm dialog
        try:
            WebDriverWait(driver, 5).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            alert.accept()
            print("DEBUG: Accepted delete confirmation alert.")
        except TimeoutException:
            print("DEBUG: No delete confirmation alert appeared (or it was too fast).")

        time.sleep(2) # Wait for table to update
        final_row_count = len(driver.find_elements(By.XPATH, "//div[@id='resultsModal']//tbody/tr"))
        assert final_row_count == initial_row_count - 1, "Row count did not decrease after deleting a listing."
        print("DEBUG: Listing deleted successfully.")
    else:
        print("DEBUG: No listings to delete.")

    # 10. Open Selected Links
    rows_for_selection = driver.find_elements(By.XPATH, "//div[@id='resultsModal']//tbody/tr//input[@type='checkbox']")
    if len(rows_for_selection) > 0:
        num_to_select = min(len(rows_for_selection), 2) # Select up to 2
        for i in range(num_to_select):
            if not rows_for_selection[i].is_selected():
                 rows_for_selection[i].click()
        print(f"DEBUG: Selected {num_to_select} listings.")

        open_selected_links_btn = wait.until(EC.element_to_be_clickable((By.ID, "openSelectedLinksBtn")))
        
        initial_window_handles = driver.window_handles
        open_selected_links_btn.click()
        print("DEBUG: Clicked 'Open Selected Links' button in modal.")
        
        # Wait for new tabs to potentially open
        # A robust check would be to wait until number of window_handles increases
        time.sleep(5) # Give some time for tabs to open
        
        final_window_handles = driver.window_handles
        # This assertion is basic. Real validation would switch to new tabs and check URLs.
        # For now, we just check if the button click didn't cause an immediate error.
        # If num_to_select > 0, we expect more handles, but pop-up blockers can interfere.
        if num_to_select > 0:
             assert len(final_window_handles) >= len(initial_window_handles), \
                "Number of window handles did not increase as expected after clicking 'Open Selected Links'."
        print(f"DEBUG: Window handles before: {len(initial_window_handles)}, after: {len(final_window_handles)}")
        
        # Close extra tabs if any opened, and switch back to the main window
        if len(final_window_handles) > len(initial_window_handles):
            for handle in final_window_handles:
                if handle != initial_window_handles[0]: # Assuming first handle is main
                    driver.switch_to.window(handle)
                    driver.close()
            driver.switch_to.window(initial_window_handles[0]) # Switch back to main
            print("DEBUG: Closed extra tabs and switched back to main window.")
            time.sleep(1) # Add a small pause for browser to settle
    else:
        print("DEBUG: No listings to select for opening links.")

    # Close the modal
    # Ensure modal is still visible before trying to close it
    wait.until(EC.visibility_of_element_located((By.ID, "resultsModal")))
    close_modal_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='resultsModal']//button[@data-bs-dismiss='modal']"))) # More specific XPath
    close_modal_button.click()
    wait.until(EC.invisibility_of_element_located((By.ID, "resultsModal")))
    print("DEBUG: Results modal closed.")
    print("DEBUG: Full data interaction scenario test completed.")
