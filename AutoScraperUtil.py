import ast
import csv
from datetime import datetime, timedelta
import json
import os
import time
from tabulate import tabulate
from bs4 import BeautifulSoup


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

def parse_html_to_json(file_path = "output.html"):
    """
    Parses the JSON-like content embedded within an HTML file.

    Args:
        file_path (str): The path to the HTML file.

    Returns:
        dict: Extracted JSON content or an error message.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            html_content = file.read()

        # Extract JSON-like content between braces assuming it's embedded
        json_start = html_content.find("{")
        json_end = html_content.rfind("}")

        if json_start == -1 or json_end == -1:
            raise ValueError("No JSON-like content found in the HTML file.")

        # Convert the extracted content into JSON
        json_content = json.loads(html_content[json_start:json_end + 1])
        #print("Successfully parsed JSON content from the HTML.")
        return json_content

    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
    except Exception as e:
        print(f"An error occurred while parsing HTML to JSON: {e}")

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

def extract_prices_from_html(html_content):
    """
    Extracts all prices from the JSON-like script elements within an HTML page.

    Args:
        html_content (str): The full HTML content as a string.

    Returns:
        list: A list of prices found in the HTML, or an empty list if none found.
    """
    try:
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Find all <script> tags containing JSON data
        script_tags = soup.find_all('script', type='application/ld+json')

        prices = []

        for script_tag in script_tags:
            try:
                if script_tag.string:
                    # Parse the JSON content
                    json_content = json.loads(script_tag.string)

                    # Extract the price from the "offers" object if available
                    offers = json_content.get("offers", {})
                    price = offers.get("price")
                    if price:
                        prices.append(price)
            except json.JSONDecodeError as e:
                print(f"Failed to decode JSON in one of the script tags: {e}")
                continue

        return prices
    except Exception as e:
        print(f"An error occurred: {e}")
        return []
    
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
            print(f"Folder '{folder}' created.")
        else:
            print(f"Folder '{folder}' already exists.")


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

def get_all_makes(cased=False, popular=True):
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

def format_time_ymd_hms(seconds = time.time()):
    """
    Formats time given in seconds into a string formatted as "yyyy-mm-dd_hh-mm-ss".

    :param seconds: int, time in seconds
    :return: str, formatted time
    """
    base_time = datetime(1970, 1, 1) + timedelta(seconds=seconds)
    return base_time.strftime("%Y-%m-%d_%H-%M-%S")

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

def filter_csv(input_file, output_file, filter_strings):
    """
    Removes rows from a CSV file if any column contains any of the strings in the filter_strings list.

    Parameters:
        input_file (str): Path to the input CSV file.
        output_file (str): Path to the output CSV file with filtered rows.
        filter_strings (list): List of strings to filter rows by.

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
            if not any(filter_string in cell for cell in row for filter_string in filter_strings):
                filtered_rows.append(row)

        # Write the updated rows to the output CSV file
        with open(output_file, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(header)  # Write the header row
            writer.writerows(filtered_rows)  # Write the filtered rows

        print(f"Filtered CSV saved to {output_file}")

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