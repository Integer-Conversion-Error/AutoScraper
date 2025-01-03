from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import requests, random,ast
import json
import csv,time,os

from GetUserSelection import get_user_responses
from AutoScraperUtil import cleaned_input, convert_km_to_double, extract_prices_from_html, filter_csv, format_time, format_time_ymd_hms, keep_if_contains, parse_html_content, parse_html_content_to_json, parse_html_to_json, read_json_file, remove_duplicates, remove_duplicates_exclusions, save_html_to_file, save_json_to_file,cls,read_payload_from_file,parse_html_file, showcarsmain, string_after_second_last

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
        "PriceMin": 0,
        "PriceMax": 999999,
        "YearMin": "1950",
        "YearMax": "2025",
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


def extract_ng_vdp_model(url, proxies=None):
    """
    Extracts the `window['ngVdpModel']` variable from a webpage by capturing the entire line and parses it into a Python dictionary.
    Detects rate limiting and raises an error if encountered. Supports proxy usage.

    Args:
        url (str): The URL to fetch data from.
        proxies (dict): Optional. A dictionary of proxies to use for the request.
            Example: {"http": "http://proxy_url", "https": "https://proxy_url"}
    """

    normalreturn = False
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
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": random.choice(ACCEPT_HEADERS),
        "Referer": random.choice(REFERERS),
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    try:
        response = requests.get(url, headers=headers, proxies=proxies)
        
        # Check for rate limiting
        if response.status_code == 429:
            raise requests.exceptions.RequestException("Rate limited: HTTP 429 Too Many Requests.")
        #filenamest = url.rfind("/")##FIND PROPER LINK
        filenamenew = string_after_second_last(url,"/")
        
        response.raise_for_status()
        while "Request unsuccessful." in response.text:
            #print("Original Block")
            #save_html_to_file(response.text)
            #print(response.text)
            print("Rate limited: Incapsula says Too Many Requests. Waiting for 10 seconds")
            for x in reversed(range(waitlength)):
                time.sleep(1)
                print(f"Retrying in {x} seconds")
            response = requests.get(url, headers=headers, proxies=proxies)
        for line in response.text.splitlines():
            if "window['ngVdpModel'] =" in line: ##ONE WAY IS THIS WAY
                respjson = extract_vehicle_info_from_html(response.text)
                #print(respjson)
                #save_html_to_file(response.text,"ngVdpModel.html")
                #os._exit(0)
                raw_data = line.split("=", 1)[1].strip()
                
                #save_html_to_file(response.text, filenamenew)
                #normalreturn = True
                if raw_data.endswith(";"):
                    raw_data = raw_data[:-1]

                cleaned_data = (
                    raw_data
                    .replace("undefined", "null")
                    .replace("\n", "")
                    .replace("\t", "")
                )

                
                ng_vdp_model = extract_vehicle_info_from_nested_json(json.loads(cleaned_data))
                
                print(ng_vdp_model,"HTML Block")
                return ng_vdp_model
                # break
            elif "Request unsuccessful. Incapsula incident ID:" in line: ##unreachable basically
                #save_html_to_file(response.text)
                print(response.text)
                raise requests.exceptions.RequestException("Rate limited: Incapsula says Too Many Requests")
                
        else:
            #save_html_to_file(response.text,filenamenew)
            ##ANOTHER WAY IS THIS WAY
            #save_json_to_file(respprejson)
            respjson = parse_html_content_to_json(response.text)#read_json_file()
            altrespjson = extract_vehicle_info_from_json(respjson)
            #print(type(respjson))
            # for item in respjson:
            #     print(item)
            #respjson = parse_string_to_json(respprejson)
            #save_json_to_file(respjson,"testoutput.json")
            print(altrespjson,"Pure JSON Block")
            #os._exit(0)
            return altrespjson#,normalreturn,response#"window['ngVdpModel'] not found in the HTML. Response dump: " + response.text#.splitlines()

        
        #normalreturn = True
        #return ng_vdp_model#,normalreturn,response

    except requests.exceptions.RequestException as e:
        return f"An error occurred during the request: {e}"
    except json.JSONDecodeError as e:
        return f"Failed to parse JSON: {e}"


def extract_vehicle_info_from_nested_json(json_content):
    """
    Extracts vehicle information from a nested JSON object structure.

    Args:
        json_content (dict): The JSON content as a dictionary.

    Returns:
        dict: A dictionary containing extracted vehicle details.
    """
    try:
        # Initialize an empty dictionary for vehicle information
        vehicle_info = {}

        # Define all required keys
        required_keys = [
            "Make",
            "Model",
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

        # Extract from hero section
        hero = json_content.get("hero", {})
        vehicle_info.update({
            "Make": hero.get("make", ""),
            "Model": hero.get("model", ""),
            "Trim": hero.get("trim", ""),
            "Price": convert_km_to_double(hero.get("price", "")),
            "Kilometres": hero.get("mileage", ""),
            "Drivetrain": hero.get("drivetrain", ""),
        })

        # Extract specifications
        specs = json_content.get("specifications", {}).get("specs", [])
        for spec in specs:
            key = spec.get("key", "")
            value = spec.get("value", "")
            if key in required_keys and "Fuel Economy" not in key and "Kilometres" not in key and "Price" not in key:
                vehicle_info[key] = value
            elif "Fuel Economy" in key:
                vehicle_info[key] = value.split("L")[0]
            elif "Kilometres" in key:
                vehicle_info[key] = convert_km_to_double(value)
            elif "Price" in key:
                vehicle_info[key] = float(value.replace(",",""))

        # Identify missing keys
        missing_keys = [key for key in required_keys if key not in vehicle_info or not vehicle_info[key]]

        if missing_keys:
            print(f"Missing keys with no values: {', '.join(missing_keys)}")

        return vehicle_info

    except Exception as e:
        print(f"An error occurred while extracting vehicle info: {e}")
        return {}

def extract_vehicle_info_from_json(json_content):
    """
    Extracts vehicle information from a JSON object.

    Args:
        json_content (dict): The JSON content as a dictionary.

    Returns:
        dict: A dictionary containing extracted vehicle details.
    """
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
            # elif "Price" in key:
            #     vehicle_info[keys_to_extract[key]] = float(value.replace(",",""))

        # Ensure all required keys are present
        for required_key in keys_to_extract.values():
            if required_key not in vehicle_info:
                vehicle_info[required_key] = ""
                #print(f"Couldn't find {required_key}")
        
        missing_keys = [key for key in keys_to_extract.keys() if key not in vehicle_info or not vehicle_info[key]]
        if missing_keys:
            print(f"Missing keys with no values: {', '.join(missing_keys)}")
        return vehicle_info
    except Exception as e:
        print(f"An error occurred while extracting vehicle info: {e}")
        return {}

def save_results_to_csv(data, filename="results.csv"):
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
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(allColNames)  # Write the header
        for item in data:
            startTime = time.time()
            link = item["link"]
            car_info = extract_ng_vdp_model(url=link)
            time.sleep(2)
            #print(car_info)
            if car_info:
                # Write the row with additional columns
                countofcars+=1
                
                writer.writerow([link,
                    car_info.get("Make", ""),
                    car_info.get("Model", ""),
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
                #print(link)
            opTime = time.time() - startTime
            averagetime = 0
            cartimes.append(opTime)
            for cartime in cartimes:
                averagetime += cartime
            averagetime /= float(len(cartimes))
            cls()
            print(f"{len(cartimes)}/{len(data)}\tTotal time: {opTime:.2f}s\tWithout Pause: {opTime-2:.2f}s\tAverage time: {averagetime:.2f}\tETA:{format_time(averagetime*((len(data)) - len(cartimes)))}")
    print(f"Results saved to {filename}")

    #print("Processing CSV to fetch car details...")
    #process_csv(input_csv=filename, output_csv=filename)

def extract_vehicle_info_from_html(html_content):
    """
    Extracts vehicle information from the JSON-like script elements within an HTML page.

    Args:
        html_content (str): The full HTML content as a string.

    Returns:
        list: A list of dictionaries containing vehicle details or an empty list if none found.
    """
    try:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all <script> tags containing JSON data
        script_tags = soup.find_all('script', type='application/ld+json')

        vehicles = []

        for script_tag in script_tags:
            try:
                if script_tag.string:
                    # Parse the JSON content
                    json_content = json.loads(script_tag.string)

                    # Map driveWheelConfiguration to Drivetrain enumeration
                    drive_config = json_content.get("driveWheelConfiguration", "")
                    drivetrain = "Unknown"
                    if "AllWheelDriveConfiguration" in drive_config:
                        drivetrain = "AWD"
                    elif "FourWheelDriveConfiguration" in drive_config:
                        drivetrain = "4WD"
                    elif "FrontWheelDriveConfiguration" in drive_config:
                        drivetrain = "FWD"
                    elif "RearWheelDriveConfiguration" in drive_config:
                        drivetrain = "RWD"

                    # Extract relevant vehicle information
                    vehicle_info = {
                        "Make": json_content.get("brand", {}).get("name", ""),
                        "Model": json_content.get("model", ""),
                        "Kilometres": json_content.get("mileageFromOdometer", {}).get("value", ""),
                        "Price": json_content.get("offers", {}).get("price", ""),
                        "Status": json_content.get("itemCondition", ""),
                        "Trim": json_content.get("vehicleConfiguration", ""),
                        "Body Type": json_content.get("bodyType", ""),
                        "Engine": json_content.get("vehicleEngine", {}).get("engineType", ""),
                        "Cylinder": json_content.get("vehicleEngine", {}).get("cylinder", ""),
                        "Transmission": json_content.get("vehicleTransmission", ""),
                        "Drivetrain": drivetrain,
                        "Fuel Type": json_content.get("vehicleEngine", {}).get("fuelType", "")
                    }
                    vehicles.append(vehicle_info)
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON in one of the script tags: {e}")
                continue

        return vehicles
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def main():
    """
    Main function to interact with the user.
    """
    print("Welcome to the Payload and AutoTrader Manager!")
    while True:
        
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
                pld_name = cleaned_input("Payload Name",f"payload_{payload['Make']}_{payload['Model']}_{format_time_ymd_hms()}.json",str)
                save_json_to_file(payload,pld_name)
                input(f"Payload saved to {pld_name}.\n\nPress enter to continue...")
                
            else:
                print("No payload found. Please create one first.")
                
        elif choice == "3":
            jsonfilename = cleaned_input("Payload Name", "payload_Ford_Fusion_2024-12-20_07-47-34.json",str)
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
                filenamestr = f"results_{payload['Make']}_{payload['Model']}_{format_time_ymd_hms()}.csv"
                save_results_to_csv(results, filename=filenamestr)
                filter_csv(filenamestr,filenamestr,payload["Exclusions"])
                keep_if_contains(filenamestr,filenamestr, payload["Inclusion"])
                print(f"Total Results Fetched: {len(results)}\tResults saved to {filenamestr}")
                showcarsmain(filenamestr)
            else:
                print("No payload found. Please create or load one first.")
                
        elif choice == "5":
            print("Exiting the Payload Manager. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")



def testmain():
    """
    Main function to interact with the user.
    """

    loaded_payload = read_payload_from_file()
    if loaded_payload:
        payload = loaded_payload
    if 'payload' in locals() and payload:
        results = fetch_autotrader_data(payload)
        results = remove_duplicates(results)
        save_results_to_csv(results)
        print(f"Total Results Fetched: {len(results)}")


if __name__ == "__main__":
    main()


    # file_path = "output.html"  # Replace with the correct path to your file
    # parsed_json = parse_html_to_json(file_path)
    # if parsed_json:
    #     save_json_to_file(parsed_json, "parsed_output.json")
