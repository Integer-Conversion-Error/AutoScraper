import concurrent
import requests,json,csv,time,os
from GetUserSelection import get_user_responses
from AutoScraperUtil import *
from concurrent.futures import ThreadPoolExecutor, as_completed

start_time = None

def fetch_autotrader_data(params, max_retries=3, retry_delay=1):
    """
    Fetch data from AutoTrader.ca API in parallel by dividing the task into pages.
    Retries fetching pages if no results are returned.

    Args:
        params (dict): Dictionary containing search parameters with default values.
        max_retries (int): Maximum number of retries for empty responses.
        retry_delay (int): Delay (in seconds) between retries.

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
        "Top": 15,
        "Address": "Kanata, ON",
        "IsNew": True,
        "IsUsed": True,
        "WithPhotos": True,
        "Exclusions": []
    }
    params = {**default_params, **params}
    exclusions = transform_strings(params["Exclusions"]) #cover upper/lower-case
    url = "https://www.autotrader.ca/Refinement/Search"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # Function to fetch a single page with retries
    def fetch_page(page):
        for attempt in range(max_retries):
            payload = {
                "Address": params["Address"],
                "Proximity": params["Proximity"],
                "Make": params["Make"],
                "Model": params["Model"],
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
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                json_response = response.json()
                search_results_json = json_response.get("SearchResultsDataJson", "")
                ad_results_json = json_response.get("AdsHtml", "")
                
                if not search_results_json:
                    print(f"No results for page {page} (Attempt {attempt + 1}/{max_retries}). Retrying...")
                    time.sleep(retry_delay)
                    continue

                parsed_html_page = parse_html_content(ad_results_json, exclusions)
                search_results = json.loads(search_results_json)
                return parsed_html_page, search_results.get("maxPage", 1)
            
            except requests.exceptions.RequestException as e:
                print(f"Request failed for page {page}: {e}. Retrying...")
                time.sleep(retry_delay)
            except json.JSONDecodeError as e:
                print(f"JSON decode error on page {page}: {e}. Retrying...")
                time.sleep(retry_delay)
        
        # If all retries fail, return an empty result
        print(f"Failed to fetch page {page} after {max_retries} attempts.")
        return [], 1

    # Fetch the first page to determine the total number of pages
    initial_results, max_page = fetch_page(0)
    all_results = initial_results

    # Fetch remaining pages in parallel
    with ThreadPoolExecutor() as executor:
        future_to_page = {
            executor.submit(fetch_page, page): page for page in range(1, max_page)
        }
        for future in as_completed(future_to_page):
            page = future_to_page[future]
            try:
                page_results, _ = future.result()
                all_results.extend(page_results)
                print(f"Page {page} fetched successfully.")
            except Exception as e:
                print(f"Error fetching page {page}: {e}")

    return all_results

def extract_vehicle_info(url):
    """
    Extracts vehicle info from the provided URL.
    Detects rate limiting and raises an error if encountered.

    Args:
        url (str): The URL to fetch data from.

    Returns:
        dict: Vehicle information extracted from the URL.

    Raises:
        Exception: If rate limiting or any other error is encountered.
    """
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

    rate_limit_wait = 3 # Seconds to wait before retrying
    max_retries = 12       # Maximum retry attempts for rate limiting

    try:
        for attempt in range(max_retries):
            response = requests.get(url, headers=headers, proxies=None)
            
            # Check for rate limiting via HTTP status code
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    print(f"Rate limited (HTTP 429). Retrying in {rate_limit_wait} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(rate_limit_wait)
                    continue
                else:
                    raise Exception("Rate limited: HTTP 429 Too Many Requests.")

            response.raise_for_status()  # Raise for other HTTP errors
            
            # Check for rate limiting patterns in the response text
            if "Request unsuccessful." in response.text or "Too Many Requests" in response.text:
                if attempt < max_retries - 1:
                    print(f"Rate limited (Response Text). Retrying in {rate_limit_wait} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(rate_limit_wait)
                    continue
                else:
                    raise Exception("Rate limited: Response indicates too many requests.")
            
            # Parse the response JSON or HTML content
            respjson = parse_html_content_to_json(response.text)  # Adjust this to your parsing logic
            altrespjson = extract_vehicle_info_from_json(respjson)
            return altrespjson
        
        # If all retries fail, raise a final exception
        raise Exception("Failed to fetch data after multiple attempts due to rate limiting.")
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"An HTTP error occurred: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse JSON: {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")

def extract_vehicle_info_from_json(json_content):
    """
    Extracts vehicle information from a JSON object.

    Args:
        json_content (dict): The JSON content as a dictionary.

    Returns:
        dict: A dictionary containing extracted vehicle details.
    """
    #save_json_to_file(json_content=json_content)
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
            "Year":hero.get("Year","")
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
                vehicle_info[keys_to_extract[key]] = value.split("L")[0]
            elif "Kilometres" in key:
                vehicle_info[keys_to_extract[key]] = convert_km_to_double(value)
            
        for required_key in keys_to_extract.values():
            if required_key not in vehicle_info:
                vehicle_info[required_key] = ""
                
        return vehicle_info
    except Exception as e:
        print(f"An error occurred while extracting vehicle info: {e}")
        return {}

def save_results_to_csv(data, payload, filename="results.csv"):
    """
    Saves fetched data by processing it using external CSV handling function, with parallelized workers.
    
    Args:
        data (list): List of links to save.
        payload (dict): Payload containing additional filtering criteria.
        filename (str): Name of the CSV file.
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
        
        car_info = extract_vehicle_info(url=link)
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
            print(f"Failed to fetch data for {link}")
            return None
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Submit tasks
        futures = [executor.submit(process_link, item) for item in data]
        
        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            if row:
                results.append(row)
    
    # Write to CSV after all workers finish
    
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(allColNames)  # Write the header
        writer.writerows(results)
        
    elapsed_time = time.time() - start_time
    print(f"Processed all in {elapsed_time:.4f}s")
    start_time = 0
    print(f"Results saved to {filename}")
    filter_csv(filename, filename, payload=payload)

def main():
    """
    Main function to interact with the user.
    """
    print("Welcome to the AutoScraper, a tool to speed up niche searches for cars on Autotrader!")
    file_initialisation()
    while True:
        foldernamestr,filenamestr,pld_name,jsonfilename = "","","",""
        print("\nOptions:")
        print("1. Create a new payload")
        print("2. Save a payload to a file")
        print("3. Load a payload from a file")
        print("4. Fetch AutoTrader data")
        print("5. Exit")

        choice = input("Enter your choice: ")
        if choice == "1":
            payload = get_user_responses()
            print("Payload created:", payload)
            cls()
        elif choice == "2":
            if 'payload' in locals() and payload:
                foldernamestr = f"Queries\\{payload['Make']}_{payload['Model']}"
                filenamestr = f"{payload['YearMin']}-{payload['YearMax']}_{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.json"
                pld_name = foldernamestr+"\\"+cleaned_input("Payload Name",filenamestr,str)
                if not os.path.exists(foldernamestr):
                    os.makedirs(foldernamestr)
                    print(f"Folder '{foldernamestr}' created.")
                save_json_to_file(payload,pld_name)
                input(f"Payload saved to {pld_name}.\n\nPress enter to continue...")
                
            else:
                print("No payload found. Please create one first.")
                
        elif choice == "3":
            jsonfilename = "Queries\\"+cleaned_input("Payload Name", "Ford_Fusion\\ff1.json",str)
            loaded_payload = read_json_file(jsonfilename)
            if loaded_payload:
                payload = loaded_payload
                cls()
                print("Loaded payload:", payload)
                
        elif choice == "4":
            if 'payload' in locals() and payload:
                results = fetch_autotrader_data(payload)
                # for result in results: print(result)
               
                results = remove_duplicates_exclusions(results,payload["Exclusions"])##ONLY SENDING LINKS
                foldernamestr = f"Results\\{payload['Make']}_{payload['Model']}"
                filenamestr = f"{foldernamestr}\\{payload['YearMin']}-{payload['YearMax']}_{payload['PriceMin']}-{payload['PriceMax']}_{format_time_ymd_hms()}.csv"
                
                if not os.path.exists(foldernamestr):
                    os.makedirs(foldernamestr)
                    print(f"Folder '{foldernamestr}' created.")
                save_results_to_csv(results,payload=payload,filename=filenamestr)
                print(f"Total Results Fetched: {len(results)}\tResults saved to {filenamestr}")
                showcarsmain(filenamestr)
            else:
                print("No payload found. Please create or load one first.")
                
        elif choice == "5":
            print("Exiting AutoScraper. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()