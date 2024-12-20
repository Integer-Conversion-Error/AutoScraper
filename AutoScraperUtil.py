import ast
import csv
from datetime import datetime, timedelta
import json
import os
import time

from bs4 import BeautifulSoup


def parse_html_file(file_path,exclusions = []):
    """
    Parses the HTML file and extracts links and their corresponding listing details.

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