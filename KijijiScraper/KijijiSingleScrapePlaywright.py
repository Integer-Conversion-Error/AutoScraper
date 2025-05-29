import asyncio
import logging
import re
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup # Import BeautifulSoup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define custom exceptions if needed (similar to KijijiSingleScrape.py)
class ScrapingTimeoutError(Exception):
    """Custom exception for scraping timeouts."""
    pass

class ScrapingNavigationError(Exception):
    """Custom exception for navigation errors."""
    pass

class ElementNotFoundError(Exception):
    """Custom exception when a required element is not found."""
    pass


# --- Helper Functions for Data Extraction (Revised) ---

def extract_quick_fact(quick_fact_list: BeautifulSoup, label_text: str) -> Optional[str]:
    """
    Finds a <span> element containing label_text within a specific <li> structure
    inside the quick_fact_list (ul[data-testid="quickFact"]) and returns the text
    of the preceding <span> (the value).

    Args:
        quick_fact_list (BeautifulSoup): The BeautifulSoup object for the <ul> element.
        label_text (str): The text to search for in the label <span> (case-insensitive).

    Returns:
        Optional[str]: The extracted text value, or None if not found.
    """
    if not quick_fact_list:
        return None

    try:
        # Find the span containing the label text
        label_span = quick_fact_list.find('span', string=re.compile(f'^{re.escape(label_text)}$', re.IGNORECASE))

        if label_span:
            # Find the parent div, then the preceding span (value) within that div
            parent_div = label_span.find_parent('div')
            if parent_div:
                value_span = parent_div.find('span') # The first span should be the value
                if value_span and value_span != label_span: # Ensure it's not the label span itself
                    value = value_span.get_text(strip=True)
                    # Handle potential non-breaking spaces
                    value = value.replace('\xa0', ' ').strip()
                    logging.debug(f"Found quick fact '{label_text}': '{value}'")
                    return value
                else:
                    logging.warning(f"Found label span for quick fact '{label_text}', but couldn't find preceding value span in parent div.")
            else:
                 logging.warning(f"Found label span for quick fact '{label_text}', but couldn't find parent div.")
        else:
            logging.debug(f"Label span for quick fact '{label_text}' not found.")

    except Exception as e:
        logging.error(f"Error extracting quick fact for '{label_text}': {e}", exc_info=True)

    return None


def extract_feature_detail(vehicle_details_container: BeautifulSoup, label_text: str) -> Optional[str]:
    """
    Finds a <span> element containing the exact label_text (including trailing colon/space)
    within the vehicle_details_container and returns the stripped text of its immediate
    next <span> sibling.

    Args:
        vehicle_details_container (BeautifulSoup): The BeautifulSoup object for the
                                                   <div data-testid="vehicleDetails"> element.
        label_text (str): The exact text to search for in the label <span> (e.g., "Make: ").

    Returns:
        Optional[str]: The extracted text value, or None if not found.
    """
    if not vehicle_details_container:
        return None

    try:
        # Find the span containing the exact label text
        # We need 'string=label_text' for exact match including colon and space
        label_span = vehicle_details_container.find('span', string=label_text)

        if label_span:
            # Find the immediate next sibling that is also a span
            value_span = label_span.find_next_sibling('span')
            if value_span:
                value = value_span.get_text(strip=True)
                # Handle potential non-breaking spaces just in case
                value = value.replace('\xa0', ' ').strip()
                logging.debug(f"Found feature '{label_text}' -> '{value}'")
                return value
            else:
                logging.warning(f"Found label span for feature '{label_text}' but no following value span.")
        else:
            logging.debug(f"Label span for feature '{label_text}' not found.")

    except Exception as e:
        logging.error(f"Error extracting feature detail for '{label_text}': {e}", exc_info=True)

    return None


def extract_price(container: BeautifulSoup) -> Optional[float]:
    """Attempts to find and parse the price within the container."""
    if not container:
        return None

    # Try the data-testid first (as it's specific if present)
    price_element = container.find('span', {'data-testid': 'price-amount'})
    if price_element:
        price_text = price_element.get_text(strip=True).replace('$', '').replace(',', '')
        try:
            price_num = float(price_text)
            logging.debug(f"Found price using data-testid: {price_num}")
            return int(price_num) if price_num.is_integer() else price_num
        except ValueError:
            logging.warning(f"Could not parse price from data-testid element: {price_element.get_text(strip=True)}")

    # Fallback: Look for spans containing '$' and digits
    logging.debug("Price data-testid not found or failed, searching for spans with '$'.")
    price_spans = container.find_all('span', string=re.compile(r'\$\s*[\d,]+(?:\.\d+)?'))
    if price_spans:
        # Often the most prominent price is the first one or the one with the largest font,
        # but let's just take the first one found for now.
        price_text = price_spans[0].get_text(strip=True).replace('$', '').replace(',', '')
        try:
            price_num = float(price_text)
            logging.debug(f"Found price using span search: {price_num}")
            return int(price_num) if price_num.is_integer() else price_num
        except ValueError:
            logging.warning(f"Could not parse price from found span: {price_spans[0].get_text(strip=True)}")

    logging.warning("Could not find price element.")
    return None


def _extract_data_from_soup(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extracts car details from a BeautifulSoup object representing the listing page HTML.

    Args:
        soup (BeautifulSoup): The parsed HTML content.

    Returns:
        Dict[str, Any]: A dictionary containing the extracted data.
    """
    extracted_data = {}
    logging.info("Parsing HTML content with BeautifulSoup...")

    # Find the main data container
    # Updated selector based on inspection of saved HTML
    data_container = soup.find('div', class_='y3hG57') # Or potentially another stable parent

    if data_container:
        logging.info("Found potential data container. Extracting data...")

        # Price (using existing helper)
        extracted_data['Price'] = extract_price(data_container)

        # Find the Quick Facts list
        quick_fact_list = data_container.find('ul', {'data-testid': 'quickFact'})
        if quick_fact_list:
            logging.info("Found quick facts list (ul[data-testid='quickFact']). Extracting...")

            # Extract fields from Quick Facts list using extract_quick_fact
            extracted_data['Status'] = extract_quick_fact(quick_fact_list, 'Condition')
            km_text = extract_quick_fact(quick_fact_list, 'Kilometres')
            extracted_data['Transmission'] = extract_quick_fact(quick_fact_list, 'Transmission')
            extracted_data['Trim'] = extract_quick_fact(quick_fact_list, 'Trim')
            extracted_data['Drivetrain'] = extract_quick_fact(quick_fact_list, 'Drivetrain')
            extracted_data['Fuel Type'] = extract_quick_fact(quick_fact_list, 'Fuel type')

            # Parse Kilometres if found
            if km_text:
                match = re.search(r'([\d,]+)', km_text) # Find digits and commas
                km_numeric_part = match.group(1).replace(',', '') if match else None
                if km_numeric_part:
                    try:
                        extracted_data['Kilometres'] = int(km_numeric_part)
                    except ValueError:
                        logging.warning(f"Could not convert extracted quick fact kilometres '{km_numeric_part}' to int.")
                        extracted_data['Kilometres'] = None
                else:
                    extracted_data['Kilometres'] = None # No digits found
            else:
                extracted_data['Kilometres'] = None # Label found but no value? Or label not found? Check logs.
        else:
            logging.warning("Quick facts list (ul[data-testid='quickFact']) not found.")
            # Set quick fact fields to None if list not found
            extracted_data['Status'] = None
            extracted_data['Kilometres'] = None
            extracted_data['Transmission'] = None
            extracted_data['Trim'] = None
            extracted_data['Drivetrain'] = None
            extracted_data['Fuel Type'] = None


        # Find the Vehicle Details container within the features section
        vehicle_details_container = data_container.find('div', {'data-testid': 'vehicleDetails'})

        if vehicle_details_container:
            logging.info("Found vehicle details container (div[data-testid='vehicleDetails']). Extracting...")
            # Use the new extract_feature_detail helper with exact labels + colon + space
            extracted_data['Make'] = extract_feature_detail(vehicle_details_container, 'Make: ')
            extracted_data['Model'] = extract_feature_detail(vehicle_details_container, 'Model: ')
            year_text = extract_feature_detail(vehicle_details_container, 'Year: ')
            extracted_data['Year'] = int(year_text) if year_text and year_text.isdigit() else None
            extracted_data['Body Type'] = extract_feature_detail(vehicle_details_container, 'Body type: ')
            # Engine: Use 'Power: ' as seen in HTML, parse out ' hp' later if needed
            extracted_data['Engine'] = extract_feature_detail(vehicle_details_container, 'Power: ')
            extracted_data['Cylinder'] = extract_feature_detail(vehicle_details_container, 'Cylinders: ')
            extracted_data['Exterior Colour'] = extract_feature_detail(vehicle_details_container, 'Colour: ')
            extracted_data['Doors'] = extract_feature_detail(vehicle_details_container, 'Door count: ')
            # Note: Trim, Transmission, Drivetrain, Fuel Type are already handled by quick facts
        else:
             logging.warning("Vehicle details container (div[data-testid='vehicleDetails']) not found.")
             # Set these fields to None if container not found
             extracted_data['Make'] = None
             extracted_data['Model'] = None
             extracted_data['Year'] = None
             extracted_data['Body Type'] = None
             extracted_data['Engine'] = None
             extracted_data['Cylinder'] = None
             extracted_data['Exterior Colour'] = None
             extracted_data['Doors'] = None

        # Clean up None values before logging/returning
        final_extracted_data = {k: v for k, v in extracted_data.items() if v is not None and v != ''} # Also remove empty strings
        logging.info(f"Extracted data: {final_extracted_data}")
        return final_extracted_data # Return cleaned data

    else:
        logging.warning("Could not find the main data container div.y3hG57 in the HTML.")
        return {} # Return empty dict if container not found


async def scrape_kijiji_single_page_playwright(url: Optional[str] = None, html_content: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Scrapes a single Kijiji Autos listing page.
    Can operate in two modes:
    1. URL Mode: Navigates to the URL, clicks 'View full listing', and extracts data.
    2. HTML Mode: Parses the provided html_content string directly and extracts data.

    Args:
        url (Optional[str]): The full URL of the Kijiji listing page (used if html_content is None).
        html_content (Optional[str]): The HTML content of the page (used if provided).

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the extracted data, or None on critical error.
    """
    if html_content:
        # --- HTML Mode ---
        logging.info("Processing provided HTML content...")
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            return _extract_data_from_soup(soup)
        except Exception as e:
            logging.error(f"Error parsing provided HTML content: {e}", exc_info=True)
            return None # Indicate failure

    elif url:
        # --- URL Mode ---
        logging.info(f"Attempting to navigate, click, and scrape data for: {url}")
        async with async_playwright() as p:
            browser = None
            page_content_after_action = None # Store content after click/error
            try:
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navigate to the URL
                logging.info(f"Navigating to {url}...")
                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                logging.info("Navigation successful.")

                # Click "View full listing" button using specific classes
                try:
                    button_selector = 'button.zXFi0_.tXFi0_.bXFi0_.mBeyd2.b2yTo_'
                    logging.info(f"Attempting to find button with selector: {button_selector}")
                    view_listing_button = page.locator(button_selector)
                    await view_listing_button.wait_for(state='visible', timeout=10000)
                    logging.info("Found 'View full listing' button. Clicking...")
                    await view_listing_button.click(timeout=5000)
                    logging.info("'View full listing' button clicked.")

                    # Wait for network activity to settle after the click
                    logging.info("Waiting for network idle after click...")
                    try:
                        await page.wait_for_load_state('networkidle', timeout=10000)
                        logging.info("Network is idle.")
                    except PlaywrightTimeoutError:
                        logging.warning("Network did not become idle within 10 seconds after click. Proceeding anyway.")
                    except Exception as e:
                         logging.warning(f"Error during wait_for_load_state: {e}. Proceeding anyway.")

                    page_content_after_action = await page.content()
                    # Save for debugging if needed
                    # with open("page_content_after_click_attempt.html", "w", encoding="utf-8") as f:
                    #     f.write(page_content_after_action)
                    # logging.info("Saved page content after click to page_content_after_click_attempt.html")

                except PlaywrightTimeoutError as e:
                    logging.warning(f"Timeout clicking 'View full listing': {e}")
                    # Save content before click failure for debugging
                    try:
                        page_content_after_action = await page.content() # Content might have changed partially
                        # with open("page_content_before_click_failure.html", "w", encoding="utf-8") as f:
                        #     f.write(page_content_after_action)
                        # logging.info("Saved page content before click failure.")
                    except Exception as save_err:
                        logging.warning(f"Could not get page content before click failure: {save_err}")

                except Exception as e:
                    logging.warning(f"An error occurred while trying to click 'View full listing': {e}", exc_info=True)
                    # Save content on other errors
                    try:
                        page_content_after_action = await page.content()
                        # with open("page_content_on_error.html", "w", encoding="utf-8") as f:
                        #     f.write(page_content_after_action)
                        # logging.info("Saved page content on error.")
                    except Exception as save_err:
                        logging.warning(f"Could not get page content on error: {save_err}")

                # --- Parse HTML and Extract Data (if content was retrieved) ---
                if page_content_after_action:
                    soup = BeautifulSoup(page_content_after_action, 'lxml')
                    extracted_data = _extract_data_from_soup(soup)
                else:
                    logging.warning("No page content was retrieved after actions, cannot extract data.")
                    extracted_data = {}

                await browser.close()
                logging.info("Browser closed.")
                return extracted_data # Return extracted data (might be empty)

            except PlaywrightTimeoutError as e:
                logging.error(f"Playwright timeout during scraping of {url}: {e}")
                if browser: await browser.close()
                raise ScrapingTimeoutError(f"Timeout scraping {url}") from e
            except Exception as e:
                logging.error(f"An unexpected error occurred during Playwright scraping of {url}: {e}", exc_info=True)
                if browser: await browser.close()
                return None # Indicate failure

    else:
        logging.error("Either url or html_content must be provided.")
        return None


# --- Main block for testing ---
async def main_test():
    """Main function to run the scraper test."""
    # --- Test URL Mode ---
    test_url = "https://www.kijijiautos.ca/cars/bmw/3-series/used/#vip=34995079"
    logging.info(f"--- Testing Playwright Scraper for URL: {test_url} ---")
    extracted_result_url = await scrape_kijiji_single_page_playwright(url=test_url)
    print("\n--- Extraction Result (URL Mode) ---")
    print(json.dumps(extracted_result_url, indent=4))

    # --- Test HTML Mode (Optional: Read from a saved file) ---
    # Use a file known to exist from previous runs or provide a valid path
    html_file_path = "page_content_on_srp_error_27_20250505_043456.html" # Example file
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            test_html_content = f.read()
        logging.info(f"\n--- Testing Playwright Scraper for HTML file: {html_file_path} ---")
        extracted_result_html = await scrape_kijiji_single_page_playwright(html_content=test_html_content)
        print("\n--- Extraction Result (HTML Mode) ---")
        print(json.dumps(extracted_result_html, indent=4))
    except FileNotFoundError:
        logging.warning(f"HTML test file not found: {html_file_path}. Skipping HTML mode test.")
    except Exception as e:
        logging.error(f"Error during HTML mode test: {e}", exc_info=True)


    print("\nScript finished. Check logs and output.")


if __name__ == "__main__":
    # Note: Ensure Playwright browsers are installed (e.g., npx playwright install --with-deps chromium)
    asyncio.run(main_test())
