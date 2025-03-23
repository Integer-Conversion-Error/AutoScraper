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

def fetch_autotrader_data(params, max_retries=5, initial_retry_delay=0.5, max_workers=200):
    """
    Fetch data from AutoTrader.ca API concurrently by processing pages in parallel.
    
    Args:
        params (dict): Dictionary containing search parameters with default values.
        max_retries (int): Maximum number of retries for empty responses.
        initial_retry_delay (int): Initial delay (in seconds) between retries (will increase with backoff).
        max_workers (int): Maximum number of concurrent workers for fetching pages.

    Returns:
        list: Combined list of all results from all pages.
    """
    global start_time
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
        "OdometerMax": None
    }
    
    params = {**default_params, **params}
    if params.get("Trim") == "All":
        params.update({"Trim": None})
        
    exclusions = transform_strings(params["Exclusions"])  # Cover upper/lower-case
    url = "https://www.autotrader.ca/Refinement/Search"
    proxy = get_proxy_from_file()
    logger.info(f"Search parameters: {params}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def fetch_page(page):
        """
        Fetch a single page with exponential backoff retry logic.
        
        Args:
            page (int): Page number to fetch.
            
        Returns:
            tuple: (parsed_html_page, max_page)
        """
        retry_delay = initial_retry_delay
        
        for attempt in range(max_retries):
            payload = {
                "Address": params["Address"],
                "Proximity": params["Proximity"],
                "Make": params["Make"],
                "Model": params["Model"],
                #"Trim": params["Trim"],
                "PriceMin": params["PriceMin"],
                "PriceMax": params["PriceMax"],
                "Skip": page * params["Top"],
                "Top": params["Top"],
                "IsNew": params["IsNew"],
                "IsUsed": params["IsUsed"],
                "WithPhotos": params["WithPhotos"],
                "YearMax": params["YearMax"],
                "YearMin": params["YearMin"],
                "OdometerMin": params["OdometerMin"],
                "OdometerMax": params["OdometerMax"],
                "micrositeType": 1,
            }
            
            try:
                response = requests.post(url=url, headers=headers, json=payload, timeout=30, proxies=proxy)
                response.raise_for_status()
                json_response = response.json()
                search_results_json = json_response.get("SearchResultsDataJson", "")
                ad_results_json = json_response.get("AdsHtml", "")

                if not search_results_json:
                    logger.warning(f"No results for page {page} (Attempt {attempt + 1}/{max_retries}). Retrying...")
                    time.sleep(retry_delay)
                    # Exponential backoff with max of 30 seconds
                    retry_delay = min(retry_delay * 2, 30)
                    continue

                parsed_html_page = parse_html_content(ad_results_json, exclusions)
                search_results = json.loads(search_results_json)
                return parsed_html_page, search_results.get("maxPage", 1)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for page {page}: {e}. Retrying...")
                time.sleep(retry_delay)
                # Exponential backoff with max of 30 seconds
                retry_delay = min(retry_delay * 2, 30)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on page {page}: {e}. Retrying...")
                time.sleep(retry_delay)
                # Exponential backoff with max of 30 seconds
                retry_delay = min(retry_delay * 2, 30)
        
        # If all retries fail, return an empty result
        logger.error(f"Failed to fetch page {page} after {max_retries} attempts.")
        return [], 1

    # Fetch the first page to determine the total number of pages
    initial_results, max_page = fetch_page(0)
    all_results = initial_results
    
    logger.info(f"Found {max_page} pages to fetch.")
    
    # Create a list to hold the remaining pages to fetch
    pages_to_fetch = list(range(1, max_page))
    pages_completed = 1  # We already fetched page 0
    
    # Process remaining pages concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all page fetch tasks
        future_to_page = {executor.submit(fetch_page, page): page for page in pages_to_fetch}
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(future_to_page):
            page = future_to_page[future]
            try:
                page_results, _ = future.result()
                all_results.extend(page_results)
                pages_completed += 1
                
                # Update progress
                cls()
                logger.info(f"{pages_completed} out of {max_page} total pages completed")
                print(f"{pages_completed} out of {max_page} total pages completed")
            except Exception as e:
                logger.error(f"Error processing page {page}: {e}")

    # Remove duplicates and apply exclusions
    filtered_results = remove_duplicates_exclusions(all_results, params["Exclusions"])
    logger.info(f"Found {len(filtered_results)} unique listings after filtering.")
    
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
    # Check if URL is in cache
    if url in vehicle_info_cache:
        return vehicle_info_cache[url]
    
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"
    ACCEPT_HEADER = "application/json, text/javascript, */*; q=0.01"
    REFERER = "https://www.google.com/"
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": ACCEPT_HEADER,
        "Referer": REFERER,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    proxy = get_proxy_from_file()
    initial_delay = .25  # Seconds to wait initially
    max_retries = 12   # Maximum retry attempts for rate limiting
    retry_delay = initial_delay

    try:
        for attempt in range(max_retries):
            response = requests.get(url, headers=headers, proxies=proxy, timeout=30)
            
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
            
            # Store in cache
            vehicle_info_cache[url] = car_info
            
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
                    results = fetch_autotrader_data(payload)
                    
                    if not results:
                        logger.warning("No results found")
                        print("No results found. Try adjusting your search parameters.")
                        continue
                        
                    results = remove_duplicates_exclusions(results, payload["Exclusions"])
                    logger.info(f"Found {len(results)} unique results after filtering exclusions")
                    
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