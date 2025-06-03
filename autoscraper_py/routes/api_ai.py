import logging
import json
import time
import requests
from bs4 import BeautifulSoup # Import BeautifulSoup
from flask import Blueprint, request, jsonify, session, g, current_app
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError # Import Playwright
from concurrent.futures import ThreadPoolExecutor # Import ThreadPoolExecutor
from ..firebase_config import get_user_settings, get_ai_analysis, save_ai_analysis # Add new imports
from googleapiclient.discovery import build # Import Google Search library
from googleapiclient.errors import HttpError # Import HttpError for search retries
from ..auth_decorator import login_required # Import the updated decorator
from ..AutoScraperUtil import clean_model_name # Import the cleaning function

# Create the blueprint
api_ai_bp = Blueprint('api_ai', __name__, url_prefix='/api')

# No placeholder decorator needed anymore

# --- Helper Function ---
# This function uses external libraries (requests) and config (api_key).
# It's okay here for now, but could be moved to a 'utils.py' or similar.
def get_exchange_rates(api_key):
    if not api_key:
        logging.warning("Exchange Rate API key not configured.")
        return None
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/CAD"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("result") == "success":
            rates = data.get("conversion_rates", {})
            usd_rate = rates.get("USD")
            eur_rate = rates.get("EUR")
            gbp_rate = rates.get("GBP")
            return {
                "USD_per_CAD": usd_rate, "EUR_per_CAD": eur_rate, "GBP_per_CAD": gbp_rate,
                "CAD_per_USD": 1 / usd_rate if usd_rate else None,
                "CAD_per_EUR": 1 / eur_rate if eur_rate else None,
                "CAD_per_GBP": 1 / gbp_rate if gbp_rate else None,
            }
        else:
            logging.error(f"ExchangeRate-API error: {data.get('error-type')}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching exchange rates: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error getting exchange rates: {e}")
        return None
# --- End Helper Function ---

# --- Helper Function for HTML Cleaning ---
def get_cleaned_html_content(url, timeout=10):
    """Fetches HTML from a URL and returns cleaned text content, with Playwright fallback."""
    html_content = None
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    
    try:
        logging.info(f"Attempting to fetch content from {url} using requests.")
        headers = {'User-Agent': user_agent}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        content_type = response.headers.get('content-type', '').lower()
        if 'html' not in content_type and 'text' not in content_type:
            logging.warning(f"Content from {url} with requests is not HTML/text ({content_type}). Will attempt Playwright.")
            # Fall through to Playwright by not setting html_content
        else:
            html_content = response.content
            logging.info(f"Successfully fetched content from {url} using requests.")

    except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
        logging.warning(f"Requests failed for {url}: {e}. Attempting fallback with Playwright.")
        # Fall through to Playwright by not setting html_content
    
    if html_content is None: # If requests failed or content type was not suitable
        try:
            logging.info(f"Attempting to fetch content from {url} using Playwright.")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(user_agent=user_agent)
                try:
                    page.goto(url, timeout=timeout * 2000, wait_until='domcontentloaded') # Increased timeout for Playwright, wait_until
                    html_content = page.content()
                    logging.info(f"Successfully fetched content from {url} using Playwright.")
                except PlaywrightTimeoutError:
                    logging.warning(f"Playwright timed out loading {url}. Trying to get content anyway.")
                    html_content = page.content() # Try to get whatever content is there
                except Exception as pe:
                    logging.error(f"Playwright navigation/content retrieval failed for {url}: {pe}")
                    return f"Playwright error processing content from {url}: {pe}"
                finally:
                    browser.close()
        except Exception as p_setup_error:
            logging.error(f"Playwright setup/execution failed for {url}: {p_setup_error}", exc_info=True)
            return f"Playwright setup error for {url}: {p_setup_error}"

    if html_content is None:
        logging.error(f"Failed to fetch content from {url} using both requests and Playwright.")
        return f"Failed to fetch content from {url} after multiple attempts."

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        tags_to_remove = ['script', 'style', 'img', 'iframe', 'nav', 'footer', 'aside', 'header', 'form', 'button', 'input', 'textarea', 'select', 'option', 'label']
        for tag_name in tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose()
        
        potential_ad_selectors = [
            "[class*='ad']", "[id*='ad']", "[class*='banner']", "[id*='banner']",
            "[class*='promo']", "[id*='promo']", "[class*='popup']", "[id*='popup']",
            "[class*='cookie']", "[id*='cookie']", "[class*='consent']", "[id*='consent']" 
        ]
        for selector in potential_ad_selectors:
            try:
                for ad_element in soup.select(selector):
                    ad_element.decompose()
            except Exception as e:
                logging.debug(f"Error applying selector {selector} for {url}: {e}")

        text_parts = []
        for element in soup.find_all(string=True):
            if element.parent.name in tags_to_remove:
                continue
            text = element.strip()
            if text:
                text_parts.append(text)
        
        cleaned_text = " ".join(text_parts)
        
        max_length = 20000 # Increased max_length slightly
        if len(cleaned_text) > max_length:
            cleaned_text = cleaned_text[:max_length] + " ... (content truncated)"
            logging.info(f"Truncated content from {url} to {max_length} characters.")

        return cleaned_text if cleaned_text else f"No textual content found after cleaning {url}."

    except Exception as e:
        logging.error(f"Error cleaning HTML from {url} (fetched successfully): {e}", exc_info=True)
        return f"Error processing fetched content from {url}."
# --- End HTML Cleaning Helper ---


@api_ai_bp.route('/analyze_car', methods=['POST'])
@login_required # Apply actual decorator (it populates g)
def analyze_car_api():
    user_id = g.user_id # Get from decorator-populated g
    user_settings = g.user_settings # Get from decorator-populated g

    # Check AI access permission
    if not user_settings.get('can_use_ai', False):
        logging.warning(f"User {user_id} denied AI analysis access.")
        return jsonify({"success": False, "error": "AI analysis access denied for this user."}), 403

    # Access shared services/config from current_app context
    # These need to be attached to the app object during initialization in app.py
    gemini_model = getattr(current_app, 'gemini_model', None)
    search_service = getattr(current_app, 'search_service', None)
    search_engine_id = getattr(current_app, 'SEARCH_ENGINE_ID', None)
    exchange_rate_api_key = getattr(current_app, 'EXCHANGE_RATE_API_KEY', None)

    if not gemini_model:
        return jsonify({"success": False, "error": "AI Model not configured on the server."}), 500

    car_details = request.json
    if not car_details:
        return jsonify({"success": False, "error": "No car details provided."}), 400

    listing_link = car_details.get('Link') # Expecting "Link" (capital L)
    if not listing_link:
        return jsonify({"success": False, "error": "Listing link not provided in car details."}), 400

    # Check for cached AI analysis first
    cached_analysis_data = get_ai_analysis(user_id, listing_link)
    if cached_analysis_data and 'analysis_text' in cached_analysis_data:
        logging.info(f"Returning cached AI analysis for user {user_id}, link {listing_link}")
        return jsonify({"success": True, "summary": cached_analysis_data['analysis_text'], "cached": True})

    # --- If not cached, proceed with new analysis ---
    logging.info(f"No cached analysis found for user {user_id}, link {listing_link}. Generating new analysis.")
    
    make = car_details.get('Make', '')
    model = car_details.get('Model', '')
    model = clean_model_name(model)
    year = car_details.get('Year', '')
    trim = car_details.get('Trim', '')
    price_str = car_details.get('Price', '')
    km_str = car_details.get('Kilometres', '')

    # Clean and convert price/km
    price_cad = None
    try:
        if price_str: price_cad = float(price_str.replace('$', '').replace(',', ''))
    except ValueError: logging.warning(f"Could not parse price: {price_str}")

    kilometres = None
    try:
        if km_str: kilometres = int(km_str.replace(',', '').split(' ')[0])
    except ValueError: logging.warning(f"Could not parse kilometres: {km_str}")

    if not make or not model or not year:
        return jsonify({"success": False, "error": "Make, Model, and Year are required for analysis."}), 400

    search_summary = ""
    if search_service and search_engine_id:
        try:
            queries = [
                f'"{year} {make} {model}" reliability rating', f'"{year} {make} {model}" common problems',
                f'"{year} {make} {model}" long term reliability', f'"{year} {make} {model}" maintenance costs',
                f'"{year} {make} {model}" repair costs', f'"{year} {make} {model}" expert review',
                f'"{year} {make} {model}" owner reviews', f'"{year} {make} {model}" pros and cons',
                f'"{year} {make} {model}" vs competitor cars', f'"{year} {make} {model}" is it a good car to buy',
                f'"{year} {make} {model}" owners forum', f'"{year} {make} {model}" reddit reviews',
                f'"{year} {make} {model}" online community feedback', f'"{make} {model}" recalls and TSBs',
                f'"{year} {make} {model}" fuel economy MPG', f'"{year} {make} {model}" safety ratings',
                f'"{year} {make} {model}" cargo space', f'"{year} {make} {model}" warranty details',
                f'"{year} {make} {model}" fair market price', f'"{year} {make} {model}" used car value',
                f'"{year} {make} {model}" lease or buy deals', f'"{year} {make} {model}" incentives rebates',
                f'"{year} {make} {model}" best time to buy', f'"{year} {make} {model}" owner satisfaction',
                f'"{year} {make} {model}" things to know before buying',
            ]
            all_search_items_with_details = [] # Stores dicts: {query, title, link, original_snippet, full_content}
            num_results_per_query = 8 
            max_search_retries = 3
            initial_search_delay = 0.5

            # --- Step 1: Perform all Google Search API calls and collect initial data ---
            for query in queries:
                logging.info(f"Performing web search: {query}")
                try:
                    google_search_items = []
                    for attempt in range(max_search_retries):
                        try:
                            result = search_service.cse().list(
                                q=query, cx=search_engine_id, num=num_results_per_query
                            ).execute()
                            google_search_items = result.get('items', [])
                            break # Success
                        except HttpError as e:
                            logging.warning(f"Search attempt {attempt + 1} failed for query '{query}': {e}")
                            if e.resp.status in [429, 500, 503] and attempt < max_search_retries - 1:
                                delay = initial_search_delay * (2 ** attempt)
                                logging.info(f"Retrying in {delay:.2f} seconds...")
                                time.sleep(delay)
                            else:
                                logging.error(f"Search failed permanently for query '{query}' after {attempt + 1} attempts.")
                                break 
                        except Exception as e_inner:
                            logging.error(f"Unexpected error during search attempt for query '{query}': {e_inner}")
                            break
                    
                    if google_search_items:
                        for item in google_search_items:
                            all_search_items_with_details.append({
                                "query": query,
                                "title": item.get('title', 'N/A'),
                                "link": item.get('link'),
                                "original_snippet": item.get('snippet', '').replace('\n', ' '),
                                "full_content": "" # Initially empty
                            })
                    else:
                         logging.info(f"No Google search results for query: {query}")

                except Exception as e_outer:
                    logging.error(f"Error processing search for query '{query}': {e_outer}", exc_info=True)
            
            # --- Helper function for parallel fetching ---
            def fetch_and_update_item(item_details):
                item_link = item_details.get("link")
                if item_link:
                    logging.info(f"Fetching and cleaning content for: {item_link} (Query: {item_details['query']})")
                    cleaned_content = get_cleaned_html_content(item_link) 
                    item_details["full_content"] = cleaned_content
                else:
                    item_details["full_content"] = "No link provided in search result."
                return item_details

            # --- Step 2: Fetch full content for each collected item in parallel ---
            if all_search_items_with_details:
                logging.info(f"Collected {len(all_search_items_with_details)} items from Google Search. Now fetching full content in parallel.")
                # Adjust max_workers based on system resources and typical number of items.
                # Too many workers for Playwright can be resource-intensive.
                num_workers = min(len(all_search_items_with_details), 250) # Max 50 workers for now
                if num_workers > 0:
                    with ThreadPoolExecutor(max_workers=num_workers) as executor:
                        # executor.map processes items in parallel and returns results in order
                        results = list(executor.map(fetch_and_update_item, all_search_items_with_details))
                        all_search_items_with_details = results # Replace with updated items
                else: # Handle case with 0 items to avoid ThreadPoolExecutor error
                    logging.info("No items to process with ThreadPoolExecutor.")

            else:
                logging.info("No items collected from Google Search to fetch full content for.")

            # --- Step 3: Construct search_summary for AI prompt using fallback ---
            search_results_text_parts = []
            if all_search_items_with_details:
                # Group by query for better readability in the prompt
                grouped_results = {}
                for item_details in all_search_items_with_details:
                    query = item_details["query"]
                    if query not in grouped_results:
                        grouped_results[query] = []
                    grouped_results[query].append(item_details)
                
                for query, items_for_query in grouped_results.items():
                    search_results_text_parts.append(f"Search results for '{query}':")
                    for item_details in items_for_query:
                        content_to_use = item_details["full_content"]
                        # Check if full_content is an error message or indicates no content
                        if not content_to_use or \
                           content_to_use.startswith("Error fetching content from") or \
                           content_to_use.startswith("Timeout fetching content from") or \
                           content_to_use.startswith("Playwright error processing content from") or \
                           content_to_use.startswith("Playwright setup error for") or \
                           content_to_use.startswith("Failed to fetch content from") or \
                           content_to_use.startswith("Error processing fetched content from") or \
                           content_to_use.startswith("No textual content found after cleaning") or \
                           content_to_use.startswith("No link provided in search result.") or \
                           content_to_use.startswith("Content from") and "is not HTML/text" in content_to_use: # Check for non-html content message
                            logging.warning(f"Using original snippet for {item_details['link']} due to full_content issue: '{content_to_use}'")
                            content_to_use = item_details["original_snippet"]
                        
                        search_results_text_parts.append(f"- {item_details['title']} ({item_details['link']}):\n{content_to_use}\n")
                    search_results_text_parts.append("\n") # Separator between queries
            else:
                search_results_text_parts.append("No web search results were found or processed.")
            
            search_summary = "\n".join(search_results_text_parts)

        except Exception as e:
            logging.error(f"Overall error during web search and content processing: {e}", exc_info=True)
            search_summary = "Error occurred during web search and content processing."
    else:
        search_summary = "Web search is not configured or enabled on the server."

    # Get current exchange rates
    rates = get_exchange_rates(exchange_rate_api_key) # Use key from app context
    rates_info = "Exchange rates not available."
    if rates:
        rates_info = f"""Current Approximate Exchange Rates:
- 1 CAD = {rates.get('USD_per_CAD', 'N/A'):.3f} USD | 1 USD = {rates.get('CAD_per_USD', 'N/A'):.2f} CAD
- 1 CAD = {rates.get('EUR_per_CAD', 'N/A'):.3f} EUR | 1 EUR = {rates.get('CAD_per_EUR', 'N/A'):.2f} CAD
- 1 CAD = {rates.get('GBP_per_CAD', 'N/A'):.3f} GBP | 1 GBP = {rates.get('CAD_per_GBP', 'N/A'):.2f} CAD"""

    # Pre-format price and kilometres for the prompt
    price_cad_str = f'{price_cad:,.0f} CAD' if price_cad is not None else 'N/A'
    kilometres_str = f'{kilometres:,} km' if kilometres is not None else 'N/A'

    # Construct prompt for Gemini
    prompt = f"""
Analyze the reliability and potential value of the following car based on the provided details, web search context, and exchange rates.

Car Listing Details:
Make: {make}
Model: {model}
Year: {year}
Trim: {trim if trim else 'N/A'}
Listed Price: {price_cad_str}
Kilometres: {kilometres_str}
Original Listing URL: {listing_link} 

{rates_info}

Web Search Context (Reliability, Problems, Reviews, etc.):
--- START CONTEXT ---
{search_summary}
--- END CONTEXT ---

Based on ALL the information provided (car details, price, mileage, web context, exchange rates), please provide a comprehensive analysis covering:

1.  **Reliability Summary:**
    *   Known Issues: List specific common problems reported (use bullet points).
    *   Positive Points: Mention positive reliability aspects found.
    *   Things to Check: Suggest specific inspection points for a potential buyer.
    *   Overall Reliability Sentiment: Summarize the general sentiment (positive, negative, mixed).

2.  **Price Analysis:**
    *   Compare the listed price ({price_cad_str}) and mileage ({kilometres_str}) to any relevant pricing information or comparable vehicles mentioned in the web search context. Remember to account for currency differences using the provided exchange rates (assume online prices might be USD, EUR, or GBP unless specified otherwise).
    *   Provide a deal rating (e.g., Excellent Deal, Good Deal, Fair Price, Slightly High, Overpriced) based on this comparison and the car's reliability profile. Justify the rating briefly.

3.  **Negotiation Tips:**
    *   Based on the reliability issues found and the price analysis, provide 2-3 specific, actionable negotiation points or questions a buyer could use to potentially lower the price.

Format the response clearly using headings (like **Reliability Summary**, **Price Analysis**, **Negotiation Tips**) and bullet points. Be objective and base the analysis ONLY on the provided information. If context is missing or contradictory, state that.
"""

    try:
        logging.info(f"Sending AI analysis request for {year} {make} {model} for user {user_id}")
        response = gemini_model.generate_content(prompt)
        ai_summary = response.text
        logging.info(f"Received AI analysis response for user {user_id}, link {listing_link}")

        # Save the new analysis to cache
        save_successful = save_ai_analysis(user_id, listing_link, ai_summary)
        if save_successful:
            logging.info(f"Successfully cached AI analysis for user {user_id}, link {listing_link}")
        else:
            logging.warning(f"Failed to cache AI analysis for user {user_id}, link {listing_link}")
        
        return jsonify({"success": True, "summary": ai_summary, "cached": False})

    except Exception as e:
        logging.error(f"Error generating content with Gemini for user {user_id}, link {listing_link}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"AI analysis failed: {e}"}), 500
