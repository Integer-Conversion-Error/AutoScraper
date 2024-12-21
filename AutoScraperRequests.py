from datetime import datetime, timedelta
import requests, random,ast
import json
import csv,time,os

from GetUserSelection import get_user_responses
from AutoScraperUtil import cleaned_input, filter_csv, format_time, format_time_ymd_hms, keep_if_contains, parse_html_to_json, read_json_file, remove_duplicates, remove_duplicates_exclusions, save_html_to_file, save_json_to_file,cls,read_payload_from_file,parse_html_file


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
        "PriceMax": 99999,
        "YearMin": "1950",
        "YearMax": "2025",
        "Top": 15,
        "Address": "Kanata, ON",
        "IsNew": True,
        "IsUsed": True,
        "WithPhotos": True,
        "Exclusions" : []
    }
    

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
            save_html_to_file(ad_results_json,"html_test_output.html")
            parsed_html_page = parse_html_file("html_test_output.html",exclusions)
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

    #return all_results#,parsed_html_ad_info ADD THIS INSTEAD OF ALLRESULTS
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
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:110.0) Gecko/20100101 Firefox/110.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 11; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.66 Mobile Safari/537.36",
        "Mozilla/5.0 (iPad; CPU OS 13_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
        "Mozilla/5.0 (Linux; Android 10; SM-A505F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.127 Mobile Safari/537.36"
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
        
        response.raise_for_status()
        while "Request unsuccessful." in response.text:
            #print("Original Block")
            save_html_to_file(response.text)
            #print(response.text)
            print("Rate limited: Incapsula says Too Many Requests. Waiting for 10 seconds")
            for x in reversed(range(waitlength)):
                time.sleep(1)
                print(f"Retrying in {x} seconds")
            response = requests.get(url, headers=headers, proxies=proxies)

        for line in response.text.splitlines():
            if "window['ngVdpModel'] =" in line: ##ONE WAY IS THIS WAY
                raw_data = line.split("=", 1)[1].strip()
                normalreturn = True
                break
            elif "Request unsuccessful. Incapsula incident ID:" in line:
                save_html_to_file(response.text)
                print(response.text)
                raise requests.exceptions.RequestException("Rate limited: Incapsula says Too Many Requests")
                
        else:
            save_html_to_file(response.text)
            respprejson = parse_html_to_json() ##ANOTHER WAY IS THIS WAY
            save_json_to_file(respprejson)
            respjson = read_json_file()
            #print(type(respjson))
            # for item in respjson:
            #     print(item)
            #respjson = parse_string_to_json(respprejson)
            return respjson,normalreturn#"window['ngVdpModel'] not found in the HTML. Response dump: " + response.text#.splitlines()

        if raw_data.endswith(";"):
            raw_data = raw_data[:-1]

        cleaned_data = (
            raw_data
            .replace("undefined", "null")
            .replace("\n", "")
            .replace("\t", "")
        )

        ng_vdp_model = json.loads(cleaned_data)
        normalreturn = True
        return ng_vdp_model,normalreturn

    except requests.exceptions.RequestException as e:
        return f"An error occurred during the request: {e}"
    except json.JSONDecodeError as e:
        return f"Failed to parse JSON: {e}"




def get_info_from_json(make="Ford", model="Fusion", url="https://www.autotrader.ca/a/ford/fusion/orangeville/ontario/5_64604589_on20070704162913228/?showcpo=ShowCpo&ncse=no&ursrc=xpl&urp=3&urm=8&sprx=-1"):
    """
    Extracts car info from the JSON data on the AutoTrader page.
    """
    result,goodreturn = extract_ng_vdp_model(url)
    carinfodict = {"Make": make, "Model": model}

    if isinstance(result, dict) and goodreturn:
        allofspecs = result.get("specifications")
        
        allspecs = allofspecs.get("specs", [])
        for spec in allspecs:
            carinfodict.update({spec["key"]: spec["value"]})
        #print("Normal GetInfoFromJson Block! ")
        return carinfodict
    elif not goodreturn:
        #print(type(result))
        # for key in result.keys():
        #     print(f"Key: {key}")
        allofspecs = dict(result["Specifications"])
        allofspecs = allofspecs.get("Specs",[])
        #print(allofspecs, type(result))
        for spec in allofspecs:
            tempdict = dict(spec)
            carinfodict.update({tempdict["Key"]: tempdict["Value"]})
        return carinfodict
    else:
        print(f"Error fetching data from URL: {url}")
        print(result)
        return None





def save_results_to_csv(data, filename="results.csv"):
    """
    Saves fetched data by processing it using external CSV handling function.

    Args:
        data (list): List of links to save.
        filename (str): Name of the CSV file.
    """
    countofcars = 0
    cartimes = []
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Link","Make", "Model", "Kilometres", "Status", "Trim", "Body Type", "Engine", "Cylinder", "Transmission", "Drivetrain", "Fuel Type"])  # Write the header
        for item in data:
            startTime = time.time()
            link = item["link"]
            car_info = get_info_from_json(url=link)
            
            time.sleep(2)
            #print(car_info)
            if car_info:
                # Write the row with additional columns
                countofcars+=1
                
                writer.writerow([link,
                    car_info.get("Make", ""),
                    car_info.get("Model", ""),
                    car_info.get("Kilometres", ""),
                    car_info.get("Status", ""),
                    car_info.get("Trim", ""),
                    car_info.get("Body Type", ""),
                    car_info.get("Engine", ""),
                    car_info.get("Cylinder", ""),
                    car_info.get("Transmission", ""),
                    car_info.get("Drivetrain", ""),
                    car_info.get("Fuel Type", ""),
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
            print(f"{len(cartimes)}/{len(data)}\tTotal time: {opTime:.2f}\tWithout Pause: {opTime-2:.2f}\tAverage time: {averagetime:.2f}\tETA:{format_time(averagetime*((len(data)) - len(cartimes)))}")
    print(f"Results saved to {filename}")

    #print("Processing CSV to fetch car details...")
    #process_csv(input_csv=filename, output_csv=filename)






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
                cls()
            else:
                print("No payload found. Please create one first.")
                
        elif choice == "3":
            jsonfilename = cleaned_input("Payload Name", "payload_Ford_Fusion_2024-12-20_07-47-34.json",str)
            loaded_payload = read_json_file(jsonfilename)
            if loaded_payload:
                payload = loaded_payload
                print("Loaded payload:", payload)
                
        elif choice == "4":
            if 'payload' in locals() and payload:
                results = fetch_autotrader_data(payload)
                for result in results: print(result)
               
                results = remove_duplicates_exclusions(results,payload["Exclusions"])##ONLY SENDING LINKS
                filenamestr = f"results_{payload['Make']}_{payload['Model']}_{format_time_ymd_hms()}.csv"
                save_results_to_csv(results, filename=filenamestr)
                filter_csv(filenamestr,filenamestr,payload["Exclusions"])
                keep_if_contains(filenamestr,filenamestr, payload["Inclusion"])
                print(f"Total Results Fetched: {len(results)}\tResults saved to {filenamestr}")
                
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
