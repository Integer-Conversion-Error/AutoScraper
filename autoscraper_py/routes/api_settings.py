import logging
from flask import Blueprint, request, jsonify, session, g
from ..firebase_config import get_user_settings, update_user_settings
from ..auth_decorator import login_required # Import the updated decorator

# Create the blueprint
api_settings_bp = Blueprint('api_settings', __name__, url_prefix='/api')

# No placeholder decorator needed anymore

@api_settings_bp.route('/get_user_settings', methods=['GET'])
@login_required # Apply actual decorator
def get_user_settings_api():
    user_id = session.get('user_id') # Already checked by decorator

    settings = get_user_settings(user_id)
    # Ensure settings are returned even if the document doesn't exist yet (defaults)
    if settings is None:
         # This case might indicate an issue or a new user. Return defaults.
         # Defaults should ideally be defined centrally, maybe in firebase_config.py
         # For now, return an empty dict or basic defaults.
         logging.warning(f"No settings found for user {user_id}, returning defaults.")
         settings = {'search_tokens': 0, 'can_use_ai': False} # Example defaults

    return jsonify({"success": True, "settings": settings})

@api_settings_bp.route('/update_user_settings', methods=['POST'])
@login_required # Apply actual decorator
def update_user_settings_api():
    user_id = session.get('user_id')
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
        # Fetch updated settings to return the current state
        updated_settings = get_user_settings(user_id)
        return jsonify({"success": True, "settings": updated_settings})
    else:
        logging.error(f"Failed to update settings for user {user_id}: {result.get('error')}")
        return jsonify({"success": False, "error": result.get('error', 'Failed to update settings')}), 500
