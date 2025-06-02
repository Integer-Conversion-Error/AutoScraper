import os
import json
import secrets
import logging
import requests # Keep for get_exchange_rates if moved back or to util
import google.generativeai as genai
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
from datetime import timedelta
from functools import wraps # Keep wraps if needed by login_required here
from flask import Flask, session, redirect, url_for, g, current_app, jsonify # Keep necessary Flask imports

# Import Firebase config functions needed for initialization and potentially direct use
from .firebase_config import (
    initialize_firebase,
    get_firestore_db,
    get_user_settings # Needed by the decorator logic
    # Add other direct use functions if any remain after refactoring
)

# Decorator is imported directly by blueprints now
# from .auth_decorator import login_required

# --- App Initialization ---
app = Flask(__name__, static_folder='../static', template_folder='../templates')
app.secret_key = secrets.token_hex(32)

# --- Configuration ---
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_USE_SIGNER'] = True

# --- Logging ---
logging.basicConfig(level=logging.INFO)
# You might want to configure Flask's logger more specifically:
# handler = logging.FileHandler('app.log') # Example: Log to a file
# handler.setLevel(logging.INFO)
# app.logger.addHandler(handler)
app.logger.info("Flask App Initializing...")

# --- Firebase Initialization ---
try:
    firebase_initialized = initialize_firebase()
    if firebase_initialized:
        app.logger.info("Firebase initialized successfully.")
        # Make DB accessible globally if needed, or rely on get_firestore_db()
        # app.db = get_firestore_db() # Example if attaching DB to app
    else:
        app.logger.error("Firebase initialization failed.")
except Exception as e:
    app.logger.error(f"Firebase initialization failed: {e}", exc_info=True)
    firebase_initialized = False


# --- AI & External Services Initialization ---
# Load API Keys from config.json
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
    GEMINI_API_KEY = config.get('GEMINI_API_KEY')
    SEARCH_API_KEY = config.get('SEARCH_API_KEY')
    SEARCH_ENGINE_ID = config.get('SEARCH_ENGINE_ID')
    EXCHANGE_RATE_API_KEY = config.get('EXCHANGE_RATE_API_KEY')
except FileNotFoundError:
    app.logger.error("config.json not found. AI/Search/Exchange features may be limited.")
    GEMINI_API_KEY = None
    SEARCH_API_KEY = None
    SEARCH_ENGINE_ID = None
    EXCHANGE_RATE_API_KEY = None
except json.JSONDecodeError:
    app.logger.error("Error decoding config.json.")
    GEMINI_API_KEY = None
    SEARCH_API_KEY = None
    SEARCH_ENGINE_ID = None
    EXCHANGE_RATE_API_KEY = None
except Exception as e:
    app.logger.error(f"An unexpected error occurred loading config.json: {e}", exc_info=True)
    GEMINI_API_KEY = None
    SEARCH_API_KEY = None
    SEARCH_ENGINE_ID = None
    EXCHANGE_RATE_API_KEY = None

# Configure Gemini
app.gemini_model = None # Initialize attribute on app
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # Attach the model to the app context for blueprints
        app.gemini_model = genai.GenerativeModel('gemini-2.0-flash-thinking-exp-01-21') # Or your chosen model
        app.logger.info("Gemini AI Model configured and attached to app.")
    except Exception as e:
        app.logger.error(f"Failed to configure Gemini AI Model: {e}", exc_info=True)
else:
    app.logger.warning("GEMINI_API_KEY not found. AI analysis will be disabled.")

# Configure Google Search
app.search_service = None # Initialize attribute on app
app.SEARCH_ENGINE_ID = SEARCH_ENGINE_ID # Attach ID to app
if SEARCH_API_KEY and SEARCH_ENGINE_ID:
    try:
        # Attach the service to the app context
        app.search_service = build("customsearch", "v1", developerKey=SEARCH_API_KEY)
        app.logger.info("Google Custom Search service configured and attached to app.")
    except Exception as e:
        app.logger.error(f"Failed to configure Google Custom Search service: {e}", exc_info=True)
else:
    app.logger.warning("SEARCH_API_KEY or SEARCH_ENGINE_ID not found. Web search will be disabled.")

# Attach Exchange Rate Key to app
app.EXCHANGE_RATE_API_KEY = EXCHANGE_RATE_API_KEY
if not EXCHANGE_RATE_API_KEY:
     app.logger.warning("EXCHANGE_RATE_API_KEY not found. Exchange rate features may be limited.")


# --- Define Actual Login Decorator ---
# The login_required decorator is now defined in auth_decorator.py
# and imported directly by the blueprints that need it.
# No need to define it here anymore.


# --- Import and Register Blueprints ---
# Import blueprint objects AFTER app and login_required are defined
from .routes.views import views_bp
from .routes.auth import auth_bp
from .routes.api_data import api_data_bp
from .routes.api_payloads import api_payloads_bp
from .routes.api_results import api_results_bp
from .routes.api_settings import api_settings_bp
from .routes.api_ai import api_ai_bp
from .tasks import tasks_bp # Import the tasks blueprint

# Register blueprints with the app
app.register_blueprint(views_bp)
app.register_blueprint(auth_bp) # No prefix needed, routes defined from root
app.register_blueprint(api_data_bp) # Prefix '/api' defined in blueprint
app.register_blueprint(api_payloads_bp) # Prefix '/api' defined in blueprint
app.register_blueprint(api_results_bp) # Prefix '/api' defined in blueprint
app.register_blueprint(api_settings_bp) # Prefix '/api' defined in blueprint
app.register_blueprint(api_ai_bp) # Prefix '/api' defined in blueprint
app.register_blueprint(tasks_bp) # Register tasks blueprint (prefix '/api/tasks' defined in blueprint)

app.logger.info("Blueprints registered.")

# --- Main Execution ---
if __name__ == '__main__':
    # Create necessary directories for legacy support (if still needed)
    # Consider moving this logic elsewhere if applicable
    if not os.path.exists("Queries"):
        os.makedirs("Queries")
        app.logger.info("Created 'Queries' directory.")
    if not os.path.exists("Results"):
        os.makedirs("Results")
        app.logger.info("Created 'Results' directory.")

    print(f"Firebase initialization: {'Successful' if firebase_initialized else 'Failed'}")
    print(f"Gemini Model: {'Configured' if app.gemini_model else 'Not Configured'}")
    print(f"Search Service: {'Configured' if app.search_service else 'Not Configured'}")
    print("---")
    print("Server running at http://localhost:5000")
    print("Access the app via landing page: http://localhost:5000/")
    print("Or login directly: http://localhost:5000/login")
    print("---")
    # Set debug=False for production
    # Use host='0.0.0.0' to make accessible on network
    app.run(debug=True, port=5000)
