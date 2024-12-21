import csv
import requests
import json,random

#DEPRECATED
def extract_ng_vdp_model(url, proxies=None):
    """
    Extracts the `window['ngVdpModel']` variable from a webpage by capturing the entire line and parses it into a Python dictionary.
    Detects rate limiting and raises an error if encountered. Supports proxy usage.

    Args:
        url (str): The URL to fetch data from.
        proxies (dict): Optional. A dictionary of proxies to use for the request.
            Example: {"http": "http://proxy_url", "https": "https://proxy_url"}
    """
    import requests
    import json
    import random

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

    # Define the proxies dictionary with actual proxy information
    proxies = proxies or {
        "http": "http://123.45.67.89:8080",
        "https": "http://123.45.67.89:8080",
    }

    try:
        response = requests.get(url, headers=headers, proxies=proxies)
        
        # Check for rate limiting
        if response.status_code == 429:
            raise requests.exceptions.RequestException("Rate limited: HTTP 429 Too Many Requests.")
        
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


def process_csv(input_csv="results.csv", output_csv="results.csv"):
    """
    Reads a CSV of links, fetches car information for each link, and writes the results to a new CSV.

    Args:
        input_csv (str): Path to the input CSV file containing links.
        output_csv (str): Path to the output CSV file with additional car information.

    Returns:
        None
    """
    try:
        with open(input_csv, mode="r", encoding="utf-8") as infile, open(output_csv, mode="w", newline="", encoding="utf-8") as outfile:
            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            # Check if the input file is empty
            try:
                header = next(reader)
            except StopIteration:
                print(f"Error: {input_csv} is empty. No data to process.")
                return

            # Write the header with additional columns
            writer.writerow(header + ["Make", "Model", "Kilometres", "Status", "Trim", "Body Type", "Engine", "Cylinder", "Transmission", "Drivetrain", "Fuel Type"])

            # Process each row
            for row in reader:
                url = row[0]  # Assuming the first column contains the link
                print(f"Processing: {url}")

                car_info = get_info_from_json(url=url)
                if car_info:
                    # Write the row with additional columns
                    writer.writerow(row + [
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
                    # Write the row with empty additional columns
                    writer.writerow(row + [""] * 11)
    except FileNotFoundError:
        print(f"Error: {input_csv} not found.")


# Example usage
if __name__ == "__main__":
    process_csv()
