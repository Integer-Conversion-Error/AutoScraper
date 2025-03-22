import requests
import json
from AutoScraperUtil import parse_html_content_to_json, print_response_size

def scrape_single_page():
    # Hardcoded URL
    url = "https://www.autotrader.ca/a/lexus/gs/brampton/ontario/5_64915219_on20071022095557420/"

    # Headers to mimic a browser request and request compression
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Accept-Encoding": "gzip, deflate, br"  # Request compressed response
    }

    try:
        # Send GET request
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes

        # Print the size of the response
        print_response_size(response)

        # Parse the HTML content to JSON
        json_content = parse_html_content_to_json(response.text)

        # Extract only the fields we're interested in
        extracted_content = extract_relevant_fields(json_content)

        # Get the size of the extracted JSON content
        json_size = len(json.dumps(extracted_content).encode('utf-8'))
        print(f"\nSize of extracted JSON content: {json_size} bytes")
        print(f"Size of extracted JSON content: {json_size / 1024:.2f} KB")

        # Print the extracted data
        print("\nExtracted data:")
        print(json.dumps(extracted_content, indent=2))

    except requests.RequestException as e:
        print(f"An error occurred while making the request: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def extract_relevant_fields(json_content):
    # Extract only the fields we're interested in
    relevant_fields = [
        "Make", "Model", "Year", "Trim", "Price", "Kilometres", "Drivetrain",
        "Status", "Body Type", "Engine", "Cylinder", "Transmission",
        "Exterior Colour", "Doors", "Fuel Type", "City Fuel Economy", "Hwy Fuel Economy"
    ]
    
    extracted = {}
    hero = json_content.get("HeroViewModel", {})
    specs = json_content.get("Specifications", {}).get("Specs", [])

    for field in relevant_fields:
        if field in hero:
            extracted[field] = hero[field]
        else:
            for spec in specs:
                if spec.get("Key") == field:
                    extracted[field] = spec.get("Value")
                    break

    return extracted

if __name__ == "__main__":
    scrape_single_page()