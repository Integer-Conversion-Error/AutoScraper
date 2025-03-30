import concurrent.futures
import requests
import json
import csv
import time
import os
import logging
from functools import lru_cache
from GetUserSelection import get_user_responses, cleaned_input
from AutoScraperUtil import *

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
# Cache for vehicle info to avoid duplicate requests
vehicle_info_cache = {}


def get_proxy_from_file(filename = "proxyconfig.json"):
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        return f"File '{filename}' not found."
    except json.JSONDecodeError:
        return "Invalid JSON format."

def fetch_autotrader_data(params, max_retries=5, initial_retry_delay=0.5, max_workers=200,
                          initial_fetch_only=False, start_page=1, initial_results_html=None, max_page_override=None):
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
        "Top": 100,
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
        "SeatingCapacity": None
    }

    # Merge provided params with defaults
    params = {**default_params, **{k: v for k, v in params.items() if v is not None}} # Ensure None doesn't overwrite defaults if passed explicitly

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


    exclusions = transform_strings(params.get("Exclusions", []))  # Cover upper/lower-case, handle missing key
    url = "https://www.autotrader.ca/Refinement/Search"
    proxy = get_proxy_from_file()
    logger.info(f"Search parameters: {params}")

    # Create a session object
    session = requests.Session()
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
                response = session.post(url=url, json=payload, timeout=30) # Headers and proxies are now part of the session
                response.raise_for_status()
                json_response = response.json()
                search_results_json_str = json_response.get("SearchResultsDataJson", "")
                ad_results_json = json_response.get("AdsHtml", "")

                if not search_results_json_str:
                    # Handle cases where only AdsHtml might be present but no SearchResultsDataJson
                    if ad_results_json and page == 0: # Only parse HTML if it's page 0 and we need initial results
                         parsed_html_page = parse_html_content(ad_results_json, exclusions)
                         logger.warning(f"No SearchResultsDataJson for page {page}, but AdsHtml found. Estimating max_page as 1.")
                         return parsed_html_page, 1, {} # Cannot determine max_page or count accurately
                    elif ad_results_json: # For subsequent pages, just return the HTML
                         parsed_html_page = parse_html_content(ad_results_json, exclusions)
                         logger.warning(f"No SearchResultsDataJson for page {page}, but AdsHtml found.")
                         return parsed_html_page, 1, {} # Cannot determine max_page accurately
                    else:
                        logger.warning(f"No results (neither SearchResultsDataJson nor AdsHtml) for page {page} (Attempt {attempt + 1}/{max_retries}). Retrying...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30) # Exponential backoff
                        continue

                # If we have SearchResultsDataJson, parse it
                search_results_dict = json.loads(search_results_json_str)
                parsed_html_page = parse_html_content(ad_results_json, exclusions) # Parse HTML ads as well
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

                    # Update progress
                    cls()
                    logger.info(f"{pages_completed} out of {max_page} total pages completed")
                    print(f"{pages_completed} out of {max_page} total pages completed")
                except Exception as e:
                    logger.error(f"Error processing page {page}: {e}")

    # Remove duplicates and apply exclusions (only at the very end)
    filtered_results = remove_duplicates_exclusions(all_results, exclusions) # Use already transformed exclusions
    logger.info(f"Found {len(filtered_results)} unique listings after filtering.")

    # Avoid logging negative time if start_time wasn't set (e.g., only second stage ran)
    if start_time:
        elapsed = time.time() - start_time
        logger.info(f"Total fetch time: {elapsed:.2f} seconds")

    return filtered_results


@lru_cache(maxsize=128)
def extract_vehicle_info_cached(url):
    """
    Cached version of extract_vehicle_info to avoid redundant requests.

    Args:
        url (str): The URL to fetch data from.

    Returns:
        dict: Vehicle information extracted from the URL.
    """
    return extract_vehicle_info(url)

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

def save_results_to_csv(data, payload, filename="results.csv", max_workers=10):
    """
    Saves fetched data by processing it concurrently with a thread pool.

    Args:
        data (list): List of links to save.
        payload (dict): Payload containing additional filtering criteria.
        filename (str): Name of the CSV file.
        max_workers (int): Maximum number of concurrent workers.
    """
    global start_time
    allColNames = [
        "Link",
        "Make",
        "Model",
        "Year",
        "Trim",
        "Price",
        "Drivetrain",
        "Kilometres",
        "Status",
        "Body Type",
        "Engine",
        "Cylinder",
        "Transmission",
        "Exterior Colour",
        "Doors",
        "Fuel Type",
        "City Fuel Economy",
        "Hwy Fuel Economy"
    ]

    def process_link(item):
        """
        Worker function to process each link.

        Args:
            item (dict): Dictionary containing link information.

        Returns:
            list: Processed row for CSV or None if extraction fails.
        """
        link = item["link"]

        try:
            car_info = extract_vehicle_info_cached(link)
            if car_info:
                return [
                    link,
                    car_info.get("Make", ""),
                    car_info.get("Model", ""),
                    car_info.get("Year", ""),
                    car_info.get("Trim", ""),
                    car_info.get("Price", ""),
                    car_info.get("Drivetrain", ""),
                    car_info.get("Kilometres", ""),
                    car_info.get("Status", ""),
                    car_info.get("Body Type", ""),
                    car_info.get("Engine", ""),
                    car_info.get("Cylinder", ""),
                    car_info.get("Transmission", ""),
                    car_info.get("Exterior Colour", ""),
                    car_info.get("Doors", ""),
                    car_info.get("Fuel Type", ""),
                    car_info.get("City Fuel Economy", ""),
                    car_info.get("Hwy Fuel Economy", "")
                ]
            else:
                logger.warning(f"Failed to fetch data for {link}")
                return None
        except Exception as e:
            logger.error(f"Error processing {link}: {e}")
            return None

    results = []
    total_links = len(data)
    processed = 0

    logger.info(f"Starting to process {total_links} links concurrently with {max_workers} workers")

    # Process data concurrently using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all processing tasks
        future_to_item = {executor.submit(process_link, item): item for item in data}

        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                row = future.result()
                if row:
                    results.append(row)

                processed += 1

                # Update progress
                if processed % 5 == 0 or processed == total_links:
                    cls()
                    progress = (processed / total_links) * 100
                    print(f"Progress: {processed}/{total_links} ({progress:.1f}%)")

            except Exception as e:
                url = item.get("link", "unknown")
                logger.error(f"Error processing {url}: {e}")

    # Write to CSV after processing all data
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(allColNames)  # Write the header
        writer.writerows(results)

    # Avoid logging negative time if start_time wasn't set
    if start_time:
        elapsed_time = time.time() - start_time
        logger.info(f"CSV processing completed in {elapsed_time:.2f} seconds")
        print(f"Processed all in {elapsed_time:.2f}s")
    print(f"Results saved to {filename}")

    # Apply filtering
    filter_csv(filename, filename, payload=payload)

def main():
    """
    Main function to interact with the user with improved error handling.
    """
    logger.info("Starting AutoScraper")
    print("Welcome to the AutoScraper, a tool to speed up niche searches for cars on Autotrader!")
    file_initialisation()

    while True:
        try:
            foldernamestr, filenamestr, pld_name, jsonfilename = "", "", "", ""
            print("\nOptions:")
            print("1. Create a new payload")
            print("2. Save a payload to a file")
            print("3. Load a payload from a file")
            print("4. Fetch AutoTrader data")
            print("5. Exit")

            choice = input("Enter your choice: ")
            if choice == "1":
                payload = get_user_responses()
                logger.info("New payload created")
                print("Payload created:", payload)
                cls()
            elif choice == "2":
                if 'payload' in locals() and payload:
                    foldernamestr = f"Queries\\{payload['Make']}_{payload['Model']}"
                    filenamestr = f"{payload['YearMin']}-{payload['YearMax']}_{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.json"
                    pld_name = foldernamestr + "\\" + cleaned_input("Payload Name", filenamestr, str)
                    if not os.path.exists(foldernamestr):
                        os.makedirs(foldernamestr)
                        logger.info(f"Created folder: {foldernamestr}")
                    save_json_to_file(payload, pld_name)
                    logger.info(f"Saved payload to {pld_name}")
                    input(f"Payload saved to {pld_name}.\n\nPress enter to continue...")

                else:
                    print("No payload found. Please create one first.")

            elif choice == "3":
                jsonfilename = "Queries\\" + cleaned_input("Payload Name", "Ford_Fusion\\ff1.json", str)
                loaded_payload = read_json_file(jsonfilename)
                if loaded_payload:
                    payload = loaded_payload
                    logger.info(f"Loaded payload from {jsonfilename}")
                    cls()
                    print("Loaded payload:", payload)

            elif choice == "4":
                if 'payload' in locals() and payload:
                    logger.info("Starting data fetch with payload")
                    # This main function part is for standalone execution,
                    # The web app will call fetch_autotrader_data directly.
                    # We might need to adjust this if running standalone is still desired.
                    results = fetch_autotrader_data(payload) # Calls the full fetch directly

                    if not results:
                        logger.warning("No results found")
                        print("No results found. Try adjusting your search parameters.")
                        continue

                    # Duplicates are removed inside fetch_autotrader_data now
                    # results = remove_duplicates_exclusions(results, payload["Exclusions"])
                    # logger.info(f"Found {len(results)} unique results after filtering exclusions")

                    foldernamestr = f"Results\\{payload['Make']}_{payload['Model']}"
                    filenamestr = f"{foldernamestr}\\{payload['YearMin']}-{payload['YearMax']}_{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.csv"

                    if not os.path.exists(foldernamestr):
                        os.makedirs(foldernamestr)
                        logger.info(f"Created folder: {foldernamestr}")

                    save_results_to_csv(results, payload=payload, filename=filenamestr,max_workers=500)
                    logger.info(f"Total Results: {len(results)}, saved to {filenamestr}")
                    print(f"Total Results Fetched: {len(results)}\tResults saved to {filenamestr}")

                    # Open links in browser
                    if len(results) > 0:
                        showcarsmain(filenamestr)
                else:
                    print("No payload found. Please create or load one first.")

            elif choice == "5":
                logger.info("Exiting AutoScraper")
                print("Exiting AutoScraper. Goodbye!")
                break
            else:
                print("Invalid choice. Please try again.")
        except KeyboardInterrupt:
            logger.info("User interrupted execution")
            print("\nOperation interrupted by user. Returning to menu...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            print(f"An unexpected error occurred: {e}")
            print("Restarting main menu...")

if __name__ == "__main__":
    main()
