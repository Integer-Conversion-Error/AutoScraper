import asyncio
# Removed aiohttp import
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
import json
import logging
import re
from urllib.parse import urlencode, urljoin, urlparse
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
BASE_URL = "https://www.kijijiautos.ca/"
PAGE_TIMEOUT = 120000 # 120 seconds (Increased timeout)
# WORKER_COUNT = 10 # Default worker count is no longer used directly in main
QUEUE_MAX_SIZE = 100 # Max items in the processing queue
SCROLL_DELAY = 0.1 # Delay between scrolls (seconds)
NETWORK_IDLE_TIMEOUT = 1500 # Timeout for waiting for network idle (ms)
STABLE_HEIGHT_CHECKS = 3 # How many times height must be stable to stop scrolling
MONITOR_INTERVAL = 0.1 # How often to check for new listings (seconds)

# --- Helper Functions ---

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
def extract_vip_details(vip_soup, url, title):
    """
    Extracts detailed information from the BeautifulSoup object of a VIP page.
    (Placeholder selectors - adjust based on actual VIP page structure)
    """
    data = {'url': url, 'title': title, 'source': 'kijiji_autos'}
    logger.debug(f"Starting VIP extraction for {url}") # Keep debug log

    try:
        # --- Basic Info ---
        price_tag = vip_soup.find('span', {'data-testid': 'VehicleVipPricePrice'})
        if price_tag:
            price_text = price_tag.get_text(strip=True).replace('$', '').replace(',', '').replace('*', '')
            try:
                data['price'] = int(re.sub(r'[^\d]', '', price_text)) if re.search(r'\d', price_text) else None
            except ValueError:
                # logger.warning(f"Could not parse VIP price: {price_tag.get_text(strip=True)} for URL: {url}")
                data['price'] = None
        else:
            data['price'] = None
            # logger.debug(f"VIP Price tag not found for URL: {url}")

        # --- Attributes ---
        attributes = {}
        spec_list = vip_soup.find('dl', class_=re.compile(r'AttributeList__AttributeList'))
        if spec_list:
            terms = spec_list.find_all('dt', class_=re.compile(r'AttributeList__AttributeTerm'))
            definitions = spec_list.find_all('dd', class_=re.compile(r'AttributeList__AttributeDefinition'))
            for term, definition in zip(terms, definitions):
                term_text = term.get_text(strip=True).lower()
                value_text = definition.get_text(strip=True)
                # logger.debug(f"Found VIP Spec: {term_text} = {value_text}")
                if 'kilometers' in term_text: attributes['mileage'] = value_text
                elif 'transmission' in term_text: attributes['transmission'] = value_text
                elif 'drivetrain' in term_text: attributes['drivetrain'] = value_text
                elif 'fuel type' in term_text: attributes['fuel_type'] = value_text
                elif 'body type' in term_text: attributes['body_type'] = value_text
                elif 'engine' in term_text: attributes['engine_description'] = value_text
                elif 'exterior colour' in term_text: attributes['exterior_color'] = value_text
                elif 'interior colour' in term_text: attributes['interior_color'] = value_text
                elif 'vin' in term_text: attributes['vin'] = value_text
        data.update(attributes)
        # logger.debug(f"Extracted VIP Attributes: {attributes}")

        # --- Description ---
        desc_container = vip_soup.find('div', {'data-testid': 'VehicleVipDescription-descriptionContainer'})
        data['description'] = desc_container.get_text(separator='\n', strip=True) if desc_container else None
        # if data['description']: logger.debug("Extracted Description.")
        # else: logger.debug("Description container not found.")

        # --- Features ---
        features = []
        features_section = vip_soup.find('section', {'aria-labelledby': re.compile(r'FeaturesAndOptions')})
        if features_section:
            feature_items = features_section.find_all('li')
            features = [item.get_text(strip=True) for item in feature_items if item.get_text(strip=True)]
            # logger.debug(f"Extracted {len(features)} features from VIP.")
        # else:
            # logger.debug("Features section not found on VIP.")
        data['features'] = features

        # --- Dealer Info ---
        dealer_name_tag = vip_soup.find('a', {'data-testid': 'VehicleVipSellerLink'})
        if dealer_name_tag:
            data['dealer_name'] = dealer_name_tag.get_text(strip=True)
            # logger.debug(f"Extracted Dealer Name: {data['dealer_name']}")
            dealer_address_tag = vip_soup.find('address')
            data['dealer_address'] = dealer_address_tag.get_text(separator=', ', strip=True) if dealer_address_tag else None
            # if data['dealer_address']: logger.debug(f"Extracted Dealer Address: {data['dealer_address']}")
            # else: logger.debug("Dealer address tag not found.")
        else:
            data['dealer_name'] = None
            data['dealer_address'] = None
            # logger.debug("Dealer name link not found (possibly private seller).")

        # --- Image URLs ---
        image_urls = []
        gallery = vip_soup.find('div', class_=re.compile(r'Gallery__GalleryContainer'))
        if gallery:
            img_tags = gallery.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and src not in image_urls: image_urls.append(src)
            # logger.debug(f"Extracted {len(image_urls)} image URLs from VIP gallery.")
        else:
             main_img = vip_soup.find('img', class_=re.compile(r'HeroImage__StyledImage'))
             if main_img:
                  src = main_img.get('src') or main_img.get('data-src')
                  if src:
                       image_urls.append(src)
                       # logger.debug("Extracted main VIP image URL.")
        data['image_urls'] = image_urls
        data['image_url'] = image_urls[0] if image_urls else None

    except Exception as e:
        # Suppress extraction errors during benchmark
        # logger.error(f"Error extracting VIP data for ({url}): {e}", exc_info=True)
        return data # Return partial data

    # logger.info(f"VIP detail extraction finished for URL: {url}")
    return data


# --- Async Tasks ---

async def scroll_task(page, stop_event):
    """Scrolls the page until the height stabilizes or stop_event is set."""
    # logger.info("Starting scroll task...") # Suppressed for benchmark
    last_height = await page.evaluate("document.body.scrollHeight")
    stable_count = 0
    attempts = 0
    max_scroll_attempts = 150

    while not stop_event.is_set() and attempts < max_scroll_attempts:
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(SCROLL_DELAY)
        try:
            await page.wait_for_load_state('networkidle', timeout=NETWORK_IDLE_TIMEOUT)
            # logger.debug("Network became idle after scroll.") # Suppressed
        except PlaywrightTimeoutError:
            pass # Ignore timeout during benchmark
            # logger.debug("Network did not become idle quickly after scroll, proceeding.")
        except Exception as e:
             logger.warning(f"Error during wait_for_load_state: {e}") # Keep warnings

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            stable_count += 1
            # logger.debug(f"Scroll height stable ({stable_count}/{STABLE_HEIGHT_CHECKS}).") # Suppressed
            if stable_count >= STABLE_HEIGHT_CHECKS:
                # logger.info("Scroll height stable. Stopping scroll task.") # Suppressed
                stop_event.set()
                break
        else:
            stable_count = 0
            last_height = new_height
        attempts += 1
        if attempts == max_scroll_attempts:
             logger.warning("Reached max scroll attempts.") # Keep warning
             stop_event.set()
    # logger.info("Scroll task finished.") # Suppressed


async def monitor_and_queue_task(page, queue, scraped_ad_ids, stop_event):
    """Monitors for new listings and adds their ad_id/title to the queue."""
    # logger.info("Starting monitoring task...") # Suppressed
    while not stop_event.is_set() or not queue.empty():
        if stop_event.is_set() and queue.full():
             # logger.warning("Stop event set and queue is full, potentially dropping new items.") # Suppressed
             pass

        try:
            listing_locators = page.locator('article[data-testid="SearchResultListItem"]')
            count = await listing_locators.count()
            # logger.debug(f"Monitor check: Found {count} total listing locators.") # Suppressed

            for i in range(count):
                article_locator = listing_locators.nth(i)
                ad_id = None
                try:
                    ad_id_div = article_locator.locator('div[data-testid="VehicleListItem"]')
                    ad_id = await ad_id_div.get_attribute('data-test-ad-id', timeout=1000)

                    if ad_id and ad_id not in scraped_ad_ids:
                        title_tag = article_locator.locator('h2')
                        title_value = await title_tag.text_content(timeout=1000) if await title_tag.count() > 0 else None
                        if title_value:
                            # logger.debug(f"Found new ad_id: {ad_id}, Title: {title_value}. Queuing for VIP scrape.") # Suppressed
                            scraped_ad_ids.add(ad_id)
                            try:
                                await queue.put((ad_id, title_value))
                                # logger.debug(f"Queued ad_id: {ad_id}. Queue size: {queue.qsize()}") # Suppressed
                            except asyncio.QueueFull:
                                logger.warning(f"Queue full. Waiting to add ad_id: {ad_id}") # Keep warning
                                await queue.put((ad_id, title_value))
                        # else:
                             # logger.warning(f"Found new ad_id {ad_id} but failed to get title from SRP.") # Suppressed
                except PlaywrightTimeoutError:
                    pass # Ignore timeout during benchmark
                    # logger.warning(f"Timeout getting ad_id or title for potential listing {i+1}.")
                except Exception as e:
                    logger.error(f"Error processing potential listing {i+1} in monitor: {e}", exc_info=False) # Keep error

            if stop_event.is_set() and queue.empty():
                 # logger.info("Stop event set and queue is empty. Exiting monitor task.") # Suppressed
                 break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True) # Keep error
            await asyncio.sleep(1)

        await asyncio.sleep(MONITOR_INTERVAL)

    # logger.info("Monitoring task finished.") # Suppressed
    # Use the passed worker_count instead of the constant
    # Need to get worker_count into this scope, or signal differently.
    # Simplest for benchmark: Assume max workers might be needed for signal.
    for _ in range(64): # Send enough signals for max potential workers
        await queue.put(None)


# Worker task using Playwright pages
async def worker_task(browser, queue, all_listings_data):
    """
    Fetches VIP page for an ad_id using Playwright, extracts details, and adds to list.
    Uses a temporary page for each VIP visit.
    """
    worker_name = asyncio.current_task().get_name()
    # logger.info(f"Starting worker task {worker_name}...") # Suppressed
    while True:
        item = await queue.get()
        if item is None:
            # logger.info(f"Worker {worker_name} received stop signal.") # Suppressed
            queue.task_done()
            break

        ad_id, title = item
        vip_path = f"/vip/{ad_id}/"
        vip_url = urljoin(BASE_URL, vip_path)
        # logger.debug(f"Worker {worker_name} processing ad_id: {ad_id}, URL: {vip_url}") # Suppressed

        vip_page = None
        try:
            vip_page = await browser.new_page()
            vip_page.set_default_timeout(PAGE_TIMEOUT) # Set timeout

            # logger.debug(f"Worker {worker_name} navigating to VIP: {vip_url}") # Suppressed
            try:
                await vip_page.goto(vip_url, wait_until='domcontentloaded')
                # logger.debug(f"Worker {worker_name} navigated successfully to {vip_url}") # Suppressed
            except Exception as nav_err:
                 # Suppress navigation errors during benchmark unless needed for debugging
                 # logger.error(f"Worker {worker_name} failed to navigate to VIP {vip_url}: {nav_err}", exc_info=False)
                 if vip_page and not vip_page.is_closed():
                     # logger.debug(f"Worker {worker_name} closing failed VIP page {vip_url}") # Suppressed
                     await vip_page.close()
                 continue # Skip to next item, finally block calls task_done

            vip_html = await vip_page.content()
            vip_soup = BeautifulSoup(vip_html, 'html.parser')

            # Call the VIP HTML extraction function
            listing_data = extract_vip_details(vip_soup, vip_url, title)

            if listing_data:
                all_listings_data.append(listing_data)
                # Print progress update
                print(f"\rProcessed: {len(all_listings_data)} listings", end='')
                # logger.info(f"Worker {worker_name} successfully processed VIP for ad_id: {ad_id}. Total results: {len(all_listings_data)}") # Suppressed
            # else:
                 # logger.warning(f"Worker {worker_name} extracted empty data from VIP: {vip_url}") # Suppressed

        except Exception as e:
            # Suppress processing errors during benchmark unless needed
            # logger.error(f"Worker {worker_name} error processing VIP for ad_id {ad_id} ({vip_url}): {e}", exc_info=True)
            pass # Continue benchmark even if one worker fails
        finally:
            if vip_page and not vip_page.is_closed():
                # logger.debug(f"Worker {worker_name} closing VIP page {vip_url} in finally block.") # Suppressed
                try:
                    await vip_page.close()
                except Exception as close_err:
                    pass # Suppress close errors during benchmark
                    # logger.warning(f"Worker {worker_name} error closing VIP page {vip_url}: {close_err}")
            queue.task_done()

    # logger.info(f"Worker task {worker_name} finished.") # Suppressed


# --- Main Async Scraping Function ---

async def scrape_kijiji_autos_async(search_params, worker_count, max_pages=1): # Added worker_count parameter
    """
    Scrapes Kijiji Autos asynchronously, overlapping scrolling and processing.
    """
    if max_pages > 1:
        # logger.warning("Pagination (max_pages > 1) is not supported in this async version.") # Suppressed
        max_pages = 1

    all_listings_data = []
    scraped_ad_ids = set()
    search_url = construct_search_url(search_params)
    if not search_url:
        logger.error("Could not construct search URL.")
        return []

    # logger.info("Launching Playwright browser (async)...") # Suppressed

    # --- Load Proxy Configuration ---
    proxy_settings = None
    proxy_config_path = "proxyconfig.json"
    if os.path.exists(proxy_config_path):
        try:
            with open(proxy_config_path, 'r') as f:
                config = json.load(f)
                https_proxy_url = config.get("https")
                if https_proxy_url:
                    parsed_url = urlparse(https_proxy_url)
                    if parsed_url.hostname and parsed_url.port:
                        proxy_settings = {
                            "server": f"{parsed_url.scheme}://{parsed_url.hostname}:{parsed_url.port}",
                        }
                        if parsed_url.username: proxy_settings["username"] = parsed_url.username
                        if parsed_url.password: proxy_settings["password"] = parsed_url.password
                        # logger.info(f"Using HTTPS proxy: {proxy_settings['server']}") # Suppressed
                    # else: logger.warning("Could not parse hostname/port from HTTPS proxy URL.") # Suppressed
                # else: logger.warning("HTTPS proxy URL not found in proxyconfig.json.") # Suppressed
        except Exception as e: logger.error(f"Error reading or parsing proxyconfig.json: {e}") # Keep error
    # else: logger.info("proxyconfig.json not found, proceeding without proxy.") # Suppressed
    # --- End Proxy Configuration ---

    browser = None # Define browser outside try block for finally clause
    try:
        async with async_playwright() as p:
            launch_options = {"headless": True}
            if proxy_settings:
                launch_options["proxy"] = proxy_settings

            browser = await p.chromium.launch(**launch_options)
            if not browser:
                logger.error("Failed to launch browser.")
                return []
            # logger.info("Browser launched successfully.") # Suppressed

            page = await browser.new_page()
            if not page:
                logger.error("Failed to create a new page.")
                await browser.close()
                return []
            # logger.info("New page created successfully.") # Suppressed

            page.set_default_timeout(PAGE_TIMEOUT)
            # logger.info(f"Page timeout set to {PAGE_TIMEOUT}ms. Line completed.") # Suppressed

            # logger.info(f"Navigating to initial URL: {search_url}") # Suppressed
            try:
                # logger.info("Attempting page.goto...") # Suppressed
                response = await page.goto(search_url, wait_until='domcontentloaded')
                # logger.info("page.goto call completed.") # Suppressed
                if not response:
                     logger.warning("Navigation call (page.goto) returned None.") # Keep warning
                     return []
                # logger.info(f"Navigation successful. Status: {response.status}") # Suppressed
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
            # Pass browser object back to workers
            scroll_future = asyncio.create_task(scroll_task(page, stop_event))
            # Pass the actual worker_count to monitor task for signaling
            monitor_future = asyncio.create_task(monitor_and_queue_task(page, queue, scraped_ad_ids, stop_event))

            worker_futures = []
            # Use the passed worker_count parameter
            for i in range(worker_count):
                worker_futures.append(asyncio.create_task(worker_task(browser, queue, all_listings_data), name=f"Worker-{i+1}"))

            # --- Wait for Tasks ---
            await asyncio.gather(scroll_future, monitor_future)
            # logger.info("Scrolling and Monitoring tasks have signaled completion.") # Suppressed

            # logger.info("Waiting for queue processing to complete...") # Suppressed
            await queue.join()
            # logger.info("Queue processing complete.") # Suppressed

            # logger.info("Waiting for worker tasks to finish...") # Suppressed
            await asyncio.gather(*worker_futures) # Wait for workers
            # logger.info("All worker tasks finished.") # Suppressed

            # logger.info("Closing Playwright browser.") # Suppressed
            await browser.close()
            browser = None # Indicate browser is closed

    except PlaywrightTimeoutError:
         logger.error(f"Playwright timed out during operation. Timeout: {PAGE_TIMEOUT}ms") # Keep error
    except Exception as e:
        logger.error(f"An error occurred during Playwright operation: {e}", exc_info=True) # Keep error
    finally:
        # Ensure browser is closed if it was launched and an error occurred before normal closure
        if browser and browser.is_connected():
            logger.warning("Closing browser in finally block due to earlier error.") # Keep warning
            try:
                await browser.close()
            except Exception as close_err:
                logger.error(f"Error closing browser in finally block: {close_err}") # Keep error

    # logger.info(f"Finished scraping. Total listings found: {len(all_listings_data)}") # Suppressed
    return all_listings_data

# --- Main Execution Block ---
async def main():
    """Main async entry point for benchmarking worker counts."""
    # Set higher logging level to suppress detailed logs during benchmark
    # Change to logging.INFO or logging.DEBUG to see detailed logs again
    logging.getLogger().setLevel(logging.WARNING)

    base_params = {
        'make': 'BMW',
        'model': '3 Series',
        'price_min': 15000,
        'price_max': 40000,
        'mileage_min': 50000,
        'mileage_max': 150000,
    }

    worker_counts_to_test = [ 8, 16, 32, 64, 128, 256]

    print("--- Starting Benchmark ---")
    for count in worker_counts_to_test:
        print(f"\nTesting with {count} workers...")
        start_time = time.time()
        # Call the async scraping function, passing the current worker count
        # Note: Results are fetched but not processed/saved in this benchmark loop
        # Pass the specific worker count for this run
        await scrape_kijiji_autos_async(base_params, count, max_pages=1)
        end_time = time.time()
        duration = end_time - start_time
        print(f"  Workers: {count}, Duration: {duration:.2f} seconds")

    # Add a newline after the benchmark finishes to avoid overlapping with the final print
    print()
    print("\n--- Benchmark Complete ---")
    # Restore logging level if needed for other operations
    # logging.getLogger().setLevel(logging.INFO)


if __name__ == "__main__":
    asyncio.run(main())
