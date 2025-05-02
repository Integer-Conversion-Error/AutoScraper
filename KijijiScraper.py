import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import httpx # Import httpx
import json
import logging
import re
from urllib.parse import urlencode, urljoin, urlparse
import time
import os

# Import the necessary ASYNC functions and proxy loader from KijijiSingleScrape
from KijijiSingleScrape import (
    scrape_kijiji_single_page_async,
    extract_relevant_kijiji_data,
    get_proxy_from_file # Need this for httpx client setup
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
BASE_URL = "https://www.kijijiautos.ca/"
PAGE_TIMEOUT = 120000 # 120 seconds (Increased timeout)
WORKER_COUNT = 20 # Default worker count is no longer used directly in main
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
# This function is no longer needed as we use the API via KijijiSingleScrape
# def extract_vip_details(vip_soup, url, title):
#     ... (removed) ...


# --- Async Tasks ---

async def scroll_task(page, stop_event):
    """Scrolls the page until the height stabilizes or stop_event is set."""
    logger.info("Starting scroll task...") # Re-enabled log
    last_height = await page.evaluate("document.body.scrollHeight")
    stable_count = 0
    attempts = 0
    max_scroll_attempts = 150 # Limit scrolls to prevent infinite loops on tricky pages

    while not stop_event.is_set() and attempts < max_scroll_attempts:
        logger.debug(f"Scroll attempt {attempts + 1}/{max_scroll_attempts}, scrolling down...")
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
            logger.info(f"Scroll height increased to: {new_height} pixels.") # Log new height
        attempts += 1
        if attempts == max_scroll_attempts:
             logger.warning(f"Reached max scroll attempts ({max_scroll_attempts}). Stopping scroll.") # Keep warning
             stop_event.set()
    logger.info("Scroll task finished.") # Re-enabled log


async def monitor_and_queue_task(page, queue, scraped_ad_ids, stop_event, worker_count): # Added worker_count parameter
    """Monitors for new listings and adds their ad_id/title to the queue."""
    logger.info("Starting monitoring task...") # Re-enabled log
    last_logged_batch = -1 # Track the last logged batch number

    while not stop_event.is_set() or not queue.empty():
        if stop_event.is_set() and queue.full():
             logger.warning("Stop event set and queue is full, potentially dropping new items.") # Re-enabled log
             pass # Allow loop to continue to potentially drain queue

        try:
            listing_locators = page.locator('article[data-testid="SearchResultListItem"]')
            current_found_count = await listing_locators.count()
            logger.debug(f"Monitor check: Found {current_found_count} total listing locators on page.")

            # Log batch progress based on the number of listings found so far
            current_batch = current_found_count // 20
            if current_batch > last_logged_batch:
                 logger.info(f"Detected listings potentially up to batch ~{current_batch} (approx {current_found_count} listings found).")
                 last_logged_batch = current_batch

            # Iterate through locators found in this check
            for i in range(current_found_count):
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
                        else:
                             logger.warning(f"Found new ad_id {ad_id} but failed to get title from SRP.") # Re-enabled log
                except PlaywrightTimeoutError:
                     logger.warning(f"Timeout getting ad_id or title for potential listing {i+1}.") # Re-enabled log
                except Exception as e:
                    logger.error(f"Error processing potential listing {i+1} in monitor: {e}", exc_info=False) # Keep error

            # Check exit condition *after* processing found items for this cycle
            if stop_event.is_set() and queue.empty():
                 logger.info("Stop event set and queue is empty. Exiting monitor task.") # Re-enabled log
                 break
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True) # Keep error
            # Add a small delay even after error before next check
            await asyncio.sleep(0.5)

        # Check stop condition again before sleeping for the interval
        if stop_event.is_set() and queue.empty():
            logger.info("Stop event set and queue empty after processing cycle. Exiting monitor task.")
            break

        await asyncio.sleep(MONITOR_INTERVAL)

    logger.info(f"Monitoring task finished. Sending {worker_count} stop signals to workers.") # Re-enabled log
    # Signal workers to stop using the correct count
    for _ in range(worker_count):
        try:
            # Use put_nowait or handle QueueFull if necessary, though unlikely here
            await queue.put(None)
        except Exception as e:
            logger.error(f"Error putting None signal onto queue: {e}")


# --- VIP Page Extraction Logic ---
# Removed process_single_listing_sync as worker is now fully async

# Worker task using KijijiSingleScrape async API calls
async def worker_task(client: httpx.AsyncClient, queue: asyncio.Queue, all_listings_data: list):
    """
    Fetches detailed listing data for an ad_id using the async Kijiji API function,
    extracts relevant details, and adds to list. Uses a shared httpx client.
    """
    worker_name = asyncio.current_task().get_name()
    logger.info(f"Starting worker task {worker_name}...") # Re-enabled log

    while True:
        item = await queue.get()
        if item is None:
            logger.info(f"Worker {worker_name} received stop signal.") # Re-enabled log
            queue.task_done()
            break

        ad_id, _ = item # We only need the ad_id now
        logger.debug(f"Worker {worker_name} processing ad_id: {ad_id}") # Re-enabled log

        try:
            # Call the ASYNC single page scraper directly
            raw_json_data = await scrape_kijiji_single_page_async(ad_id, client)

            if raw_json_data:
                # Extraction is still synchronous, but fast enough not to block significantly
                extracted_data = extract_relevant_kijiji_data(raw_json_data)

                if extracted_data:
                    vip_url = urljoin(BASE_URL, f"/vip/{ad_id}/")
                    extracted_data['ad_id'] = ad_id
                    extracted_data['url'] = vip_url
                    extracted_data['source'] = 'kijiji_autos'

                    all_listings_data.append(extracted_data)
                    # Print progress update (keep this for concise feedback)
                    print(f"\rProcessed: {len(all_listings_data)} listings", end='')
                    logger.info(f"Worker {worker_name} successfully processed API for ad_id: {ad_id}. Total results: {len(all_listings_data)}") # Re-enabled log
                else:
                    logger.warning(f"Worker {worker_name} extracted empty data from API response for ad_id: {ad_id}") # Keep warning
            else: # Logging handled within scrape_kijiji_single_page_async
                 logger.warning(f"Worker {worker_name} failed to fetch API data for ad_id: {ad_id}") # Re-enabled log

        except Exception as e:
            # Catch any unexpected errors during the async call or extraction
            logger.error(f"Worker {worker_name} error processing ad_id {ad_id}: {e}", exc_info=True) # Keep error
            # Do not re-raise, allow worker to continue
        finally:
            queue.task_done()

    logger.info(f"Worker task {worker_name} finished.") # Re-enabled log


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

    logger.info("Launching Playwright browser (async)...") # Re-enabled log

    # --- Load Proxy Configuration ---
    # Use the imported function to get the proxy dict
    proxy_config_dict = get_proxy_from_file()
    # Extract the HTTPS URL string for httpx, default to None
    httpx_proxy_url = None
    if isinstance(proxy_config_dict, dict):
        httpx_proxy_url = proxy_config_dict.get('https') # Or 'http' if needed
        # Corrected indentation for the following block
        if httpx_proxy_url:
            logger.info(f"Using httpx proxy: {httpx_proxy_url}") # Keep info log
        else:
            logger.info("HTTPS proxy URL not found in config dict for httpx.") # Keep info log
    # --- End Proxy Configuration ---

    # --- Setup Playwright ---
    playwright_proxy_settings = None # Separate proxy settings for Playwright if needed
    # (Could reuse httpx_proxies if format is compatible or adapt)
    # For now, assume Playwright runs without proxy unless specifically configured here
    # ... (existing Playwright proxy setup logic could be added here if needed) ...

    browser = None
    # Create httpx client outside the Playwright context, but within the main async function scope
    # Pass the extracted URL string (or None) to the 'proxy' argument
    async with httpx.AsyncClient(proxy=httpx_proxy_url, http2=True, follow_redirects=True, timeout=30.0) as client:
        # Corrected indentation for the following block
        try:
            async with async_playwright() as p:
                launch_options = {"headless": True}
                if playwright_proxy_settings: # Use separate Playwright proxy if defined
                    launch_options["proxy"] = playwright_proxy_settings

                browser = await p.chromium.launch(**launch_options)
                if not browser:
                    logger.error("Failed to launch browser.")
                    return []
                logger.info("Browser launched successfully.") # Re-enabled log

                page = await browser.new_page()
                if not page:
                    logger.error("Failed to create a new page.")
                    await browser.close()
                    return []
                logger.info("New page created successfully.") # Re-enabled log

                page.set_default_timeout(PAGE_TIMEOUT)
                logger.info(f"Page timeout set to {PAGE_TIMEOUT}ms.") # Re-enabled log

                logger.info(f"Navigating to initial URL: {search_url}") # Re-enabled log
                try:
                    response = await page.goto(search_url, wait_until='domcontentloaded')
                    if not response:
                         logger.warning("Navigation call (page.goto) returned None.") # Keep warning
                         return []
                    logger.info(f"Navigation successful. Status: {response.status}") # Re-enabled log
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
                scroll_future = asyncio.create_task(scroll_task(page, stop_event))
                # Pass worker_count to the monitor task
                monitor_future = asyncio.create_task(monitor_and_queue_task(page, queue, scraped_ad_ids, stop_event, worker_count))

                # Worker tasks now need the shared httpx client
                worker_futures = []
                for i in range(worker_count):
                    worker_futures.append(asyncio.create_task(worker_task(client, queue, all_listings_data), name=f"Worker-{i+1}"))

                # --- Wait for Tasks ---
                await asyncio.gather(scroll_future, monitor_future)
                logger.info("Scrolling and Monitoring tasks have signaled completion.") # Re-enabled log

                logger.info("Waiting for queue processing to complete...") # Re-enabled log
                await queue.join()
                logger.info("Queue processing complete.") # Re-enabled log

                logger.info("Waiting for worker tasks to finish...") # Re-enabled log
                await asyncio.gather(*worker_futures) # Wait for workers
                logger.info("All worker tasks finished.") # Re-enabled log

                logger.info("Closing Playwright browser.") # Re-enabled log
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

    logger.info(f"Finished scraping. Total listings found: {len(all_listings_data)}") # Re-enabled log
    return all_listings_data

# --- Main Execution Block ---
async def main():
    """Main async entry point for benchmarking worker counts."""
    # Set logging level - Use INFO to see the new progress logs
    logging.getLogger().setLevel(logging.INFO)
    # Suppress noisy Playwright logs if desired
    logging.getLogger("playwright").setLevel(logging.WARNING) # Quieten Playwright logs

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
