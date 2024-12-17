import csv
import requests
import json

# Existing functions
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
