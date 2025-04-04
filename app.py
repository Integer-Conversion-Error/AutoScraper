# Update the imports in app.py to include csv
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
import os
import json
import csv  # Add this import
import secrets
import logging # Import logging
import requests # Import requests for exchange rate API
import math # Import math for ceil
import google.generativeai as genai # Import Gemini library
from googleapiclient.discovery import build # Import Google Search library
from googleapiclient.errors import HttpError # Import HttpError for search retries
import time # Import time for sleep
from datetime import timedelta
from functools import wraps
from urllib.parse import unquote # Add unquote import
from AutoScraperUtil import (
    get_all_makes,
    get_models_for_make,
    get_trims_for_model,
    get_colors, # Import the new color function
    transform_strings,
    read_json_file,
    save_json_to_file,
    format_time_ymd_hms,
    showcarsmain
)
# fetch_autotrader_data now returns dict for initial fetch or list for full fetch
from AutoScraper import fetch_autotrader_data, save_results_to_csv

# Import Firebase config
from firebase_config import (
    initialize_firebase,
    get_firestore_db,
    create_user,
    verify_id_token,
    get_user,
    save_payload,
    get_user_payloads,
    get_payload,
    update_payload,
    delete_payload,
    save_results,           # Add these new imports
    get_user_results,       # Add these new imports
    get_result,             # Add these new imports
    delete_result,          # Add these new imports
    get_user_settings,      # Add settings functions
    update_user_settings,   # Add settings functions
    get_firestore_db        # Import db access for direct updates
)
# Initialize Firebase
firebase_initialized = initialize_firebase()

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = secrets.token_hex(32)  # Use a stronger secret key

# --- AI Integration Setup ---
# Configure logging for AI parts specifically if needed, or rely on Flask's logger
logging.basicConfig(level=logging.INFO) # Basic logging config

try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    GEMINI_API_KEY = config.get('GEMINI_API_KEY')
    SEARCH_API_KEY = config.get('SEARCH_API_KEY')
    SEARCH_ENGINE_ID = config.get('SEARCH_ENGINE_ID')
    EXCHANGE_RATE_API_KEY = config.get('EXCHANGE_RATE_API_KEY') # Load Exchange Rate Key

    if not GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY not found in config.json")
        gemini_model = None
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        # Consider making the model name configurable or choosing based on task
        gemini_model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21') # Reverted to gemini-pro for stability if flash isn't available
        logging.info("Gemini AI Model configured.")

    if not SEARCH_API_KEY or not SEARCH_ENGINE_ID:
        logging.warning("SEARCH_API_KEY or SEARCH_ENGINE_ID not found in config.json. Web search functionality will be disabled.")
        search_service = None
    else:
        # Build the search service
        search_service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
        logging.info("Google Custom Search service configured.")

except FileNotFoundError:
    logging.error("config.json not found. AI features require API keys.")
    GEMINI_API_KEY = None
    SEARCH_API_KEY = None
    SEARCH_ENGINE_ID = None
    EXCHANGE_RATE_API_KEY = None # Init key var
    gemini_model = None
    search_service = None
except json.JSONDecodeError:
    logging.error("Error decoding config.json.")
    GEMINI_API_KEY = None
    SEARCH_API_KEY = None
    SEARCH_ENGINE_ID = None
    EXCHANGE_RATE_API_KEY = None # Init key var
    gemini_model = None
    search_service = None
except Exception as e:
    logging.error(f"An unexpected error occurred during AI setup: {e}")
    GEMINI_API_KEY = None
    SEARCH_API_KEY = None
    SEARCH_ENGINE_ID = None
    EXCHANGE_RATE_API_KEY = None # Init key var
    gemini_model = None
    search_service = None

# Function to get exchange rates
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
            # Extract relevant rates
            usd_rate = rates.get("USD")
            eur_rate = rates.get("EUR")
            gbp_rate = rates.get("GBP")
            return {
                "USD_per_CAD": usd_rate,
                "EUR_per_CAD": eur_rate,
                "GBP_per_CAD": gbp_rate,
                # Add CAD_per_X for easier conversion in prompt
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

# --- End AI Integration Setup ---

# Configure session
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions on filesystem
app.config['SESSION_PERMANENT'] = True     # Make sessions permanent
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # Increase session lifetime
app.config['SESSION_USE_SIGNER'] = True    # Add a signer for security

# Import the login_required decorator after app is created
from auth_decorator import login_required_with_app
from flask import g # Import g
login_required = lambda f: login_required_with_app(app, f)  # Pass app to the decorator

@app.route('/')
def landing():
    """Serves the public landing page."""
    # Check if user is already logged in, if so, redirect to the app page
    if 'user_id' in session:
        return redirect(url_for('app_interface'))
    return render_template('landing.html')

@app.route('/app')
@login_required
def app_interface():
    """Serves the main application interface for logged-in users."""
    # Print session info for debugging
    print(f"User session: {session.get('user_id')}, {session.get('email')}")
    return render_template('index.html', username=session.get('display_name', 'User'))

@app.route('/pricing')
def pricing():
    """Serves the public pricing page."""
    return render_template('pricing.html')

@app.route('/about')
def about():
    """Serves the public about page."""
    return render_template('about.html')

@app.route('/terms')
def terms():
    """Serves the terms and conditions page."""
    return render_template('terms.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to the app interface
    if 'user_id' in session:
        return redirect(url_for('app_interface'))

    if request.method == 'POST':
        # This route now only receives the Firebase ID token after client-side auth
        id_token = request.form.get('idToken')
        if id_token:
            # Verify the token with Firebase
            result = verify_id_token(id_token)
            if result['success']:
                user_info = result['user']
                # Store user information in session
                session['user_id'] = user_info.get('uid')
                session['email'] = user_info.get('email')
                session['display_name'] = user_info.get('name', user_info.get('email', 'User'))
                session.modified = True  # Mark session as modified

                print(f"Login successful for user: {session.get('email')}")
                flash('Login successful!', 'success')
                # Redirect to the main app interface after login
                return redirect(url_for('app_interface'))
            else:
                flash('Authentication failed: ' + result.get('error', 'Unknown error'), 'danger')
        else:
            flash('No authentication token provided', 'danger')

    # If it's a GET request or login failed
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    # This page will handle user registration
    return render_template('register.html')

@app.route('/logout')
def logout():
    """
    Handle user logout with proper session cleanup and Firebase sign out.
    Renders a logout page that handles Firebase client-side logout before redirecting.
    """
    # Clear the user session on the server side
    user_email = session.get('email', 'Unknown user')
    session.clear()

    # Log the logout
    print(f"Logged out user: {user_email}")

    # Render the logout page which will handle Firebase client-side logout
    # After client-side logout, it should redirect to the landing page
    return render_template('logout.html', redirect_url=url_for('landing'))

@app.route('/api/makes')
@login_required
def get_makes():
    popular = request.args.get('popular', 'true').lower() == 'true'
    makes = get_all_makes(popular=popular)
    return jsonify(makes)

@app.route('/api/models/<make>')
@login_required
def get_models(make):
    models = get_models_for_make(make)
    return jsonify(models)

@app.route('/api/trims/<make>/<model>')
@login_required
def get_trims_api(make, model):
    """API endpoint to get trims for a specific make and model."""
    # Decode URL components
    decoded_make = unquote(make)
    decoded_model = unquote(model)
    trims = get_trims_for_model(decoded_make, decoded_model)
    # The function already returns a dict {trim_name: count}, which is JSON serializable
    return jsonify(trims)

@app.route('/api/colors/<make>/<model>')
@app.route('/api/colors/<make>/<model>/<trim>') # Add route with optional trim
@login_required
def get_colors_api(make, model, trim=None):
    """API endpoint to get colors for a specific make, model, and optional trim."""
    # Decode URL components
    decoded_make = unquote(make)
    decoded_model = unquote(model)
    decoded_trim = unquote(trim) if trim else None

    colors = get_colors(decoded_make, decoded_model, decoded_trim)
    # The function returns a list of strings, which is JSON serializable
    return jsonify(colors)

@app.route('/api/create_payload', methods=['POST'])
@login_required
def create_payload():
    payload = request.json
    # --- ADDED LOGGING ---
    print(f"--- DEBUG: Received payload in /api/create_payload: {payload}")
    # --- END LOGGING ---
    return jsonify({"success": True, "payload": payload})

@app.route('/api/save_payload', methods=['POST'])
@login_required
def save_payload_api():
    payload = request.json.get('payload')
    user_id = session.get('user_id')

    if not payload:
        return jsonify({"success": False, "error": "No payload provided"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    # Save payload to Firebase
    result = save_payload(user_id, payload)

    if result['success']:
        return jsonify({
            "success": True,
            "file_path": f"Firebase/{result['doc_id']}",
            "doc_id": result['doc_id']
        })
    else:
        return jsonify({"success": False, "error": result.get('error', 'Failed to save payload')})

@app.route('/api/list_payloads')
@login_required
def list_payloads():
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Get payloads from Firebase
        payloads = get_user_payloads(user_id)

        # Format for the frontend
        formatted_payloads = []
        for payload_data in payloads:
            payload = payload_data['payload']

            # Use custom_name if available, otherwise create a formatted name
            if 'custom_name' in payload:
                formatted_name = payload['custom_name']
            else:
                make = payload.get('Make', 'Unknown')
                model = payload.get('Model', 'Unknown')
                year_min = payload.get('YearMin', '')
                year_max = payload.get('YearMax', '')
                price_min = payload.get('PriceMin', '')
                price_max = payload.get('PriceMax', '')

                formatted_name = f"{make} {model} ({year_min}-{year_max}, ${price_min}-${price_max})"

            formatted_payloads.append({
                "name": formatted_name,
                "id": payload_data['id']
            })

        return jsonify({"success": True, "payloads": formatted_payloads})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# In your load_payload_api function in app.py
@app.route('/api/load_payload', methods=['POST'])
@login_required
def load_payload_api():
    file_path = request.json.get('file_path')
    doc_id = request.json.get('doc_id')  # Get the document ID directly
    user_id = session.get('user_id')

    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    # Check if it's a Firebase path
    if file_path.startswith("Firebase/"):
        # Use the doc_id directly
        if not doc_id:
            return jsonify({"success": False, "error": "No document ID provided"})

        # Get the payload from Firebase
        payload = get_payload(user_id, doc_id)

        if not payload:
            return jsonify({"success": False, "error": f"Failed to load payload from Firebase"})

        return jsonify({"success": True, "payload": payload})
    else:
        # Legacy file-based loading (for backward compatibility)
        payload = read_json_file(file_path)
        if not payload:
            return jsonify({"success": False, "error": f"Failed to load payload from {file_path}"})

        return jsonify({"success": True, "payload": payload})


# --- User Settings API ---
@app.route('/api/get_user_settings', methods=['GET'])
@login_required
def get_user_settings_api():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"}), 401

    settings = get_user_settings(user_id)
    return jsonify({"success": True, "settings": settings})

@app.route('/api/update_user_settings', methods=['POST'])
@login_required
def update_user_settings_api():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"}), 401

    data = request.json
    tokens = data.get('search_tokens')
    can_use_ai = data.get('can_use_ai')

    update_data = {}
    if tokens is not None:
        try:
            update_data['search_tokens'] = int(tokens)
            if update_data['search_tokens'] < 0:
                 return jsonify({"success": False, "error": "Tokens cannot be negative."}), 400
        except ValueError:
            return jsonify({"success": False, "error": "Invalid value for search_tokens."}), 400

    if can_use_ai is not None:
        if isinstance(can_use_ai, bool):
            update_data['can_use_ai'] = can_use_ai
        else:
            return jsonify({"success": False, "error": "Invalid value for can_use_ai."}), 400

    if not update_data:
         return jsonify({"success": False, "error": "No settings provided to update."}), 400

    result = update_user_settings(user_id, update_data)

    if result['success']:
        # Fetch updated settings to return
        updated_settings = get_user_settings(user_id)
        return jsonify({"success": True, "settings": updated_settings})
    else:
        return jsonify({"success": False, "error": result.get('error', 'Failed to update settings')}), 500
# --- End User Settings API ---


@app.route('/api/fetch_data', methods=['POST'])
@login_required
def fetch_data_api():
    payload = request.json.get('payload')
    # --- ADDED LOGGING ---
    print(f"--- DEBUG: Received payload in /api/fetch_data: {payload}")
    # --- END LOGGING ---
    user_id = session.get('user_id')

    if not payload:
        return jsonify({"success": False, "error": "No payload provided"}), 400

    # user_id is implicitly checked by @login_required
    # user_settings are fetched by the decorator and stored in g

    try:
        # 1. Get user settings (including current tokens) from g
        # The decorator ensures g.user_id and g.user_settings exist if we reach here
        user_settings = g.user_settings
        current_tokens = user_settings.get('search_tokens', 0)
        user_id = g.user_id # Get user_id from g as well

        # 2. Perform initial fetch to get estimated count
        initial_scrape_data = fetch_autotrader_data(payload, initial_fetch_only=True)
        if not isinstance(initial_scrape_data, dict):
             # Handle potential errors from fetch_autotrader_data if it doesn't return a dict
             logging.error(f"Initial fetch did not return expected dictionary. Got: {initial_scrape_data}")
             return jsonify({"success": False, "error": "Initial data fetch failed unexpectedly."}), 500

        estimated_count = initial_scrape_data.get('estimated_count', 0)
        initial_results_html = initial_scrape_data.get('initial_results_html', [])
        max_page = initial_scrape_data.get('max_page', 1)

        # 3. Calculate required tokens (1 token per 100 listings, ceiling)
        required_tokens = round(max(estimated_count / 100.0, 0.1), 1) if estimated_count > 0 else 0

        print(required_tokens)
        time.sleep(10)
        # 4. Check if user has enough tokens
        if current_tokens < required_tokens:
            logging.warning(f"User {user_id} insufficient tokens. Has: {current_tokens}, Needs: {required_tokens} for {estimated_count} listings.")
            return jsonify({
                "success": False,
                "error": f"Insufficient tokens. This search requires {required_tokens} tokens ({estimated_count} listings found), but you only have {current_tokens}."
            }), 402 # Payment Required status code

        # 5. If enough tokens, proceed with fetching remaining pages
        logging.info(f"User {user_id} has sufficient tokens ({current_tokens} >= {required_tokens}). Proceeding with full scrape.")
        if max_page > 1: # Only fetch remaining if there are more pages
            remaining_results_html = fetch_autotrader_data(
                payload,
                start_page=1, # Start from page 1 (0 was already fetched)
                initial_results_html=initial_results_html, # Pass page 0 results
                max_page_override=max_page # Pass known max_page
            )
            # Note: fetch_autotrader_data returns the combined list when not initial_fetch_only
            all_results_html = remaining_results_html
        else:
            # If max_page was 1, the initial fetch got everything
            all_results_html = initial_results_html

        if not all_results_html:
            # This case might happen if initial fetch estimated > 0 but full fetch failed or returned nothing
            logging.warning(f"Initial estimate was {estimated_count}, but full fetch returned no results.")
            # Don't charge tokens if no results were actually processed
            required_tokens = 0 # Reset required tokens
            # Still return success, but with 0 results
            return jsonify({
                "success": True,
                "file_path": None, # No file saved
                "result_count": 0,
                "tokens_charged": 0,
                "tokens_remaining": current_tokens # No change
            })


        # --- Processing and Saving Results (as before, but using all_results_html) ---
        make = payload.get('Make', 'Unknown')
        model = payload.get('Model', 'Unknown')
        folder_path = f"Results/{make}_{model}"

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        file_name = f"{payload.get('YearMin', '')}-{payload.get('YearMax', '')}_{payload.get('PriceMin', '')}-{payload.get('PriceMax', '')}_{format_time_ymd_hms()}.csv"
        full_path = os.path.join(folder_path, file_name).replace("\\", "/") # Ensure forward slashes

        # Save results to CSV (save_results_to_csv expects list of dicts with 'link')
        # all_results_html is already the list of dicts from parse_html_content
        save_results_to_csv(all_results_html, payload=payload, filename=full_path, max_workers=1000)

        # Read the CSV to get the processed results for Firebase
        processed_results_for_firebase = []
        try:
            with open(full_path, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    processed_results_for_firebase.append(dict(row))
        except FileNotFoundError:
             logging.error(f"CSV file {full_path} not found after saving.")
             # Don't charge tokens if saving/reading failed
             return jsonify({"success": False, "error": "Failed to process saved results."}), 500


        # --- Save to Firebase (as before) ---
        metadata = {
            'make': make,
            'model': model,
            'yearMin': payload.get('YearMin', ''),
            'yearMax': payload.get('YearMax', ''),
            'priceMin': payload.get('PriceMin', ''),
            'priceMax': payload.get('PriceMax', ''),
            'file_name': file_name, # Just the filename, not the full path
            'timestamp': format_time_ymd_hms(),
            'estimated_listings_scanned': estimated_count, # Add scanned count
            'tokens_charged': required_tokens # Add token cost
        }

        firebase_result = save_results(user_id, processed_results_for_firebase, metadata)

        # 6. Deduct tokens and update user settings
        new_token_count = current_tokens - required_tokens
        update_result = update_user_settings(user_id, {'search_tokens': new_token_count})
        if not update_result.get('success'):
            # Log error but proceed - search was successful, token update failed
            logging.error(f"Failed to update tokens for user {user_id} after successful search. Error: {update_result.get('error')}")

        # --- Prepare Response ---
        response_data = {
            "success": True,
            "file_path": full_path, # Return the full path for potential local use
            "result_count": len(processed_results_for_firebase),
            "tokens_charged": required_tokens,
            "tokens_remaining": new_token_count
        }

        if firebase_result.get('success'):
            response_data["doc_id"] = firebase_result.get('doc_id')
        else:
             # Log error if Firebase save failed, but don't fail the whole request
             logging.error(f"Failed to save results to Firebase for user {user_id}. Error: {firebase_result.get('error')}")


        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Error in fetch_data_api: {e}", exc_info=True) # Log traceback
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/api/open_links', methods=['POST'])
@login_required
def open_links_api():
    file_path = request.json.get('file_path')
    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"})

    try:
        # Ensure the path exists before trying to open
        if not os.path.exists(file_path):
             return jsonify({"success": False, "error": f"File not found: {file_path}"})
        showcarsmain(file_path)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# Add these API endpoints to app.py

@app.route('/api/list_results')
@login_required
def list_results():
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Get results from Firebase
        results = get_user_results(user_id)

        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/get_result', methods=['POST'])
@login_required
def get_result_api():
    result_id = request.json.get('result_id')
    user_id = session.get('user_id')

    if not result_id:
        return jsonify({"success": False, "error": "No result ID provided"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Get the result from Firebase
        result = get_result(user_id, result_id)

        if not result:
            return jsonify({"success": False, "error": "Result not found"})

        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/delete_result', methods=['POST'])
@login_required
def delete_result_api():
    result_id = request.json.get('result_id')
    user_id = session.get('user_id')

    if not result_id:
        return jsonify({"success": False, "error": "No result ID provided"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Delete the result from Firebase
        result = delete_result(user_id, result_id)

        if not result.get('success'):
            return jsonify({"success": False, "error": result.get('error', 'Failed to delete result')})

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# New endpoint to delete a specific listing from a saved result
@app.route('/api/delete_listing_from_result', methods=['POST'])
@login_required
def delete_listing_from_result_api():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"}), 401

    data = request.json
    result_id = data.get('result_id')
    listing_identifier = data.get('listing_identifier') # Expecting {'Link': '...'}

    if not result_id:
        return jsonify({"success": False, "error": "Result ID not provided"}), 400
    if not listing_identifier or 'Link' not in listing_identifier:
        return jsonify({"success": False, "error": "Listing identifier (Link) not provided"}), 400

    link_to_delete = listing_identifier['Link']

    try:
        db = get_firestore_db()
        doc_ref = db.collection('users').document(user_id).collection('results').document(result_id)
        doc = doc_ref.get()

        if not doc.exists:
            return jsonify({"success": False, "error": "Result document not found"}), 404

        doc_data = doc.to_dict()
        current_results = doc_data.get('results', [])

        # Filter out the listing to delete based on the Link
        original_count = len(current_results)
        new_results = [listing for listing in current_results if listing.get('Link') != link_to_delete]
        new_count = len(new_results)

        if new_count == original_count:
            # Log if the link wasn't found, but maybe don't return error to frontend?
            # Or return success=True but with a note? For now, just log.
            logging.warning(f"Listing with link '{link_to_delete}' not found in result '{result_id}' for user '{user_id}'. No changes made.")
            # Still return success as the state matches the desired outcome (listing is gone)
            return jsonify({"success": True, "message": "Listing not found, no changes needed."})

        # Update the document with the filtered list
        doc_ref.update({'results': new_results})
        logging.info(f"Deleted listing with link '{link_to_delete}' from result '{result_id}' for user '{user_id}'.")

        return jsonify({"success": True})

    except Exception as e:
        logging.error(f"Error deleting listing from result '{result_id}' for user '{user_id}': {e}", exc_info=True)
        return jsonify({"success": False, "error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route('/favicon.ico')
def favicon():
    """
    Serves the favicon.ico file from the static folder.
    If the file doesn't exist, it returns a 404 Not Found response.
    """
    from flask import send_from_directory

    try:
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except FileNotFoundError:
        # Log that favicon wasn't found
        print("Favicon.ico not found in static directory")
        return '', 404  # Return empty response with 404 status code

@app.route('/static/index.js')
@login_required # Assuming this script is part of the logged-in app experience
def serve_main_js():
    """Serves the main index.js file for the application."""
    from flask import send_from_directory
    try:
        # Use app.static_folder which is already set to 'static'
        return send_from_directory(app.static_folder, 'index.js', mimetype='application/javascript')
    except FileNotFoundError:
        logging.error("static/index.js not found when serving via /app/index.js")
        return jsonify({"success": False, "error": "Main script file not found."}), 404

# Add these API endpoints to app.py

@app.route('/api/rename_payload', methods=['POST'])
@login_required
def rename_payload_api():
    payload_id = request.json.get('payload_id')
    new_name = request.json.get('new_name')
    user_id = session.get('user_id')

    if not payload_id or not new_name:
        return jsonify({"success": False, "error": "Missing payload ID or new name"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Get the current payload
        payload = get_payload(user_id, payload_id)
        if not payload:
            return jsonify({"success": False, "error": "Payload not found"})

        # Add a custom_name field instead of overwriting existing data
        payload_data = payload.copy()
        payload_data['custom_name'] = new_name

        # Save the updated payload
        result = update_payload(user_id, payload_id, payload_data)

        if result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result.get('error', 'Failed to rename payload')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/delete_payload', methods=['POST'])
@login_required
def delete_payload_api():
    payload_id = request.json.get('payload_id')
    user_id = session.get('user_id')

    if not payload_id:
        return jsonify({"success": False, "error": "No payload ID provided"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Delete the payload from Firebase
        result = delete_payload(user_id, payload_id)

        if result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result.get('error', 'Failed to delete payload')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/rename_result', methods=['POST'])
@login_required
def rename_result_api():
    result_id = request.json.get('result_id')
    new_name = request.json.get('new_name')
    user_id = session.get('user_id')

    if not result_id or not new_name:
        return jsonify({"success": False, "error": "Missing result ID or new name"})

    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"})

    try:
        # Get the current result
        result_data = get_result(user_id, result_id)

        if not result_data:
            return jsonify({"success": False, "error": "Result not found"})

        # Create a copy of the original document to preserve all fields
        new_result_data = result_data.copy()

        # Update the metadata with the custom name
        if 'metadata' not in new_result_data:
            new_result_data['metadata'] = {}
        new_result_data['metadata']['custom_name'] = new_name

        # Get the results array
        results = new_result_data.get('results', [])

        # Get the updated metadata
        metadata = new_result_data.get('metadata', {})

        # First delete the existing result
        delete_result_response = delete_result(user_id, result_id)
        if not delete_result_response.get('success'):
            return jsonify({"success": False, "error": delete_result_response.get('error', 'Failed to delete existing result')})

        # Then create a new result with the updated metadata
        create_result = save_results(user_id, results, metadata)

        if create_result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": create_result.get('error', 'Failed to rename result')})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# --- AI Analysis Route ---
@app.route('/api/analyze_car', methods=['POST'])
@login_required
def analyze_car_api():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "User not authenticated"}), 401

    # Check AI access permission
    user_settings = get_user_settings(user_id)
    if not user_settings.get('can_use_ai', False):
        logging.warning(f"User {user_id} denied AI analysis access.")
        return jsonify({"success": False, "error": "AI analysis access denied for this user."}), 403

    # Proceed with AI analysis if permitted
    if not gemini_model:
        return jsonify({"success": False, "error": "AI Model not configured. Check API keys."}), 500

    car_details = request.json
    if not car_details:
        return jsonify({"success": False, "error": "No car details provided."}), 400

    make = car_details.get('Make', '')
    model = car_details.get('Model', '')
    year = car_details.get('Year', '')
    trim = car_details.get('Trim', '')
    price_str = car_details.get('Price', '') # Get price string
    km_str = car_details.get('Kilometres', '') # Get km string

    # Clean and convert price/km
    price_cad = None
    try:
        if price_str:
            price_cad = float(price_str.replace('$', '').replace(',', ''))
    except ValueError:
        logging.warning(f"Could not parse price: {price_str}")

    kilometres = None
    try:
        if km_str:
             # Assuming km_str might be like "123,456 km" or just "123456"
            kilometres = int(km_str.replace(',', '').split(' ')[0])
    except ValueError:
        logging.warning(f"Could not parse kilometres: {km_str}")


    if not make or not model or not year:
        return jsonify({"success": False, "error": "Make, Model, and Year are required for analysis."}), 400

    search_summary = ""
    if search_service and SEARCH_ENGINE_ID:
        try:
            # Define expanded search queries
            queries = [
                # Top 5 Reliability Questions
                f'"{year} {make} {model}" reliability rating',
                f'"{year} {make} {model}" common problems',
                f'"{year} {make} {model}" long term reliability',
                f'"{year} {make} {model}" maintenance costs',
                f'"{year} {make} {model}" repair costs',

                # Top 5 Review & Comparison Questions
                f'"{year} {make} {model}" expert review',
                f'"{year} {make} {model}" owner reviews',
                f'"{year} {make} {model}" pros and cons',
                f'"{year} {make} {model}" vs competitor cars',
                f'"{year} {make} {model}" is it a good car to buy',

                # Top 3 Forum/Community Questions
                f'"{year} {make} {model}" owners forum',
                f'"{year} {make} {model}" reddit reviews',
                f'"{year} {make} {model}" online community feedback',

                # Top 5 Practical & Technical Questions
                f'"{make} {model}" recalls and TSBs',
                f'"{year} {make} {model}" fuel economy MPG',
                f'"{year} {make} {model}" safety ratings',
                f'"{year} {make} {model}" cargo space',
                f'"{year} {make} {model}" warranty details',

                # Top 5 Buying & Pricing Questions
                f'"{year} {make} {model}" fair market price',
                f'"{year} {make} {model}" used car value',
                f'"{year} {make} {model}" lease or buy deals',
                f'"{year} {make} {model}" incentives rebates',
                f'"{year} {make} {model}" best time to buy',

                # 2 Subjective/Experience Questions
                f'"{year} {make} {model}" owner satisfaction',
                f'"{year} {make} {model}" things to know before buying',
            ]
            search_results_text = []
            num_results_per_query = 10 # Limit results per query slightly more to keep context manageable
            max_search_retries = 3
            initial_search_delay = 0.5 # seconds

            for query in queries:
                logging.info(f"Performing web search: {query}")
                items = []
                for attempt in range(max_search_retries):
                    try:
                        # Execute the search
                        result = search_service.cse().list(
                            q=query,
                            cx=SEARCH_ENGINE_ID,
                            num=num_results_per_query
                        ).execute()
                        items = result.get('items', [])
                        break # Success, exit retry loop
                    except HttpError as e:
                        logging.warning(f"Search attempt {attempt + 1} failed for query '{query}': {e}")
                        # Check if it's a rate limit or server error (worth retrying)
                        if e.resp.status in [429, 500, 503] and attempt < max_search_retries - 1:
                            delay = initial_search_delay * (2 ** attempt)
                            logging.info(f"Retrying in {delay:.2f} seconds...")
                            time.sleep(delay)
                        else:
                            logging.error(f"Search failed permanently for query '{query}' after {attempt + 1} attempts.")
                            break # Non-retryable error or max retries reached
                    except Exception as e: # Catch other potential errors
                         logging.error(f"Unexpected error during search for query '{query}': {e}")
                         break # Don't retry on unexpected errors

                # Process the items found (or note if none were found after retries)
                if items:
                    search_results_text.append(f"Search results for '{query}':")
                    for item in items:
                        title = item.get('title')
                        link = item.get('link')
                        snippet = item.get('snippet', '').replace('\n', ' ')
                        search_results_text.append(f"- {title} ({link}): {snippet}")
                else:
                     search_results_text.append(f"No significant results found for '{query}' (or search failed).")
                search_results_text.append("\n") # Add spacing

            search_summary = "\n".join(search_results_text)

        except Exception as e:
            # Catch potential errors in the overall search block setup
            logging.error(f"Error during web search setup or processing: {e}")
            search_summary = "Error occurred during web search processing."
    else:
        search_summary = "Web search is not configured."

    # Get current exchange rates
    rates = get_exchange_rates(EXCHANGE_RATE_API_KEY)
    rates_info = "Exchange rates not available."
    if rates:
        rates_info = f"""Current Approximate Exchange Rates:
- 1 CAD = {rates.get('USD_per_CAD', 'N/A'):.3f} USD
- 1 CAD = {rates.get('EUR_per_CAD', 'N/A'):.3f} EUR
- 1 CAD = {rates.get('GBP_per_CAD', 'N/A'):.3f} GBP
- 1 USD = {rates.get('CAD_per_USD', 'N/A'):.2f} CAD
- 1 EUR = {rates.get('CAD_per_EUR', 'N/A'):.2f} CAD
- 1 GBP = {rates.get('CAD_per_GBP', 'N/A'):.2f} CAD"""

    # Construct prompt for Gemini
    prompt = f"""
Analyze the reliability and potential value of the following car based on the provided details, web search context, and exchange rates.

Car Listing Details:
Make: {make}
Model: {model}
Year: {year}
Trim: {trim if trim else 'N/A'}
Listed Price: {f'{price_cad:,.0f} CAD' if price_cad is not None else 'N/A'}
Kilometres: {f'{kilometres:,} km' if kilometres is not None else 'N/A'}

{rates_info}

Web Search Context (Reliability, Problems, Reviews, etc.):
{search_summary}
Based on ALL the information provided (car details, price, mileage, web context, exchange rates), please provide a comprehensive analysis covering:

1.  **Reliability Summary:**
    *   Known Issues: List specific common problems reported (use bullet points).
    *   Positive Points: Mention positive reliability aspects found.
    *   Things to Check: Suggest specific inspection points for a potential buyer.
    *   Overall Reliability Sentiment: Summarize the general sentiment (positive, negative, mixed).

2.  **Price Analysis:**
    *   Compare the listed price ({f'{price_cad:,.0f} CAD' if price_cad is not None else 'N/A'}) and mileage ({f'{kilometres:,} km' if kilometres is not None else 'N/A'}) to any relevant pricing information or comparable vehicles mentioned in the web search context. Remember to account for currency differences using the provided exchange rates (assume online prices might be USD, EUR, or GBP unless specified otherwise).
    *   Provide a deal rating (e.g., Excellent Deal, Good Deal, Fair Price, Slightly High, Overpriced) based on this comparison and the car's reliability profile. Justify the rating briefly.

3.  **Negotiation Tips:**
    *   Based on the reliability issues found and the price analysis, provide 2-3 specific, actionable negotiation points or questions a buyer could use to potentially lower the price.

Format the response clearly using headings (like **Reliability Summary**, **Price Analysis**, **Negotiation Tips**) and bullet points. Be objective and base the analysis ONLY on the provided information.
"""

    try:
        logging.info("Sending request to Gemini API...")
        response = gemini_model.generate_content(prompt)
        ai_summary = response.text
        logging.info("Received response from Gemini API.")
        return jsonify({"success": True, "summary": ai_summary})

    except Exception as e:
        logging.error(f"Error generating content with Gemini: {e}")
        # Check for specific Gemini errors if needed
        # e.g., if hasattr(e, 'response') and e.response.prompt_feedback: ...
        return jsonify({"success": False, "error": f"AI analysis failed: {e}"}), 500
# --- End AI Analysis Route ---


if __name__ == '__main__':
    # Create necessary directories for legacy support
    if not os.path.exists("Queries"):
        os.makedirs("Queries")
    if not os.path.exists("Results"):
        os.makedirs("Results")

    print("Firebase initialization:", "Successful" if firebase_initialized else "Failed")
    print("Server running at http://localhost:5000")
    print("Go to the login page at http://localhost:5000/login")
    app.run(debug=True, port=5000)
