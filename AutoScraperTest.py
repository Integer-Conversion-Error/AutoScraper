import json
import requests
from SaveToFile import save_html_to_file
from bs4 import BeautifulSoup

def fetch_autotrader_data(params, exclusions = []):
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
            save_html_to_file(ad_results_json,"html_test_output.html")
            parsed_html_page = parse_html_file("html_test_output.html",exclusions)
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

    return all_results,parsed_html_ad_info




    



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

def sendTestPayload():
    payload = {
        "Address": "Kanata, ON",
        "Make": "Ford",
        "Model": "Fusion",
        "PriceMin": "12000",
        "PriceMax": "17000",
        "Skip": 0,
        "Top": 15,
        "IsNew": "True",
        "IsUsed": "True",
        "WithPhotos": "True",
        "YearMax": "2019",
        "YearMin": "2017",
        "micrositeType": 1,  # This field is fixed
    }
    excl = ["SE","Titanium", "2.0"]
    links,all_ads = fetch_autotrader_data(params=payload,exclusions=excl)

    # for link in links:
    #     print(link)
    print(f"Link amount = {len(links)}")
    print(f"Ad amount = {len(all_ads)}")

while True:
    sendTestPayload()
    break