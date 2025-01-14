
import requests
import json
import csv,time,os

from GetUserSelection import get_user_responses
from AutoScraperUtil import *


def fetch_autotrader_data(params):
    """
    Continuously fetch data from AutoTrader.ca API with lazy loading (pagination).

    Args:
        params (dict): Dictionary containing search parameters with default values.

    Returns:
        list: Combined list of all results from all pages.
    """
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
        "Exclusions" : []
    }
    #measut baris

    # Update default values with provided parameters
    params = {**default_params, **params}
    exclusions = params["Exclusions"]
    url = "https://www.autotrader.ca/Refinement/Search"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }

    all_results = []
    current_page = 1
    max_page = None
    skip = 0
    parsed_html_ad_info = []
    

    while True:
        payload = {
            "Address": params["Address"],
            "Proximity":params["Proximity"],
            "Make": params["Make"],
            "Model": params["Model"],
            "PriceMin": params["PriceMin"],
            "PriceMax": params["PriceMax"],
            "Skip": skip,
            "Top": params["Top"],
            "IsNew": params["IsNew"],
            "IsUsed": params["IsUsed"],
            "WithPhotos": params["WithPhotos"],
            "YearMax": params["YearMax"],
            "YearMin": params["YearMin"],
            "OdometerMin":params["OdometerMin"],
            "OdometerMax":params["OdometerMax"],
            "micrositeType": 1,
        }
        

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            json_response = response.json()
            search_results_json = json_response.get("SearchResultsDataJson", "")
            ad_results_json = json_response.get("AdsHtml","")
            if not search_results_json:
                print("No more data available.")
                break
            parsed_html_page = parse_html_content(ad_results_json,exclusions)
            parsed_html_ad_info.extend(parsed_html_page)
            search_results = json.loads(search_results_json)
            all_results.extend(search_results.get("compositeIdUrls", []))
            current_page = search_results.get("currentPage", 0)
            max_page = search_results.get("maxPage", current_page)
            print(f"Fetched page {current_page} of {max_page}...")
            if current_page >= max_page:
                print("Reached the last page.")
                break
            skip += params["Top"]
            
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"Failed to decode SearchResultsDataJson: {e}")
            break
    return parsed_html_ad_info


def extract_vehicle_info(url):
    """
    Extracts the vehicle info
    Detects rate limiting and raises an error if encountered. 

    Args:
        url (str): The URL to fetch data from.
    """

    waitlength = 10
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    ]

    ACCEPT_HEADERS = [
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "text/html,application/json;q=0.9,image/webp,*/*;q=0.8",
        "application/json, text/javascript, */*; q=0.01",
    ]

    REFERERS = [
        "https://www.google.com/",
        "https://www.bing.com/",
        "https://www.yahoo.com/",
        "https://duckduckgo.com/",
    ]

    headers = {
        "User-Agent": USER_AGENTS[0],
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": ACCEPT_HEADERS[2],
        "Referer": REFERERS[0],
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = requests.get(url, headers=headers, proxies=None)
        
        # Check for rate limiting
        if response.status_code == 429:
            raise requests.exceptions.RequestException("Rate limited: HTTP 429 Too Many Requests.")
        response.raise_for_status()
        while "Request unsuccessful." in response.text:
            print("Rate limited: Incapsula says Too Many Requests. Waiting for 10 seconds")
            for x in reversed(range(waitlength)):
                time.sleep(1)
                print(f"Retrying in {x} seconds")
            response = requests.get(url, headers=headers, proxies=None)
        respjson = parse_html_content_to_json(response.text)#read_json_file()
        altrespjson = extract_vehicle_info_from_json(respjson)
        return altrespjson
    except requests.exceptions.RequestException as e:
        return f"An error occurred during the request: {e}"
    except json.JSONDecodeError as e:
        return f"Failed to parse JSON: {e}"

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


def save_results_to_csv(data, payload,filename="results.csv"):
    """
    Saves fetched data by processing it using external CSV handling function.

    Args:
        data (list): List of links to save.
        filename (str): Name of the CSV file.
    """
    countofcars = 0
    cartimes = []
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
    sleeptime = 2 
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(allColNames)  # Write the header
        if len(data) <= 2500:
            sleeptime = 0
        for item in data:
            startTime = time.time()
            link = item["link"]
            car_info = extract_vehicle_info(url=link)
            time.sleep(sleeptime)
            if car_info:
                # Write the row with additional columns
                countofcars+=1
                writer.writerow([link,
                    car_info.get("Make", ""),
                    car_info.get("Model", ""),
                    car_info.get("Year", ""),
                    car_info.get("Trim", ""),
                    car_info.get("Price",""),
                    car_info.get("Drivetrain", ""),
                    car_info.get("Kilometres", ""),
                    car_info.get("Status", ""),
                    car_info.get("Body Type", ""),
                    car_info.get("Engine", ""),
                    car_info.get("Cylinder", ""),
                    car_info.get("Transmission", ""),
                    car_info.get("Exterior Colour",""),
                    car_info.get("Doors",""),
                    car_info.get("Fuel Type", ""),
                    car_info.get("City Fuel Economy",""),
                    car_info.get("Hwy Fuel Economy","")
                ])
            else: 
                print(f"No valid data found for {link}")
                os.abort()
            opTime = time.time() - startTime
            averagetime = 0
            cartimes.append(opTime)
            for cartime in cartimes:
                averagetime += cartime
            averagetime /= float(len(cartimes))
            cls()
            print(f"{len(cartimes)}/{len(data)}\tTotal time: {opTime:.2f}s\tAverage time: {averagetime:.2f}\tETA:{format_time(averagetime*((len(data)) - len(cartimes)))}")
    print(f"Results saved to {filename}")
    filter_csv(filename,filename,payload=payload)

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

