import requests
import json
import csv
from AutotraderXHRTest import process_csv

def get_user_responses():
    """
    Prompt the user for responses to populate the payload items.

    Returns:
        dict: A dictionary containing user inputs for the payload.
    """
    payload = {
        "Address": input("Enter Address (default: null): ") or "Kanata, ON",
        "Make": input("Enter Make (default: null): ") or None,
        "Model": input("Enter Model (default: null): ") or None,
        "PriceMin": input("Enter Minimum Price (default: null): ") or None,
        "PriceMax": input("Enter Maximum Price (default: null): ") or None,
        "Skip": 0,
        "Top": 15,
        "IsNew": "True",
        "IsUsed": "True",
        "WithPhotos": "True",
        "YearMax": input("Enter Maximum Year (default: null): ") or None,
        "YearMin": input("Enter Minimum Year (default: null): ") or None,
        "micrositeType": 1,  # This field is fixed
    }

    # Convert numerical inputs or booleans
    for key in ["PriceMin", "PriceMax", "Skip", "Top", "YearMax", "YearMin"]:
        if payload[key] is not None:
            try:
                payload[key] = int(payload[key])
            except ValueError:
                payload[key] = None

    for key in ["IsNew", "IsUsed", "WithPhotos"]:
        if payload[key] is not None:
            payload[key] = payload[key].strip().lower() == "true"

    return payload

def save_payload_to_file(payload):
    """
    Save the payload to a file in JSON format.

    Args:
        payload (dict): The payload to save.
    """
    filename = input("Enter the name of the file to save (with .txt extension): ")
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=4)
    print(f"Payload saved to {filename}")

def read_payload_from_file():
    """
    Read a payload from a file in JSON format.

    Returns:
        dict: The payload read from the file.
    """
    filename = input("Enter the name of the file to read (with .txt extension): ")
    try:
        with open(filename, "r", encoding="utf-8") as file:
            payload = json.load(file)
            print(f"Payload successfully loaded from {filename}")
            return payload
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return None

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
    }

    # Update default values with provided parameters
    params = {**default_params, **params}

    url = "https://www.autotrader.ca/Refinement/Search"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    all_results = []
    current_page = 1
    max_page = None
    skip = 0

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
            if not search_results_json:
                print("No more data available.")
                break

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

    return all_results

def remove_duplicates(arr):
    """
    Removes duplicates from an array while maintaining the order of elements.

    Args:
        arr (list): The input array.

    Returns:
        list: A new array with duplicates removed.
    """
    seen = set()
    result = []
    for item in arr:
        if item not in seen:
            result.append("https://www.autotrader.ca" + item)
            seen.add(item)
    return result

def extract_ng_vdp_model(url):
    """
    Extracts the `window['ngVdpModel']` variable from a webpage by capturing the entire line and parses it into a Python dictionary.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        for line in response.text.splitlines():
            if "window['ngVdpModel'] =" in line:
                raw_data = line.split("=", 1)[1].strip()
                break
        else:
            return "window['ngVdpModel'] not found in the HTML."

        if raw_data.endswith(";"):
            raw_data = raw_data[:-1]

        cleaned_data = (
            raw_data
            .replace("undefined", "null")
            .replace("\n", "")
            .replace("\t", "")
        )

        ng_vdp_model = json.loads(cleaned_data)
        return ng_vdp_model

    except requests.exceptions.RequestException as e:
        return f"An error occurred during the request: {e}"
    except json.JSONDecodeError as e:
        return f"Failed to parse JSON: {e}"

def get_info_from_json(make="Ford", model="Fusion", url="https://www.autotrader.ca/a/ford/fusion/orangeville/ontario/5_64604589_on20070704162913228/?showcpo=ShowCpo&ncse=no&ursrc=xpl&urp=3&urm=8&sprx=-1"):
    """
    Extracts car info from the JSON data on the AutoTrader page.
    """
    result = extract_ng_vdp_model(url)
    carinfodict = {"Make": make, "Model": model}

    if isinstance(result, dict):
        allofspecs = result.get("specifications")
        allspecs = allofspecs.get("specs", [])
        for spec in allspecs:
            carinfodict.update({spec["key"]: spec["value"]})

        #print(carinfodict)
        return carinfodict
    else:
        print(f"Error fetching data from URL: {url}")
        return None

def save_to_csv(data, filename="results.csv"):
    """
    Saves fetched data by processing it using external CSV handling function.

    Args:
        data (list): List of links to save.
        filename (str): Name of the CSV file.
    """
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Link","Make", "Model", "Kilometres", "Status", "Trim", "Body Type", "Engine", "Cylinder", "Transmission", "Drivetrain", "Fuel Type"])  # Write the header
        for link in data:
            car_info = get_info_from_json(url=link)
            if car_info:
                # Write the row with additional columns
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
    print(f"Results saved to {filename}")

    print("Processing CSV to fetch car details...")
    process_csv(input_csv=filename, output_csv=filename)

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
        elif choice == "2":
            if 'payload' in locals() and payload:
                save_payload_to_file(payload)
            else:
                print("No payload found. Please create one first.")
        elif choice == "3":
            loaded_payload = read_payload_from_file()
            if loaded_payload:
                payload = loaded_payload
                print("Loaded payload:", payload)
        elif choice == "4":
            if 'payload' in locals() and payload:
                results = fetch_autotrader_data(payload)
                results = remove_duplicates(results)
                save_to_csv(results)
                print(f"Total Results Fetched: {len(results)}")
            else:
                print("No payload found. Please create or load one first.")
        elif choice == "5":
            print("Exiting the Payload Manager. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
