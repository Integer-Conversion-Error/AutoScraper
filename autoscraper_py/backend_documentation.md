# AutoScraper Backend Python Documentation

This document provides a comprehensive overview of the Python backend files for the AutoScraper application, detailing their purpose, key functionalities, and interactions.

---

## `autoscraper_py/app.py`

**File Overview:**
This is the main entry point for the Flask web application. It handles the initialization of the Flask app, configuration settings (sessions, logging), integration with external services like Firebase, Google Gemini AI, and Google Custom Search, and the registration of various Flask Blueprints that define the application's routes.

**Key Components/Functionality:**

*   **`app = Flask(__name__, static_folder='../static', template_folder='../templates')`**:
    *   Initializes the Flask application instance.
    *   Configures `static_folder` and `template_folder` to serve static assets and HTML templates.
*   **Configuration (`app.config`, `app.secret_key`):**
    *   Sets up session management (`SESSION_TYPE`, `SESSION_PERMANENT`, `PERMANENT_SESSION_LIFETIME`, `SESSION_USE_SIGNER`).
    *   Generates a random `secret_key` for session security.
*   **Logging:**
    *   Configures basic logging to console and potentially a file (`autoscraper.log`).
*   **Firebase Initialization:**
    *   Calls `initialize_firebase()` from `firebase_config.py` to set up the Firebase Admin SDK.
    *   Logs success or failure of Firebase initialization.
*   **AI & External Services Initialization:**
    *   Loads API keys (GEMINI_API_KEY, SEARCH_API_KEY, SEARCH_ENGINE_ID, EXCHANGE_RATE_API_KEY) from `config.json`.
    *   **Gemini AI (`genai.configure`, `app.gemini_model`):**
        *   Configures the Google Gemini AI model using the `GEMINI_API_KEY`.
        *   Attaches a `GenerativeModel` instance (e.g., 'gemini-2.0-flash-thinking-exp-01-21') to the `app` context for use in blueprints.
    *   **Google Custom Search (`build("customsearch", "v1", ...)`):**
        *   Configures the Google Custom Search service using `SEARCH_API_KEY` and `SEARCH_ENGINE_ID`.
        *   Attaches the `search_service` instance and `SEARCH_ENGINE_ID` to the `app` context.
    *   **Exchange Rate API:**
        *   Attaches `EXCHANGE_RATE_API_KEY` to the `app` context.
*   **Blueprint Registration:**
    *   Imports various Flask Blueprints from the `routes` and `tasks` submodules:
        *   `views_bp` (for public and main application views)
        *   `auth_bp` (for authentication routes)
        *   `api_data_bp` (for dynamic data API)
        *   `api_payloads_bp` (for saved search payload API)
        *   `api_results_bp` (for search results API)
        *   `api_settings_bp` (for user settings API)
        *   `tasks_bp` (for Celery task status API)
    *   Registers each blueprint with the main `app` instance.
*   **Main Execution Block (`if __name__ == '__main__':`):**
    *   Creates `Queries` and `Results` directories if they don't exist (for legacy/local file storage).
    *   Prints server access information.
    *   Runs the Flask development server (`app.run(debug=True, port=5000)`).

**Dependencies and Interactions:**
*   Imports `firebase_config` for Firebase initialization and user settings.
*   Imports `auth_decorator` (though the decorator itself is used directly by blueprints, not defined here).
*   Imports various blueprints from `routes` and `tasks` to register their routes.
*   Relies on `config.json` for API keys.

---

## `autoscraper_py/auth_decorator.py`

**File Overview:**
This file defines the `login_required` decorator, a crucial component for securing Flask routes. It ensures that only authenticated users can access specific endpoints, handling both session-based and token-based authentication.

**Key Components/Functionality:**

*   **`login_required(f)`**:
    *   **Purpose:** A custom Flask decorator that wraps view functions to enforce authentication.
    *   **Parameters:** `f` (the Flask view function to be decorated).
    *   **Functionality:**
        1.  **Session Check:** First, it checks if `user_id` is present in the Flask `session`.
            *   If found, it periodically re-validates the user against Firebase (using `get_user` from `firebase_config.py`) to ensure the user still exists and to refresh session data (email, display name). This re-validation happens approximately once per hour for performance.
            *   It fetches `user_settings` using `get_user_settings` from `firebase_config.py`.
            *   It stores `user_id` and `user_settings` in Flask's `g` object, making them easily accessible within the decorated view function.
            *   If the user is authenticated and valid, the original function `f` is called.
        2.  **Bearer Token Check (for API requests):** If `user_id` is not in the session, it checks the `Authorization` header for a `Bearer` token.
            *   It calls `verify_id_token` from `firebase_config.py` to validate the Firebase ID token.
            *   If the token is valid, it populates the session with user information (UID, email, display name) and fetches user settings.
            *   For API requests (`/api/` paths), it proceeds to call the original function `f`.
            *   For web pages, it redirects to the login page if authentication fails.
        3.  **Redirection/Error Handling:**
            *   If no valid session or token is found for an API request, it returns a JSON error response with a 401 (Unauthorized) status.
            *   For regular web pages requiring login, it flashes a warning message and redirects the user to the `auth.login` page.
            *   It includes logic to prevent redirect loops on public authentication pages (`auth.login`, `auth.register`) and other public views (`views.landing`, `views.pricing`, etc.).

**Dependencies and Interactions:**
*   Imports `flask` components (`request`, `jsonify`, `redirect`, `url_for`, `session`, `flash`, `g`, `current_app`).
*   Imports `functools.wraps` for proper decorator behavior.
*   Imports `time` for session validation timing.
*   Imports `logging` for internal logging.
*   Imports `firebase_config` for `verify_id_token`, `get_user`, and `get_user_settings`.

---

## `autoscraper_py/AutoScraper.py`

**File Overview:**
This is the core web scraping module responsible for fetching, processing, and caching car listing data from AutoTrader.ca. It handles API interactions, concurrent data fetching, and persistent data storage using a CSV cache.

**Key Components/Functionality:**

*   **Logging Configuration:** Sets up a dedicated logger for `AutoScraper` activities, outputting to both a file (`autoscraper.log`) and the console.
*   **CSV Cache Configuration (`CACHE_FILE`, `CACHE_HEADERS`):**
    *   Defines the filename (`autoscraper_cache.csv`) and the expected headers for the CSV cache file.
*   **`load_cache(filepath=CACHE_FILE)`**:
    *   **Purpose:** Loads existing data from the CSV cache file into a Python dictionary, using the 'Link' as the key.
    *   **Returns:** A dictionary representing the cache. Returns an empty dictionary if the file is not found or an error occurs.
    *   **Note:** Includes a warning if CSV headers don't match `CACHE_HEADERS`.
*   **`append_to_cache(data_rows, filepath=CACHE_FILE, headers=CACHE_HEADERS)`**:
    *   **Purpose:** Appends new data rows (list of dictionaries) to the CSV cache file.
    *   **Functionality:** If the file doesn't exist or is empty, it writes the header row first.
*   **`write_cache(cache_dict, filepath=CACHE_FILE, headers=CACHE_HEADERS)`**:
    *   **Purpose:** Overwrites the entire CSV cache file with the contents of the provided cache dictionary.
    *   **Functionality:** Writes the header row, then all values from the dictionary.
*   **`get_proxy_from_file(filename="proxyconfig.json")`**:
    *   **Purpose:** Reads proxy configuration from a JSON file.
    *   **Returns:** A dictionary containing proxy settings. Handles `FileNotFoundError` and `json.JSONDecodeError`.
*   **`fetch_autotrader_data(params, ...)`**:
    *   **Purpose:** Fetches car listing data from the AutoTrader.ca API based on provided search parameters.
    *   **Parameters:**
        *   `params` (dict): Search criteria (Make, Model, PriceMin, YearMin, etc.).
        *   `initial_fetch_only` (bool): If `True`, only fetches the first page to estimate total count and max pages.
        *   `start_page`, `initial_results_html`, `max_page_override`: Used for continuing a fetch in a second stage (e.g., from a Celery task).
        *   `task_instance`: (Optional) A Celery task instance for progress updates.
    *   **Functionality:**
        1.  **Parameter Cleaning:** Cleans and validates input parameters (e.g., converting "Any" to `None`, ensuring numeric types).
        2.  **Session Setup:** Creates a `requests.Session` with a custom User-Agent, JSON headers, and proxy settings.
        3.  **`fetch_page(page, session)` (Inner Function):**
            *   Performs a single POST request to the AutoTrader API for a given page.
            *   Includes exponential backoff retry logic for network errors or empty responses.
            *   Parses `SearchResultsDataJson` and `AdsHtml` from the response.
            *   Returns parsed HTML results, `maxPage`, and `SearchResultsDataJson` dictionary.
        4.  **Initial Fetch Logic:** If `initial_fetch_only` is `True`, it calls `fetch_page(0)` and returns an estimated total count, initial HTML results, and max pages.
        5.  **Full Fetch Logic:** If performing a full fetch, it fetches page 0, then uses `concurrent.futures.ThreadPoolExecutor` to concurrently fetch all remaining pages.
        6.  **Progress Updates:** Updates progress via the `task_instance` if provided.
        7.  **Duplicate Removal:** Calls `remove_duplicates_exclusions` (from `AutoScraperUtil.py`) to remove duplicate listings.
    *   **Returns:** A list of dictionaries, each representing a car listing.
*   **`extract_vehicle_info(url)`**:
    *   **Purpose:** Extracts detailed vehicle information from a single AutoTrader listing URL.
    *   **Functionality:**
        1.  Creates a `requests.Session` with headers and proxies.
        2.  Fetches the URL with exponential backoff retry logic for rate limiting (HTTP 429 or specific text patterns).
        3.  Calls `parse_html_content_to_json` (from `AutoScraperUtil.py`) to extract embedded JSON.
        4.  Calls `extract_vehicle_info_from_json` to parse the JSON into a structured dictionary.
    *   **Returns:** A dictionary of vehicle details.
*   **`extract_vehicle_info_from_json(json_content)`**:
    *   **Purpose:** Parses a JSON object (typically from `extract_vehicle_info`) to extract specific car details.
    *   **Functionality:** Extracts data from `HeroViewModel` and `Specifications` sections of the JSON.
    *   **Returns:** A dictionary with standardized keys for car information (Make, Model, Price, Kilometres, etc.).
*   **`process_links_and_update_cache(data, transformed_exclusions, max_workers=1000, task_instance=None)`**:
    *   **Purpose:** Orchestrates the process of checking links against the CSV cache, fetching data for new/stale links, applying exclusions, and updating the cache.
    *   **Parameters:**
        *   `data` (list): List of link dictionaries (from `fetch_autotrader_data`).
        *   `transformed_exclusions` (list): List of strings to exclude.
        *   `max_workers`: Max concurrent workers for fetching.
        *   `task_instance`: (Optional) A Celery task instance for progress updates.
    *   **Functionality:**
        1.  Loads the `persistent_cache` from `autoscraper_cache.csv`.
        2.  Iterates through input `data`:
            *   If a link is in the cache and `date_cached` is today, it's a fresh hit (and filtered).
            *   If a link is in the cache but stale, it's marked for re-fetching.
            *   If a link is not in the cache, it's a miss and marked for fetching.
        3.  Uses `concurrent.futures.ThreadPoolExecutor` to fetch data for all marked links concurrently using `extract_vehicle_info`.
        4.  For each fetched item, it adds the 'Link' and `date_cached` to the `car_info` and applies the exclusion filter.
        5.  Updates the `persistent_cache` in memory with new/refreshed data.
        6.  Writes the entire updated `persistent_cache` back to `autoscraper_cache.csv` using `write_cache`.
    *   **Returns:** A list of dictionaries for all links relevant to the current search (cached or newly fetched and not excluded).

**Dependencies and Interactions:**
*   Imports `requests` for HTTP requests.
*   Imports `json`, `csv`, `os`, `time`, `logging`, `datetime`, `concurrent.futures`.
*   Imports `GetUserSelection` (though `get_user_responses` and `cleaned_input` are not directly used in the main scraping logic here, they are part of the CLI flow).
*   Imports `AutoScraperUtil` for various helper functions like `parse_html_content`, `remove_duplicates_exclusions`, `transform_strings`, `cls`, `convert_km_to_double`.

---

## `autoscraper_py/AutoScraperUtil.py`

**File Overview:**
This file contains a collection of utility functions that support the main `AutoScraper` module and other parts of the backend. These functions handle HTML parsing, data cleaning, file operations, API interactions for dynamic data, and data filtering.

**Key Components/Functionality:**

*   **`clean_model_name(model_name)`**:
    *   **Purpose:** Removes trailing ` (number)` suffixes from car model names (e.g., "3 Series (1433)" becomes "3 Series").
    *   **Returns:** The cleaned model name string.
*   **`showcarsmain(file_path, column_name="Link")`**:
    *   **Purpose:** Reads a CSV file and opens links from a specified column in new Chrome browser tabs.
    *   **Functionality:** Limits opening to the first 15 links to prevent overwhelming the browser.
*   **`parse_html_content(html_content, exclusions=[])`**:
    *   **Purpose:** Parses HTML content (typically search results pages) to extract basic listing details (link, title, price, mileage, location).
    *   **Functionality:** Uses `BeautifulSoup` to navigate the HTML structure.
    *   **Returns:** A list of dictionaries, each representing a car listing with extracted details. (Note: Exclusion filtering is now handled elsewhere).
*   **`convert_km_to_double(km_string)`**:
    *   **Purpose:** Converts a string representing kilometers (e.g., "109,403 km") into an integer.
    *   **Returns:** The numeric kilometer value.
*   **`file_initialisation()`**:
    *   **Purpose:** Creates `Results` and `Queries` directories if they do not already exist.
*   **`parse_html_content_to_json(html_content)`**:
    *   **Purpose:** Extracts a JSON object embedded within an HTML string.
    *   **Functionality:** Assumes the JSON is enclosed in `{...}` within the HTML.
    *   **Returns:** The parsed JSON content as a Python dictionary.
*   **`save_json_to_file(json_content, file_name="output.json")`**:
    *   **Purpose:** Saves a Python dictionary as a JSON file.
*   **`save_html_to_file(html_content, file_name="output.html")`**:
    *   **Purpose:** Saves an HTML string to a file.
*   **`parse_string_to_json(input_string)`**:
    *   **Purpose:** Parses a string representation of a dictionary into a Python dictionary (JSON object).
    *   **Functionality:** Uses `ast.literal_eval` for safe evaluation.
*   **`cls()`**:
    *   **Purpose:** Clears the console screen (cross-platform).
*   **`read_payload_from_file(filename)`**:
    *   **Purpose:** Reads a JSON payload from a specified file.
*   **`extract_car_makes_from_html(html_content, popular=True)`**:
    *   **Purpose:** Extracts car makes from `<optgroup>` elements within AutoTrader.ca's HTML (either "Popular Makes" or "All Makes").
    *   **Returns:** A list of car make strings.
*   **`get_html_from_url(url)`**:
    *   **Purpose:** Fetches the raw HTML content of a given URL using a custom User-Agent.
    *   **Returns:** The HTML content as a string, or `None` on failure.
*   **`get_all_makes(popular=True)`**:
    *   **Purpose:** Fetches all car makes (popular or all) by scraping the AutoTrader.ca homepage.
    *   **Functionality:** Uses `get_html_from_url` and `extract_car_makes_from_html`.
*   **`get_models_for_make(make)`**:
    *   **Purpose:** Fetches available models for a given car make by sending a POST request to the AutoTrader API.
    *   **Returns:** A dictionary of models and their counts.
*   **`get_colors(make, model, trim=None)`**:
    *   **Purpose:** Fetches available exterior colors for a given car make, model, and optional trim via the AutoTrader API.
    *   **Functionality:** Cleans the model name before the API call.
    *   **Returns:** A dictionary of colors and their counts.
*   **`get_trims_for_model(make, model)`**:
    *   **Purpose:** Fetches available trims for a given car make and model via the AutoTrader API.
    *   **Functionality:** Cleans the model name before the API call.
    *   **Returns:** A dictionary of trims and their counts.
*   **`transform_strings(input_list)`**:
    *   **Purpose:** Takes a list of strings and returns a new list containing uppercase, lowercase, and capitalized versions of each original string. Used for robust keyword matching.
*   **`read_json_file(file_path="output.json")`**:
    *   **Purpose:** Reads a JSON file and returns its content as a Python dictionary.
*   **`format_time_ymd_hms(seconds=None)`**:
    *   **Purpose:** Formats a given time (in seconds since epoch) into a "yyyy-mm-dd\_hh-mm-ss" string in the local timezone.
*   **`remove_duplicates_exclusions(arr, excl=[])`**:
    *   **Purpose:** Removes duplicate dictionaries from a list based on their 'link' value, while also ensuring links are full URLs. (Note: Exclusion filtering by content is now handled in `process_links_and_update_cache`).
*   **`print_response_size(response)`**:
    *   **Purpose:** Prints the size of a `requests.Response` object in bytes and kilobytes.
*   **`filter_dicts(data, exclusion_strings)`**:
    *   **Purpose:** Filters a list of dictionaries, removing any dictionary if any of its values contain any of the specified exclusion strings (case-insensitive).
*   **`filter_csv(input_file, output_file, payload)`**:
    *   **Purpose:** Filters rows in a CSV file based on exclusion strings from a payload, then applies an inclusion filter.
*   **`keep_if_contains(input_file, output_file, required_string=None)`**:
    *   **Purpose:** Filters rows in a CSV file, keeping only those where at least one column contains the `required_string` (case-insensitive).

**Dependencies and Interactions:**
*   Imports `ast`, `csv`, `json`, `os`, `re`, `webbrowser`, `requests`, `bs4` (BeautifulSoup).
*   Used extensively by `AutoScraper.py` and `GetUserSelection.py` for data fetching, parsing, and manipulation.
*   Used by Flask routes (`api_data.py`, `api_payloads.py`, `api_results.py`) for data retrieval and processing.

---

## `autoscraper_py/extract_initial_state.py`

**File Overview:**
This script is a standalone utility designed to extract a specific JSON object, `window.INITIAL_STATE`, embedded within an HTML file. This pattern is common in web applications that render initial data on the server-side. It also extracts a sub-section of this data, `pages.srp.items`, which likely represents search results.

**Key Components/Functionality:**

*   **`extract_and_save_initial_state(html_file_path)`**:
    *   **Purpose:** Reads an HTML file, finds the `window.INITIAL_STATE` JavaScript variable, extracts its JSON value, and saves it to a new JSON file.
    *   **Parameters:** `html_file_path` (path to the input HTML file).
    *   **Functionality:**
        1.  Reads the content of the HTML file.
        2.  Uses a regular expression (`re.search`) to locate the `<script>` tag containing `window.INITIAL_STATE = {JSON_OBJECT};`.
        3.  Extracts the JSON string.
        4.  Parses the JSON string using `json.loads`. Includes basic error handling for `json.JSONDecodeError` and attempts a simple cleanup (e.g., removing trailing commas) if parsing initially fails.
        5.  Constructs an output filename by appending " INITIAL STATE.json" to the base HTML filename.
        6.  Saves the extracted JSON data to the new file with pretty-printing (`indent=4`).
        7.  Calls `extract_and_save_srp_items` to further process the extracted `INITIAL_STATE`.
*   **`extract_and_save_srp_items(initial_state_json, base_name, output_dir)`**:
    *   **Purpose:** Extracts the list of search results items from the `initial_state_json` and saves them to a separate JSON file.
    *   **Parameters:**
        *   `initial_state_json` (dict): The parsed `window.INITIAL_STATE` JSON.
        *   `base_name` (str): The base name of the original HTML file.
        *   `output_dir` (str): The directory where the output file should be saved.
    *   **Functionality:**
        1.  Safely navigates the `initial_state_json` dictionary to find `['pages']['srp']['items']`.
        2.  If the `items` list is found and is indeed a list, it saves this list to a file named `{base_name} ITEMS.json`.
        3.  Includes error handling for `KeyError` or `TypeError` if the expected path or type is not found.
*   **Command-Line Interface (`if __name__ == "__main__":`)**:
    *   Allows the script to be run directly from the command line, taking the HTML file path as an argument using `argparse`.

**Dependencies and Interactions:**
*   Imports `argparse` for command-line argument parsing.
*   Imports `json` for JSON encoding/decoding.
*   Imports `os` for path manipulation.
*   Imports `re` for regular expressions.
*   This script is a utility and does not directly interact with the main Flask application or other core modules at runtime, but it processes data that might originate from or be similar to data handled by the scraper.

---

## `autoscraper_py/firebase_config.py`

**File Overview:**
This file provides a centralized interface for interacting with Firebase services, including Firebase Authentication and Firestore (NoSQL database). It handles SDK initialization, user management, and CRUD operations for search payloads and results.

**Key Components/Functionality:**

*   **`initialize_firebase()`**:
    *   **Purpose:** Initializes the Firebase Admin SDK.
    *   **Functionality:** Attempts to load credentials from `firebase_credentials.json` first. If not found, it tries to load credentials from the `FIREBASE_CREDENTIALS` environment variable (expected as a JSON string).
    *   **Returns:** `True` on successful initialization, `False` otherwise.
*   **`get_firestore_db()`**:
    *   **Purpose:** Returns the Firestore database client instance.
    *   **Returns:** `firestore.Client` object, or `None` if an error occurs.
*   **Firebase Authentication Functions:**
    *   **`create_user(email, password, display_name=None)`**:
        *   **Purpose:** Creates a new user in Firebase Authentication.
        *   **Returns:** A dictionary indicating success/failure and the user's UID.
    *   **`verify_id_token(id_token)`**:
        *   **Purpose:** Verifies a Firebase ID token (received from client-side authentication).
        *   **Returns:** A dictionary indicating success/failure and the decoded token information (`user`).
    *   **`get_user(uid)`**:
        *   **Purpose:** Retrieves a user's record by their UID from Firebase Authentication.
        *   **Returns:** `firebase_admin.auth.UserRecord` object, or `None`.
*   **Firestore Operations for Payloads (`users/{user_id}/payloads` subcollection):**
    *   **`save_payload(user_id, payload)`**:
        *   **Purpose:** Saves a user's search payload (search criteria) to Firestore.
        *   **Functionality:** Adds `created_at` and `updated_at` timestamps.
        *   **Returns:** A dictionary with success status and the document ID.
    *   **`get_user_payloads(user_id)`**:
        *   **Purpose:** Retrieves all saved search payloads for a specific user.
        *   **Returns:** A list of dictionaries, each containing payload data, its ID, and creation timestamp.
    *   **`get_payload(user_id, payload_id)`**:
        *   **Purpose:** Retrieves a specific search payload by its ID for a given user.
        *   **Returns:** The payload data as a dictionary, or `None` if not found.
    *   **`update_payload(user_id, payload_id, payload_data)`**:
        *   **Purpose:** Updates an existing search payload.
        *   **Functionality:** Updates the `updated_at` timestamp.
        *   **Returns:** A dictionary with success status.
    *   **`delete_payload(user_id, payload_id)`**:
        *   **Purpose:** Deletes a specific search payload.
        *   **Returns:** A dictionary with success status.
*   **User Settings Functions (`users/{user_id}` document):**
    *   **`get_user_settings(user_id)`**:
        *   **Purpose:** Retrieves user-specific settings (e.g., `search_tokens`, `can_use_ai`, `isPayingUser`).
        *   **Returns:** A dictionary of settings, with default values if the user document or specific fields are not found.
    *   **`update_user_settings(user_id, settings_update)`**:
        *   **Purpose:** Updates user-specific settings.
        *   **Functionality:** Uses `set(..., merge=True)` to create the document if it doesn't exist or update existing fields.
        *   **Returns:** A dictionary with success status.
    *   **`deduct_search_tokens(user_id, tokens_to_deduct)`**:
        *   **Purpose:** Atomically deducts a specified number of search tokens from a user's account.
        *   **Functionality:** Uses `firestore.Increment` for safe, concurrent updates.
        *   **Returns:** A dictionary with success status and `tokens_remaining`.
*   **Helper Function (`_delete_collection(coll_ref, batch_size)`):**
    *   **Purpose:** A recursive helper function used internally to delete all documents within a Firestore collection in batches. Essential for deleting subcollections.
*   **Firestore Results Functions (`users/{user_id}/results/{result_id}/listings` subcollection):**
    *   **`save_results(user_id, results_list, metadata)`**:
        *   **Purpose:** Saves a set of search results to Firestore.
        *   **Functionality:** Creates a main result document with `metadata` and `result_count`, then saves individual `listings` as separate documents in a subcollection using batch writes for efficiency.
        *   **Returns:** A dictionary with success status and the main result document ID.
    *   **`get_user_results(user_id)`**:
        *   **Purpose:** Retrieves metadata for all saved search results for a user. Does NOT fetch the actual listings to keep the response light.
        *   **Returns:** A list of dictionaries, each containing result metadata, ID, and creation timestamp.
    *   **`get_result(user_id, result_id)`**:
        *   **Purpose:** Retrieves a specific search result, including its metadata and all associated listings from its subcollection.
        *   **Returns:** The full result data as a dictionary, or `None` if not found.
    *   **`delete_result(user_id, result_id)`**:
        *   **Purpose:** Deletes a specific search result document and its entire 'listings' subcollection.
        *   **Functionality:** Uses `_delete_collection` to recursively delete the subcollection before deleting the main document.
        *   **Returns:** A dictionary with success status.

**Dependencies and Interactions:**
*   Imports `firebase_admin` (specifically `credentials`, `firestore`, `auth`).
*   Imports `json` and `os` for credential handling.
*   This file is a core dependency for `app.py`, `auth_decorator.py`, `tasks.py`, and all API route blueprints (`api_payloads.py`, `api_results.py`, `api_settings.py`, `auth.py`).

---

## `autoscraper_py/GetUserSelection.py`

**File Overview:**
This script provides a command-line interface for users to input and manage search parameters for car scraping. It interacts with `AutoScraperUtil.py` to fetch dynamic data like car makes and models, presenting them in an interactive, user-friendly manner.

**Key Components/Functionality:**

*   **`get_keywords_from_user(kw_type="exclude")`**:
    *   **Purpose:** Prompts the user to enter keywords (for exclusion or inclusion) and allows them to add/remove keywords through a menu.
    *   **Functionality:** Continuously prompts for input until the user stops. Provides a menu to modify the list.
    *   **Returns:** A list of transformed keywords (uppercase, lowercase, capitalized) using `transform_strings` from `AutoScraperUtil.py`.
*   **`get_user_responses()`**:
    *   **Purpose:** Orchestrates the collection of all search parameters from the user.
    *   **Functionality:**
        1.  Initializes a `payload` dictionary with default values.
        2.  Calls `get_makes_input()` to get the car make.
        3.  If a make is selected, calls `get_models_for_make()` (from `AutoScraperUtil.py`) and then `get_models_input()` to get the car model. The model name is then cleaned using `clean_model_name()` (from `AutoScraperUtil.py`).
        4.  Uses `cleaned_input()` for other parameters like address, proximity, year range, price range, and odometer range, providing default values and type validation.
        5.  Includes logical validation to ensure consistency (e.g., `PriceMin` is not greater than `PriceMax`).
        6.  Calls `get_keywords_from_user()` for exclusion keywords and `cleaned_input()` for an inclusion string.
    *   **Returns:** A dictionary (`payload`) containing all collected user inputs.
*   **`get_makes_input()`**:
    *   **Purpose:** Prompts the user to select a car make from a list of options.
    *   **Functionality:**
        1.  Fetches popular car makes using `get_all_makes(popular=True)` (from `AutoScraperUtil.py`).
        2.  Displays options in a numbered, tabular format using the `tabulate` library.
        3.  Allows the user to type `-1` to see all available makes (by calling `get_all_makes(popular=False)`).
        4.  Validates numeric input against the displayed options.
    *   **Returns:** The selected car make string.
*   **`get_models_input(models_for_make)`**:
    *   **Purpose:** Prompts the user to select a model from a given dictionary of models for a specific make.
    *   **Functionality:** Displays models in a numbered, tabular format. Validates numeric input.
    *   **Returns:** The selected model string.
*   **`cleaned_input(itemTitle, defaultval, expectedtype)`**:
    *   **Purpose:** A generic helper function for prompting user input, providing a default value, and validating the input against an `expectedtype`.
    *   **Returns:** The validated input value of the correct type.
*   **Main Execution Block (`if __name__ == "__main__":`)**:
    *   When the script is run directly, it calls `get_user_responses()` to start the interactive input process.

**Dependencies and Interactions:**
*   Imports `tabulate` for displaying data in tabular format.
*   Imports all necessary functions from `AutoScraperUtil.py` (`get_all_makes`, `get_models_for_make`, `clean_model_name`, `transform_strings`, `cls`).
*   This file is primarily for command-line interaction and is not directly used by the Flask web application's routes, but it demonstrates how a search payload can be constructed.

---

## `autoscraper_py/tasks.py`

**File Overview:**
This file defines Celery asynchronous tasks for handling long-running operations, specifically the full web scraping and data processing workflow. By offloading these tasks to a Celery worker, the main Flask application remains responsive. It also provides an API endpoint to check the status of these tasks.

**Key Components/Functionality:**

*   **Celery Configuration (`celery_app`):**
    *   Initializes a Celery application instance named `tasks`.
    *   Configures a Redis broker and backend (`redis://localhost:6379/0`).
    *   Sets up JSON serialization for tasks and results, and defines the timezone.
*   **Firebase Initialization in Worker:**
    *   Calls `initialize_firebase()` from `firebase_config.py` directly within the worker context. This ensures that each Celery worker process has its own initialized Firebase Admin SDK instance to interact with Firestore.
*   **`ProgressTask(Task)` Class:**
    *   **Purpose:** A custom Celery `Task` class that extends the base `celery.Task`.
    *   **`update_progress(self, current, total, step="Processing")`**:
        *   **Purpose:** A helper method to update the task's state to `PROGRESS` and provide metadata about the current progress (e.g., `current` item, `total` items, `step` description). This allows clients to monitor the task's execution.
*   **`@celery_app.task(bind=True, base=ProgressTask, name='tasks.scrape_and_process_task')`**:
    *   **`scrape_and_process_task(self, payload, user_id, required_tokens, initial_scrape_data)`**:
        *   **Purpose:** The main asynchronous Celery task that executes the complete car scraping and processing workflow.
        *   **Parameters:**
            *   `self`: The task instance (due to `bind=True`), allowing access to `update_progress`.
            *   `payload` (dict): The search criteria provided by the user.
            *   `user_id` (str): The ID of the user who initiated the task.
            *   `required_tokens` (float): The estimated number of tokens to charge the user.
            *   `initial_scrape_data` (dict): Contains results from a preliminary, quick scrape (e.g., `initial_results_html`, `max_page`, `estimated_count`) to optimize the full scrape.
        *   **Workflow:**
            1.  **Full Data Fetch:** Calls `fetch_autotrader_data` (from `AutoScraper.py`) to perform the full scrape, passing the `payload` and the `initial_scrape_data`. It also passes `self` to enable progress updates from within `fetch_autotrader_data`.
            2.  **Processing and Caching:** Calls `process_links_and_update_cache` (from `AutoScraper.py`) to extract detailed vehicle info, apply exclusions, and update the CSV cache. Again, `self` is passed for progress updates.
            3.  **Save to Local File:** If results are found, they are saved to a timestamped CSV file in the `Results/{Make}_{Model}/` directory structure.
            4.  **Save to Firebase:** If results are found, they are saved to Firestore using `save_results` (from `firebase_config.py`), including metadata about the search and the actual listings in a subcollection.
            5.  **Deduct Tokens:** Calls `deduct_search_tokens` (from `firebase_config.py`) to charge the user the `required_tokens`. This happens regardless of whether results were found, as the attempt was made.
            6.  **Return Final Result:** Returns a dictionary with the task's final status, local file path, result count, Firebase document ID, tokens charged, and remaining tokens.
        *   **Error Handling:** Includes robust `try-except` blocks. If an exception occurs, the task's state is set to `FAILURE`, and the exception is re-raised to be handled by Celery. Tokens are generally not deducted if the task fails before the deduction step.
*   **Flask Blueprint for Task Status (`tasks_bp`):**
    *   **Purpose:** Provides a Flask API endpoint to check the status and progress of a Celery task.
    *   **`@tasks_bp.route('/status/<task_id>')`**:
        *   **`task_status(task_id)`**:
            *   **Purpose:** Retrieves the current state and metadata of a Celery task using its `task_id`.
            *   **Functionality:** Uses `celery.result.AsyncResult` to query the task's state (`PENDING`, `PROGRESS`, `SUCCESS`, `FAILURE`).
            *   **Returns:** A JSON response containing the task ID, state, progress details (if `PROGRESS`), final result (if `SUCCESS`), or error information (if `FAILURE`).

**Dependencies and Interactions:**
*   Imports `celery`, `celery.utils.log`, `celery.result.AsyncResult`.
*   Imports `AutoScraper` for `fetch_autotrader_data` and `process_links_and_update_cache`.
*   Imports `AutoScraperUtil` for `format_time_ymd_hms`, `clean_model_name`, `transform_strings`.
*   Imports `firebase_config` for `initialize_firebase`, `save_results`, `deduct_search_tokens`, `get_firestore_db`.
*   Interacts with Redis (as the Celery broker and backend).
*   The `tasks_bp` blueprint is registered in `app.py`.

---

## `autoscraper_py/test_autoscraper.py`

**File Overview:**
This file contains a comprehensive suite of unit tests for the `AutoScraper.py` module. It uses Python's built-in `unittest` framework along with `unittest.mock` to isolate and test individual functions and their behaviors, including network requests, file operations, and data processing logic.

**Key Components/Functionality:**

*   **`TestFetchAutotraderData(unittest.TestCase)`**:
    *   Tests the `fetch_autotrader_data` function.
    *   Includes tests for:
        *   Correct parameter cleaning and application of default values.
        *   Behavior when `initial_fetch_only` is `True` (estimating count).
        *   Successful full data fetching across multiple pages using concurrent execution.
    *   Uses `@patch` decorators to mock `remove_duplicates_exclusions`, `get_proxy_from_file`, `requests.Session`, `time.sleep`, `concurrent.futures.ThreadPoolExecutor`, `AutoScraper.transform_strings`, `AutoScraper.parse_html_content`, and `concurrent.futures.as_completed`.
*   **`TestExtractVehicleInfo(unittest.TestCase)`**:
    *   Tests the `extract_vehicle_info` function.
    *   Includes tests for:
        *   Successful data extraction on the first attempt.
        *   Successful extraction after handling HTTP 429 (Too Many Requests) errors.
        *   Successful extraction after handling text-based rate limit indicators.
        *   Failure scenarios after maximum retries due to persistent rate limiting.
        *   Failure due to general `requests.exceptions.RequestException` (e.g., connection errors).
        *   Failure due to exceptions during HTML/JSON parsing.
    *   Uses `@patch` decorators to mock `requests.Session`, `AutoScraper.parse_html_content_to_json`, `AutoScraper.extract_vehicle_info_from_json`, `time.sleep`, and `AutoScraper.get_proxy_from_file`.
*   **`TestProcessLinksAndUpdateCache(unittest.TestCase)`**:
    *   Tests the `process_links_and_update_cache` function.
    *   Includes tests for:
        *   Scenario where all links are new (cache miss).
        *   Scenario where all links are fresh cache hits (no re-fetching).
        *   Scenario where all links are stale cache hits (requiring refresh).
        *   Scenario with a mixed combination of fresh, stale, and new links.
    *   Uses `@patch` decorators to mock `AutoScraper.write_cache`, `AutoScraper.extract_vehicle_info`, `AutoScraper.load_cache`, and `datetime.date`.
*   **`TestExtractVehicleInfoFromJson(unittest.TestCase)`**:
    *   Tests the `extract_vehicle_info_from_json` function.
    *   Includes tests for:
        *   Extracting data from a complete JSON structure.
        *   Extracting data when some keys or sections are missing.
        *   Extracting data when `Specifications` or `Specs` lists are empty/missing.
        *   Handling empty or `None` input.
    *   Uses `@patch` to mock `AutoScraper.convert_km_to_double`.
*   **`TestProxyFunction(unittest.TestCase)`**:
    *   Tests the `get_proxy_from_file` function.
    *   Includes tests for:
        *   Successful loading of proxy data from a JSON file.
        *   Handling `FileNotFoundError`.
        *   Handling invalid JSON content.
    *   Uses `@patch` for `builtins.open`.
*   **`TestCacheFunctions(unittest.TestCase)`**:
    *   Tests `load_cache`, `append_to_cache`, and `write_cache` functions.
    *   Includes tests for:
        *   `load_cache` when the file is not found, successful loading, and header mismatches.
        *   `append_to_cache` when writing to a new file (header written) and an existing file (no header written).
        *   `write_cache` for correctly overwriting a file with new cache data.
    *   Uses `@patch` for `builtins.open`, `os.path.isfile`, `os.path.getsize`, and `csv.DictReader`.
*   **`unittest.main()`**:
    *   Allows running all tests when the script is executed directly.

**Dependencies and Interactions:**
*   Imports `unittest`, `csv`, `os`, `io`, `requests`, `time`, `datetime`, `json`, `concurrent.futures` for testing purposes.
*   Imports the functions and constants from `AutoScraper.py` and `AutoScraperUtil.py` that are being tested.
*   Heavily relies on `unittest.mock` for creating mock objects and patching dependencies to isolate units of code for testing.

---

## `autoscraper_py/trigger_task.py`

**File Overview:**
This is a simple standalone Python script designed for manually triggering the `scrape_and_process_task` Celery task. It's primarily used for development and testing purposes, allowing developers to initiate a scraping job without interacting with the full web application.

**Key Components/Functionality:**

*   **Imports:**
    *   Imports `celery_app` and `scrape_and_process_task` from the `tasks` module.
    *   Imports `logging` for basic script logging.
*   **`task_kwargs` Dictionary:**
    *   Defines a sample dictionary containing all the arguments required by the `scrape_and_process_task`. This includes:
        *   `payload`: A sample search query (e.g., for a Ford Bronco).
        *   `user_id`: A hardcoded user ID.
        *   `required_tokens`: A sample value for the estimated tokens needed for the scrape.
        *   `initial_scrape_data`: A dictionary mimicking the output of an initial quick scrape, providing an estimated count and max pages.
*   **Main Execution Block (`if __name__ == "__main__":`)**:
    *   When the script is run directly:
        *   It attempts to send the `scrape_and_process_task` to the Celery worker using the `.delay()` method, unpacking the `task_kwargs` dictionary.
        *   It logs the successful submission of the task and its unique `task_id`.
        *   Includes a `try-except` block to catch and log any errors that occur during the task submission process.

**Dependencies and Interactions:**
*   Depends on `tasks.py` for the Celery application and task definition.
*   Requires a running Celery worker and Redis broker (as configured in `tasks.py`) for the task to be processed.
*   Does not interact with the Flask web application directly, but rather with the Celery infrastructure.

---

## `autoscraper_py/wsgi.py`

**File Overview:**
This file serves as the Web Server Gateway Interface (WSGI) entry point for the Flask application. Its primary purpose is to provide a callable application object that a WSGI server (like Gunicorn or uWSGI) can use to run the Flask application in a production or more robust development environment.

**Key Components/Functionality:**

*   **`from .app import app`**:
    *   Imports the main Flask application instance (`app`) from `autoscraper_py/app.py`. This `app` object is the WSGI callable that servers will use.
*   **Main Execution Block (`if __name__ == "__main__":`)**:
    *   This block is executed only when `wsgi.py` is run directly (e.g., `python wsgi.py`), typically for development or testing purposes.
    *   It starts the Flask development server (`app.run(debug=True, port=5000)`), making the application accessible locally.
    *   When a production WSGI server (like Gunicorn) is used, it directly imports the `app` object from this file and does not execute this `if __name__ == "__main__":` block.

**Dependencies and Interactions:**
*   Directly depends on `autoscraper_py/app.py` to get the Flask application instance.
*   It is the standard entry point for deploying Flask applications with production WSGI servers.

---

## `autoscraper_py/routes/api_ai.py`

**File Overview:**
This Flask Blueprint defines API endpoints related to AI-powered car analysis. It integrates with Google Gemini for natural language processing and Google Custom Search for gathering external context, providing users with detailed insights into car listings.

**Key Components/Functionality:**

*   **`api_ai_bp = Blueprint('api_ai', __name__, url_prefix='/api')`**:
    *   Initializes a Flask Blueprint for AI-related API routes, prefixed with `/api`.
*   **`get_exchange_rates(api_key)`**:
    *   **Purpose:** Fetches current exchange rates (CAD to USD, EUR, GBP and vice-versa) from `exchangerate-api.com`.
    *   **Parameters:** `api_key` for the exchange rate service.
    *   **Returns:** A dictionary of exchange rates or `None` on failure.
    *   **Functionality:** Uses `requests` to make an HTTP GET request and handles potential errors.
*   **`@api_ai_bp.route('/analyze_car', methods=['POST'])`**:
    *   **`analyze_car_api()`**:
        *   **Purpose:** Provides an AI-driven analysis of a car listing.
        *   **Authentication:** Protected by `@login_required`, ensuring only authenticated users can access it. It retrieves `user_id` and `user_settings` from Flask's `g` object.
        *   **Access Control:** Checks `user_settings.get('can_use_ai', False)` to ensure the user has permission to use AI analysis. Returns 403 if denied.
        *   **Service Access:** Retrieves the `gemini_model`, `search_service`, `SEARCH_ENGINE_ID`, and `EXCHANGE_RATE_API_KEY` from `current_app` (these are initialized in `app.py`). Returns 500 if the AI model is not configured.
        *   **Input:** Expects a JSON payload with car details (`Make`, `Model`, `Year`, `Trim`, `Price`, `Kilometres`).
        *   **Data Cleaning:** Cleans the `Model` name using `clean_model_name` from `AutoScraperUtil.py` and attempts to parse `Price` and `Kilometres` into numerical types.
        *   **Web Search Integration:**
            *   If Google Custom Search is configured, it performs multiple targeted searches (e.g., "reliability", "common problems", "reviews") for the specified car.
            *   Uses `search_service.cse().list().execute()` with retry logic for `HttpError` (e.g., 429 Too Many Requests).
            *   Aggregates search results snippets into a `search_summary`.
        *   **Exchange Rate Integration:** Calls `get_exchange_rates` to get current currency conversion rates.
        *   **Prompt Construction:** Dynamically builds a detailed prompt for the Gemini AI model, incorporating car details, exchange rates, and the `search_summary`. The prompt instructs the AI to provide a reliability summary, price analysis, and negotiation tips.
        *   **AI Analysis:** Sends the constructed prompt to `gemini_model.generate_content()`.
        *   **Response:** Returns a JSON response with `success: True` and the AI-generated `summary`, or `success: False` with an error message if any step fails.

**Dependencies and Interactions:**
*   Imports `logging`, `json`, `time`, `requests`.
*   Imports `flask` components (`Blueprint`, `request`, `jsonify`, `session`, `g`, `current_app`).
*   Imports `firebase_config` for `get_user_settings`.
*   Imports `googleapiclient.discovery` and `googleapiclient.errors` for Google Custom Search.
*   Imports `auth_decorator` for `login_required`.
*   Imports `AutoScraperUtil` for `clean_model_name`.
*   Relies on `app.py` to initialize and attach `gemini_model`, `search_service`, `SEARCH_ENGINE_ID`, and `EXCHANGE_RATE_API_KEY` to `current_app`.

---

## `autoscraper_py/routes/api_data.py`

**File Overview:**
This Flask Blueprint defines API endpoints that provide dynamic data for car selection, such as lists of car makes, models, trims, and colors. These endpoints are designed to be consumed by the frontend to populate dropdowns and other interactive elements in the user interface.

**Key Components/Functionality:**

*   **`api_data_bp = Blueprint('api_data', __name__, url_prefix='/api')`**:
    *   Initializes a Flask Blueprint for data-related API routes, prefixed with `/api`.
*   All endpoints in this blueprint are protected by the `@login_required` decorator, ensuring that only authenticated users can access this dynamic data.
*   **`@api_data_bp.route('/makes')`**:
    *   **`get_makes_api()`**:
        *   **Purpose:** Returns a list of car makes.
        *   **Parameters:** Accepts an optional `popular` query parameter (e.g., `/api/makes?popular=false`) to fetch all makes instead of just popular ones.
        *   **Functionality:** Calls `get_all_makes` from `AutoScraperUtil.py`.
        *   **Returns:** A JSON list of car makes.
*   **`@api_data_bp.route('/models/<make>')`**:
    *   **`get_models_api(make)`**:
        *   **Purpose:** Returns a dictionary of models available for a given car make.
        *   **Parameters:** `make` (str) - the car make, passed as a URL path parameter.
        *   **Functionality:** URL-decodes the `make` parameter and calls `get_models_for_make` from `AutoScraperUtil.py`.
        *   **Returns:** A JSON dictionary of models (keys are model names, values are counts).
*   **`@api_data_bp.route('/trims/<make>/<model>')`**:
    *   **`get_trims_api(make, model)`**:
        *   **Purpose:** Returns a dictionary of trims available for a specific car make and model.
        *   **Parameters:** `make` (str) and `model` (str), passed as URL path parameters.
        *   **Functionality:** URL-decodes `make` and `model`, then cleans the `model` name using `clean_model_name` from `AutoScraperUtil.py`. Calls `get_trims_for_model` from `AutoScraperUtil.py`.
        *   **Returns:** A JSON dictionary of trims.
*   **`@api_data_bp.route('/colors/<make>/<model>')` and `@api_data_bp.route('/colors/<make>/<model>/<trim>')`**:
    *   **`get_colors_api(make, model, trim=None)`**:
        *   **Purpose:** Returns a dictionary of exterior colors available for a specific car make, model, and optionally a trim.
        *   **Parameters:** `make` (str), `model` (str), and optional `trim` (str), passed as URL path parameters.
        *   **Functionality:** URL-decodes parameters, cleans the `model` name, and calls `get_colors` from `AutoScraperUtil.py`.
        *   **Returns:** A JSON dictionary of colors.

**Dependencies and Interactions:**
*   Imports `flask` components (`Blueprint`, `request`, `jsonify`, `session`).
*   Imports `urllib.parse.unquote` for URL decoding.
*   Imports `auth_decorator` for `login_required`.
*   Imports `AutoScraperUtil` for `get_all_makes`, `get_models_for_make`, `get_trims_for_model`, `get_colors`, and `clean_model_name`.
*   These endpoints are typically called by client-side JavaScript to dynamically populate forms and filters.

---

## `autoscraper_py/routes/api_payloads.py`

**File Overview:**
This Flask Blueprint defines API endpoints for managing user-specific search payloads (saved search criteria). It provides functionalities to create, save, list, load, rename, and delete these payloads, primarily interacting with Firestore via `firebase_config.py`.

**Key Components/Functionality:**

*   **`api_payloads_bp = Blueprint('api_payloads', __name__, url_prefix='/api')`**:
    *   Initializes a Flask Blueprint for payload management API routes, prefixed with `/api`.
*   All endpoints in this blueprint are protected by the `@login_required` decorator.
*   **`@api_payloads_bp.route('/create_payload', methods=['POST'])`**:
    *   **`create_payload()`**:
        *   **Purpose:** A simple endpoint to receive a payload structure.
        *   **Input:** Expects a JSON payload.
        *   **Returns:** A basic success response with the received payload. (Currently, it's a placeholder for potential pre-validation or processing before a formal save).
*   **`@api_payloads_bp.route('/save_payload', methods=['POST'])`**:
    *   **`save_payload_api()`**:
        *   **Purpose:** Saves a user's search payload to Firebase.
        *   **Input:** Expects a JSON object containing the `payload`.
        *   **Functionality:** Retrieves `user_id` from the session and calls `save_payload` from `firebase_config.py`.
        *   **Returns:** A success response with a "Firebase path" (e.g., `Firebase/{doc_id}`) and the `doc_id`, or an error response.
*   **`@api_payloads_bp.route('/list_payloads')`**:
    *   **`list_payloads_api()`**:
        *   **Purpose:** Retrieves and lists all saved payloads for the current user.
        *   **Functionality:** Retrieves `user_id` from the session and calls `get_user_payloads` from `firebase_config.py`.
        *   **Formatting:** Formats the retrieved payloads for frontend display, using a `custom_name` if available, or generating a descriptive name from payload details (make, model, year/price ranges) using `clean_model_name` from `AutoScraperUtil.py`.
        *   **Returns:** A JSON response with `success: True` and a list of formatted payloads (each with `name` and `id`).
*   **`@api_payloads_bp.route('/load_payload', methods=['POST'])`**:
    *   **`load_payload_api()`**:
        *   **Purpose:** Loads a specific search payload, either from Firebase or a local file (for legacy/testing).
        *   **Input:** Expects a JSON object with `file_path` (e.g., "Firebase/DOC_ID") or `doc_id`.
        *   **Functionality:**
            *   **Firebase:** If the path indicates Firebase or a `doc_id` is provided, it calls `get_payload` from `firebase_config.py`.
            *   **Legacy File:** Otherwise, it attempts to read from a local JSON file using `read_json_file` from `AutoScraperUtil.py`.
        *   **Returns:** A JSON response with `success: True` and the loaded `payload`, or an error if not found or loading fails.
*   **`@api_payloads_bp.route('/rename_payload', methods=['POST'])`**:
    *   **`rename_payload_api()`**:
        *   **Purpose:** Renames a saved payload by updating its `custom_name` field.
        *   **Input:** Expects `payload_id` and `new_name` in the JSON request.
        *   **Functionality:** Retrieves the existing payload using `get_payload`, updates its `custom_name`, and then calls `update_payload` from `firebase_config.py`.
        *   **Returns:** A success or error JSON response.
*   **`@api_payloads_bp.route('/delete_payload', methods=['POST'])`**:
    *   **`delete_payload_api()`**:
        *   **Purpose:** Deletes a specific saved payload from Firebase.
        *   **Input:** Expects `payload_id` in the JSON request.
        *   **Functionality:** Calls `delete_payload` from `firebase_config.py`.
        *   **Returns:** A success or error JSON response, with specific status codes for "not found" errors.

**Dependencies and Interactions:**
*   Imports `flask` components (`Blueprint`, `request`, `jsonify`, `session`).
*   Imports `firebase_config` for `save_payload`, `get_user_payloads`, `get_payload`, `update_payload`, `delete_payload`.
*   Imports `AutoScraperUtil` for `read_json_file` and `clean_model_name`.
*   Imports `auth_decorator` for `login_required`.
*   These endpoints form the backend API for the "Saved Searches" or "Payloads" feature in the application.

---

## `autoscraper_py/routes/api_results.py`

**File Overview:**
This Flask Blueprint defines API endpoints for managing and interacting with scraped car search results. It orchestrates the initiation of scraping tasks (via Celery), retrieval of results from Firebase, and actions like opening links or deleting results.

**Key Components/Functionality:**

*   **`api_results_bp = Blueprint('api_results', __name__, url_prefix='/api')`**:
    *   Initializes a Flask Blueprint for results management API routes, prefixed with `/api`.
*   All endpoints in this blueprint are protected by the `@login_required` decorator.
*   **`@api_results_bp.route('/fetch_data', methods=['POST'])`**:
    *   **`fetch_data_api()`**:
        *   **Purpose:** Initiates a car scraping task. This is the primary endpoint for starting a new search.
        *   **Input:** Expects a JSON `payload` (search criteria).
        *   **Functionality:**
            1.  Retrieves `user_id` and `user_settings` (including `search_tokens`) from Flask's `g` object.
            2.  Performs an **initial fetch** using `fetch_autotrader_data(payload, initial_fetch_only=True)` (from `AutoScraper.py`) to quickly get an `estimated_count` of listings and `max_page`.
            3.  Calculates `required_tokens` based on the `estimated_count`.
            4.  **Token Check:** Compares `current_tokens` with `required_tokens`. If insufficient, returns a 402 (Payment Required) error.
            5.  **Launches Celery Task:** If tokens are sufficient, it dispatches the long-running `scrape_and_process_task` (from `tasks.py`) to a Celery worker using `.delay()`. It passes the `payload`, `user_id`, `required_tokens`, and the `initial_scrape_data` (which includes the initial HTML results and max page) to the task.
        *   **Returns:** A JSON response with `success: True` and the `task_id` of the launched Celery task, allowing the frontend to poll for progress.
*   **`@api_results_bp.route('/open_links', methods=['POST'])`**:
    *   **`open_links_api()`**:
        *   **Purpose:** Opens car listing links from a local CSV file in a web browser.
        *   **Input:** Expects a JSON object with `file_path` (path to the CSV).
        *   **Functionality:** Performs basic validation to ensure the file exists and is within the `Results/` directory. Calls `showcarsmain` from `AutoScraperUtil.py`.
        *   **Returns:** A success or error JSON response.
*   **`@api_results_bp.route('/list_results')`**:
    *   **`list_results_api()`**:
        *   **Purpose:** Retrieves metadata for all saved search results for the current user.
        *   **Functionality:** Retrieves `user_id` from the session and calls `get_user_results` from `firebase_config.py`. This function only fetches metadata, not the full listings, for efficiency.
        *   **Returns:** A JSON response with `success: True` and a list of result metadata.
*   **`@api_results_bp.route('/get_result', methods=['POST'])`**:
    *   **`get_result_api()`**:
        *   **Purpose:** Retrieves a specific saved search result, including its metadata and all associated car listings.
        *   **Input:** Expects a JSON object with `result_id` (Firestore document ID).
        *   **Functionality:** Retrieves `user_id` from the session and calls `get_result` from `firebase_config.py`.
        *   **Returns:** A JSON response with `success: True` and the full `result` data (including `metadata` and `results` list), or an error if not found.
*   **`@api_results_bp.route('/delete_result', methods=['POST'])`**:
    *   **`delete_result_api()`**:
        *   **Purpose:** Deletes a specific saved search result and all its associated listings from Firebase.
        *   **Input:** Expects a JSON object with `result_id`.
        *   **Functionality:** Retrieves `user_id` from the session and calls `delete_result` from `firebase_config.py`.
        *   **Returns:** A success or error JSON response.
*   **`@api_results_bp.route('/delete_listing_from_result', methods=['POST'])`**:
    *   **`delete_listing_from_result_api()`**:
        *   **Purpose:** Deletes a single car listing from within a saved search result in Firebase.
        *   **Input:** Expects `result_id` and `listing_identifier` (a dictionary containing the `Link` of the listing to delete).
        *   **Functionality:** Directly queries the 'listings' subcollection in Firestore for the specified `Link` and deletes the matching document.
        *   **Returns:** A success response (even if the listing wasn't found, as the desired state is achieved) or an error.
*   **`@api_results_bp.route('/rename_result', methods=['POST'])`**:
    *   **`rename_result_api()`**:
        *   **Purpose:** Renames a saved search result by updating its `custom_name` in the metadata.
        *   **Input:** Expects `result_id` and `new_name`.
        *   **Functionality:** Updates the `metadata.custom_name` field of the result document in Firestore.
        *   **Returns:** A success or error JSON response.

**Dependencies and Interactions:**
*   Imports `os`, `csv`, `time`, `logging`.
*   Imports `flask` components (`Blueprint`, `request`, `jsonify`, `session`, `g`, `current_app`).
*   Imports `AutoScraperUtil` for `format_time_ymd_hms`, `showcarsmain`, `clean_model_name`, `transform_strings`.
*   Imports `AutoScraper` for `fetch_autotrader_data`.
*   Imports `firebase_config` for `get_user_results`, `get_result`, `delete_result`, `get_firestore_db`.
*   Imports `auth_decorator` for `login_required`.
*   Imports `tasks` for `scrape_and_process_task`.
*   This blueprint is central to the application's core functionality, linking the frontend UI to the scraping logic and Firebase data storage.

---

## `autoscraper_py/routes/api_settings.py`

**File Overview:**
This Flask Blueprint defines API endpoints for managing user-specific settings within the application. These settings typically include parameters like `search_tokens` (for controlling usage of scraping features) and `can_use_ai` (for enabling/disabling AI analysis features).

**Key Components/Functionality:**

*   **`api_settings_bp = Blueprint('api_settings', __name__, url_prefix='/api')`**:
    *   Initializes a Flask Blueprint for user settings API routes, prefixed with `/api`.
*   All endpoints in this blueprint are protected by the `@login_required` decorator, ensuring that only authenticated users can view or modify their settings.
*   **`@api_settings_bp.route('/get_user_settings', methods=['GET'])`**:
    *   **`get_user_settings_api()`**:
        *   **Purpose:** Retrieves the current settings for the logged-in user.
        *   **Functionality:** Gets the `user_id` from the session (which is populated by the `login_required` decorator) and calls `get_user_settings` from `firebase_config.py`.
        *   **Default Handling:** If no settings document is found for the user in Firestore (e.g., for a new user), it logs a warning and returns a set of default settings (`{'search_tokens': 0, 'can_use_ai': False}`).
        *   **Returns:** A JSON response with `success: True` and the user's `settings` dictionary.
*   **`@api_settings_bp.route('/update_user_settings', methods=['POST'])`**:
    *   **`update_user_settings_api()`**:
        *   **Purpose:** Updates specific settings for the logged-in user.
        *   **Input:** Expects a JSON payload containing the settings to update (e.g., `{"search_tokens": 100, "can_use_ai": true}`).
        *   **Functionality:**
            1.  Retrieves `user_id` from the session.
            2.  Extracts `search_tokens` and `can_use_ai` from the request JSON.
            3.  **Input Validation:**
                *   Validates that `search_tokens` is a non-negative integer.
                *   Validates that `can_use_ai` is a boolean.
                *   Returns a 400 (Bad Request) error if validation fails or if no valid settings are provided for update.
            4.  Calls `update_user_settings` from `firebase_config.py` to apply the changes to the user's document in Firestore.
            5.  If the update is successful, it fetches the *newly updated* settings using `get_user_settings` to ensure the client receives the most current state.
        *   **Returns:** A JSON response with `success: True` and the `updated_settings`, or an error response if the update fails.

**Dependencies and Interactions:**
*   Imports `logging`.
*   Imports `flask` components (`Blueprint`, `request`, `jsonify`, `session`, `g`).
*   Imports `firebase_config` for `get_user_settings` and `update_user_settings`.
*   Imports `auth_decorator` for `login_required`.
*   These endpoints are typically used by an administrative panel or a user's profile page to manage their application permissions and usage limits.

---

## `autoscraper_py/routes/auth.py`

**File Overview:**
This Flask Blueprint handles user authentication processes, including login, registration, and logout. It integrates with Firebase Authentication for secure user management, primarily relying on client-side Firebase SDK for initial authentication and then verifying tokens on the server.

**Key Components/Functionality:**

*   **`auth_bp = Blueprint('auth', __name__)`**:
    *   Initializes a Flask Blueprint named `auth`. This blueprint does not have a URL prefix, meaning its routes are at the application's root (e.g., `/login`, `/register`).
*   **`@auth_bp.route('/login', methods=['GET', 'POST'])`**:
    *   **`login()`**:
        *   **Purpose:** Handles user login.
        *   **GET Request:** If a user is already logged in (checked via `session['user_id']`), it redirects them to the main application interface (`views.app_interface`). Otherwise, it renders the `login.html` template.
        *   **POST Request:**
            1.  Expects a Firebase ID token (`idToken`) from the client-side (after successful Firebase client-side authentication).
            2.  Calls `verify_id_token` from `firebase_config.py` to validate the token with Firebase.
            3.  If the token is valid, it extracts user information (UID, email, display name) from the decoded token and stores it in the Flask `session`.
            4.  Flashes a success message and redirects the user to `views.app_interface`.
            5.  If token verification fails or no token is provided, it flashes an error message and re-renders `login.html`.
*   **`@auth_bp.route('/register', methods=['GET', 'POST'])`**:
    *   **`register()`**:
        *   **Purpose:** Handles user registration.
        *   **Functionality:** Currently, this route only renders the `register.html` template. The actual user creation logic (which would typically involve `firebase_config.create_user` after client-side Firebase registration) is expected to be added here if server-side registration is required.
*   **`@auth_bp.route('/logout')`**:
    *   **`logout()`**:
        *   **Purpose:** Handles user logout.
        *   **Functionality:**
            1.  Clears the Flask server-side session (`session.clear()`).
            2.  Logs the logout event.
            3.  Renders the `logout.html` template. This template is designed to trigger the Firebase client-side sign-out process and then redirect the user to the landing page (`views.landing`).

**Dependencies and Interactions:**
*   Imports `flask` components (`Blueprint`, `request`, `render_template`, `redirect`, `url_for`, `session`, `flash`).
*   Imports `firebase_config` for `verify_id_token`.
*   Interacts with Firebase Authentication (via `firebase_config.py`) and the client-side Firebase SDK.
*   Redirects to routes defined in `views.py`.

---

## `autoscraper_py/routes/views.py`

**File Overview:**
This Flask Blueprint defines the application's public-facing web pages and the main application interface. It handles rendering HTML templates and serving static assets like the favicon and the main JavaScript file.

**Key Components/Functionality:**

*   **`views_bp = Blueprint('views', __name__)`**:
    *   Initializes a Flask Blueprint named `views`. This blueprint does not have a URL prefix, meaning its routes are at the application's root (e.g., `/`, `/app`).
*   **`@views_bp.route('/')`**:
    *   **`landing()`**:
        *   **Purpose:** Serves the public landing page.
        *   **Functionality:** If a user is already logged in (checked via `session['user_id']`), it redirects them to the main application interface (`views.app_interface`). Otherwise, it renders `landing.html`.
*   **`@views_bp.route('/app')`**:
    *   **`app_interface()`**:
        *   **Purpose:** Serves the main application interface for logged-in users.
        *   **Authentication:** Protected by the `@login_required` decorator, ensuring only authenticated users can access it.
        *   **Functionality:** Renders `index.html`, passing the user's `display_name` from the session to the template.
*   **`@views_bp.route('/pricing')`**:
    *   **`pricing()`**:
        *   **Purpose:** Serves the public pricing page.
        *   **Functionality:** Renders `pricing.html`.
*   **`@views_bp.route('/about')`**:
    *   **`about()`**:
        *   **Purpose:** Serves the public about page.
        *   **Functionality:** Renders `about.html`.
*   **`@views_bp.route('/terms')`**:
    *   **`terms()`**:
        *   **Purpose:** Serves the terms and conditions page.
        *   **Functionality:** Renders `terms.html`.
*   **`@views_bp.route('/favicon.ico')`**:
    *   **`favicon()`**:
        *   **Purpose:** Serves the `favicon.ico` file.
        *   **Functionality:** Uses `send_from_directory` to serve the favicon from the `static` folder. Returns a 404 if the file is not found.
*   **`@views_bp.route('/static/index.js')`**:
    *   **`serve_main_js()`**:
        *   **Purpose:** Serves the main `index.js` JavaScript file for the application.
        *   **Authentication:** Protected by `@login_required`, implying this script contains logic relevant only to logged-in users.
        *   **Functionality:** Uses `send_from_directory` to serve `index.js` from the configured `static_folder` of the `current_app`. Returns a 404 if the file is not found.

**Dependencies and Interactions:**
*   Imports `flask` components (`Blueprint`, `render_template`, `redirect`, `url_for`, `session`, `current_app`, `send_from_directory`, `jsonify`).
*   Imports `os` for path manipulation (used in `favicon` route).
*   Imports `auth_decorator` for `login_required`.
*   These routes define the user-facing web pages and static assets that make up the application's frontend.
