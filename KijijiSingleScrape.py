import requests, os # Keep requests for the sync version if needed
import httpx # Import httpx for async requests
import asyncio # Import asyncio for sleep
import json
import logging
import re # Import regex for parsing
import time # Import time for sync sleep
from typing import Optional, Dict, Any # For type hinting

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Proxy Loading ---
def get_proxy_from_file(filename="proxyconfig.json"):
    """Loads proxy configuration from a JSON file."""
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            # Return the whole dict, requests will pick http/https
            return data
    except FileNotFoundError:
        logging.warning(f"Proxy file '{filename}' not found. Proceeding without proxy.")
        return None
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in proxy file '{filename}'. Proceeding without proxy.")
        return None
    except Exception as e:
        logging.error(f"Error loading proxy file '{filename}': {e}. Proceeding without proxy.")
        return None

# --- Synchronous Scraper (Keep for potential direct use/testing) ---
def scrape_kijiji_single_page(partial_url: str, output_filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches JSON data from a Kijiji Autos API URL. Optionally saves it to a file.

    Args:
        partial_url (str): The listing ID part of the Kijiji URL (e.g., "34992435").
        output_filename (Optional[str]): If provided, the name of the file to save
                                         the JSON data to. Defaults to None (no saving).

    Returns:
        Optional[Dict[str, Any]]: The fetched JSON data as a dictionary, or None on failure.
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
    # Load proxies before making the request
    proxies = get_proxy_from_file()

    max_retries = 3 # Number of retries for 403 errors
    initial_retry_delay = 1.0 # Initial delay in seconds
    request_timeout = 15 # Increased timeout
    response = None # Initialize response to None

    for attempt in range(max_retries + 1):
        try:
            # --- Make the request ---
            logging.info(f"Attempting to fetch data from: {url} (Attempt {attempt + 1}/{max_retries + 1})")
            response = requests.get(url, headers=headers, proxies=proxies, timeout=request_timeout)

            # --- Handle 403 Forbidden ---
            if response.status_code == 403:
                if attempt < max_retries:
                    retry_delay = initial_retry_delay * (2 ** attempt) # Exponential backoff
                    logging.warning(f"Received 403 Forbidden for {url}. Retrying in {retry_delay:.2f} seconds...")
                    time.sleep(retry_delay)
                    continue # Go to the next attempt in the loop
                else:
                    logging.error(f"Received 403 Forbidden for {url} after {max_retries + 1} attempts. Giving up.")
                    response.raise_for_status() # Raise the final 403 error

            # --- Handle other HTTP errors ---
            response.raise_for_status() # Raises HTTPError for 4xx/5xx responses (excluding the handled 403)
            logging.info(f"Successfully fetched data. Status code: {response.status_code}")

            # --- Process successful response ---
            try:
                data = response.json()
                logging.info("Successfully parsed JSON response.")

                # Only save if output_filename is provided
                if output_filename:
                    try:
                        with open(output_filename, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)
                        logging.info(f"Successfully saved JSON data to {output_filename}")
                    except IOError as e:
                        logging.error(f"Failed to write JSON to {output_filename}: {e}")

                return data # Success! Return the data

            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON from response for {url}. Content: {response.text[:200]}...")
                return None # Failed to parse JSON, return None

        # --- Handle exceptions during the request/processing attempt ---
        except requests.exceptions.RequestException as e:
            status_code = response.status_code if response is not None else "N/A"
            logging.error(f"Request failed for {url} on attempt {attempt + 1} (Status: {status_code}): {e}")
            if attempt >= max_retries:
                logging.error(f"Request failed definitively for {url} after {max_retries + 1} attempts.")
                return None # Return None after final failure
            # Delay before next retry (if it wasn't a 403)
            if response is None or response.status_code != 403:
                 retry_delay = initial_retry_delay * (2 ** attempt)
                 logging.info(f"Waiting {retry_delay:.2f} seconds before next request attempt...")
                 time.sleep(retry_delay)

        except Exception as e: # Catch other unexpected errors
            logging.error(f"An unexpected error occurred during attempt {attempt + 1} for {url}: {e}", exc_info=True)
            # Stop retrying on unexpected errors
            return None

    # This should theoretically not be reached if logic is correct, but acts as a safeguard
    logging.error(f"Scraping failed for {url} after exhausting retries or encountering unexpected error.")
    return None


# --- Asynchronous Scraper using httpx ---
async def scrape_kijiji_single_page_async(partial_url: str, client: httpx.AsyncClient, output_filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches JSON data from a Kijiji Autos API URL asynchronously using httpx.
    Optionally saves it to a file. Uses a shared httpx.AsyncClient.

    Args:
        partial_url (str): The listing ID part of the Kijiji URL (e.g., "34992435").
        client (httpx.AsyncClient): An active httpx AsyncClient instance (potentially with proxy config).
        output_filename (Optional[str]): If provided, the name of the file to save
                                         the JSON data to. Defaults to None (no saving).

    Returns:
        Optional[Dict[str, Any]]: The fetched JSON data as a dictionary, or None on failure.
    """
    url = "https://www.kijijiautos.ca/consumer/svc/a/" + partial_url + "/"
    # Headers remain the same
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0',
        'Accept': 'application/json',
        'Accept-Language': 'en-CA',
        'x-client': 'ca.move.web.app',
        'content-type': 'application/json',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    }

    max_retries = 3
    initial_retry_delay = 1.0
    request_timeout = 15.0 # httpx uses float for timeout
    response = None

    for attempt in range(max_retries + 1):
        try:
            logging.debug(f"Attempting async fetch for {url} (Attempt {attempt + 1}/{max_retries + 1})")
            response = await client.get(url, headers=headers, timeout=request_timeout)

            if response.status_code == 403:
                if attempt < max_retries:
                    retry_delay = initial_retry_delay * (2 ** attempt)
                    logging.warning(f"Received 403 Forbidden (async) for {url}. Retrying in {retry_delay:.2f} seconds...")
                    await asyncio.sleep(retry_delay) # Use asyncio.sleep
                    continue
                else:
                    logging.error(f"Received 403 Forbidden (async) for {url} after {max_retries + 1} attempts. Giving up.")
                    response.raise_for_status()

            response.raise_for_status() # Raise for other 4xx/5xx
            logging.debug(f"Successfully fetched data (async). Status code: {response.status_code}")

            try:
                data = response.json()
                logging.debug("Successfully parsed JSON response (async).")

                if output_filename:
                    # File saving remains synchronous for simplicity within the async function
                    # For fully async file I/O, would need a library like aiofiles
                    try:
                        with open(output_filename, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=4, ensure_ascii=False)
                        logging.info(f"Successfully saved JSON data to {output_filename}")
                    except IOError as e:
                        logging.error(f"Failed to write JSON to {output_filename}: {e}")

                return data # Success

            except json.JSONDecodeError:
                logging.error(f"Failed to decode JSON (async) from response for {url}. Content: {response.text[:200]}...")
                return None

        except httpx.RequestError as e: # Catch httpx specific request errors
            status_code = response.status_code if response is not None else "N/A"
            logging.error(f"Request failed (async) for {url} on attempt {attempt + 1} (Status: {status_code}): {e}")
            if attempt >= max_retries:
                logging.error(f"Request failed definitively (async) for {url} after {max_retries + 1} attempts.")
                return None
            if response is None or response.status_code != 403:
                 retry_delay = initial_retry_delay * (2 ** attempt)
                 logging.info(f"Waiting {retry_delay:.2f} seconds before next async request attempt...")
                 await asyncio.sleep(retry_delay)

        except Exception as e: # Catch other unexpected errors
            logging.error(f"An unexpected error occurred during async attempt {attempt + 1} for {url}: {e}", exc_info=True)
            return None

    logging.error(f"Async scraping failed for {url} after exhausting retries or encountering unexpected error.")
    return None


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


# --- Main block for testing (requires async context to run async scraper) ---
async def _test_async_scrape():
    """Helper async function to test the async scraper."""
    logging.info("--- Testing Async Scraper ---")
    test_partial_url = "34992435"
    proxies = get_proxy_from_file() # Load proxies once
    # Create an httpx client (consider reusing this in the main scraper)
    async with httpx.AsyncClient(proxies=proxies, http2=True, follow_redirects=True) as client: # Enable HTTP/2 if supported
        # Save the file during this test run
        raw_data = await scrape_kijiji_single_page_async(test_partial_url, client, output_filename="test_single_page_kijiji_async.json")
        if raw_data:
            extracted_data = extract_relevant_kijiji_data(raw_data)
            print("\n--- Extracted Data (from async scrape & save) ---")
            print(json.dumps(extracted_data, indent=4))
        else:
            print("Async scraping failed.")

if __name__ == "__main__":
    # --- Option 1: Test Sync Scraper ---
    # test_partial_url_sync = "34992435"
    # raw_data_sync = scrape_kijiji_single_page(test_partial_url_sync, output_filename="test_single_page_kijiji_sync.json")
    # if raw_data_sync:
    #     extracted_data_sync = extract_relevant_kijiji_data(raw_data_sync)
    #     print("\n--- Extracted Data (from sync scrape & save) ---")
    #     print(json.dumps(extracted_data_sync, indent=4))
    # else:
    #     print("Sync scraping failed.")

    # --- Option 2: Test Async Scraper ---
    # Running the async test function
    # Note: This will only run if the script is executed directly.
    # KijijiScraper.py will import and call the async function directly.
    try:
        asyncio.run(_test_async_scrape())
    except RuntimeError as e:
         if "cannot run event loop while another loop is running" in str(e):
              logging.warning("Cannot run async test directly when an event loop is already running (e.g., in some IDEs).")
         else:
              raise e


    # --- Option 3: Load existing file and process ---
    # This part remains useful for testing the extraction logic independently
    input_filename_load_test = "test_single_page_kijiji_async.json" # Or _sync.json
    if os.path.exists(input_filename_load_test):
        try:
            with open(input_filename_load_test, 'r', encoding='utf-8') as f:
                logging.info(f"Loading data from {input_filename_load_test}")
                raw_data_from_file = json.load(f)

            extracted_data_from_file = extract_relevant_kijiji_data(raw_data_from_file)
            print("\n--- Extracted Data (from loaded file) ---")
            # Corrected variable name here:
            print(json.dumps(extracted_data_from_file, indent=4))

        # Added missing except clauses for the try block above
        except FileNotFoundError:
            logging.error(f"File not found during load test: {input_filename_load_test}.")
        except json.JSONDecodeError:
            logging.error(f"Error decoding JSON during load test from {input_filename_load_test}.")
        except Exception as e:
            logging.error(f"An error occurred during load test file processing: {e}")
    else:
        logging.info(f"{input_filename_load_test} not found, skipping load test.")

    # Note: The original Option 2 logic was duplicated/merged into Option 3 logic above.
    # Keeping the structure clean.
