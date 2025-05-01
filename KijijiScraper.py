import asyncio
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
PAGE_TIMEOUT = 30000 # 30 seconds
WORKER_COUNT = 4 # Number of parallel workers for processing listings
QUEUE_MAX_SIZE = 100 # Max items in the processing queue
SCROLL_DELAY = 0.5 # Delay between scrolls (seconds)
NETWORK_IDLE_TIMEOUT = 1500 # Timeout for waiting for network idle (ms)
STABLE_HEIGHT_CHECKS = 3 # How many times height must be stable to stop scrolling
MONITOR_INTERVAL = 0.2 # How often to check for new listings (seconds)

# --- Helper Functions ---

def construct_search_url(params):
    """Constructs the Kijiji Autos search URL (remains synchronous)."""
    path_parts = ["cars"]
    if params.get('make'):
        path_parts.append(params['make'].lower().replace(' ', '-'))
    if params.get('model'):
        path_parts.append(params['model'].lower().replace(' ', '-'))
    if params.get('location'):
         location_slug = params['location'].lower().replace(', ', '-').replace(' ', '-')
         path_parts.append(location_slug)
    base_path = "/".join(path_parts) + "/"
    query_params = {}
    if params.get('year_min'):
        query_params['year-min'] = params['year_min']
    if params.get('year_max'):
        query_params['year-max'] = params['year_max']
    if params.get('price_min'):
        query_params['price-min'] = params['price_min']
    if params.get('price_max'):
        query_params['price-max'] = params['price_max']
    full_url = urljoin(BASE_URL, base_path)
    if query_params:
        full_url += "?" + urlencode(query_params)
    logger.info(f"Constructed URL: {full_url}")
    return full_url

def extract_listing_details_from_soup(listing_soup, url, title):
    """
    Extracts details (excluding URL and Title) from a BeautifulSoup object
    representing a single listing's <article> tag (remains synchronous).
    """
    data = {'url': url, 'title': title}
    try:
        # Price
        price_tag = listing_soup.find('span', {'data-testid': 'searchResultItemPrice'})
        if price_tag:
            price_text = price_tag.get_text(strip=True).replace('$', '').replace(',', '').replace('*', '')
            try:
                data['price'] = int(re.sub(r'[^\d]', '', price_text)) if re.search(r'\d', price_text) else None
            except ValueError:
                logger.warning(f"Could not parse price: {price_tag.get_text(strip=True)} for URL: {data['url']}")
                data['price'] = None
        else:
            data['price'] = None

        # Attributes
        attributes = {}
        attr_list = listing_soup.find('ul', class_='b3n44x')
        if attr_list:
            for item in attr_list.find_all('li', class_='c3n44x'):
                value_span = item.find('span', {'data-testid': 'VehicleListItemAttributeValue'})
                if value_span and value_span.get('title'):
                    title_attr = value_span['title'].strip()
                    value = value_span.get_text(strip=True)
                    if 'km' in title_attr:
                        attributes['mileage'] = value
                    elif ',' in title_attr and any(prov in title_attr for prov in ['ON', 'QC', 'BC', 'AB', 'MB', 'SK', 'NS', 'NB', 'PE', 'NL', 'YT', 'NT', 'NU']):
                         attributes['location'] = value
                    elif value in ['Automatic', 'Manual', 'OTHER']:
                         attributes['transmission'] = value
                    elif value in ['Gas', 'Diesel', 'Electric', 'Hybrid', 'Other']:
                         attributes['fuel_type'] = value
        data.update(attributes)

        # Image URL
        img_tag = listing_soup.find('img', {'data-testid': 'VehicleListItem-imageLoader'})
        data['image_url'] = img_tag.get('data-src') or img_tag.get('src') if img_tag else None

        # Features
        features_div = listing_soup.find('div', class_='b1mTRs')
        if features_div:
             features_list_items = features_div.find_all('li')
             data['features'] = [li.get_text(strip=True) for li in features_list_items if li.find('h5') is None]
        else:
             data['features'] = []

    except Exception as e:
        url_for_log = data.get('url', 'URL not extracted yet')
        logger.error(f"Error extracting data from listing ({url_for_log}): {e}", exc_info=True)
        return data if 'url' in data and 'title' in data else {}

    logger.debug(f"Detail extraction via BeautifulSoup finished for URL: {data['url']}")
    return data

# --- Async Tasks ---

async def scroll_task(page, stop_event):
    """Scrolls the page until the height stabilizes or stop_event is set."""
    logger.info("Starting scroll task...")
    last_height = await page.evaluate("document.body.scrollHeight")
    stable_count = 0
    attempts = 0
    max_scroll_attempts = 150 # Safety limit

    while not stop_event.is_set() and attempts < max_scroll_attempts:
        await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
        await asyncio.sleep(SCROLL_DELAY) # Wait for potential loading

        try:
            # Optional: Wait briefly for network idle, but don't block long
            await page.wait_for_load_state('networkidle', timeout=NETWORK_IDLE_TIMEOUT)
            logger.debug("Network became idle after scroll.")
        except PlaywrightTimeoutError:
            logger.debug("Network did not become idle quickly after scroll, proceeding.")
        except Exception as e:
             logger.warning(f"Error during wait_for_load_state: {e}")


        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            stable_count += 1
            logger.debug(f"Scroll height stable ({stable_count}/{STABLE_HEIGHT_CHECKS}).")
            if stable_count >= STABLE_HEIGHT_CHECKS:
                logger.info("Scroll height stable. Stopping scroll task.")
                stop_event.set() # Signal monitoring task to stop checking
                break
        else:
            stable_count = 0
            last_height = new_height

        attempts += 1
        if attempts == max_scroll_attempts:
             logger.warning("Reached max scroll attempts.")
             stop_event.set() # Signal stop if max attempts reached

    logger.info("Scroll task finished.")


async def monitor_and_queue_task(page, queue, scraped_ad_ids, stop_event):
    """Monitors for new listings and adds their HTML/ID to the queue."""
    logger.info("Starting monitoring task...")
    while not stop_event.is_set() or not queue.empty(): # Continue if stop signaled but queue has items
        if stop_event.is_set() and queue.full():
             logger.warning("Stop event set and queue is full, potentially dropping new items found before workers finish.")
             # Decide if we should wait or just break. Breaking might lose items found right at the end.
             # Let's allow one more pass to queue items if space becomes available.
             pass # Allow loop to run if queue might become free

        try:
            listing_locators = page.locator('article[data-testid="SearchResultListItem"]')
            count = await listing_locators.count()
            logger.debug(f"Monitor check: Found {count} total listing locators.")

            for i in range(count):
                article_locator = listing_locators.nth(i)
                ad_id = None
                try:
                    # Get ad_id first to check if it's new without fetching full HTML yet
                    # Using evaluate to get the attribute directly might be faster
                    ad_id_div = article_locator.locator('div[data-testid="VehicleListItem"]')
                    ad_id = await ad_id_div.get_attribute('data-test-ad-id', timeout=1000) # Short timeout

                    if ad_id and ad_id not in scraped_ad_ids:
                        logger.debug(f"Found new ad_id: {ad_id}. Fetching HTML...")
                        article_html = await article_locator.evaluate("element => element.outerHTML", timeout=2000)
                        if article_html:
                            scraped_ad_ids.add(ad_id) # Add ID immediately to prevent re-queueing
                            try:
                                # Put tuple (ad_id, html) onto the queue
                                await queue.put((ad_id, article_html))
                                logger.debug(f"Queued ad_id: {ad_id}. Queue size: {queue.qsize()}")
                            except asyncio.QueueFull:
                                logger.warning(f"Queue full. Waiting to add ad_id: {ad_id}")
                                # Wait for space in the queue
                                await queue.put((ad_id, article_html)) # This will block until space is available
                        else:
                            logger.warning(f"Got null HTML for new ad_id: {ad_id}")

                except PlaywrightTimeoutError:
                    logger.warning(f"Timeout getting ad_id or HTML for potential listing {i+1}.")
                except Exception as e:
                    # Log error but continue monitoring other elements
                    logger.error(f"Error processing potential listing {i+1} in monitor: {e}", exc_info=False) # Keep log level reasonable

            # If stop event is set and queue is empty, workers are done, we can exit.
            if stop_event.is_set() and queue.empty():
                 logger.info("Stop event set and queue is empty. Exiting monitor task.")
                 break

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}", exc_info=True)
            # Decide whether to break or continue after error
            await asyncio.sleep(1) # Wait a bit before retrying after a major error

        await asyncio.sleep(MONITOR_INTERVAL) # Wait before checking again

    logger.info("Monitoring task finished.")
    # Signal workers that no more items will be added
    for _ in range(WORKER_COUNT):
        await queue.put(None)


async def worker_task(queue, all_listings_data):
    """Processes listing HTML from the queue."""
    logger.info(f"Starting worker task {asyncio.current_task().get_name()}...")
    while True:
        item = await queue.get()
        if item is None: # Sentinel value to stop worker
            logger.info(f"Worker {asyncio.current_task().get_name()} received stop signal.")
            queue.task_done()
            break

        ad_id, article_html = item
        logger.debug(f"Worker processing ad_id: {ad_id}")
        try:
            article_soup = BeautifulSoup(article_html, 'html.parser').find('article')
            if not article_soup:
                logger.warning(f"Worker failed to parse article soup for ad_id: {ad_id}")
                queue.task_done()
                continue

            title_tag = article_soup.find('h2')
            title_value = title_tag.get_text(strip=True) if title_tag else None

            if title_value:
                vip_path = f"/vip/{ad_id}/"
                url = urljoin(BASE_URL, vip_path)
                title = title_value
                # Run synchronous extraction function
                listing_data = extract_listing_details_from_soup(article_soup, url, title)
                if listing_data:
                    all_listings_data.append(listing_data)
                    logger.info(f"Worker successfully processed ad_id: {ad_id}. Total results: {len(all_listings_data)}")
                else:
                     logger.warning(f"Worker extracted empty data for ad_id: {ad_id}")
            else:
                logger.warning(f"Worker could not find title for ad_id: {ad_id}")

        except Exception as e:
            logger.error(f"Worker error processing ad_id {ad_id}: {e}", exc_info=True)
        finally:
            # Ensure task_done is called even if errors occur
            queue.task_done()

    logger.info(f"Worker task {asyncio.current_task().get_name()} finished.")


# --- Main Async Scraping Function ---

async def scrape_kijiji_autos_async(search_params, max_pages=1):
    """
    Scrapes Kijiji Autos asynchronously, overlapping scrolling and processing.
    Note: Pagination (max_pages > 1) is NOT implemented in this async version
          as it adds significant complexity with task coordination across pages.
          This version focuses on optimizing single-page infinite scroll.
    """
    if max_pages > 1:
        logger.warning("Pagination (max_pages > 1) is not supported in this async version. Scraping first page only.")
        max_pages = 1 # Force single page

    all_listings_data = []
    scraped_ad_ids = set() # Track processed ad IDs across tasks
    search_url = construct_search_url(search_params)
    if not search_url:
        logger.error("Could not construct search URL.")
        return []

    logger.info("Launching Playwright browser (async)...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True) # Use await
            if not browser:
                logger.error("Failed to launch browser.")
                return []
            logger.info("Browser launched successfully.")

            page = await browser.new_page() # Use await
            if not page:
                logger.error("Failed to create a new page.")
                await browser.close()
                return []
            logger.info("New page created successfully.")

            page.set_default_timeout(PAGE_TIMEOUT) # Removed await
            logger.info(f"Page timeout set to {PAGE_TIMEOUT}ms. Line completed.") # Added confirmation log

            logger.info(f"Navigating to initial URL: {search_url}")
            if not page: # Redundant check for safety
                logger.error("Page object became None unexpectedly before navigation.")
                return []
            try:
                logger.info("Attempting page.goto...") # Log right before the call
                response = await page.goto(search_url, wait_until='domcontentloaded')
                logger.info("page.goto call completed.") # Log right after the call
                if not response:
                     logger.warning("Navigation call (page.goto) returned None.")
                     # Let the outer exception handler deal with browser closing
                     return [] # Exit if navigation didn't return a response object
                logger.info(f"Navigation successful. Status: {response.status}")
            except PlaywrightTimeoutError as nav_timeout:
                 logger.error(f"Timeout during page.goto navigation: {nav_timeout}", exc_info=True)
                 # Let the outer exception handler deal with browser closing
                 return []
            except Exception as nav_err:
                 logger.error(f"Error during page.goto navigation: {nav_err}", exc_info=True)
                 # Let the outer exception handler deal with browser closing
                 return []

            # --- Setup Async Components ---
            queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
            stop_event = asyncio.Event() # To signal scrolling/monitoring should stop

            # --- Start Tasks ---
            scroll_future = asyncio.create_task(scroll_task(page, stop_event))
            monitor_future = asyncio.create_task(monitor_and_queue_task(page, queue, scraped_ad_ids, stop_event))

            worker_futures = []
            for i in range(WORKER_COUNT):
                worker_futures.append(asyncio.create_task(worker_task(queue, all_listings_data), name=f"Worker-{i+1}"))

            # --- Wait for Tasks ---
            # Wait for scrolling and monitoring to indicate completion
            # Monitor task will only exit when stop_event is set AND queue is empty
            # Scroll task exits when stop_event is set (by itself or monitor)
            await asyncio.gather(scroll_future, monitor_future) # Wait for these core tasks

            logger.info("Scrolling and Monitoring tasks have signaled completion.")

            # Wait for the queue to be fully processed by workers
            logger.info("Waiting for queue processing to complete...")
            await queue.join() # Waits until queue.task_done() called for all items
            logger.info("Queue processing complete.")

            # Wait for all worker tasks to finish (they exit after receiving None)
            logger.info("Waiting for worker tasks to finish...")
            await asyncio.gather(*worker_futures)
            logger.info("All worker tasks finished.")

            logger.info("Closing Playwright browser.")
            await browser.close() # Use await

    except PlaywrightTimeoutError:
         logger.error(f"Playwright timed out during operation. Timeout: {PAGE_TIMEOUT}ms")
    except Exception as e:
        logger.error(f"An error occurred during Playwright operation: {e}", exc_info=True)
        # Ensure browser is closed even if error occurs mid-process
        try:
            if 'browser' in locals() and browser.is_connected:
                await browser.close()
        except Exception as close_err:
            logger.error(f"Error closing browser after failure: {close_err}")

    logger.info(f"Finished scraping. Total listings found: {len(all_listings_data)}")
    return all_listings_data

# --- Main Execution Block ---
async def main():
    """Main async entry point."""
    params = {
        'make': 'BMW',
        'model': '3 Series',
    }

    start_time = time.time()
    # Call the async scraping function
    results = await scrape_kijiji_autos_async(params, max_pages=1) # Use await
    end_time = time.time()
    duration = end_time - start_time

    if results:
        print("\n--- SCRAPING RESULTS ---")
        print(f"\nTotal results: {len(results)}")
        print(f"Scraping completed in {duration:.2f} seconds.")

        output_filename = "kijiji_results_async.json" # Changed filename
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=4, ensure_ascii=False)
            print(f"Results saved to {output_filename}")
        except Exception as e:
            logger.error(f"Error saving results to JSON: {e}")
    else:
        print("\n--- SCRAPING RESULTS ---")
        print("No results found or scraping failed.")
        print("------------------------")

if __name__ == "__main__":
    # Run the main async function
    asyncio.run(main())
