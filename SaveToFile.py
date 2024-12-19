import csv
import json
import os
import time




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
        #print(f"JSON content saved to {file_name}")
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



