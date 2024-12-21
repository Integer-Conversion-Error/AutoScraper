import requests
import json
import csv

##DEPRECATED

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
        "make": "",
        "model": "",
        "price_min": 0,
        "price_max": 99999,
        "year_min": "1950",
        "year_max": "2025",
        "top": 15,
        "address": "Kanata, ON",
        "is_new": True,
        "is_used": True,
        "with_photos": True,
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
            "Address": params["address"],
            "Make": params["make"],
            "Model": params["model"],
            "PriceMin": params["price_min"],
            "PriceMax": params["price_max"],
            "Skip": skip,
            "Top": params["top"],
            "IsNew": params["is_new"],
            "IsUsed": params["is_used"],
            "WithPhotos": params["with_photos"],
            "YearMax": params["year_max"],
            "YearMin": params["year_min"],
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

            skip += params["top"]

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

def save_to_csv(data, filename="results.csv"):
    """
    Saves a list of links to a CSV file with one column.

    Args:
        data (list): List of links to save.
        filename (str): Name of the CSV file. (default: "results.csv")
    """
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Link"])  # Write the header
        for link in data:
            writer.writerow([link])
    print(f"Results saved to {filename}")

# Example usage
if __name__ == "__main__":
    search_params = {
        "make": "Tesla",
        "model": "Model 3",
        "price_min": 3000,
        "price_max": 35000,
    }

    results = fetch_autotrader_data(search_params)
    results = remove_duplicates(results)
    save_to_csv(results)

    print(f"Total Results Fetched: {len(results)}")
