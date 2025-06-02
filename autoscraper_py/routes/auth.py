from flask import Blueprint, request, render_template, redirect, url_for, session, flash
from ..firebase_config import verify_id_token # Import necessary Firebase functions

# Create the blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to the app interface
    if 'user_id' in session:
        return redirect(url_for('views.app_interface')) # Use blueprint name

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
                return redirect(url_for('views.app_interface')) # Use blueprint name
            else:
                flash('Authentication failed: ' + result.get('error', 'Unknown error'), 'danger')
        else:
            flash('No authentication token provided', 'danger')

    # If it's a GET request or login failed
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # This page will handle user registration (currently just renders template)
    # If POST logic is added later, it should go here.
    return render_template('register.html')

@auth_bp.route('/logout')
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
    return render_template('logout.html', redirect_url=url_for('views.landing')) # Use blueprint name
