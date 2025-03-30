from flask import request, jsonify, redirect, url_for, session, flash, g
from functools import wraps
import time
import logging # Import logging
from firebase_config import verify_id_token, get_user, get_user_settings # Import get_user_settings

def login_required_with_app(app, f):
    """
    Enhanced login_required decorator that ensures session persistence
    and proper authentication across requests.
    
    Args:
        app: The Flask application instance
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
                        return redirect(url_for('login'))
            except Exception as e:
                # Log the error but don't disrupt the user experience
                print(f"Error validating user: {e}")
                
            # Fetch user settings and check payment status
            logging.info(f"Decorator: Checking settings for user_id: {user_id}") # Log User ID
            user_settings = get_user_settings(user_id)
            logging.info(f"Decorator: Fetched user_settings: {user_settings}") # Log fetched settings
            # is_paying = user_settings.get('isPayingUser', False) # Removed isPayingUser check
            # logging.info(f"Decorator: isPayingUser check result: {is_paying} (Type: {type(is_paying)})") # Log check result and type

            # if not is_paying: # Removed isPayingUser check
            #     # User is not a paying user
            #     logging.warning(f"Decorator: Access denied for user {user_id} to {request.path}. Reason: Not a paying user.") # Log denial
            #     if request.path.startswith('/api/'):
            #         return jsonify({"success": False, "error": "Access denied. Requires an active subscription."}), 403
            #     else:
            #         flash('This feature requires an active subscription.', 'warning')
            #         return redirect(url_for('pricing')) # Redirect to pricing page

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
                logging.info(f"Decorator (Token Auth): Checking settings for user_id: {user_id}") # Log User ID
                user_settings = get_user_settings(user_id)
                logging.info(f"Decorator (Token Auth): Fetched user_settings: {user_settings}") # Log fetched settings
                # is_paying = user_settings.get('isPayingUser', False) # Removed isPayingUser check
                # logging.info(f"Decorator (Token Auth): isPayingUser check result: {is_paying} (Type: {type(is_paying)})") # Log check result and type

                # if not is_paying: # Removed isPayingUser check
                #     # User is not a paying user
                #     logging.warning(f"Decorator (Token Auth): Access denied for user {user_id} to {request.path}. Reason: Not a paying user.") # Log denial
                #     if request.path.startswith('/api/'):
                #         return jsonify({"success": False, "error": "Access denied. Requires an active subscription."}), 403
                #     else:
                #         flash('This feature requires an active subscription.', 'warning')
                #         return redirect(url_for('pricing')) # Redirect to pricing page

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
                return redirect(url_for('login'))
        
        # If no token is provided in a header for API requests
        if request.path.startswith('/api/'):
            return jsonify({"success": False, "error": "Authentication required"}), 401
        
        # For regular pages without authentication, redirect to login
        if request.path != '/login' and request.path != '/register':
            flash('Please log in to access this page', 'warning')
        return redirect(url_for('login'))
    
    return decorated_function
