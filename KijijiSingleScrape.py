import requests
import json
import logging
import re # Import regex for parsing

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_kijiji_single_page(partial_url: str, output_filename: str = "test_single_page_kijiji.json"):
    """
    Fetches JSON data from a Kijiji Autos API URL and saves it to a file.

    Args:
        url (str): The Kijiji Autos API URL to fetch data from.
                   Example: "https://www.kijijiautos.ca/consumer/svc/a/34992435"
        output_filename (str): The name of the file to save the JSON data to.
                               Defaults to "test_single_page_kijiji.json".
    """
    # Headers based on user-provided inspection (Restored)
    url = "https://www.kijijiautos.ca/consumer/svc/a/" + partial_url + "/" # Keep the URL logic
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0',
        'Accept': 'application/json',
        'Accept-Language': 'en-CA',
        # 'Accept-Encoding': 'gzip, deflate, br, zstd', # requests handles encoding
        #'Referer': 'https://www.kijijiautos.ca/cars/bmw/3-series/used/', # Specific referer might be important
        #'x-parent-transaction-id': '9b3d87a6-fffc-4864-8303-1365e710443d', # Custom header
        'x-client': 'ca.move.web.app', # Custom header, CRITICAL FOR REQUEST TO PASS
        'content-type': 'application/json', # Content-Type often needed
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        #'x-client-id': 'c0233f8e-4b61-4e3a-9817-d8d2da7cbc0a', # Custom header
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        # 'Connection': 'keep-alive', # requests handles connection
    }
    try:
        logging.info(f"Attempting to fetch data from: {url} with specific headers.") # Simplified log
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        logging.info(f"Successfully fetched data. Status code: {response.status_code}")

        try:
            data = response.json()
            logging.info("Successfully parsed JSON response.")

            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logging.info(f"Successfully saved JSON data to {output_filename}")
            return data
        except json.JSONDecodeError:
            logging.error("Failed to decode JSON from response.")
            # Optionally save the raw text for debugging
            # with open(f"{output_filename}.raw.txt", 'w', encoding='utf-8') as f:
            #     f.write(response.text)
            # logging.info(f"Saved raw response text to {output_filename}.raw.txt")

    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    return None # Return None if scraping fails

# --- Helper Functions ---

def safe_get(data, keys, default=None):
    """Safely get a nested value from a dictionary."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
        if data is None:
            return default
    return data

def parse_attribute(details_list, target_key, return_first_value=True):
    """
    Searches through lists like 'vehicleDetails' or 'attributeGroups'
    for a specific key and returns its corresponding value(s).
    Handles different attribute structures.
    """
    for group in details_list:
        attributes = group.get("attributes", [])
        for attr in attributes:
            values = attr.get("values", [])
            if not values:
                continue

            # Handle structure where key is the first element: ["Key", "Value"]
            if len(values) >= 2 and values[0] == target_key:
                return values[1] if return_first_value else values[1:]

            # Handle structure where key is in a 'key' field and value in 'value': {"key": "Key", "value": "Value"}
            # (Seen in 'quickFacts')
            key_field = attr.get("key")
            value_field = attr.get("value")
            if key_field == target_key and value_field is not None:
                 return value_field # quickFacts seems to always have single value

    return None # Return None if not found


def extract_relevant_kijiji_data(data: dict):
    """
    Extracts relevant fields from the Kijiji JSON data, mapping them
    to the fields used in AutoScraper.py.

    Args:
        data (dict): The raw JSON data loaded from the Kijiji API response.

    Returns:
        dict: A dictionary containing the extracted and mapped fields.
    """
    if not data:
        return {}

    extracted = {}

    # Direct mappings
    extracted["Make"] = safe_get(data, ["make"])
    extracted["Model"] = safe_get(data, ["model"])
    extracted["Year"] = safe_get(data, ["year"])
    extracted["Trim"] = safe_get(data, ["trim"])
    extracted["Price"] = safe_get(data, ["prices", "consumerPrice", "amount"])
    extracted["Drivetrain"] = safe_get(data, ["driveTrain"]) # Top level seems reliable
    extracted["Fuel Type"] = safe_get(data, ["fuelType"]) # Top level seems reliable

    # Extract from quickFacts or vehicleDetails/attributeGroups
    quick_facts_attrs = safe_get(data, ["quickFacts", "attributes"], [])
    vehicle_details = safe_get(data, ["vehicleDetails"], [])
    attribute_groups = safe_get(data, ["attributeGroups"], []) # Fallback

    # Kilometres (needs parsing) - Prioritize quickFacts
    km_str = parse_attribute(quick_facts_attrs, "Kilometres")
    if km_str:
        # Regex to find digits and commas, ignoring surrounding text like ' km'
        match = re.search(r"([\d,]+)", km_str)
        if match:
            km_numeric_part = match.group(1).replace(",", "") # Get captured group 1 and remove commas
            try:
                extracted["Kilometres"] = int(km_numeric_part)
                logging.debug(f"Parsed Kilometres: {km_str} -> {extracted['Kilometres']}")
            except ValueError:
                logging.warning(f"Could not convert extracted kilometres '{km_numeric_part}' to int.")
                extracted["Kilometres"] = None
        else:
            logging.warning(f"Could not find numeric part in Kilometres string: '{km_str}'")
            extracted["Kilometres"] = None
    else:
         # Fallback: Check top-level vehicleUsage if quickFacts fails (less likely needed based on example)
         km_str_fallback = safe_get(data, ["vehicleUsage", "currentMileage"])
         if km_str_fallback:
             match = re.search(r"([\d,]+)", km_str_fallback)
             if match:
                 km_numeric_part = match.group(1).replace(",", "")
                 try:
                     extracted["Kilometres"] = int(km_numeric_part)
                     logging.debug(f"Parsed Kilometres (fallback): {km_str_fallback} -> {extracted['Kilometres']}")
                 except ValueError:
                     logging.warning(f"Could not convert extracted fallback kilometres '{km_numeric_part}' to int.")
                     extracted["Kilometres"] = None
             else:
                 logging.warning(f"Could not find numeric part in fallback Kilometres string: '{km_str_fallback}'")
                 extracted["Kilometres"] = None
         else:
             extracted["Kilometres"] = None # Set to None if not found anywhere


    # Status (Condition)
    extracted["Status"] = parse_attribute(quick_facts_attrs, "Condition")

    # Body Type (Use vehicleDetails first, fallback to top-level)
    extracted["Body Type"] = parse_attribute(vehicle_details, "Body type") or safe_get(data, ["bodyType"])

    # Engine (Description) - Look in Mechanical specs
    engine_str = parse_attribute(vehicle_details, "Power") # Often includes HP
    if engine_str:
        # Replace non-breaking space with regular space
        extracted["Engine"] = engine_str.replace('\u00a0', ' ')
    else:
        # Fallback if Power is not found
        engine_str_fallback = parse_attribute(vehicle_details, "Engine capacity")
        if engine_str_fallback:
             extracted["Engine"] = engine_str_fallback.replace('\u00a0', ' ')
        else:
             extracted["Engine"] = None # Set to None if not found

    # Cylinder - Look in Mechanical specs
    extracted["Cylinder"] = parse_attribute(vehicle_details, "Cylinders")

    # Transmission (Use quickFacts first, fallback to top-level)
    extracted["Transmission"] = parse_attribute(quick_facts_attrs, "Transmission") or safe_get(data, ["transmission"])

    # Exterior Colour - Not directly available in this example, might be in description or features
    extracted["Exterior Colour"] = None # Placeholder

    # Doors - Look in Dimensions
    door_str = parse_attribute(vehicle_details, "Door count")
    if door_str:
         match = re.search(r"\d+", door_str) # Get the first number
         extracted["Doors"] = match.group() if match else None
    else:
         extracted["Doors"] = None


    # Clean up None values if desired, or keep them
    # extracted = {k: v for k, v in extracted.items() if v is not None}

    return extracted


if __name__ == "__main__":
    # --- Option 1: Scrape a new URL and then process ---
    test_url = "34992435"
    raw_data = scrape_kijiji_single_page(test_url, output_filename="test_single_page_kijiji.json")
    if raw_data:
        extracted_data = extract_relevant_kijiji_data(raw_data)
        print("--- Extracted Data ---")
        print(json.dumps(extracted_data, indent=4))
    else:
        print("Scraping failed, cannot extract data.")

    # --- Option 2: Load existing file and process ---
