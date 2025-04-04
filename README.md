# AutoScraper Web Application

## Overview

AutoScraper is a web application designed to streamline the process of searching for vehicles on AutoTrader.ca. It allows users to define detailed search criteria (payloads), execute searches concurrently, filter results based on inclusion/exclusion keywords, save search parameters and results, and leverage AI for in-depth analysis of specific listings.

## Rust Rewrite (Work In Progress)

A rewrite of this application in Rust is currently underway, located in the `autoscraper_rust/` directory.

**Motivation:**
*   Explore the performance benefits and type safety offered by Rust.
*   Leverage modern asynchronous programming with Tokio and Actix-web.
*   Build a more robust and potentially scalable backend.

**Technology Stack (Rust Version):**
*   **Backend Framework:** Actix-web
*   **Asynchronous Runtime:** Tokio
*   **HTTP Client:** Reqwest
*   **Serialization/Deserialization:** Serde
*   **Database/Auth:** Firebase (via REST API or potential Rust SDKs) - *Integration details in `firestore.rs` and `auth.rs`*
*   **Templating:** Askama (inferred from common Rust web practices)
*   **Frontend:** Similar HTML, CSS, JavaScript structure as the Python version, served by Actix-web.

**Status:**
*   Work In Progress (WIP). Core features like authentication, static page serving, and basic API interactions are being developed.

*(Setup and usage instructions for the Rust version will be added to this README or within the `autoscraper_rust/` directory as development progresses.)*

## Problem Solved

Finding specific vehicles, especially niche models or configurations, on large platforms like AutoTrader can be time-consuming. Users often need to manually sift through numerous listings, apply filters repeatedly, and cross-reference information externally (e.g., reliability data, market pricing). AutoScraper aims to solve this by:

1.  **Automating Searches:** Running searches based on saved, detailed criteria.
2.  **Batch Processing:** Fetching and processing large numbers of listings efficiently.
3.  **Advanced Filtering:** Allowing users to specify exclusion keywords (e.g., "salvage", "rebuilt") and required inclusion keywords (e.g., "leather", "navigation") to quickly narrow down relevant listings.
4.  **Persistence:** Saving search payloads and results for later use and review.
5.  **AI-Powered Insights:** Providing automated analysis of a listing's reliability, price competitiveness (including currency conversion awareness), and negotiation points directly within the application.

## Key Features

*   **Web-Based UI:** User-friendly interface built with Flask and Bootstrap.
*   **User Authentication:** Secure login/registration using Firebase Authentication.
*   **Detailed Search Criteria:** Specify Make, Model, Year Range, Price Range, Mileage Range, Location, Distance, New/Used status, and Photo requirements.
*   **Keyword Filtering:**
    *   **Exclusions:** Automatically filter out listings containing specified keywords in their details.
    *   **Inclusions:** Filter results to only show listings containing a specific required keyword.
*   **Concurrent Scraping:** Utilizes `concurrent.futures` for faster fetching of search result pages and individual vehicle details from AutoTrader.ca.
*   **Payload Management:**
    *   Create and save complex search parameter sets (payloads) to Firebase Firestore.
    *   Load, rename, and delete saved payloads.
*   **Results Management:**
    *   Save search results (including detailed vehicle info) to Firebase Firestore.
    *   View saved results in a sortable table within a modal.
    *   Rename and delete saved result sets.
*   **CSV Export:** Download search results as a CSV file.
*   **Batch Link Opening:** Open multiple selected listing links in browser tabs.
*   **AI Analysis (Google Gemini & Custom Search):**
    *   For any listing in the results, trigger an AI analysis.
    *   Performs targeted web searches (using Google Custom Search) for reliability info, common problems, reviews, TSBs, etc.
    *   Fetches current exchange rates (CAD/USD/EUR/GBP).
    *   Sends car details, web search context, and exchange rates to Google Gemini AI.
    *   Displays a formatted summary including:
        *   Reliability assessment (known issues, positives, things to check).
        *   Price analysis and deal rating (considering mileage and currency conversion).
        *   Actionable negotiation tips.
    *   Includes retry logic with exponential backoff for web search API calls.
*   **Proxy Support:** Configurable proxy usage for scraping requests (`proxyconfig.json`).
*   **Logging:** Records scraper activity and potential errors to `autoscraper.log`.

## Technology Stack

*   **Backend:** Python, Flask
*   **Frontend:** HTML, CSS, JavaScript, Bootstrap 5
*   **Scraping:** `requests`, `BeautifulSoup4`
*   **Concurrency:** `concurrent.futures`
*   **Database/Auth:** Firebase (Authentication, Firestore)
*   **AI:** Google Generative AI (Gemini), Google Custom Search API
*   **Exchange Rates:** ExchangeRate-API.com
*   **Markdown Parsing:** Showdown.js (via CDN)

## Project Structure

```
.
├── .gitattributes
├── .gitignore
├── app.py                  # Flask application logic, API routes
├── auth_decorator.py       # Decorator for requiring login on routes
├── AutoScraper.code-workspace # VS Code workspace file
├── AutoScraper.py          # Core AutoTrader scraping logic
├── AutoScraperBackground.jpg # Background image (likely unused by web app)
├── AutoScraperUtil.py      # Utility functions for scraping, parsing, file handling
├── config.json             # Stores API keys (GEMINI, SEARCH, EXCHANGE_RATE) - **DO NOT COMMIT**
├── firebase_config.py      # Firebase initialization and interaction functions
├── GetUserSelection.py     # (Likely legacy) Console input functions
├── proxyconfig.json        # Proxy configuration (optional) - **DO NOT COMMIT if contains credentials**
├── Queries/                # (Likely legacy) Directory for saving console payloads
├── Results/                # Directory for saving CSV results
├── static/
│   └── favicon.ico         # Favicon
├── templates/
│   ├── index.html          # Main application page template
│   ├── login.html          # Login page template
│   ├── logout.html         # Logout intermediate page template
│   └── register.html       # Registration page template
└── README.md               # This file
```

## Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd AutoScraper
    ```
2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install Flask requests beautifulsoup4 google-api-python-client google-generativeai firebase-admin
    # If using lxml for potentially faster parsing (optional):
    # pip install lxml
    ```
    *(Note: Ensure `lxml` is installed if you modify `AutoScraperUtil.py` to use it as the BeautifulSoup parser)*

## Configuration (API Keys)

This application requires several API keys to function fully, especially for the AI analysis features.

1.  **Create `config.json`:** In the project's root directory, create a file named `config.json`.
2.  **Add API Keys:** Populate `config.json` with your keys. **IMPORTANT:** Keep this file secure and do not commit it to version control (it should be listed in `.gitignore`).

    ```json
    {
      "GEMINI_API_KEY": "YOUR_GOOGLE_AI_GEMINI_API_KEY",
      "SEARCH_API_KEY": "YOUR_GOOGLE_CUSTOM_SEARCH_API_KEY",
      "SEARCH_ENGINE_ID": "YOUR_PROGRAMMABLE_SEARCH_ENGINE_ID_CX",
      "EXCHANGE_RATE_API_KEY": "YOUR_EXCHANGERATE-API.COM_API_KEY"
    }
    ```
    *   **`GEMINI_API_KEY`**: Obtain from [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   **`SEARCH_API_KEY`**: Obtain from [Google Cloud Console](https://console.cloud.google.com/) (enable "Custom Search API").
    *   **`SEARCH_ENGINE_ID`**: Obtain from [Google Programmable Search Engine control panel](https://programmablesearchengine.google.com/controlpanel/all) after creating a search engine instance. Configure this instance to search relevant sites (e.g., `reddit.com/r/cars`, specific car forums) or the entire web. (this project uses the entire web for now)
    *   **`EXCHANGE_RATE_API_KEY`**: Obtain a free key from [ExchangeRate-API.com](https://www.exchangerate-api.com/).

3.  **Firebase Configuration:**
    *   Set up a Firebase project at [https://firebase.google.com/](https://firebase.google.com/).
    *   Enable **Authentication** (Email/Password method).
    *   Enable **Firestore** database.
    *   Download your Firebase Admin SDK service account key (a JSON file).
    *   **Crucially:** Update `firebase_config.py` with the correct path to your downloaded service account key file and potentially your Firebase project details if they differ from the placeholders.
    *   Update the `firebaseConfig` object in `templates/login.html`, `templates/register.html`, and `templates/index.html` with your Firebase project's web configuration details (apiKey, authDomain, projectId, etc.).

4.  **Proxy Configuration (Optional):**
    *   If you need to use proxies for scraping, create a `proxyconfig.json` file in the root directory. Format it according to how `AutoScraper.py` expects to read it (likely `{"http": "http://user:pass@host:port", "https": "https://user:pass@host:port"}`).

## Usage

1.  **Run the Flask Application:**
    ```bash
    python app.py
    ```
2.  **Access the Web Interface:** Open your browser and navigate to `http://localhost:5000`.
3.  **Register/Login:** Use the web interface to register a new account or log in. Authentication is handled by Firebase.
4.  **Define Search:** Use the form to select Make, Model, Year, Price, Mileage, Location, and other filters (including exclusion/inclusion keywords).
5.  **Create Payload:** Click "Create Payload" to generate the search parameters based on the form.
6.  **Save Payload (Optional):** Click "Save Current" to save the current payload to Firebase for later use. You'll be prompted to name it.
7.  **Load Payload (Optional):** Select a previously saved payload from the dropdown and click "Load Selected" to populate the form.
8.  **Fetch Data:** Click "Fetch Data". The backend will start scraping AutoTrader based on the current payload. Progress might be logged in the console where `app.py` is running.
9.  **View Results:** Once fetching is complete, the "Current Search Results" card will update. Click "View Selected" under "Saved Results Management" (after selecting the newly created result set) to open a modal displaying the listings in a table.
10. **Analyze Results:**
    *   In the results modal table, click the "Analyze" (<i class="bi bi-robot"></i>) button next to any listing.
    *   A new modal will appear, showing a loading indicator while the backend performs web searches and calls the Gemini AI.
    *   The AI's analysis (reliability, price comparison, negotiation tips) will be displayed in the modal.
11. **Other Actions:**
    *   Use "Open Links" / "Open Selected Links" to open listings in your browser.
    *   Use "Download CSV" / "Download Selected Result" to get the data in CSV format.
    *   Use the "Rename" and "Delete" buttons in the Payload and Results management sections as needed.

## AI Analysis Feature Details

*   **Input:** Takes Make, Model, Year, Trim, Price (CAD), and Kilometers of the selected car.
*   **Web Search:** Uses Google Custom Search API to query for reliability, common problems, reviews, TSBs, complaints, and specific forums (e.g., Reddit). Uses retry logic for robustness.
*   **Exchange Rates:** Fetches current CAD vs. USD/EUR/GBP rates via ExchangeRate-API.com.
*   **AI Model:** Uses Google Gemini (configured in `app.py`).
*   **Prompting:** Provides the AI with structured car details, exchange rates, and web search snippets. Asks for specific analysis points: Reliability Summary, Price Analysis (with currency awareness and deal rating), and Negotiation Tips.
*   **Output:** Displays the AI's formatted response (Markdown rendered as HTML) in a dedicated modal.

## Potential Future Improvements

*   More sophisticated web scraping error handling.
*   User configuration for target forums in Programmable Search Engine.
*   Caching exchange rates to reduce API calls.
*   Background task queue (e.g., Celery) for long-running scrape jobs instead of blocking web requests.
*   More detailed progress reporting during scraping.
*   UI improvements for displaying AI analysis and search context.
*   Allowing users to customize the AI prompt.
*   Integration with other data sources (e.g., CarFax reports if APIs exist).
*   **TODO:** Implement robust security measures (input validation, rate limiting, dependency scanning).
*   **TODO:** Refactor backend to handle concurrent data fetch requests from multiple users efficiently and without blocking (e.g., using asynchronous tasks/workers like Celery or RQ).
*   **TODO:** Improve code rigidity and scalability (e.g., comprehensive testing, better error handling, modular design).
*   **TODO:** Enhance mobile-friendliness (Responsive Design):
    *   Review and adjust Bootstrap grid layouts (`col-xs-*`, `col-sm-*`, `col-md-*`, `col-lg-*`) for optimal display on various screen sizes.
    *   Use CSS media queries to apply specific styles for different viewport widths (e.g., adjusting font sizes, margins, padding).
    *   Ensure interactive elements (buttons, forms, modals) are easily usable on touchscreens (sufficient size and spacing).
    *   Test the application thoroughly on different mobile devices and browsers (or using browser developer tools).
