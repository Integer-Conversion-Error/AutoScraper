import concurrent.futures
import requests
from requests.adapters import HTTPAdapter # Import HTTPAdapter
from urllib3.util.retry import Retry # Optional: for more robust retries
import json
import csv
import time
import os
import logging
import csv # Added for CSV cache handling
import datetime # Added for date caching
from functools import lru_cache # Will be removed later, but keep import for now if used elsewhere

from .AutoScraperUtil import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("autoscraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("AutoScraper")

# --- Expected Payload Schema (Based on Example) ---
# {
#     "micrositeType": 1,
#     "Microsite": { ... }, # Complex object, likely not needed for basic search
#     "Address": "K0A 1L0",
#     "Proximity": 1000,
#     "WithFreeCarProof": false,
#     "WithPrice": true,
#     "WithPhotos": true,
#     "HasLiveChat": false,
#     "HasVirtualAppraisal": false,
#     "HasHomeTestDrive": false,
#     "HasOnlineReservation": false,
#     "HasDigitalRetail": false,
#     "HasDealerDelivery": false,
#     "HasHomeDelivery": false,
#     "HasTryBeforeYouBuy": false,
#     "HasMoneyBackGuarantee": false,
#     "IsNew": true,
#     "IsUsed": true,
#     "IsDamaged": false,
#     "IsCpo": true,
#     "IsDealer": true,
#     "IsPrivate": true,
#     "IsOnlineSellerPlus": false,
#     "Top": 15, # Or 100
#     "Make": "Alfa Romeo",
#     "Model": "2000",
#     "BodyType": null, # Likely specific values exist
#     "PriceAnalysis": null,
#     "PhoneNumber": "",
#     "PriceMin": null,
#     "PriceMax": null,
#     "WheelBaseMin": null, "WheelBaseMax": null,
#     "EngineSizeMin": null, "EngineSizeMax": null,
#     "LengthMin": null, "LengthMax": null,
#     "WeightMin": null, "WeightMax": null,
#     "HorsepowerMin": null, "HorsepowerMax": null,
#     "HoursMin": null, "HoursMax": null,
#     "OdometerMin": null,
#     "OdometerMax": null,
#     "YearMin": null,
#     "YearMax": null,
#     "Keywords": "",
#     "FuelTypes": null, # Likely specific values exist
#     "Transmissions": null, # e.g., "Automatic", "Manual"
#     "Colours": null, # e.g., "Red", "Black"
#     "Drivetrain": null, # e.g., "AWD", "FWD"
#     "Engine": null,
#     "SeatingCapacity": null,
#     "NumberOfDoors": null,
#     "Sleeps": null,
#     "SlideOuts": null,
#     "Trim": null, # e.g., "Sport", "Limited"
#     "RelatedCompanyOwnerCompositeId": null,
#     "": null # Unclear what this empty key is for
# }
# --- End Schema ---


# Global variables
start_time = None
# Cache for vehicle info to avoid duplicate requests (lru_cache will be removed)
# vehicle_info_cache = {} # Removed, using CSV cache now

# --- CSV Cache Configuration ---
CACHE_FILE = "autoscraper_cache.csv"
CACHE_HEADERS = [
    "Link", "Make", "Model", "Year", "Trim", "Price", "Drivetrain",
    "Kilometres", "Status", "Body Type", "Engine", "Cylinder",
    "Transmission", "Exterior Colour", "Doors", "Fuel Type",
    "City Fuel Economy", "Hwy Fuel Economy", "date_cached" # Added date column
]

def load_cache(filepath=CACHE_FILE):
    """Loads the CSV cache file into a dictionary."""
    cache = {}
    try:
        with open(filepath, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != CACHE_HEADERS:
                 logger.warning(f"Cache file '{filepath}' headers mismatch expected headers. Rebuilding cache might be necessary.")
                 # Decide if you want to return {} or try to proceed
                 # return {}
            for row in reader:
                link = row.get("Link")
                if link:
                    cache[link] = row
        logger.info(f"Loaded {len(cache)} items from cache file '{filepath}'.")
    except FileNotFoundError:
        logger.info(f"Cache file '{filepath}' not found. A new one will be created.")
    except Exception as e:
        logger.error(f"Error loading cache file '{filepath}': {e}")
    return cache

def append_to_cache(data_rows, filepath=CACHE_FILE, headers=CACHE_HEADERS):
    """Appends new data rows (list of dicts) to the CSV cache file."""
    if not data_rows:
        return

    file_exists = os.path.isfile(filepath)
    try:
        with open(filepath, mode='a', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            if not file_exists or os.path.getsize(filepath) == 0:
                writer.writeheader()
                logger.info(f"Created or wrote headers to cache file '{filepath}'.")
            writer.writerows(data_rows)
        logger.info(f"Appended {len(data_rows)} new items to cache file '{filepath}'.")
    except Exception as e:
        logger.error(f"Error appending to cache file '{filepath}': {e}")

def write_cache(cache_dict, filepath=CACHE_FILE, headers=CACHE_HEADERS):
    """Writes the entire cache dictionary to the CSV file, overwriting existing content."""
    try:
        with open(filepath, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(cache_dict.values()) # Write all values from the cache dict
        logger.info(f"Wrote {len(cache_dict)} items to cache file '{filepath}'.")
    except Exception as e:
        logger.error(f"Error writing cache file '{filepath}': {e}")


def get_proxy_from_file(filename = "proxyconfig.json"):
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        return f"File '{filename}' not found."
    except json.JSONDecodeError:
        return "Invalid JSON format."

# Reduced default max_workers significantly
def fetch_autotrader_data(params, max_retries=5, initial_retry_delay=0.5, max_workers=1000,
                          initial_fetch_only=False, start_page=1, initial_results_html=None, max_page_override=None,
                          task_instance=None): # Added task_instance
    call_specific_start_time = time.time() # For timing this specific call
    """
    Fetch data from AutoTrader.ca API. Can perform an initial fetch for count or fetch all pages.

    Args:
        params (dict): Search parameters.
        max_retries (int): Max retries for empty responses.
        initial_retry_delay (float): Initial retry delay.
        max_workers (int): Max concurrent workers.
        initial_fetch_only (bool): If True, fetches only page 0 and returns count estimate.
        start_page (int): Page number to start fetching from (used when initial_fetch_only=False).
        initial_results_html (list, optional): Parsed HTML results from page 0 (passed in second stage).
        max_page_override (int, optional): Known max page number (passed in second stage).

    Returns:
        dict or list: If initial_fetch_only=True, returns dict with estimate. Otherwise, list of results.
    """
    global start_time
    # Only reset timer on the first call (or when not continuing a fetch)
    if start_page <= 1 and initial_results_html is None:
        start_time = time.time()

    # Set default values for parameters
    default_params = {
        "Make": "",
        "Model": "",
        "Proximity": "-1",
        "PriceMin": 0,
        "PriceMax": 999999,
        "YearMin": "1950",
        "YearMax": "2050",
        "Address": "Kanata, ON",
        "IsNew": True,
        "IsUsed": True,
        "WithPhotos": True,
        "WithPrice": True,
        "Exclusions": [],
        "OdometerMin": None,
        "OdometerMax": None,
        "Trim": None,
        "Color": None,
        "Drivetrain": None,
        "Transmission": None,
        # Add defaults for new payload fields
        "IsDamaged": False, # Default to not including damaged
        "BodyType": None,
        "NumberOfDoors": None,
        "SeatingCapacity": None,
        "micrositeType":1,
        "Skip" : 0,
        "Top" : 15
    }

    # Merge provided params with defaults
    params = {**default_params, **{k: v for k, v in params.items() if v is not None}} # Ensure None doesn't overwrite defaults if passed explicitly
    print(params)
    # Clean up potential "Any" or empty string values passed from the frontend if they weren't caught earlier
    if params.get("Trim") == "Any" or params.get("Trim") == "": params["Trim"] = None
    if params.get("Color") == "Any" or params.get("Color") == "": params["Color"] = None
    if params.get("Drivetrain") == "Any" or params.get("Drivetrain") == "": params["Drivetrain"] = None
    if params.get("Transmission") == "Any" or params.get("Transmission") == "": params["Transmission"] = None
    # Clean up new fields
    if params.get("BodyType") == "Any" or params.get("BodyType") == "": params["BodyType"] = None
    # For numeric fields, ensure they are numbers or None. Assume "Any" maps to None.
    try:
        if params.get("NumberOfDoors") == "Any" or params.get("NumberOfDoors") == "":
             params["NumberOfDoors"] = None
        elif params.get("NumberOfDoors") is not None:
             params["NumberOfDoors"] = int(params["NumberOfDoors"])
    except (ValueError, TypeError):
         logger.warning(f"Invalid NumberOfDoors value received: {params.get('NumberOfDoors')}. Setting to None.")
         params["NumberOfDoors"] = None
    try:
        if params.get("SeatingCapacity") == "Any" or params.get("SeatingCapacity") == "":
             params["SeatingCapacity"] = None
        elif params.get("SeatingCapacity") is not None:
             params["SeatingCapacity"] = int(params["SeatingCapacity"])
    except (ValueError, TypeError):
         logger.warning(f"Invalid SeatingCapacity value received: {params.get('SeatingCapacity')}. Setting to None.")
         params["SeatingCapacity"] = None
    # Ensure IsDamaged is boolean
    if not isinstance(params.get("IsDamaged"), bool):
        # Handle potential string "true"/"false" from form if needed, default to False
        params["IsDamaged"] = str(params.get("IsDamaged")).lower() == 'true'


    # Get raw exclusions first
    raw_exclusions = params.get("Exclusions", [])
    # Transform exclusions for later use (e.g., final filtering if needed)
    transformed_exclusions = transform_strings(raw_exclusions)
    logger.info(f"Using raw exclusions for initial parsing: {raw_exclusions}")
    logger.info(f"Transformed exclusions for later steps: {transformed_exclusions}")

    url = "https://www.autotrader.ca/Refinement/Search"
    proxy = get_proxy_from_file()
    logger.info(f"Search parameters: {params}")

    # Create a session object with a larger connection pool
    session = requests.Session()
    # Configure adapter with increased pool size
    adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100)
    # Optional: Add retries for connection errors, etc.
    # retry_strategy = Retry(
    #     total=3,
    #     status_forcelist=[429, 500, 502, 503, 504],
    #     allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
    #     backoff_factor=1
    # )
    # adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retry_strategy)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    })
    session.proxies.update(proxy) # Add proxies to the session

    def fetch_page(page, session):
        """
        Fetch a single page using a session with exponential backoff retry logic.

        Args:
            page (int): Page number to fetch.
            session (requests.Session): The session object to use.

        Returns:
            tuple: (parsed_html_page, max_page, search_results_dict)
                   Returns ([], 1, {}) on failure after retries.
        """
        retry_delay = initial_retry_delay

        for attempt in range(max_retries):
            payload = {
                "Address": params["Address"],
                "Proximity": params["Proximity"],
                "Make": params["Make"],
                "Model": params.get("Model"), # Use .get for safety
                # "Trim": params["Trim"], # Keep commented, use trimm below if needed
                "PriceMin": params.get("PriceMin"),
                "PriceMax": params.get("PriceMax"),
                "Skip": page * params.get("Top", 100), # Use .get for safety
                "Top": params["Top"],
                "IsNew": params["IsNew"],
                "IsUsed": params.get("IsUsed"),
                "WithPhotos": params.get("WithPhotos"),
                "YearMax": params.get("YearMax"),
                "YearMin": params.get("YearMin"),
                "OdometerMin": params.get("OdometerMin"),
                "OdometerMax": params.get("OdometerMax"),
                "micrositeType": 1,
            }
            # Conditionally add new parameters if they exist, using keys from example
            if params.get("Trim"):
                payload["Trim"] = params["Trim"]
            if params.get("Color"):
                 payload["Colours"] = params["Color"] # Note the 'u' and plural
            if params.get("Drivetrain"):
                 payload["Drivetrain"] = params["Drivetrain"]
            if params.get("Transmission"):
                 payload["Transmissions"] = params["Transmission"] # Note the plural
            # Add new parameters conditionally
            if params.get("IsDamaged") is not None: # Check explicitly for None if default is False
                 payload["IsDamaged"] = params["IsDamaged"]
            if params.get("BodyType"):
                 payload["BodyType"] = params["BodyType"]
            if params.get("NumberOfDoors"):
                 payload["NumberOfDoors"] = params["NumberOfDoors"]
            if params.get("SeatingCapacity"):
                 payload["SeatingCapacity"] = params["SeatingCapacity"]


            try:
                # Use the session object for the request
                # Use the session object for the request
                response = session.post(url=url, json=payload, timeout=30) # Headers and proxies are now part of the session
                time.sleep(0.25) # Add a small delay after each request
                response.raise_for_status()
                json_response = response.json()
                search_results_json_str = json_response.get("SearchResultsDataJson", "")
                ad_results_json = json_response.get("AdsHtml", "")

                if not search_results_json_str:
                    # Handle cases where only AdsHtml might be present but no SearchResultsDataJson
                    if ad_results_json and page == 0: # Only parse HTML if it's page 0 and we need initial results
                         # Pass RAW exclusions to parse_html_content (filtering removed there later)
                         parsed_html_page = parse_html_content(ad_results_json, raw_exclusions)
                         logger.warning(f"No SearchResultsDataJson for page {page}, but AdsHtml found. Estimating max_page as 1.")
                         return parsed_html_page, 1, {} # Cannot determine max_page or count accurately
                    elif ad_results_json: # For subsequent pages, just return the HTML
                         # Pass RAW exclusions to parse_html_content (filtering removed there later)
                         parsed_html_page = parse_html_content(ad_results_json, raw_exclusions)
                         logger.warning(f"No SearchResultsDataJson for page {page}, but AdsHtml found.")
                         return parsed_html_page, 1, {} # Cannot determine max_page accurately
                    else:
                        logger.warning(f"No results (neither SearchResultsDataJson nor AdsHtml) for page {page} (Attempt {attempt + 1}/{max_retries}). Retrying...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30) # Exponential backoff
                        continue

                # If we have SearchResultsDataJson, parse it
                search_results_dict = json.loads(search_results_json_str)
                 # Pass RAW exclusions to parse_html_content (filtering removed there later)
                parsed_html_page = parse_html_content(ad_results_json, raw_exclusions) # Parse HTML ads as well
                max_page_from_json = search_results_dict.get("maxPage", 1)
                return parsed_html_page, max_page_from_json, search_results_dict

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for page {page}: {e}. Retrying...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30) # Exponential backoff
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on page {page} for SearchResultsDataJson: {e}. Content: '{search_results_json_str[:200]}...' Retrying...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30) # Exponential backoff

        # If all retries fail, return an empty result
        logger.error(f"Failed to fetch page {page} after {max_retries} attempts.")
        return [], 1, {} # Return empty results, max_page 1, and empty search_results dict

    # --- Initial Fetch Logic ---
    if initial_fetch_only:
        logger.info("Performing initial fetch (page 0) for count estimate...")
        page_0_results_html, max_page, search_results_data = fetch_page(0, session)

        # Estimate total count - Look for a specific key, fallback to calculation
        estimated_count = search_results_data.get("totalResultCount") # Common key name
        if estimated_count is None:
            estimated_count = search_results_data.get("totalResults") # Another possibility
        if estimated_count is None:
             # Fallback: Estimate based on max_page and items per page
            estimated_count = max_page * params["Top"]
            logger.warning(f"Could not find exact total count key in search results. Estimating as {estimated_count} ({max_page} pages * {params['Top']} items/page).")
        else:
            # Ensure estimated_count is an integer
            try:
                estimated_count = int(estimated_count)
                logger.info(f"Found exact total count: {estimated_count}")
            except (ValueError, TypeError):
                 logger.warning(f"Found total count key, but value '{estimated_count}' is not an integer. Estimating based on pages.")
                 estimated_count = max_page * params["Top"]


        logger.info(f"Initial fetch complete. Estimated listings: {estimated_count}, Max pages: {max_page}")
        
        current_call_duration = time.time() - call_specific_start_time
        logger.info(f"fetch_autotrader_data (initial_fetch_only=True) call took: {current_call_duration:.2f} seconds")
        
        return {
            'estimated_count': estimated_count,
            'initial_results_html': page_0_results_html, # Parsed HTML results from page 0
            'max_page': max_page
        }

    # --- Full Fetch Logic (or continuation) ---
    all_results = []
    pages_completed = 0
    max_page = 1 # Default

    if initial_results_html is not None and max_page_override is not None:
        # This is the second stage call, we already have page 0 results and max_page
        all_results = initial_results_html
        max_page = max_page_override
        pages_completed = 1 # Page 0 is done
        logger.info(f"Continuing fetch from page {start_page} to {max_page}. Page 0 results provided.")
    else:
        # This is a direct full fetch call (or first stage if initial_fetch_only was False)
        logger.info("Performing full fetch...")
        page_0_results_html, max_page, _ = fetch_page(0, session)
        all_results = page_0_results_html
        pages_completed = 1 # Page 0 is done
        logger.info(f"Full fetch: Found {max_page} pages. Starting from page {start_page}.")


    # Determine pages to fetch in this stage
    pages_to_fetch = list(range(start_page, max_page))

    if not pages_to_fetch:
         logger.info("No further pages to fetch (or only page 0 existed).")
    else:
        logger.info(f"Fetching pages {start_page} to {max_page - 1}...")
        # Process remaining pages concurrently using the session
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all page fetch tasks, passing the session
            future_to_page = {executor.submit(fetch_page, page, session): page for page in pages_to_fetch}

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    # We only need the HTML results here, ignore max_page and search_results_data
                    page_results_html, _, _ = future.result()
                    all_results.extend(page_results_html)
                    pages_completed += 1

                    # Update progress via Celery task if available
                    if task_instance:
                        task_instance.update_progress(pages_completed, max_page, step=f"Fetching page {pages_completed}/{max_page}")
                    else: # Fallback to console logging if no task instance
                        cls()
                        logger.info(f"{pages_completed} out of {max_page} total pages completed")
                        print(f"{pages_completed} out of {max_page} total pages completed")
                except Exception as e:
                    logger.error(f"Error processing page {page}: {e}")

    # Remove duplicates (pass transformed exclusions, though function ignores them now for filtering)
    unique_link_results = remove_duplicates_exclusions(all_results, transformed_exclusions)
    logger.info(f"Found {len(unique_link_results)} unique listings after duplicate removal.") # Renamed variable

    # Avoid logging negative time if start_time wasn't set (e.g., only second stage ran)
    if start_time: # This refers to the global start_time for the whole operation
        elapsed = time.time() - start_time
        logger.info(f"Total fetch time for operation: {elapsed:.2f} seconds")

    current_call_duration = time.time() - call_specific_start_time
    logger.info(f"fetch_autotrader_data (full fetch part) call took: {current_call_duration:.2f} seconds")

    # Filtering based on content will happen in process_links_and_update_cache
    return unique_link_results


# Removed @lru_cache and the wrapper function extract_vehicle_info_cached
# The CSV cache handles persistence now.

def extract_vehicle_info(url):
    """
    Extracts vehicle info from the provided URL with improved error handling
    and exponential backoff for rate limiting.

    Args:
        url (str): The URL to fetch data from.

    Returns:
        dict: Vehicle information extracted from the URL.
    """
    # Manual cache dictionary removed; relying on @lru_cache on the wrapper function.

    # Create a session object for this function scope
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    proxy = get_proxy_from_file()
    session.proxies.update(proxy) # Add proxies to the session

    initial_delay = .25  # Seconds to wait initially
    max_retries = 12   # Maximum retry attempts for rate limiting
    retry_delay = initial_delay

    try:
        for attempt in range(max_retries):
            # Use the session object for the request
            response = session.get(url, timeout=30) # Headers and proxies are now part of the session

            # Check for rate limiting via HTTP status code
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limited (HTTP 429). Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    # Exponential backoff with max of 60 seconds
                    retry_delay = min(retry_delay * 2, 10)
                    continue
                else:
                    raise Exception("Rate limited: HTTP 429 Too Many Requests.")

            response.raise_for_status()  # Raise for other HTTP errors

            # Check for rate limiting patterns in the response text
            if "Request unsuccessful." in response.text or "Too Many Requests" in response.text:
                if attempt < max_retries - 1:
                    logger.warning(f"Rate limited (Response Text). Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    # Exponential backoff with max of 60 seconds
                    retry_delay = min(retry_delay * 2, 10)
                    continue
                else:
                    raise Exception("Rate limited: Response indicates too many requests.")

            logger.debug(f"Successfully fetched vehicle info for {url}")
            # time.sleep(1)  # Brief pause to be nice to the server

            # Parse the response JSON or HTML content
            respjson = parse_html_content_to_json(response.text)
            car_info = extract_vehicle_info_from_json(respjson)

            # Caching is handled by @lru_cache on extract_vehicle_info_cached

            return car_info

        # If all retries fail, raise a final exception
        raise Exception("Failed to fetch data after multiple attempts due to rate limiting.")

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP error for {url}: {e}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error for {url}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        return {}

def extract_vehicle_info_from_json(json_content):
    """
    Extracts vehicle information from a JSON object with improved error handling.

    Args:
        json_content (dict): The JSON content as a dictionary.

    Returns:
        dict: A dictionary containing extracted vehicle details.
    """
    if not json_content:
        return {}

    try:
        # Map of keys to extract from Specifications
        vehicle_info = {}
        hero = json_content.get("HeroViewModel", {})
        vehicle_info.update({
            "Make": hero.get("Make", ""),
            "Model": hero.get("Model", ""),
            "Trim": hero.get("Trim", ""),
            "Price": hero.get("Price", ""),
            "Kilometres": hero.get("mileage", ""),
            "Drivetrain": hero.get("drivetrain", ""),
            "Year": hero.get("Year", "")
        })

        keys_to_extract = {
            "Kilometres": "Kilometres",
            "Status": "Status",
            "Trim": "Trim",
            "Body Type": "Body Type",
            "Engine": "Engine",
            "Cylinder": "Cylinder",
            "Transmission": "Transmission",
            "Drivetrain": "Drivetrain",
            "Exterior Colour": "Exterior Colour",
            "Doors": "Doors",
            "Fuel Type": "Fuel Type",
            "City Fuel Economy": "City Fuel Economy",
            "Hwy Fuel Economy": "Hwy Fuel Economy"
        }

        # Extract specifications
        specs = json_content.get("Specifications", {}).get("Specs", [])

        for spec in specs:
            key = spec.get("Key")
            value = spec.get("Value")
            if key in keys_to_extract and "Fuel Economy" not in key and "Kilometres" not in key:
                vehicle_info[keys_to_extract[key]] = value
            elif "Fuel Economy" in key:
                vehicle_info[keys_to_extract[key]] = value.split("L")[0] if value else ""
            elif "Kilometres" in key:
                vehicle_info[keys_to_extract[key]] = convert_km_to_double(value) if value else 0

        # Ensure all required keys are present
        for required_key in keys_to_extract.values():
            if required_key not in vehicle_info:
                vehicle_info[required_key] = ""

        return vehicle_info
    except Exception as e:
        logger.error(f"Error extracting vehicle info: {e}")
        return {}

# Add transformed_exclusions and task_instance parameters
# Reduced default max_workers significantly
def process_links_and_update_cache(data, transformed_exclusions, max_workers=1000, task_instance=None):
    """
    Processes links, using and updating a persistent CSV cache.
    Fetches data for new links, filters based on exclusions, and updates the cache file.
    Returns the data for all links relevant to the current search (cached or newly fetched).

    Args:
        data (list): List of link dictionaries (e.g., [{'link': 'url1'}, {'link': 'url2'}]).
        max_workers (int): Maximum number of concurrent workers for fetching new data.

    Returns:
        list: A list of dictionaries, where each dictionary represents a car's data
              corresponding to the input links.
    """
    global start_time # Keep track of overall time if needed
    if not start_time: # Ensure start_time is set if this is the first major step
        start_time = time.time()

    logger.info(f"Processing {len(data)} links with exclusions. Loading cache...")
    persistent_cache = load_cache() # Load the main cache
    results_for_current_search = [] # Holds results (dict) for this specific run
    links_to_fetch = [] # Links not found in cache or stale
    # Prepare lowercase exclusions for efficient filtering
    lower_exclusion_strings = [excl.lower() for excl in transformed_exclusions]
    cache_hits_fresh = 0
    cache_hits_stale = 0
    cache_misses = 0

    today_date = datetime.date.today().isoformat() # Get today's date as YYYY-MM-DD string

    # 1. Check cache and filter fresh hits
    logger.info("Checking cache and filtering fresh hits...")
    for item in data:
        link = item.get("link")
        if not link:
            logger.warning("Skipping item with no link.")
            continue

        cached_item = persistent_cache.get(link)
        if cached_item:
            # Cache Hit: Check if it's fresh (cached today)
            if cached_item.get('date_cached') == today_date:
                # Apply exclusion filter to fresh cache hit
                is_excluded = any(excl_lower in str(value).lower() for value in cached_item.values() for excl_lower in lower_exclusion_strings)
                if not is_excluded:
                    results_for_current_search.append(cached_item)
                    cache_hits_fresh += 1
                    logger.debug(f"Cache hit (fresh, kept) for: {link}")
                else:
                    cache_hits_fresh += 1 # Count as hit, but excluded
                    logger.debug(f"Cache hit (fresh, excluded) for: {link}")
            else:
                # Stale Cache Hit: Mark for re-fetching (will be filtered after fetch)
                links_to_fetch.append(item)
                cache_hits_stale += 1
                logger.debug(f"Cache hit (stale, cached {cached_item.get('date_cached')}) for: {link}. Marked for refresh.")
        else:
            # Cache Miss: Mark for fetching
            links_to_fetch.append(item)
            cache_misses += 1
            logger.debug(f"Cache miss for: {link}")

    # Log cache statistics
    logger.info(f"Cache Stats: {cache_hits_fresh} fresh hits, {cache_hits_stale} stale hits, {cache_misses} misses.")
    logger.info(f"Found {len(persistent_cache)} total items currently in cache.")
    logger.info(f"Need to fetch/refresh {len(links_to_fetch)} links (stale + misses).")

    # 2. Fetch data for new links concurrently
    if links_to_fetch:
        processed_new = 0
        total_to_fetch = len(links_to_fetch)
        logger.info(f"Starting concurrent fetch for {total_to_fetch} links with {max_workers} workers...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_link_item = {executor.submit(extract_vehicle_info, item["link"]): item for item in links_to_fetch}

            for future in concurrent.futures.as_completed(future_to_link_item):
                link_item = future_to_link_item[future]
                link = link_item["link"]
                try:
                    car_info = future.result() # car_info is a dict from extract_vehicle_info
                    if car_info:
                        # Add the link itself and date to the car_info dict
                        car_info_with_link = {"Link": link, **car_info, 'date_cached': today_date}

                        # Ensure all headers are present, fill missing with ""
                        row_dict = {header: car_info_with_link.get(header, "") for header in CACHE_HEADERS}

                        # Apply exclusion filter *before* adding to results or cache
                        is_excluded = any(excl_lower in str(value).lower() for value in row_dict.values() for excl_lower in lower_exclusion_strings)

                        if not is_excluded:
                            results_for_current_search.append(row_dict) # Add to current search results
                            persistent_cache[link] = row_dict # Update in-memory cache (overwrites stale if existed)
                            logger.debug(f"Successfully fetched/refreshed and kept: {link}")
                        else:
                            # If excluded, don't add to results, but DO update cache if it was stale
                            # to prevent re-fetching an excluded item repeatedly.
                            # However, if it was a *new* miss, don't add the excluded item to cache.
                            if link in persistent_cache: # Only update cache if it was stale
                                persistent_cache[link] = row_dict # Update cache with excluded item to mark as 'fetched today'
                                logger.debug(f"Successfully fetched/refreshed but excluded: {link}. Cache updated.")
                            else: # It was a new miss and excluded
                                logger.debug(f"Successfully fetched new item but excluded: {link}. Not added to cache.")
                    else:
                        logger.warning(f"Failed to fetch data for {link}, skipping.")

                    processed_new += 1
                    # Update progress via Celery task if available, periodically
                    if task_instance and (processed_new % 5 == 0 or processed_new == total_to_fetch):
                        task_instance.update_progress(processed_new, total_to_fetch, step=f"Processing link {processed_new}/{total_to_fetch}")
                    elif processed_new % 5 == 0 or processed_new == total_to_fetch: # Fallback to console logging
                        cls()
                        progress = (processed_new / total_to_fetch) * 100
                        print(f"Processing Link Progress: {processed_new}/{total_to_fetch} ({progress:.1f}%)")
                        logger.info(f"Processing Link Progress: {processed_new}/{total_to_fetch} ({progress:.1f}%)")

                except Exception as e:
                    logger.error(f"Error processing future for {link}: {e}")

    # 3. Write the potentially updated cache back to the file
    # Cache now contains non-excluded new items, updated non-excluded stale items,
    # and potentially updated but excluded stale items (to prevent re-fetch).
    write_cache(persistent_cache)

    # Filtering was applied as items were processed.
    logger.info(f"Finished processing links and updated cache. Returning {len(results_for_current_search)} filtered results for this search.")
    # Note: The returned list contains dicts. The calling function will handle writing to the timestamped CSV.
    return results_for_current_search

    # The filter_csv call at the end of the script/calling function should be removed
    # as filtering is now done here.
    # print(f"Results saved to {filename}") # This print and the filter_csv call below likely belong in the calling script, not here.
