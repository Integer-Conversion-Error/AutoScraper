import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException # Added for more specific exception handling
import time

# The driver fixture is now in conftest.py and will be automatically discovered by pytest.

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
    
    make_select_element = wait.until(
        EC.element_to_be_clickable((By.ID, "makeSelect"))
    )
    select_make = Select(make_select_element)
    
    # Select the first valid make (not the placeholder "Select Make")
    first_valid_make_text = None
    all_make_options = select_make.options 
    
    for option_element in all_make_options:
        # The first option is usually the placeholder like "Select Make"
        if option_element.get_attribute("value") != "":  # Check for a non-empty value attribute
            first_valid_make_text = option_element.text
            break 
            
    if not first_valid_make_text:
        # This case means the dropdown is likely only "Select Make" or all options have empty values
        available_makes_texts = [opt.text for opt in all_make_options]
        pytest.fail(f"No valid make with a non-empty value found to select in 'Make' dropdown. Options: {available_makes_texts}")
        
    try:
        select_make.select_by_visible_text(first_valid_make_text)
        print(f"DEBUG: Selected make '{first_valid_make_text}' from Make dropdown.")
    except Exception as e:
        # This path should ideally not be hit if first_valid_make_text was found and is valid.
        available_makes_texts = [opt.text for opt in all_make_options]
        print(f"DEBUG: Could not select make '{first_valid_make_text}'. Available makes: {available_makes_texts}")
        pytest.fail(f"Failed to select make '{first_valid_make_text}' from Make dropdown: {e}. Available: {available_makes_texts}")

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
