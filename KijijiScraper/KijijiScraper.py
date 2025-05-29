import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import httpx # Import httpx
import json
import logging
import re
from urllib.parse import urlencode, urljoin, urlparse
import time
import os
import glob # Added for glob pattern matching
from datetime import datetime # Added for timestamp

# Import the necessary ASYNC functions, proxy loader, and custom exceptions from KijijiSingleScrape
from KijijiSingleScrape import (
    scrape_kijiji_single_page_async,
    extract_relevant_kijiji_data,
    get_proxy_from_file, # Need this for httpx client setup
    ScrapingTimeoutError, # Import the custom timeout exception
    ScrapingConnectionError # Import the custom connection error exception
)
# Import the Playwright single scraper function and its exceptions
from KijijiSingleScrapePlaywright import (
    scrape_kijiji_single_page_playwright,
    ScrapingTimeoutError as PlaywrightTimeoutErrorAlias, # Alias to avoid name clash
    ScrapingNavigationError as PlaywrightNavigationErrorAlias # Alias to avoid name clash
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
BASE_URL = "https://www.kijijiautos.ca/"
PAGE_TIMEOUT = 120000 # 120 seconds (Increased timeout)
WORKER_COUNT = 1000 # Default worker count is no longer used directly in main
QUEUE_MAX_SIZE = 100 # Max items in the processing queue
SCROLL_DELAY = 0.1 # Delay between scrolls (seconds)
NETWORK_IDLE_TIMEOUT = 1500 # Timeout for waiting for network idle (ms)
STABLE_HEIGHT_CHECKS = 3 # How many times height must be stable to stop scrolling
MONITOR_INTERVAL = 0.1 # How often to check for new listings (seconds)
FAILED_SCRAPE_DEBUG = True # If True, suppress successful logs, only show failures/fallbacks
JSON_DEBUG = False # If True, enable detailed JSON logging per scroll and duplicate analysis
SAVE_HTML_DEBUG = False # If True, save HTML content on certain errors for debugging

# --- Helper Functions ---

def extract_srp_items_from_html(html_content):
    """
    Extracts SRP items from the window.INITIAL_STATE in HTML content.
    Returns a list of items, or an empty list if extraction fails.
    """
    match = re.search(r'<script[^>]*>\s*window\.INITIAL_STATE\s*=\s*(\{.*?\})\s*;?\s*</script>', html_content, re.DOTALL)
    if not match:
        logger.warning("Could not find 'window.INITIAL_STATE' script tag in HTML content for item extraction.")
        return []
    json_string = match.group(1)
    try:
        initial_state_json = json.loads(json_string)
        return initial_state_json.get('pages', {}).get('srp', {}).get('items', [])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to decode INITIAL_STATE JSON: {e}")
        # Attempt to clean up potential trailing commas
        cleaned_json_string = re.sub(r',\s*([}\]])', r'\1', json_string)
        try:
            initial_state_json = json.loads(cleaned_json_string)
            logger.info("Successfully parsed INITIAL_STATE JSON after cleaning attempt.")
            return initial_state_json.get('pages', {}).get('srp', {}).get('items', [])
        except json.JSONDecodeError as e_cleaned:
            logger.error(f"Still failed to decode INITIAL_STATE JSON after cleaning: {e_cleaned}")
            return []
    except Exception as e:
        logger.error(f"Unexpected error extracting SRP items from HTML: {e}")
        return []

def construct_search_url(params):
    """
    Constructs the Kijiji Autos search URL, including fragment parameters.
    Uses parameter names observed from Kijiji Autos URLs.
    """
    # --- Base Path Construction ---
    path_parts = ["cars"]
    make = params.get('make')
    model = params.get('model')
    location = params.get('location') # Optional location in path

    if make:
        path_parts.append(make.lower().replace(' ', '-'))
    if model:
        # Ensure model is appended only if make exists
        if make:
            path_parts.append(model.lower().replace(' ', '-'))
        else:
            logger.warning("Model provided without Make, model path ignored.")

    base_path = "/".join(path_parts) + "/"
    base_url_with_path = urljoin(BASE_URL, base_path)

    # --- Fragment Parameter Construction ---
    fragment_params = []

    # Helper to add range parameters (e.g., year, price, mileage)
    def add_range_param(key, min_val_key, max_val_key):
        min_val = params.get(min_val_key)
        max_val = params.get(max_val_key)
        if min_val is not None or max_val is not None:
            min_str = str(min_val) if min_val is not None else ""
            max_str = str(max_val) if max_val is not None else ""
            fragment_params.append(f"{key}={min_str}:{max_str}")

    # Helper to add multi-select parameters (e.g., colors, features)
    def add_multi_select_param(key, param_key):
        values = params.get(param_key)
        if values and isinstance(values, list):
            for value in values:
                fragment_params.append(f"{key}={value}")
        elif values:
            fragment_params.append(f"{key}={values}")

    # Map user-friendly keys to Kijiji fragment keys and add them
    add_range_param('yc', 'year_min', 'year_max')
    add_range_param('p', 'price_min', 'price_max')
    add_range_param('ml', 'mileage_min', 'mileage_max')
    add_range_param('engineSize', 'engine_size_min', 'engine_size_max')
    add_range_param('pw', 'power_min', 'power_max')
    add_range_param('sc', 'seats_min', 'seats_max')
    add_multi_select_param('c', 'body_types')
    add_multi_select_param('con', 'conditions')
    add_multi_select_param('cylinders', 'cylinders')
    add_multi_select_param('doors', 'doors')
    add_multi_select_param('dt', 'drivetrains')
    add_multi_select_param('ecol', 'exterior_colors')
    add_multi_select_param('fe', 'features')
    add_multi_select_param('ft', 'fuel_types')
    add_multi_select_param('mo', 'media_options')
    add_multi_select_param('st', 'seller_types')
    add_multi_select_param('tr', 'transmissions')
    add_multi_select_param('tct', 'trailer_couplings')
    if params.get('climate_control'):
        fragment_params.append(f"clim={params['climate_control']}")
    if params.get('payment_assistance'):
        fragment_params.append(f"pa={params['payment_assistance']}")

    sort_by = params.get('sort_by', 'rel')
    order_direction = params.get('order_direction', 'down')
    fragment_params.append(f"sb={sort_by}")
    fragment_params.append(f"od={order_direction}")

    full_url = base_url_with_path
    if fragment_params:
        fragment_string = "&".join(fragment_params)
        full_url += "#" + fragment_string

    # Suppress URL logging during benchmark
    # logger.info(f"Constructed URL: {full_url}")
    return full_url

# --- VIP Page Extraction Logic (Using BeautifulSoup) ---
# This function is no longer needed as we use the API via KijijiSingleScrape
# def extract_vip_details(vip_soup, url, title):
#     ... (removed) ...


# --- Async Tasks ---

async def scroll_task(page, stop_event, debug_html_path, items_per_scroll_snapshot, cross_scroll_item_tracker): # Parameters will be None if JSON_DEBUG is False
    """Scrolls the page. If JSON_DEBUG is True, saves HTML content, extracts items, and tracks them."""
    # logger.info("Starting scroll task...") # Suppressed log
    last_height = await page.evaluate("document.body.scrollHeight")
    stable_count = 0
    scroll_attempt_number = 0
    max_scroll_attempts = 150 # Limit scrolls

    while not stop_event.is_set() and scroll_attempt_number < max_scroll_attempts:
        scroll_attempt_number += 1
        # logger.debug(f"Scroll attempt {scroll_attempt_number}/{max_scroll_attempts}, scrolling down...")
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(SCROLL_DELAY) # Give content time to load after scroll action

        if JSON_DEBUG:
            # --- Save HTML content and extract items (only if JSON_DEBUG is True) ---
            try:
                html_content = await page.content()
                # Ensure debug_html_path is valid before joining
                if debug_html_path:
                    html_file_path = os.path.join(debug_html_path, f"scroll_{scroll_attempt_number}_page_content.html")
                    with open(html_file_path, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                    # logger.info(f"Saved HTML for scroll {scroll_attempt_number} to {html_file_path}")

                current_scroll_items = extract_srp_items_from_html(html_content)
                if current_scroll_items:
                    if debug_html_path: # Ensure path exists before writing
                        items_file_path = os.path.join(debug_html_path, f"scroll_{scroll_attempt_number}_items.json")
                        with open(items_file_path, 'w', encoding='utf-8') as f:
                            json.dump(current_scroll_items, f, indent=2)
                        # logger.info(f"Saved {len(current_scroll_items)} items for scroll {scroll_attempt_number} to {items_file_path}")

                    current_item_ids = {item['id'] for item in current_scroll_items if 'id' in item}

                    # Distinct Item Check (ensure items_per_scroll_snapshot is initialized)
                    if items_per_scroll_snapshot is not None:
                        if items_per_scroll_snapshot: # If not the first scroll
                            previous_item_ids = items_per_scroll_snapshot[-1]
                            if current_item_ids == previous_item_ids:
                                logger.info(f"Scroll {scroll_attempt_number}: Items are identical to the previous scroll (scroll {scroll_attempt_number -1}).")
                        items_per_scroll_snapshot.append(current_item_ids)

                    # Update cross_scroll_item_tracker (ensure it's initialized)
                    if cross_scroll_item_tracker is not None:
                        for item in current_scroll_items:
                            item_id = item.get('id')
                            item_link_path = item.get('url', f"/a-car/{item_id}")
                            item_full_link = urljoin(BASE_URL, item_link_path)

                            if item_id:
                                if item_id in cross_scroll_item_tracker:
                                    cross_scroll_item_tracker[item_id]['scroll_numbers'].add(scroll_attempt_number)
                                else:
                                    cross_scroll_item_tracker[item_id] = {
                                        "link": item_full_link,
                                        "scroll_numbers": {scroll_attempt_number}
                                    }
                else:
                    # If no items extracted, still add an empty set if tracking
                    if items_per_scroll_snapshot is not None:
                        items_per_scroll_snapshot.append(set())
                    logger.info(f"Scroll {scroll_attempt_number}: No items extracted from HTML.")

            except Exception as e:
                logger.error(f"Error during JSON_DEBUG HTML processing/saving for scroll {scroll_attempt_number}: {e}", exc_info=True)
            # --- End HTML processing ---

        try:
            await page.wait_for_load_state('networkidle', timeout=NETWORK_IDLE_TIMEOUT)
            # logger.debug("Network became idle after scroll.")
        except PlaywrightTimeoutError:
            pass # logger.debug("Network did not become idle quickly after scroll, proceeding.")
        except Exception as e:
            logger.warning(f"Error during wait_for_load_state: {e}")

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            stable_count += 1
            # logger.debug(f"Scroll height stable ({stable_count}/{STABLE_HEIGHT_CHECKS}).")
            if stable_count >= STABLE_HEIGHT_CHECKS:
                # logger.info("Scroll height stable. Stopping scroll task.")
                stop_event.set()
                break
        else:
            stable_count = 0
            last_height = new_height
            # logger.info(f"Scroll height increased to: {new_height} pixels.")
        
        if scroll_attempt_number == max_scroll_attempts:
            logger.warning(f"Reached max scroll attempts ({max_scroll_attempts}). Stopping scroll.")
            stop_event.set()
    # logger.info("Scroll task finished.")


async def monitor_and_queue_task(page, queue, scraped_ad_ids, all_listings_data, stop_event, worker_count, srp_failed_log_path="failed_srp_links.txt"): # Added srp_failed_log_path
    """Monitors for new listings and adds their ad_id/title to the queue. Logs SRP failures."""
    # logger.info(f"Starting monitoring task... Logging SRP failures to: {srp_failed_log_path}") # Suppressed log
    last_logged_batch = -1 # Track the last logged batch number

    while not stop_event.is_set() or not queue.empty():
        if stop_event.is_set() and queue.full():
            logger.warning("Stop event set and queue is full, potentially dropping new items.") # Keep warning
            pass # Allow loop to continue to potentially drain queue

        try:
            listing_locators = page.locator('article[data-testid="SearchResultListItem"]')
            current_found_count = await listing_locators.count()
            # logger.debug(f"Monitor check: Found {current_found_count} total listing locators on page.") # Suppressed debug log

            # Log batch progress based on the number of listings found so far
            current_batch = current_found_count // 20
            if current_batch > last_logged_batch:
                # logger.info(f"Detected listings potentially up to batch ~{current_batch} (approx {current_found_count} listings found).") # Suppressed log
                last_logged_batch = current_batch

            # Iterate through locators found in this check
            for i in range(current_found_count):
                article_locator = listing_locators.nth(i)
                ad_id = None # Reset ad_id for each iteration
                title_value = None # Reset title_value for each iteration
                if not FAILED_SCRAPE_DEBUG:
                    logger.info(f"Monitor: Processing SRP item index {i} (0-based).")

                try:
                    ad_id_div = article_locator.locator('div[data-testid="VehicleListItem"]')
                    ad_id = await ad_id_div.get_attribute('data-test-ad-id', timeout=100) # Short timeout for quick check

                    if ad_id: # Only proceed if ad_id is found
                        title_tag = article_locator.locator('h2')
                        title_value = await title_tag.text_content(timeout=100) if await title_tag.count() > 0 else "N/A"

                        if ad_id not in scraped_ad_ids:
                            if title_value and title_value != "N/A":
                                if not FAILED_SCRAPE_DEBUG:
                                    logger.info(f"Monitor: Successfully extracted for SRP index {i}: ad_id='{ad_id}', title='{title_value}'. Queuing.")
                                scraped_ad_ids.add(ad_id)
                                try:
                                    await queue.put((ad_id, title_value))
                                except asyncio.QueueFull:
                                    logger.warning(f"Queue full. Waiting to add ad_id: {ad_id}, title: '{title_value}'") # Keep warning
                                    await queue.put((ad_id, title_value)) # Retry putting after warning
                            else: # This means title_value is "N/A" or was not found
                                logger.warning(f"Monitor: For SRP index {i}, got ad_id='{ad_id}' but title is '{title_value}'. Queuing with ad_id only.")
                                scraped_ad_ids.add(ad_id)
                                try:
                                    await queue.put((ad_id, title_value)) # title_value here will be "N/A"
                                except asyncio.QueueFull:
                                    logger.warning(f"Queue full. Waiting to add ad_id: {ad_id} (title: '{title_value}').")
                                    await queue.put((ad_id, title_value))
                        else:
                            if not FAILED_SCRAPE_DEBUG:
                                logger.info(f"Monitor: SRP index {i}, ad_id='{ad_id}' (title: '{title_value}') already scraped or queued. Skipping.")
                    else:
                        logger.warning(f"Monitor: Failed to get ad_id for SRP item index {i} after initial attempt.")

                except PlaywrightTimeoutError:
                    current_url = page.url # Get current URL for logging
                    logger.warning(f"Monitor: SRP Timeout for index {i}. ad_id so far: '{ad_id}'. URL: {current_url}. Found count: {current_found_count}")

                    # --- Count VehicleListItems on error ---
                    try:
                        vehicle_list_item_locator = page.locator('div[data-testid="VehicleListItem"]')
                        vehicle_list_item_count = await vehicle_list_item_locator.count()
                        logger.info(f"On SRP Timeout for index {i}, found {vehicle_list_item_count} div elements with data-testid='VehicleListItem'.")
                    except Exception as e_count_vli:
                        logger.error(f"Error counting VehicleListItems on SRP Timeout for index {i}: {e_count_vli}")
                    # --- End Count VehicleListItems ---

                    # --- Attempt to save full page content on error ---
                    if SAVE_HTML_DEBUG:
                        try:
                            page_content = await page.content()
                            timestamp = time.strftime("%Y%m%d_%H%M%S")
                            
                            # Ensure debug_html directory exists
                            debug_html_dir = "debug_html"
                            os.makedirs(debug_html_dir, exist_ok=True)
                            
                            base_error_filename = f"page_content_on_srp_error_{i}_{timestamp}.html"
                            error_filepath = os.path.join(debug_html_dir, base_error_filename)
                            
                            with open(error_filepath, 'w', encoding='utf-8') as f_err:
                                f_err.write(page_content)
                            logger.warning(f"Saved full page content to {error_filepath} due to SRP timeout on index {i}.")
                        except Exception as page_content_err:
                            logger.error(f"Failed to get or save page content on SRP timeout for index {i}: {page_content_err}")
                    # --- End page content saving ---

                    # --- Attempt to log the failed element's HTML (might still fail) ---
                    raw_element_html = None # Initialize
                    try:
                        # Attempt to get outerHTML of the specific failing element
                        raw_element_html = await article_locator.evaluate("element => element.outerHTML", timeout=1000)
                        if raw_element_html:
                            logger.warning(f"Getting raw HTML for failed SRP element (index {i})")
                            # Write this to the SRP failed log file
                            try:
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                                log_message = f"[{timestamp}] SRP Timeout - Index {i}: Raw Element HTML:\n---\n{raw_element_html}\n---"
                                absolute_log_path = os.path.abspath(srp_failed_log_path)
                                with open(srp_failed_log_path, 'a', encoding='utf-8') as f_log:
                                    f_log.write(f"{log_message}\n\n")
                            except Exception as file_write_err:
                                logger.error(f"!!! FAILED to write raw element HTML SRP log to {absolute_log_path}: {file_write_err}")
                        else:
                            logger.warning(f"Could not extract raw HTML for failed SRP element (index {i}).")
                    except Exception as element_html_err:
                        logger.warning(f"Could not get raw HTML for failed SRP element (index {i}) due to error: {element_html_err}")
                    # --- End HTML logging attempt ---

                    # --- Attempt to parse raw_element_html if ad_id is still None ---
                    parsed_from_raw_html = False
                    if not ad_id and raw_element_html:
                        logger.info(f"Monitor: SRP Timeout for index {i}, ad_id not found via Playwright. Attempting to parse from raw element HTML.")
                        ad_id_match = re.search(r'data-test-ad-id="([^"]+)"', raw_element_html)
                        title_match = re.search(r'<h2[^>]*>(.*?)<\/h2>', raw_element_html, re.DOTALL)

                        if ad_id_match:
                            extracted_ad_id_from_raw = ad_id_match.group(1)
                            extracted_title_from_raw = title_match.group(1).strip() if title_match else "N/A (from raw HTML)"
                            
                            if extracted_ad_id_from_raw not in scraped_ad_ids:
                                logger.info(f"Monitor: Successfully extracted from raw HTML for SRP index {i}: ad_id='{extracted_ad_id_from_raw}', title='{extracted_title_from_raw}'. Queuing.")
                                ad_id = extracted_ad_id_from_raw # Assign to ad_id for further logic
                                title_value = extracted_title_from_raw # Assign to title_value
                                scraped_ad_ids.add(ad_id)
                                try:
                                    await queue.put((ad_id, title_value))
                                    parsed_from_raw_html = True
                                except asyncio.QueueFull:
                                    logger.warning(f"Queue full. Waiting to add (from raw HTML) ad_id: {ad_id}, title: '{title_value}'")
                                    await queue.put((ad_id, title_value))
                                    parsed_from_raw_html = True
                            else:
                                logger.info(f"Monitor: SRP index {i}, ad_id='{extracted_ad_id_from_raw}' (from raw HTML) already scraped or queued. Skipping.")
                                parsed_from_raw_html = True # Still consider it handled
                        else:
                            logger.warning(f"Monitor: Failed to extract ad_id from raw HTML for SRP index {i}.")
                    
                    if parsed_from_raw_html:
                        continue # Successfully processed from raw HTML, move to next item

                    # --- Playwright Fallback for SRP Timeout (if ad_id was found before timeout or by raw HTML parse) ---
                    if ad_id and ad_id not in scraped_ad_ids: # ad_id might have been populated by Playwright before timeout OR by raw HTML parsing
                        vip_url = urljoin(BASE_URL, f"/vip/{ad_id}/")
                        logger.info(f"Monitor: SRP Timeout for index {i}, but ad_id='{ad_id}' was retrieved (possibly from raw HTML). Attempting Playwright fallback for URL: {vip_url}.")
                        try:
                            # Call the Playwright single page scraper
                            playwright_data = await scrape_kijiji_single_page_playwright(vip_url)
                            if playwright_data:
                                if not FAILED_SCRAPE_DEBUG:
                                    logger.info(f"Monitor: Playwright SRP fallback for ad_id='{ad_id}' (URL: {vip_url}) SUCCEEDED. Data extracted.")
                                # Add necessary fields similar to the primary method
                                playwright_data['ad_id'] = ad_id
                                playwright_data['url'] = vip_url
                                playwright_data['source'] = 'kijiji_autos_playwright_srp_fallback' # New source identifier
                                all_listings_data.append(playwright_data)
                                scraped_ad_ids.add(ad_id) # Mark as scraped to avoid re-processing
                                # Print progress update
                                if not FAILED_SCRAPE_DEBUG:
                                    print(f"\rProcessed: {len(all_listings_data)} listings (SRP Playwright Fallback)", end='')
                            else:
                                logger.warning(f"Monitor: Playwright SRP fallback for ad_id='{ad_id}' (URL: {vip_url}) completed but extracted NO data.")
                        except (PlaywrightTimeoutErrorAlias, PlaywrightNavigationErrorAlias) as pw_scrape_err:
                            logger.error(f"Monitor: Playwright SRP fallback for ad_id='{ad_id}' (URL: {vip_url}) FAILED with specific error: {pw_scrape_err}")
                        except Exception as pw_fallback_err:
                            logger.error(f"Monitor: Playwright SRP fallback for ad_id='{ad_id}' (URL: {vip_url}) FAILED with general error: {pw_fallback_err}", exc_info=True)
                    else:
                        # Log why fallback wasn't attempted
                        reason = ""
                        if not ad_id: # This means ad_id was not found by Playwright locators NOR by raw HTML parsing
                            reason = "ad_id was not retrieved by any method"
                            logger.warning(f"SRP Timeout for index {i} and {reason}. Skipping this item. URL: {current_url}")
                            continue # Skip to the next item
                        elif ad_id in scraped_ad_ids: # This means ad_id was found (either by Playwright or raw HTML) but already processed
                            reason = f"ad_id {ad_id} was retrieved but already scraped/queued"
                            logger.warning(f"SRP Timeout for index {i}, {reason}. Skipping Playwright fallback. URL: {current_url}")
                            # No continue here, might still save SearchResultList HTML if SAVE_HTML_DEBUG is true

                        # <<< START NEW CODE TO SAVE SearchResultList HTML >>>
                        if SAVE_HTML_DEBUG:
                            try:
                                debug_html_dir = "debug_html"
                                os.makedirs(debug_html_dir, exist_ok=True) # Ensure dir exists

                                # Check if a resultlist file for this index already exists
                                existing_files_pattern = f"resultlist_{i}_*.html"
                                existing_files = glob.glob(os.path.join(debug_html_dir, existing_files_pattern))

                                if existing_files:
                                    logger.info(f"SearchResultList HTML for index {i} already exists (e.g., {existing_files[0]}). Skipping save.")
                                else:
                                    logger.info(f"Attempting to save SearchResultList HTML for SRP Timeout index {i} as fallback was not attempted and no existing file found.")
                                    search_result_list_locator = page.locator('div[data-testid="SearchResultList"]')
                                    if await search_result_list_locator.count() > 0:
                                        search_result_list_html = await search_result_list_locator.first.evaluate("element => element.outerHTML")
                                        
                                        timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                                        filename = f"resultlist_{i}_{timestamp_str}.html"
                                        filepath = os.path.join(debug_html_dir, filename)
                                        
                                        with open(filepath, 'w', encoding='utf-8') as f_debug:
                                            f_debug.write(search_result_list_html)
                                        logger.info(f"Saved SearchResultList HTML to {filepath} for SRP Timeout index {i}.")
                                    else:
                                        logger.warning(f"Could not find div[data-testid=\"SearchResultList\"] to save for SRP Timeout index {i}.")
                            except Exception as e_debug_save:
                                logger.error(f"Error saving SearchResultList HTML for SRP Timeout index {i}: {e_debug_save}", exc_info=True)
                        # <<< END NEW CODE TO SAVE SearchResultList HTML >>>

                        # If HTML wasn't logged above (because the try block failed), log container now
                        if not raw_element_html:
                            try:
                                # Try a potential container selector (adjust if needed based on actual page structure)
                                container_locator = page.locator('div[data-testid*="Results-"]') # Example selector
                                if await container_locator.count() > 0:
                                    raw_container_html = await container_locator.first.evaluate("element => element.outerHTML", timeout=2000) # Longer timeout for container
                                    if raw_container_html:
                                         logger.warning(f"Raw HTML for listings container (index {i} failed, reason: {reason}):\n---\n{raw_container_html[:5000]}...\n---") # Log truncated container HTML
                                    else:
                                         logger.warning(f"Could not extract raw HTML for listings container (index {i} failed, reason: {reason}).")
                                else:
                                    logger.warning(f"Could not find listings container element (index {i} failed, reason: {reason}).")
                            except Exception as container_html_err:
                                logger.warning(f"Could not get raw HTML for listings container (index {i} failed, reason: {reason}) due to error: {container_html_err}")
                    # --- End Playwright Fallback ---

                except Exception as e:
                    logger.error(f"Error processing potential listing index {i} in monitor: {e}", exc_info=False) # Keep error

            # Check exit condition *after* processing found items for this cycle
            if stop_event.is_set() and queue.empty():
                # logger.info("Stop event set and queue is empty. Exiting monitor task.") # Suppressed log
                break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True) # Keep error
            # Add a small delay even after error before next check
            await asyncio.sleep(0.5)

        # Check stop condition again before sleeping for the interval
        if stop_event.is_set() and queue.empty():
            # logger.info("Stop event set and queue empty after processing cycle. Exiting monitor task.") # Suppressed log
            break

        await asyncio.sleep(MONITOR_INTERVAL)

    # logger.info(f"Monitoring task finished. Sending {worker_count} stop signals to workers.") # Suppressed log
    # Signal workers to stop using the correct count
    for _ in range(worker_count):
        try:
            # Use put_nowait or handle QueueFull if necessary, though unlikely here
            await queue.put(None)
        except Exception as e:
            logger.error(f"Error putting None signal onto queue: {e}") # Keep error


# --- VIP Page Extraction Logic ---
# Removed process_single_listing_sync as worker is now fully async

# Worker task using KijijiSingleScrape async API calls
async def worker_task(client: httpx.AsyncClient, queue: asyncio.Queue, all_listings_data: list, failed_log_path="failed_links.txt"):
    """
    Fetches detailed listing data for an ad_id using the async Kijiji API function,
     extracts relevant details, and adds to list. Uses a shared httpx client.
     """
    worker_name = asyncio.current_task().get_name()
    # logger.info(f"Starting worker task {worker_name}...") # Suppressed log

    while True:
        item = await queue.get()
        if item is None:
            # logger.info(f"Worker {worker_name} received stop signal.") # Suppressed log
            queue.task_done()
            break

        ad_id, title_from_srp = item # Now we also get the title from SRP for logging
        if not FAILED_SCRAPE_DEBUG:
            logger.info(f"Worker {worker_name}: Dequeued ad_id='{ad_id}', title_from_srp='{title_from_srp}'. Starting VIP processing.")

        try:
            if not FAILED_SCRAPE_DEBUG:
                logger.info(f"Worker {worker_name}: Attempting Kijiji API scrape for ad_id='{ad_id}'.")
            # Call the ASYNC single page scraper directly
            raw_json_data = await scrape_kijiji_single_page_async(ad_id, client)

            if raw_json_data:
                if not FAILED_SCRAPE_DEBUG:
                    logger.info(f"Worker {worker_name}: Successfully fetched API data for ad_id='{ad_id}'. Attempting extraction.")
                # Extraction is still synchronous, but fast enough not to block significantly
                extracted_data = extract_relevant_kijiji_data(raw_json_data)

                if extracted_data:
                    vip_url = urljoin(BASE_URL, f"/vip/{ad_id}/")
                    extracted_data['ad_id'] = ad_id
                    extracted_data['url'] = vip_url
                    extracted_data['source'] = 'kijiji_autos'
                    if not FAILED_SCRAPE_DEBUG:
                        logger.info(f"Worker {worker_name}: Successfully extracted data for ad_id='{ad_id}'. Title: '{extracted_data.get('title', 'N/A')}'. Adding to results.")
                    all_listings_data.append(extracted_data)
                    # Print progress update (keep this for concise feedback)
                    if not FAILED_SCRAPE_DEBUG:
                        print(f"\rProcessed: {len(all_listings_data)} listings", end='')
                else:
                    logger.warning(f"Worker {worker_name}: API data fetched for ad_id='{ad_id}', but extraction yielded no data.")
            else: # Logging handled within scrape_kijiji_single_page_async for specific failures
                logger.warning(f"Worker {worker_name}: Failed to fetch API data for ad_id='{ad_id}' (scrape_kijiji_single_page_async returned None/empty).")

        except (ScrapingTimeoutError, ScrapingConnectionError) as e: # Catch specific errors from KijijiSingleScrape
            error_type = "TIMEOUT" if isinstance(e, ScrapingTimeoutError) else "CONNECTION_ERROR"
            vip_url = urljoin(BASE_URL, f"/vip/{ad_id}/") # Construct URL for logging
            logger.warning(f"Worker {worker_name}: Kijiji API {error_type} for ad_id='{ad_id}'. Error: {e}. Saving link to {failed_log_path}.")
            try:
                # Use standard file I/O for simplicity
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                log_message = f"[{timestamp}] API {error_type} - Ad ID {ad_id}: URL: {vip_url} | Error: {e}"
                absolute_log_path = os.path.abspath(failed_log_path)
                # logger.info(f"Worker {worker_name} attempting to write verbose API {error_type} log to {absolute_log_path}") # Suppressed log
                with open(failed_log_path, 'a', encoding='utf-8') as f_log:
                    f_log.write(f"{log_message}\n")
                # logger.info(f"Worker {worker_name} successfully wrote verbose API {error_type} log to {absolute_log_path}.") # Suppressed log
            except Exception as log_err:
                logger.error(f"Worker {worker_name} failed to write verbose API failure log ({error_type}) for {vip_url} to {absolute_log_path}: {log_err}") # Keep error

            # --- Fallback to Playwright Scraper ---
            logger.info(f"Worker {worker_name}: Kijiji API failed for ad_id='{ad_id}'. Attempting Playwright fallback for URL: {vip_url}.")
            try:
                playwright_data = await scrape_kijiji_single_page_playwright(vip_url)
                if playwright_data: # Check if data was successfully extracted
                    if not FAILED_SCRAPE_DEBUG:
                        logger.info(f"Worker {worker_name}: Playwright fallback for ad_id='{ad_id}' (URL: {vip_url}) SUCCEEDED. Data extracted.")
                    # Add necessary fields similar to the primary method
                    playwright_data['ad_id'] = ad_id
                    playwright_data['url'] = vip_url
                    playwright_data['source'] = 'kijiji_autos_playwright_api_fallback' # More specific source
                    all_listings_data.append(playwright_data)
                    # Print progress update
                    if not FAILED_SCRAPE_DEBUG:
                        print(f"\rProcessed: {len(all_listings_data)} listings (Playwright API Fallback)", end='')
                else:
                    logger.warning(f"Worker {worker_name}: Playwright fallback for ad_id='{ad_id}' (URL: {vip_url}) completed but extracted NO data.")
            except (PlaywrightTimeoutErrorAlias, PlaywrightNavigationErrorAlias) as pw_scrape_err:
                logger.error(f"Worker {worker_name}: Playwright fallback for ad_id='{ad_id}' (URL: {vip_url}) FAILED with specific error: {pw_scrape_err}")
            except Exception as pw_fallback_err:
                logger.error(f"Worker {worker_name}: Playwright fallback for ad_id='{ad_id}' (URL: {vip_url}) FAILED with general error: {pw_fallback_err}", exc_info=True)
            # --- End Fallback ---
            # Do not re-raise, allow worker to continue with next item

        except Exception as e:
            # Catch any other unexpected errors during the primary async call or extraction
            vip_url = urljoin(BASE_URL, f"/vip/{ad_id}/") # Construct URL for logging
            logger.error(f"Worker {worker_name}: UNEXPECTED error processing ad_id='{ad_id}' (URL: {vip_url}): {e}", exc_info=True)
            # Do not re-raise, allow worker to continue
        finally:
            queue.task_done()

    # logger.info(f"Worker task {worker_name} finished.") # Suppressed log


 # --- Main Async Scraping Function ---

async def scrape_kijiji_autos_async(search_params, worker_count, max_pages=1): # Added worker_count parameter
    """
    Scrapes Kijiji Autos asynchronously, overlapping scrolling and processing.
    """
    if max_pages > 1:
        # logger.warning("Pagination (max_pages > 1) is not supported in this async version.") # Suppressed
        max_pages = 1

    debug_html_path = None
    items_per_scroll_snapshot = None
    cross_scroll_item_tracker = None

    if JSON_DEBUG:
        # --- Timestamped Debug Directory (only if JSON_DEBUG is True) ---
        current_run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_html_base_path = "debug_html"
        os.makedirs(debug_html_base_path, exist_ok=True)
        debug_html_path = os.path.join(debug_html_base_path, current_run_timestamp)
        os.makedirs(debug_html_path, exist_ok=True)
        logger.info(f"JSON_DEBUG enabled: Debug HTML and item data will be saved in: {debug_html_path}")
        # --- End Timestamped Debug Directory ---

        # --- Data structures for new scroll analysis (only if JSON_DEBUG is True) ---
        items_per_scroll_snapshot = []
        cross_scroll_item_tracker = {}
        # ---

    all_listings_data = []
    scraped_ad_ids = set()
    search_url = construct_search_url(search_params)
    if not search_url:
        logger.error("Could not construct search URL.") # Keep error
        return []

    # logger.info("Launching Playwright browser (async)...") # Suppressed log

    # --- Load Proxy Configuration ---
    # Use the imported function to get the proxy dict
    proxy_config_dict = get_proxy_from_file()
    # Extract the HTTPS URL string for httpx, default to None
    httpx_proxy_url = None
    if isinstance(proxy_config_dict, dict):
        httpx_proxy_url = proxy_config_dict.get('https') # Or 'http' if needed
        if httpx_proxy_url:
            if not FAILED_SCRAPE_DEBUG:
                logger.info(f"Using httpx proxy: {httpx_proxy_url}")
        else:
            if not FAILED_SCRAPE_DEBUG:
                logger.info("HTTPS proxy URL not found in config dict for httpx.")
    else:
        if not FAILED_SCRAPE_DEBUG:
            logger.info("Proxy config file not found or invalid format, httpx will run without proxy.")
    # --- End Proxy Configuration ---

    # --- Log the actual proxy being passed to httpx ---
    if not FAILED_SCRAPE_DEBUG:
        logger.info(f"Attempting to initialize httpx.AsyncClient with proxy setting: {httpx_proxy_url}")
    # ---

    # --- Setup Playwright ---
    playwright_proxy_settings = None # Separate proxy settings for Playwright if needed
    # (Could reuse httpx_proxies if format is compatible or adapt)
    # For now, assume Playwright runs without proxy unless specifically configured here
    # ... (existing Playwright proxy setup logic could be added here if needed) ...

    browser = None
    # Create httpx client outside the Playwright context, but within the main async function scope
    # Pass the extracted URL string (or None) to the 'proxy' argument
    async with httpx.AsyncClient(proxy=httpx_proxy_url, http2=True, follow_redirects=True, timeout=30.0) as client:
        browser = None # Define browser outside try block to ensure it's available in finally
        try:
            async with async_playwright() as p:
                launch_options = {"headless": True}
                if playwright_proxy_settings: # Use separate Playwright proxy if defined
                    launch_options["proxy"] = playwright_proxy_settings

                browser = await p.chromium.launch(**launch_options)
                if not browser:
                    logger.error("Failed to launch browser.") # Keep error
                    return []
                # logger.info("Browser launched successfully.") # Suppressed log

                page = await browser.new_page()
                if not page:
                    logger.error("Failed to create a new page.") # Keep error
                    await browser.close()
                    return []
                # logger.info("New page created successfully.") # Suppressed log

                # --- Request Interception ---
                async def intercept_request(route):
                    """Blocks non-essential resources."""
                    resource_type = route.request.resource_type
                    if resource_type in ["image", "media", "font"]:
                        # logger.debug(f"Blocking request for {resource_type}: {route.request.url}") # Suppress debug log
                        await route.abort()
                    # Add more domain-based blocking here if needed later
                    # elif "google-analytics.com" in route.request.url or "doubleclick.net" in route.request.url:
                    #     await route.abort()
                    else:
                        await route.continue_()

                await page.route("**/*", intercept_request)
                # logger.info("Request interception enabled (blocking images, media, fonts).") # Suppressed log
                # --- End Request Interception ---

                page.set_default_timeout(PAGE_TIMEOUT)
                # logger.info(f"Page timeout set to {PAGE_TIMEOUT}ms.") # Suppressed log

                # logger.info(f"Navigating to initial URL: {search_url}") # Suppressed log
                try:
                    response = await page.goto(search_url, wait_until='domcontentloaded')
                    if not response:
                        logger.warning("Navigation call (page.goto) returned None.") # Keep warning
                        return []
                    # logger.info(f"Navigation successful. Status: {response.status}") # Suppressed log
                except PlaywrightTimeoutError as nav_timeout:
                    logger.error(f"Timeout during page.goto navigation: {nav_timeout}", exc_info=True) # Keep error
                    return []
                except Exception as nav_err:
                    logger.error(f"Error during page.goto navigation: {nav_err}", exc_info=True) # Keep error
                    return []

                # --- Setup Async Components ---
                queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
                stop_event = asyncio.Event()

                # --- Start Tasks ---
                # Pass new structures to scroll_task
                scroll_future = asyncio.create_task(scroll_task(page, stop_event, debug_html_path, items_per_scroll_snapshot, cross_scroll_item_tracker))

                # Define log filenames based on search params
                make_model_suffix = f"{search_params.get('make', 'unknown')}_{search_params.get('model', 'unknown')}"
                failed_log_filename = f"failed_api_links_{make_model_suffix}.txt"
                srp_failed_log_filename = f"failed_srp_links_{make_model_suffix}.txt"

                # Pass worker_count and SRP log path to the monitor task
                monitor_future = asyncio.create_task(monitor_and_queue_task(page, queue, scraped_ad_ids, all_listings_data, stop_event, worker_count, srp_failed_log_filename))

                # Worker tasks now need the shared httpx client and the API failure log path
                worker_futures = []
                for i in range(worker_count):
                    # Pass the specific API log file path to each worker
                    worker_futures.append(asyncio.create_task(worker_task(client, queue, all_listings_data, failed_log_filename), name=f"Worker-{i+1}"))

                # --- Wait for Tasks ---
                await asyncio.gather(scroll_future, monitor_future)
                # logger.info("Scrolling and Monitoring tasks have signaled completion.") # Suppressed log

                # logger.info("Waiting for queue processing to complete...") # Suppressed log
                await queue.join()
                # logger.info("Queue processing complete.") # Suppressed log

                # logger.info("Waiting for worker tasks to finish...") # Suppressed log
                await asyncio.gather(*worker_futures) # Wait for workers
                # logger.info("All worker tasks finished.") # Suppressed log

                # logger.info("Closing Playwright browser.") # Suppressed log
                await browser.close()
                browser = None # Indicate browser is closed

        except PlaywrightTimeoutError:
            logger.error(f"Playwright timed out during operation. Timeout: {PAGE_TIMEOUT}ms") # Keep error
        except Exception as e:
            logger.error(f"An error occurred during Playwright operation: {e}", exc_info=True) # Keep error
        finally:
            if browser and browser.is_connected():
                logger.warning("Closing browser in finally block due to earlier error.") # Keep warning
                try:
                    await browser.close()
                except Exception as close_err:
                    logger.error(f"Error closing browser in finally block: {close_err}") # Keep error

    if JSON_DEBUG and cross_scroll_item_tracker is not None and debug_html_path is not None:
        # --- Process cross_scroll_item_tracker for duplicates (only if JSON_DEBUG is True) ---
        duplicate_items_report = []
        for item_id, data in cross_scroll_item_tracker.items():
            if len(data['scroll_numbers']) >= 2:
                duplicate_items_report.append({
                    "id": item_id,
                    "link": data['link'],
                    "seen_in_scrolls": sorted(list(data['scroll_numbers']))
                })

        if duplicate_items_report:
            logger.info("\n--- Duplicate Items Found Across Scrolls (JSON_DEBUG) ---")
            # Pretty print to console
            print(json.dumps(duplicate_items_report, indent=2))
            # Save to JSON file
            duplicates_file_path = os.path.join(debug_html_path, "duplicate_items_summary.json")
            try:
                with open(duplicates_file_path, 'w', encoding='utf-8') as f:
                    json.dump(duplicate_items_report, f, indent=2, ensure_ascii=False)
                logger.info(f"Duplicate items summary saved to {duplicates_file_path}")
            except Exception as e:
                logger.error(f"Failed to save duplicate items summary: {e}")
        else:
            logger.info("No duplicate items found across multiple scrolls (JSON_DEBUG).")
        # --- End Duplicate Processing ---
    elif JSON_DEBUG:
        logger.info("JSON_DEBUG is True, but cross_scroll_item_tracker or debug_html_path was not properly initialized. Skipping duplicate report.")


    if not FAILED_SCRAPE_DEBUG:
        logger.info(f"Finished scraping. Total listings found: {len(all_listings_data)}")
    elif len(all_listings_data) == 0 : # Still log if FAILED_SCRAPE_DEBUG is true but found 0, as that's a notable outcome
        logger.info(f"Finished scraping. Total listings found: {len(all_listings_data)}")
    return all_listings_data

 # --- Main Execution Block ---
async def main():
    """Main async entry point for benchmarking worker counts."""
    # Set overall logging level
    logging.getLogger().setLevel(logging.INFO) # Keep this for general script info

    # Adjust httpx logging level based on FAILED_SCRAPE_DEBUG
    if FAILED_SCRAPE_DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        # Also suppress playwright info logs if in debug mode for failures
        logging.getLogger("playwright").setLevel(logging.WARNING)
    else:
        logging.getLogger("httpx").setLevel(logging.INFO) # Or logging.DEBUG for more verbosity
        logging.getLogger("playwright").setLevel(logging.INFO) # Show Playwright info if not debugging failures

    benchmark_results = [] # List to store results

    base_params = {
        'make': 'BMW',
        'model': '3 Series',
        'price_min': 15000,
        'price_max': 40000,
        'mileage_min': 50000,
        'mileage_max': 150000,
    }

    worker_counts_to_test = [20]
    print("--- Starting Benchmark ---")
    for count in worker_counts_to_test:
        print(f"\nTesting with {count} workers...")
        start_time = time.time()
        # Call the async scraping function, passing the current worker count
        # Call the async scraping function, passing the current worker count
        # Get the results list back
        listings_found = await scrape_kijiji_autos_async(base_params, count, max_pages=1)
        end_time = time.time()
        duration = end_time - start_time
        num_listings = len(listings_found)
        print(f"  Workers: {count}, Duration: {duration:.2f} seconds, Listings Found: {num_listings}")
        benchmark_results.append({
            "workers": count,
            "duration": duration,
            "listings": num_listings
        })

    # Add a newline after the benchmark finishes
    print()
    print("\n--- Benchmark Complete ---")

    # --- Leaderboard ---
    # Sort results by duration (fastest first)
    benchmark_results.sort(key=lambda x: x["duration"])

    print("\n--- Top 3 Fastest Worker Settings ---")
    print("Rank | Workers | Duration (s) | Listings Found")
    print("-----|---------|--------------|----------------")
    for i, result in enumerate(benchmark_results[:3]):
        rank = i + 1
        workers = result['workers']
        duration = result['duration']
        listings = result['listings']
        print(f"{rank:<4} | {workers:<7} | {duration:<12.2f} | {listings:<14}")

    # Restore logging level if needed
    # logging.getLogger().setLevel(logging.INFO) # Or WARNING


if __name__ == "__main__":
    asyncio.run(main())
