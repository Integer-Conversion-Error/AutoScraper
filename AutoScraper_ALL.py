import ast
import csv
from datetime import datetime, timedelta
import json
import os
from tabulate import tabulate
from bs4 import BeautifulSoup

import requests, random
import json
import csv,time,os

import csv
import webbrowser

import requests

def open_links_from_csv(file_path, column_name = "Link"):
    """
    Opens links from a specified column in a CSV file in Chrome tabs.

    Parameters:
        file_path (str): Path to the CSV file.
        column_name (str): The name of the column containing the links.
    """
    openedcount = 0
    try:
        # Open the CSV file
        with open(file_path, 'r') as csv_file:
            reader = csv.DictReader(csv_file)

            # Check if the column exists
            if column_name not in reader.fieldnames:
                print(f"Error: Column '{column_name}' not found in the CSV file.")
                return

            # Open each link in a new tab
            
            for row in reader:
                link = row[column_name].strip()
                openedcount+=1
                if link:
                    webbrowser.open_new_tab(link)
                if openedcount > 15:
                    print(f"Large amount of links, opening first 15")
                    break
            print("Links have been opened in Chrome.")
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

def showcarsmain(csv_file_path):
    # Replace with the path to your CSV file
    link_column_name = 'Link'  # Replace with the actual column name in your CSV
    open_links_from_csv(csv_file_path, link_column_name)

def parse_html_file(file_path,exclusions = []):
    """
    DEPRECATED: Parses the HTML file and extracts links and their corresponding listing details.

    :param file_path: str, path to the HTML file
    :return: list of dictionaries, each containing a link and associated listing details
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')

    listings = []

    # Find all listing containers
    for result_item in soup.find_all('div', class_='result-item'):
        listing = {}
        excluded = False
        # Extract link
        link_tag = result_item.find('a', class_='inner-link')
        if link_tag and link_tag.get('href'):
            listing['link'] = link_tag['href']

        # Extract title
        title_tag = result_item.find('span', class_='title-with-trim')
        if title_tag:
            if any(exclusion in title_tag.get_text(strip=True) for exclusion in exclusions):
                excluded = True
            listing['title'] = title_tag.get_text(strip=True)

        # Extract price
        price_tag = result_item.find('span', class_='price-amount')
        if price_tag:
            listing['price'] = price_tag.get_text(strip=True)

        # Extract mileage
        mileage_tag = result_item.find('span', class_='odometer-proximity')
        if mileage_tag:
            listing['mileage'] = mileage_tag.get_text(strip=True)

        # Extract location
        location_tag = result_item.find('span', class_='proximity-text', attrs={'class': None})
        if location_tag:
            listing['location'] = location_tag.get_text(strip=True)

        # Add the listing if it has a link
        if 'link' in listing and not excluded:
            listings.append(listing)
    
    return listings

def parse_html_content(html_content, exclusions=[]):
    """
    Parses the HTML content and extracts links and their corresponding listing details.

    :param html_content: str, the HTML content as a string
    :param exclusions: list, strings to exclude from titles
    :return: list of dictionaries, each containing a link and associated listing details
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    listings = []

    # Find all listing containers
    for result_item in soup.find_all('div', class_='result-item'):
        listing = {}
        excluded = False
        
        # Extract link
        link_tag = result_item.find('a', class_='inner-link')
        if link_tag and link_tag.get('href'):
            listing['link'] = link_tag['href']

        # Extract title
        title_tag = result_item.find('span', class_='title-with-trim')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            if any(exclusion in title_text for exclusion in exclusions):
                excluded = True
            listing['title'] = title_text

        # Extract price
        price_tag = result_item.find('span', class_='price-amount')
        if price_tag:
            listing['price'] = price_tag.get_text(strip=True)

        # Extract mileage
        mileage_tag = result_item.find('span', class_='odometer-proximity')
        if mileage_tag:
            listing['mileage'] = mileage_tag.get_text(strip=True)

        # Extract location
        location_tag = result_item.find('span', class_='proximity-text', attrs={'class': None})
        if location_tag:
            listing['location'] = location_tag.get_text(strip=True)

        # Add the listing if it has a link and is not excluded
        if 'link' in listing and not excluded:
            listings.append(listing)
    
    return listings

def string_after_second_last(string, char):
    # Find the last occurrence
    last_index = string.rfind(char)
    if last_index == -1:
        return ""  # Character not found
    # Find the second last occurrence
    second_last_index = string.rfind(char, 0, last_index)
    if second_last_index == -1:
        return ""  # Second last occurrence does not exist
    # Return the substring after the second last occurrence
    return string[second_last_index + 1:-1]+".html"
    
def convert_km_to_double(km_string):
    """
    Converts a string like "109,403 km" to a float.

    Args:
        km_string (str): The input string representing kilometres.

    Returns:
        float: The numeric value of kilometres.
    """
    try:
        return float(km_string.replace(",", "").replace(" km", ""))
    except ValueError:
        print(f"Invalid format: {km_string}")
        return 0.0

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

def file_initialisation():
    """
    Initializes two folders: 'Results' and 'Queries'.
    If the folders already exist, they are left untouched.
    """
    import os

    folders = ["Results", "Queries"]
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            #print(f"Folder '{folder}' created.")
        #else:
            #print(f"Folder '{folder}' already exists.")

def parse_html_content_to_json(html_content):
    """
    Parses the JSON-like content embedded within an HTML string.

    Args:
        html_content (str): The HTML content as a string.

    Returns:
        dict: Extracted JSON content or an error message.
    """
    try:
        # Extract JSON-like content between braces assuming it's embedded
        json_start = html_content.find("{")
        json_end = html_content.rfind("}")

        if json_start == -1 or json_end == -1:
            raise ValueError("No JSON-like content found in the HTML content.")

        # Convert the extracted content into JSON
        json_content = json.loads(html_content[json_start:json_end + 1])
        return json_content

    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
    except Exception as e:
        print(f"An error occurred while parsing HTML to JSON: {e}")

def save_json_to_file(json_content, file_name="output.json"):
    """
    Saves the provided JSON content to a file.

    Args:
        json_content (dict): The JSON content to save.
        file_name (str): The name of the JSON file. Default is "output.json".
    """
    try:
        with open(file_name, "w", encoding="utf-8") as file:
            json.dump(json_content, file, indent=4)
        if file_name != "output.json":
            print(f"Payload content saved to {file_name}") ##different string means payload 
    except Exception as e:
        print(f"An error occurred while saving JSON to file: {e}")

def save_html_to_file(html_content, file_name="output.html"):
    """
    Saves the provided HTML content to a file.

    Args:
        html_content (str): The HTML content to save.
        file_name (str): The name of the HTML file. Default is "output.html".
    """
    try:
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(html_content)
        #print(f"HTML content saved to {file_name}")
    except Exception as e:
        print(f"An error occurred while saving HTML to file: {e}")

def process_line(line):
    """
    Process the input string `line` by extracting the portion after the first `=`,
    stripping whitespace, and performing cleanup operations.

    Parameters:
        line (str): The input string to process.

    Returns:
        str: The cleaned and processed string.
    """
    # Extract the part after the first `=` and strip leading/trailing whitespace
    raw_data = line.split("=", 1)[1].strip()

    # Remove the trailing semicolon, if present
    if raw_data.endswith(";"):
        raw_data = raw_data[:-1]

    # Perform cleanup operations
    cleaned_data = (
        raw_data
        .replace("undefined", "null")
        .replace("\n", "")
        .replace("\t", "")
    )

    return cleaned_data

def parse_string_to_json(input_string):
    """
    Parses a string representing a dictionary into a JSON object and returns it as a Python dictionary.

    :param input_string: str, the string representation of a dictionary
    :return: dict, the parsed JSON object
    """
    try:
        # Convert the string to a dictionary using ast.literal_eval for safe evaluation
        parsed_dict = ast.literal_eval(input_string)
        # Convert the dictionary to JSON to ensure valid format
        json_data = json.dumps(parsed_dict)
        # Parse the JSON back to a Python dictionary
        return json.loads(json_data)
    except Exception as e:
        print(f"Error parsing the string: {e}")
        return None
    
def cls():
    """
    Clears the console screen for a cleaner display.
    """
    # Check the operating system and execute the appropriate clear command
    if os.name == 'nt':  # For Windows
        os.system('cls')
    else:  # For Linux and MacOS
        os.system('clear')

def read_payload_from_file(filename = "ff2019.txt"):
    """
    Read a payload from a file in JSON format.

    Returns:
        dict: The payload read from the file.
    """
    #filename = input("Enter the name of the file to read (with .txt extension): ")
    print("TEST PAYLOAD: FORD FUSION 2017-19")
    try:
        with open(filename, "r", encoding="utf-8") as file:
            payload = json.load(file)
            print(f"Payload successfully loaded from {filename}")
            return payload
    except FileNotFoundError:
        print(f"File {filename} not found.")
        return None

def cleaned_input(itemTitle, defaultval, expectedtype):
    """
    Prompts the user for input, validates it, and ensures it matches the expected type.

    :param itemTitle: str, title of the item being requested
    :param defaultval: default value to use if input is empty
    :param expectedtype: type, the expected type of the input
    :return: value of the correct type
    """
    while True:
        try:
            user_input = input(f"Enter {itemTitle} (default: {defaultval}): ")
            if not user_input.strip():
                return defaultval
            value = expectedtype(user_input)
            return value
        except ValueError:
            print(f"Invalid input. Please enter a value of type {expectedtype.__name__}.")

def extract_car_makes_from_html(html_content, popular = True):
    """
    Extracts all car makes from the optgroup element within an HTML page.

    Args:
        html_content (str): The full HTML content as a string.

    Returns:
        list: A list of car makes found in the optgroup, or an empty list if none found.
    """
    try:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find the <optgroup> tag with label "All Makes"
        if popular: optgroup = soup.find('optgroup', {'label': 'Popular Makes'})
        else: optgroup = soup.find('optgroup', {'label': 'All Makes'})

        car_makes = []

        if optgroup:
            # Extract all <option> values within the optgroup
            for option in optgroup.find_all('option'):
                make = option.get_text(strip=True)
                if make:
                    car_makes.append(make)

        return car_makes
    except Exception as e:
        print(f"An error occurred while parsing HTML: {e}")
        return []

def get_html_from_url(url):
    """
    Fetches the HTML content of a given URL with a custom User-Agent.

    Parameters:
        url (str): The URL of the webpage.

    Returns:
        str: The HTML content of the webpage, or None if the request fails.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching the URL: {e}")
        return None

def get_all_makes(popular=True):
    url = "https://www.autotrader.ca/"
    html_content = get_html_from_url(url)

    if html_content:  # Proceed only if HTML content was fetched successfully
        car_makes = extract_car_makes_from_html(html_content, popular=popular)
        if car_makes:
            return car_makes
        else:
            print("No car makes found in the specified optgroup.")
    else:
        print("Failed to fetch HTML content.")

def get_makes_input():
    """
    Prompts the user for input and validates it against a list of valid strings,
    displaying popular options in a tabular format with numeration for each cell.

    :return: str, the validated input matching an item from the list
    """
    itemTitle = "Make"

    # Fetch popular car makes initially
    valid_options = get_all_makes(popular=True)
    popular = True
    table_len = 8
    while True:
        # Display options in tabular format with numeration for each cell
        cls()
        if popular:
            table = []
            for idx, option in enumerate(valid_options, start=1):
                table.append([f"{idx}. {option}"])

            formatted_table = tabulate([table[i:i+table_len] for i in range(0, len(table), table_len)], tablefmt="plain")
            print(formatted_table)
        else:
            print("Displaying all available options:")
            table = []
            for idx, option in enumerate(valid_options, start=1):
                table.append([f"{idx}. {option}"])

            formatted_table = tabulate([table[i:i+table_len] for i in range(0, len(table), table_len)], tablefmt="plain")
            print(formatted_table)

        user_input = input(f"Enter {itemTitle} number (-1 to see all options): ").strip()

        # Check if the user wants to see all options
        if user_input == "-1":
            popular = False
            valid_options = get_all_makes(popular=False)
        elif user_input.isdigit():
            number = int(user_input)
            if 1 <= number <= len(valid_options):
                return valid_options[number - 1]
            else:
                print("Invalid number. Please choose a valid number from the list.")
        else:
            print("Invalid input. Please enter a valid number or -1 to see all options.")

def get_models_for_make(make):
    """
    Fetches all models for a given car make by sending a POST request to the AutoTrader API.

    Args:
        make (str): The car make for which models are to be fetched.

    Returns:
        dict: A dictionary of models and their respective counts, or an empty dictionary if none found.
    """
    try:
        url = "https://www.autotrader.ca/Home/Refine"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'en-US,en;q=0.9',
            'AllowMvt': 'true'
        }
        # Using cookies from the response
        cookies = {
            'atOptUser': 'db0860a4-b562-4270-9ed0-b2d2875c873c',
            'nlbi_820541_1646237': 'Z30UdORIkUeQlTEnZpjQsQAAAACqH714EnL/JlzmRPTWgXMX'
        }
        payload = {
            "IsDealer": True,
            "IsPrivate": True,
            "InMarketType": "basicSearch",
            "Address": "Rockland",
            "Proximity": -1,
            "Make": make,
            "Model": None,
            "IsNew": True,
            "IsUsed": True,
            "IsCpo": True,
            "IsDamaged": False,
            "WithPhotos": True,
            "WithPrice": True,
            "HasDigitalRetail": False
        }

        # Sending POST request with headers and cookies
        response = requests.post(url, json=payload, headers=headers, cookies=cookies)
        response.raise_for_status()  # Raise HTTPError for bad responses

        data = response.json()

        # Extract and return models from the response
        return data.get("Models", {})
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the request: {e}")
        return {}
    except ValueError as e:
        print(f"Failed to parse JSON response: {e}")
        return {}

def get_models_input(models_for_make):
    """
    Prompts the user to select a model from the available options for a given make.
    Displays the models in a tabular format with numeration for each cell.

    :param models_for_make: dict, models as keys and counts as values
    :return: str, the selected model
    """
    itemTitle = "Model"
    valid_options = list(models_for_make.keys())
    table_len = 8
    while True:
        # Display options in tabular format with numeration for each cell
        cls()
        table = []
        for idx, option in enumerate(valid_options, start=1):
            table.append([f"{idx}. {option}"])

        formatted_table = tabulate([table[i:i+table_len] for i in range(0, len(table), table_len)], tablefmt="plain")
        print(formatted_table)

        user_input = input(f"Enter {itemTitle} number: ").strip()

        if user_input.isdigit():
            number = int(user_input)
            if 1 <= number <= len(valid_options):
                return valid_options[number - 1]
            else:
                print("Invalid number. Please choose a valid number from the list.")
        else:
            print("Invalid input. Please enter a valid number.")

def transform_strings(input_list):
    """
    Takes a list of strings and returns a list of strings where each original string
    is transformed into uppercase, lowercase, and first-letter uppercase format.

    :param input_list: list of strings
    :return: list of transformed strings
    """
    transformed = []
    for string in input_list:
        transformed.append(string.upper())
        transformed.append(string.lower())
        transformed.append(string.capitalize())
    return transformed

def read_json_file(file_path = "output.json"):
    """
    Reads the contents of a JSON file and returns it as a Python dictionary.

    :param file_path: str, the path to the JSON file
    :return: dict, the parsed JSON content
    """
    try:
        with open(file_path, 'r') as file:
            # Load the JSON content from the file
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON - {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
    
def format_time(seconds):
    """
    Formats time given in seconds into hours, minutes, and seconds.

    :param seconds: int, time in seconds
    :return: str, formatted time as "h m s"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}h {minutes}m {seconds:.2f}s"

def format_time_ymd_hms(seconds=None):
    """
    Formats time given in seconds into a string formatted as "yyyy-mm-dd_hh-mm-ss"
    in the current time zone.

    :param seconds: int, time in seconds (defaults to current time)
    :return: str, formatted time
    """
    from datetime import datetime, timezone, timedelta
    import time

    if seconds is None:
        seconds = time.time()

    # Get the current time zone's offset
    #current_time = datetime.now()
    #offset = current_time.utcoffset()

    # Adjust time to the current time zone
    base_time = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    local_time = base_time.astimezone()

    return local_time.strftime("%Y-%m-%d_%H-%M-%S")

def remove_duplicates(arr, excl = []):
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

def remove_duplicates_exclusions(arr, excl=[]):
    """
    Removes duplicates from an array of dictionaries while maintaining the order of elements.
    Excludes entries with 'link' values in the exclusions list.
    
    Args:
        arr (list): The input array of dictionaries.
        excl (list): The exclusions array of 'link' values.
    
    Returns:
        list: A new array with duplicates removed and exclusions applied.
    """
    seen = set()
    result = []
    for item in arr:
        full_link = "https://www.autotrader.ca" + item["link"]
        if full_link not in seen and full_link not in excl:
            # Add the full_link to the item dictionary before appending
            item_with_full_link = item.copy()
            item_with_full_link["link"] = full_link
            result.append(item_with_full_link)
            seen.add(full_link)

    result = filter_dicts(result,excl)
    return result

def filter_dicts(data, exclusion_strings):
    """
    Removes dictionaries from a list if any of their values contain any of the exclusion strings.

    Parameters:
        data (list): List of dictionaries to filter.
        exclusion_strings (list): List of strings to check against dictionary values.

    Returns:
        list: Filtered list of dictionaries.
    """
    filtered_data = []
    for record in data:
        if not any(exclusion_string in str(value) for value in record.values() for exclusion_string in exclusion_strings):
            filtered_data.append(record)
    return filtered_data

def filter_csv(input_file, output_file, payload):
    """
    Removes rows from a CSV file if any column contains any of the strings in the filter_strings list.

    Parameters:
        input_file (str): Path to the input CSV file.
        output_file (str): Path to the output CSV file with filtered rows.
        filter_strings (list): List of strings to filter rows by.

    Returns:
        None
    """
    filter_strings = payload["Exclusions"]
    try:
        # Read the input CSV file
        with open(input_file, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            header = next(reader)  # Get the header row
            rows = list(reader)  # Get the remaining rows

        # Filter rows
        filtered_rows = []
        for row in rows:
            if not any(filter_string in cell for cell in row for filter_string in filter_strings):
                filtered_rows.append(row)

        # Write the updated rows to the output CSV file
        with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(header)  # Write the header row
            writer.writerows(filtered_rows)  # Write the filtered rows

        #print(f"Filtered CSV saved to {output_file}")
        keep_if_contains(input_file=input_file,output_file=output_file,required_string=payload["Inclusion"])
    except FileNotFoundError:
        print(f"Error: The file {input_file} does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

def keep_if_contains(input_file, output_file, required_string = None):
    """
    Removes rows from a CSV file if none of the columns contain the specified string.

    Parameters:
        input_file (str): Path to the input CSV file.
        output_file (str): Path to the output CSV file with filtered rows.
        required_string (str): String that must be present in at least one column to keep the row.

    Returns:
        None
    """
    try:
        # Read the input CSV file
        with open(input_file, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            header = next(reader)  # Get the header row
            rows = list(reader)  # Get the remaining rows

        # Filter rows
        filtered_rows = []
        for row in rows:
            if any(required_string in cell for cell in row) or required_string == None:
                filtered_rows.append(row)

        # Write the updated rows to the output CSV file
        with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(header)  # Write the header row
            writer.writerows(filtered_rows)  # Write the filtered rows

        #print(f"Filtered CSV saved to {output_file}")

    except FileNotFoundError:
        print(f"Error: The file {input_file} does not exist.")
    except Exception as e:
        print(f"An error occurred: {e}")

def get_keywords_from_user(kw_type = "exclude"):
    """
    Allows the user to input keywords and manage them through a menu system.
    Inputs: kw_type (default: exclude) exclude or include
    Returns a list of keywords.
    """
    keywords = []

    print(f"Enter keywords to {kw_type} one by one. Press -1 to stop entering keywords.")
    while True:
        keyword = input(f"Enter a keyword to {kw_type}: ").strip()
        if keyword == '-1':
            break
        if keyword:
            keywords.append(keyword)

    while True:
        print(f"\nCurrent {kw_type} keywords:", ", ".join(keywords) if keywords else "None")
        print("Menu:")
        print(f"1. Add a keyword to {kw_type} ")
        print(f"2. Remove an {kw_type}  keyword")
        print("3. Finish")

        choice = input("Choose an option (1, 2, or 3): ").strip()
        if choice == '1':
            new_keyword = input(f"Enter a new keyword to {kw_type}: ").strip()
            if new_keyword:
                keywords.append(new_keyword)
        elif choice == '2':
            keyword_to_remove = input(f"Enter an {kw_type} keyword to remove: ").strip()
            if keyword_to_remove in keywords:
                keywords.remove(keyword_to_remove)
            else:
                print("Keyword not found.")
        elif choice == '3':
            break
        else:
            print("Invalid choice. Please try again.")

    return transform_strings(keywords)

def get_user_responses():
    """
    Prompt the user for responses to populate the payload items and validate logical consistency.

    Returns:
        dict: A dictionary containing user inputs for the payload.
    """
    #all_makes = get_all_makes()
    payload = {
        "Make": get_makes_input(),
        "Model": None,
        "Proximity": -1,
        "Address": None,
        "YearMin": None,
        "YearMax": None,
        "PriceMin": None,
        "PriceMax": None,
        "Skip": 0,
        "Top": 15,
        "IsNew": True,
        "IsUsed": True,
        "WithPhotos": True,
        "Exclusions": [],
        "Inclusion": "",
        "micrositeType": 1,  # This field is fixed
    }

    if payload["Make"]:
        models_for_make = get_models_for_make(payload["Make"])
        if models_for_make:
            payload["Model"] = get_models_input(models_for_make)

    payload["Address"] = cleaned_input("Address", "Kanata, ON", str)
    payload["Proximity"] = cleaned_input("Distance",-1,int)

    payload["YearMin"] = cleaned_input("Minimum Year", None, int)
    payload["YearMax"] = cleaned_input("Maximum Year", None, int)

    payload["PriceMin"] = cleaned_input("Minimum Price", None, int)
    payload["PriceMax"] = cleaned_input("Maximum Price", None, int)

    # Validate logical consistency of inputs
    if payload["PriceMin"] is not None and payload["PriceMax"] is not None:
        if payload["PriceMin"] > payload["PriceMax"]:
            print("Error: Minimum Price cannot be greater than Maximum Price. Please re-enter.")
            payload["PriceMin"] = cleaned_input("Minimum Price", None, int)
            payload["PriceMax"] = cleaned_input("Maximum Price", None, int)

    if payload["YearMin"] is not None and payload["YearMax"] is not None:
        if payload["YearMin"] > payload["YearMax"]:
            print("Error: Minimum Year cannot be greater than Maximum Year. Please re-enter.")
            payload["YearMin"] = cleaned_input("Minimum Year", None, int)
            payload["YearMax"] = cleaned_input("Maximum Year", None, int)

    payload["Exclusions"] = get_keywords_from_user()
    payload["Inclusion"] = cleaned_input("String To Be Always Included", None, str)
    print(payload)
    return payload





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
    return parsed_html_ad_info##ONLY SENDS PARTIAL URLS


def extract_ng_vdp_model(url):
    """
    Extracts the `window['ngVdpModel']` variable from a webpage by capturing the entire line and parses it into a Python dictionary.
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
        for line in response.text.splitlines():
            if "window['ngVdpModel'] =" in line: 
                cleaned_data = process_line(line)
                ng_vdp_model = extract_vehicle_info_from_nested_json(json.loads(cleaned_data))
                return ng_vdp_model                
            elif "Request unsuccessful. Incapsula incident ID:" in line: ##unreachable basically
                print(response.text)
                raise requests.exceptions.RequestException("Rate limited: Incapsula says Too Many Requests")                
        else:
            respjson = parse_html_content_to_json(response.text)#read_json_file()
            altrespjson = extract_vehicle_info_from_json(respjson)
            return altrespjson#,normalreturn,response#"window['ngVdpModel'] not found in the HTML. Response dump: " + response.text#.splitlines()
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
        # missing_keys = [key for key in required_keys if key not in vehicle_info or not vehicle_info[key]]

        # if missing_keys:
        #     print(f"Missing keys with no values: {', '.join(missing_keys)}")

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
            

        # Ensure all required keys are present
        for required_key in keys_to_extract.values():
            if required_key not in vehicle_info:
                vehicle_info[required_key] = ""
                
        
        # missing_keys = [key for key in keys_to_extract.keys() if key not in vehicle_info or not vehicle_info[key]]
        # if missing_keys:
        #     print(f"Missing keys with no values: {', '.join(missing_keys)}")
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
            opTime = time.time() - startTime
            averagetime = 0
            cartimes.append(opTime)
            for cartime in cartimes:
                averagetime += cartime
            averagetime /= float(len(cartimes))
            cls()
            print(f"{len(cartimes)}/{len(data)}\tTotal time: {opTime:.2f}s\tWithout Pause: {opTime-2:.2f}s\tAverage time: {averagetime:.2f}\tETA:{format_time(averagetime*((len(data)) - len(cartimes)))}")
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




