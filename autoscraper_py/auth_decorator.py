from flask import request, jsonify, redirect, url_for, session, flash, g
from functools import wraps
import time
import logging # Import logging
from flask import current_app # Import current_app if needed for logging or config
from .firebase_config import verify_id_token, get_user, get_user_settings # Import get_user_settings

def login_required(f):
    """
    Enhanced login_required decorator that ensures session persistence
    and proper authentication across requests. Relies on Flask request context.

    Args:
        f: The function to decorate
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # First, check if the user is already in session
        if 'user_id' in session:
            user_id = session.get('user_id')
            
            # Re-validate the user if needed
            try:
                # Only re-validate occasionally for performance
                if 'last_validated' not in session or (time.time() - session.get('last_validated', 0) > 3600):
                    # Verify that the user still exists in Firebase
                    user = get_user(user_id)
                    if user:
                        # Update session with fresh data
                        session['last_validated'] = time.time()
                        session['email'] = user.email
                        session['display_name'] = user.display_name or user.email
                        session.modified = True  # Mark session as modified
                    else:
                        # User no longer exists, clear session
                        session.clear()
                        flash('Your session has expired. Please log in again.', 'warning')
                        return redirect(url_for('auth.login')) # Use blueprint name
            except Exception as e:
                # Log the error using current_app logger if available
                # current_app.logger.error(f"Error validating user {user_id}: {e}", exc_info=True)
                print(f"Error validating user {user_id}: {e}") # Keep print for now

            # Fetch user settings and check payment status
            logging.info(f"Decorator: Checking settings for user_id: {user_id}") # Log User ID
            user_settings = get_user_settings(user_id)
            logging.info(f"Decorator: Fetched user_settings: {user_settings}") # Log fetched settings
            # Payment check logic is commented out, no changes needed here

            # Store user_id and settings in g for potential use in the route
            g.user_id = user_id
            g.user_settings = user_settings

            # User is authenticated and paying, proceed
            return f(*args, **kwargs)

        # If not in session, check for Bearer token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]
            result = verify_id_token(token)
            
            if result['success']:
                user_info = result['user']
                # Store user information in session
                session['user_id'] = user_info.get('uid')
                session['email'] = user_info.get('email')
                session['display_name'] = user_info.get('name', user_info.get('email', 'User'))
                session['last_validated'] = time.time()
                session.modified = True  # Mark session as modified

                # Fetch user settings and check payment status (after token verification)
                user_id = user_info.get('uid')
                # Use logger if available
                # logging.info(f"Decorator (Token Auth): Checking settings for user_id: {user_id}") # Log User ID
                user_settings = get_user_settings(user_id)
                # logging.info(f"Decorator (Token Auth): Fetched user_settings: {user_settings}") # Log fetched settings

                # Payment check logic is commented out, no changes needed here

                # Store user_id and settings in g for potential use in the route
                g.user_id = user_id
                g.user_settings = user_settings

                # User is authenticated and paying, proceed
                # If it's an API request, continue
                if request.path.startswith('/api/'):
                    return f(*args, **kwargs)
                    
                # For web pages, we might want to redirect to ensure a clean URL
                # But this causes problems with the auth flow, so we'll just proceed
                return f(*args, **kwargs)
            else:
                # For API endpoints, return JSON response
                if request.path.startswith('/api/'):
                    return jsonify({"success": False, "error": "Authentication failed"}), 401
                # For web pages, redirect to login
                flash('Authentication failed. Please log in again.', 'danger')
                return redirect(url_for('auth.login')) # Use blueprint name
        
        # If no token is provided in a header for API requests
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        # For regular pages without authentication, redirect to login
        # Check against blueprint endpoints
        if request.endpoint and not request.endpoint.startswith('auth.'): # Avoid redirect loop from login/register
             # Check if the requested endpoint is public (part of views_bp but not requiring login)
             # This check might need refinement based on public routes
             public_endpoints = ['views.landing', 'views.pricing', 'views.about', 'views.terms', 'views.favicon']
             if request.endpoint not in public_endpoints:
                flash('Please log in to access this page', 'warning')
                return redirect(url_for('auth.login')) # Use blueprint name

        # If it's the login/register page itself or already handled, proceed (or let Flask handle 404)
        # This final redirect might be redundant if Flask handles unauthenticated access correctly via the decorator
        # Let's remove the final redirect for now, as the decorator should handle unauthorized access.
        # return redirect(url_for('auth.login')) # Use blueprint name - REMOVED

    return decorated_function
