import logging
import json
import time
import requests
from flask import Blueprint, request, jsonify, session, g, current_app
from ..firebase_config import get_user_settings
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

    make = car_details.get('Make', '')
    model = car_details.get('Model', '')
    model = clean_model_name(model) # Clean the model name
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
            search_results_text = []
            num_results_per_query = 10
            max_search_retries = 3
            initial_search_delay = 0.5

            for query in queries:
                logging.info(f"Performing web search: {query}")
                items = []
                for attempt in range(max_search_retries):
                    try:
                        result = search_service.cse().list(
                            q=query, cx=search_engine_id, num=num_results_per_query
                        ).execute()
                        items = result.get('items', [])
                        break
                    except HttpError as e:
                        logging.warning(f"Search attempt {attempt + 1} failed for query '{query}': {e}")
                        if e.resp.status in [429, 500, 503] and attempt < max_search_retries - 1:
                            delay = initial_search_delay * (2 ** attempt)
                            logging.info(f"Retrying in {delay:.2f} seconds...")
                            time.sleep(delay)
                        else:
                            logging.error(f"Search failed permanently for query '{query}' after {attempt + 1} attempts.")
                            break
                    except Exception as e:
                         logging.error(f"Unexpected error during search for query '{query}': {e}")
                         break

                if items:
                    search_results_text.append(f"Search results for '{query}':")
                    for item in items:
                        title = item.get('title')
                        link = item.get('link')
                        snippet = item.get('snippet', '').replace('\n', ' ')
                        search_results_text.append(f"- {title} ({link}): {snippet}")
                else:
                     search_results_text.append(f"No significant results found for '{query}' (or search failed).")
                search_results_text.append("\n")

            search_summary = "\n".join(search_results_text)

        except Exception as e:
            logging.error(f"Error during web search setup or processing: {e}", exc_info=True)
            search_summary = "Error occurred during web search processing."
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
        logging.info(f"Received AI analysis response for user {user_id}")
        return jsonify({"success": True, "summary": ai_summary})

    except Exception as e:
        logging.error(f"Error generating content with Gemini for user {user_id}: {e}", exc_info=True)
        # Consider more specific error handling for Gemini API responses if needed
        return jsonify({"success": False, "error": f"AI analysis failed: {e}"}), 500
