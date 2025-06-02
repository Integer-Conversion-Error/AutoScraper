import argparse
import json
import os
import re

def extract_and_save_initial_state(html_file_path):
    """
    Extracts the JSON object from a specific script tag in an HTML file
    and saves it to a new JSON file.

    The script tag is expected to start with 'window.INITIAL_STATE = '.
    The output file will be named based on the input HTML file name,
    with ' INITIAL STATE.json' appended.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {html_file_path}")
        return
    except Exception as e:
        print(f"Error reading file {html_file_path}: {e}")
        return

    # Regex to find the script content starting with window.INITIAL_STATE
    # It captures the JSON object.
    # Assumes the JSON object is the rest of the content after 'window.INITIAL_STATE = '
    # and before the closing </script> tag, possibly with a semicolon at the end.
    match = re.search(r'<script[^>]*>\s*window\.INITIAL_STATE\s*=\s*(\{.*?\})\s*;?\s*</script>', html_content, re.DOTALL)

    if not match:
        print("Error: Could not find the 'window.INITIAL_STATE' script tag or JSON object within it.")
        return

    json_string = match.group(1)

    try:
        # Validate and parse the JSON
        json_data = json.loads(json_string)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON from the script tag. {e}")
        # Attempt to clean up potential trailing commas or other minor issues if simple
        # For more complex issues, this might not be enough.
        # Example: remove trailing comma before a closing brace or bracket
        cleaned_json_string = re.sub(r',\s*([}\]])', r'\1', json_string)
        try:
            json_data = json.loads(cleaned_json_string)
            print("Successfully parsed JSON after attempting to clean it.")
        except json.JSONDecodeError as e_cleaned:
            print(f"Error: Still failed to decode JSON after cleaning attempt. {e_cleaned}")
            print("Problematic JSON string snippet (first 500 chars):")
            print(json_string[:500])
            return


    base_name = os.path.splitext(os.path.basename(html_file_path))[0]
    output_filename = f"{base_name} INITIAL STATE.json"
    # Save in the same directory as the input file
    input_dir = os.path.dirname(html_file_path)
    if not input_dir: # Handle case where file is in CWD and path is just filename
        input_dir = "."
    output_path = os.path.join(input_dir, output_filename)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=4, ensure_ascii=False)
        print(f"Successfully extracted and saved INITIAL_STATE to {output_path}")

        # After saving INITIAL_STATE, extract and save SRP items
        extract_and_save_srp_items(json_data, base_name, input_dir)

    except Exception as e:
        print(f"Error writing INITIAL_STATE JSON to file {output_path}: {e}")


def extract_and_save_srp_items(initial_state_json, base_name, output_dir):
    """
    Extracts the list of items from initial_state_json['pages']['srp']['items']
    and saves it to a new JSON file named '{base_name} ITEMS.json'.
    """
    try:
        # Navigate to the items list
        srp_items = initial_state_json.get('pages', {}).get('srp', {}).get('items', None)

        if srp_items is None:
            print(f"Warning: 'pages/srp/items' path not found in INITIAL_STATE for {base_name}. Skipping ITEMS file creation.")
            return
        
        if not isinstance(srp_items, list):
            print(f"Warning: 'pages/srp/items' in INITIAL_STATE for {base_name} is not a list. Skipping ITEMS file creation.")
            return

        items_output_filename = f"{base_name} ITEMS.json"
        items_output_path = os.path.join(output_dir, items_output_filename)

        with open(items_output_path, 'w', encoding='utf-8') as f:
            json.dump(srp_items, f, indent=4, ensure_ascii=False)
        print(f"Successfully extracted and saved SRP items to {items_output_path}")

    except KeyError as e:
        print(f"KeyError accessing 'pages/srp/items' for {base_name}: {e}. Skipping ITEMS file creation.")
    except TypeError as e:
        print(f"TypeError while processing 'pages/srp/items' for {base_name}: {e}. This might indicate an unexpected structure. Skipping ITEMS file creation.")
    except Exception as e:
        print(f"Error processing or writing SRP items for {base_name}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract window.INITIAL_STATE JSON from an HTML file and save it.")
    parser.add_argument("html_file", help="Path to the HTML file")

    args = parser.parse_args()

    extract_and_save_initial_state(args.html_file)
