from flask import Blueprint, request, jsonify, session
from ..firebase_config import (
    save_payload,
    get_user_payloads,
    get_payload,
    update_payload,
    delete_payload
)
from ..AutoScraperUtil import read_json_file, clean_model_name # For legacy file loading & model cleaning
from ..auth_decorator import login_required # Import the updated decorator

# Create the blueprint
api_payloads_bp = Blueprint('api_payloads', __name__, url_prefix='/api')

# No placeholder decorator needed anymore

@api_payloads_bp.route('/create_payload', methods=['POST'])
@login_required # Apply actual decorator
def create_payload():
    """
    (Currently simple) Endpoint to receive and potentially validate a payload structure.
    """
    payload = request.json
    # --- ADDED LOGGING ---
    print(f"--- DEBUG: Received payload in /api/create_payload: {payload}")
    # --- END LOGGING ---
    # Could add validation here if needed
    return jsonify({"success": True, "payload": payload})

@api_payloads_bp.route('/save_payload', methods=['POST'])
@login_required # Apply actual decorator
def save_payload_api():
    payload = request.json.get('payload')
    user_id = session.get('user_id') # Already checked by decorator, but good practice

    if not payload:
        return jsonify({"success": False, "error": "No payload provided"}), 400

    # Save payload to Firebase
    result = save_payload(user_id, payload)

    if result['success']:
        return jsonify({
            "success": True,
            "file_path": f"Firebase/{result['doc_id']}", # Indicate it's a Firebase path
            "doc_id": result['doc_id']
        })
    else:
        return jsonify({"success": False, "error": result.get('error', 'Failed to save payload')}), 500

@api_payloads_bp.route('/list_payloads')
@login_required # Apply actual decorator
def list_payloads_api(): # Renamed function
    user_id = session.get('user_id')

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
                model = clean_model_name(model) # Clean the model name
                year_min = payload.get('YearMin', '')
                year_max = payload.get('YearMax', '')
                price_min = payload.get('PriceMin', '')
                price_max = payload.get('PriceMax', '')
                formatted_name = f"{make} {model} ({year_min}-{year_max}, ${price_min}-${price_max})"

            formatted_payloads.append({
                "name": formatted_name,
                "id": payload_data['id'] # Pass the document ID
            })

        return jsonify({"success": True, "payloads": formatted_payloads})
    except Exception as e:
        # Log the exception
        # current_app.logger.error(f"Error listing payloads for user {user_id}: {e}", exc_info=True)
        print(f"Error listing payloads for user {user_id}: {e}") # Basic print for now
        return jsonify({"success": False, "error": str(e)}), 500

@api_payloads_bp.route('/load_payload', methods=['POST'])
@login_required # Apply actual decorator
def load_payload_api():
    file_path = request.json.get('file_path')
    doc_id = request.json.get('doc_id')  # Get the document ID directly
    user_id = session.get('user_id')

    if not file_path:
        return jsonify({"success": False, "error": "No file path provided"}), 400

    # Check if it's a Firebase path (preferred method)
    if file_path.startswith("Firebase/") or doc_id:
        if not doc_id:
             # Try extracting from file_path if not provided directly
             if file_path.startswith("Firebase/"):
                 doc_id = file_path.split('/')[-1]
             else:
                return jsonify({"success": False, "error": "No document ID provided for Firebase load"}), 400

        # Get the payload from Firebase
        payload = get_payload(user_id, doc_id)

        if payload is None: # Check for None explicitly
            return jsonify({"success": False, "error": f"Failed to load payload from Firebase or not found"}), 404

        return jsonify({"success": True, "payload": payload})
    else:
        # Legacy file-based loading (for backward compatibility or local files)
        # Consider security implications if allowing arbitrary file paths
        try:
            payload = read_json_file(file_path)
            if payload is None:
                return jsonify({"success": False, "error": f"Failed to load payload from {file_path}"}), 404
            return jsonify({"success": True, "payload": payload})
        except Exception as e:
            # Log error
            print(f"Error loading legacy payload {file_path}: {e}")
            return jsonify({"success": False, "error": f"Error loading file {file_path}"}), 500


@api_payloads_bp.route('/rename_payload', methods=['POST'])
@login_required # Apply actual decorator
def rename_payload_api():
    payload_id = request.json.get('payload_id')
    new_name = request.json.get('new_name')
    user_id = session.get('user_id')

    if not payload_id or not new_name:
        return jsonify({"success": False, "error": "Missing payload ID or new name"}), 400

    try:
        # Get the current payload to update it
        payload = get_payload(user_id, payload_id)
        if payload is None:
            return jsonify({"success": False, "error": "Payload not found"}), 404

        # Add/Update the custom_name field
        payload_data = payload.copy() # Avoid modifying the original dict directly if needed elsewhere
        payload_data['custom_name'] = new_name

        # Save the updated payload using update_payload
        result = update_payload(user_id, payload_id, payload_data)

        if result.get('success'):
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": result.get('error', 'Failed to rename payload')}), 500
    except Exception as e:
        print(f"Error renaming payload {payload_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@api_payloads_bp.route('/delete_payload', methods=['POST'])
@login_required # Apply actual decorator
def delete_payload_api():
    payload_id = request.json.get('payload_id')
    user_id = session.get('user_id')

    if not payload_id:
        return jsonify({"success": False, "error": "No payload ID provided"}), 400

    try:
        # Delete the payload from Firebase
        result = delete_payload(user_id, payload_id)

        if result.get('success'):
            return jsonify({"success": True})
        else:
            # Check if error was 'not found' vs actual delete error
            error_msg = result.get('error', 'Failed to delete payload')
            status_code = 404 if "not found" in error_msg.lower() else 500
            return jsonify({"success": False, "error": error_msg}), status_code
    except Exception as e:
        print(f"Error deleting payload {payload_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
