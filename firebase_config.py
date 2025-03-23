import firebase_admin
from firebase_admin import credentials, firestore, auth
import json
import os

# Initialize Firebase Admin SDK
def initialize_firebase():
    """
    Initialize the Firebase Admin SDK with credentials from the firebase_credentials.json file.
    If running in production, the credentials may be stored as environment variables.
    """
    try:
        # First try to load from a credentials file
        if os.path.exists('firebase_credentials.json'):
            cred = credentials.Certificate('firebase_credentials.json')
            firebase_admin.initialize_app(cred)
        # If no file exists, try to load from environment variables
        else:
            # This assumes the credentials are stored as a JSON string in the FIREBASE_CREDENTIALS env var
            firebase_creds = json.loads(os.environ.get('FIREBASE_CREDENTIALS', '{}'))
            if firebase_creds:
                cred = credentials.Certificate(firebase_creds)
                firebase_admin.initialize_app(cred)
            else:
                print("WARNING: No Firebase credentials found.")
                return False
        
        # Initialize Firestore
        db = firestore.client()
        return True
    except Exception as e:
        print(f"Error initializing Firebase: {e}")
        return False

def get_firestore_db():
    """
    Get the Firestore database instance.
    
    Returns:
        firestore.Client: The Firestore database client
    """
    try:
        return firestore.client()
    except Exception as e:
        print(f"Error getting Firestore client: {e}")
        return None

# Firebase Authentication functions
def create_user(email, password, display_name=None):
    """
    Create a new user in Firebase Authentication.
    
    Args:
        email (str): The user's email
        password (str): The user's password
        display_name (str, optional): The user's display name
        
    Returns:
        dict: User information including UID
    """
    try:
        user = auth.create_user(
            email=email,
            password=password,
            display_name=display_name or email.split('@')[0]
        )
        return {'success': True, 'uid': user.uid}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def verify_id_token(id_token):
    """
    Verify a Firebase authentication token.
    
    Args:
        id_token (str): The ID token to verify
        
    Returns:
        dict: The decoded token information
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return {'success': True, 'user': decoded_token}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user(uid):
    """
    Retrieve a user by their UID.
    
    Args:
        uid (str): The user's UID
        
    Returns:
        UserRecord: The user record
    """
    try:
        return auth.get_user(uid)
    except Exception as e:
        print(f"Error retrieving user: {e}")
        return None

# Firestore operations for payloads
def save_payload(user_id, payload):
    """
    Save a search payload to Firestore.
    
    Args:
        user_id (str): The ID of the user who created the payload
        payload (dict): The search payload to save
        
    Returns:
        dict: Success status and document ID
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}
        
        # Create a reference to the payloads collection for this user
        payloads_ref = db.collection('users').document(user_id).collection('payloads')
        
        # Add necessary metadata
        payload_with_metadata = {
            **payload,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Save the payload
        doc_ref = payloads_ref.add(payload_with_metadata)
        return {'success': True, 'doc_id': doc_ref[1].id}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_payloads(user_id):
    """
    Get all payloads for a specific user.
    
    Args:
        user_id (str): The user's ID
        
    Returns:
        list: List of payload documents
    """
    try:
        db = get_firestore_db()
        if not db:
            return []
        
        payloads_ref = db.collection('users').document(user_id).collection('payloads')
        payloads = payloads_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()
        
        result = []
        for payload_doc in payloads:
            data = payload_doc.to_dict()
            result.append({
                'id': payload_doc.id,
                'payload': data,
                'created_at': data.get('created_at')
            })
        
        return result
    except Exception as e:
        print(f"Error retrieving payloads: {e}")
        return []

def get_payload(user_id, payload_id):
    """
    Get a specific payload by ID.
    
    Args:
        user_id (str): The user's ID
        payload_id (str): The payload document ID
        
    Returns:
        dict: The payload data
    """
    try:
        db = get_firestore_db()
        if not db:
            print(f"Debug - get_payload: Database connection failed")
            return None
        
        print(f"Debug - get_payload: Fetching document for User: {user_id}, Payload ID: {payload_id}")
        payload_ref = db.collection('users').document(user_id).collection('payloads').document(payload_id)
        payload = payload_ref.get()
        
        if not payload.exists:
            print(f"Debug - get_payload: Document does not exist")
            return None
            
        print(f"Debug - get_payload: Document found, contains keys: {list(payload.to_dict().keys())}")
        return payload.to_dict()
    except Exception as e:
        print(f"Error retrieving payload: {e}")
        return None

def update_payload(user_id, payload_id, payload_data):
    """
    Update an existing payload.
    
    Args:
        user_id (str): The user's ID
        payload_id (str): The payload document ID
        payload_data (dict): The updated payload data
        
    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}
        
        # Add updated timestamp
        payload_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        payload_ref = db.collection('users').document(user_id).collection('payloads').document(payload_id)
        payload_ref.update(payload_data)
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def delete_payload(user_id, payload_id):
    """
    Delete a payload.
    
    Args:
        user_id (str): The user's ID
        payload_id (str): The payload document ID
        
    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}
        
        payload_ref = db.collection('users').document(user_id).collection('payloads').document(payload_id)
        payload_ref.delete()
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
    
    
    
# Add these functions to firebase_config.py

def save_results(user_id, results, metadata):
    """
    Save search results to Firestore.
    
    Args:
        user_id (str): The ID of the user who owns the results
        results (list): The list of result dictionaries
        metadata (dict): Metadata about the search (make, model, etc.)
        
    Returns:
        dict: Success status and document ID
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}
        
        # Create a reference to the results collection for this user
        results_ref = db.collection('users').document(user_id).collection('results')
        
        # Add necessary metadata
        results_with_metadata = {
            'results': results,
            'metadata': metadata,
            'created_at': firestore.SERVER_TIMESTAMP,
            'result_count': len(results)
        }
        
        # Save the results
        doc_ref = results_ref.add(results_with_metadata)
        return {'success': True, 'doc_id': doc_ref[1].id}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_user_results(user_id):
    """
    Get all results for a specific user.
    
    Args:
        user_id (str): The user's ID
        
    Returns:
        list: List of result documents with metadata
    """
    try:
        db = get_firestore_db()
        if not db:
            return []
        
        results_ref = db.collection('users').document(user_id).collection('results')
        results = results_ref.order_by('created_at', direction=firestore.Query.DESCENDING).get()
        
        result_list = []
        for result_doc in results:
            data = result_doc.to_dict()
            metadata = data.get('metadata', {})
            result_list.append({
                'id': result_doc.id,
                'metadata': metadata,
                'created_at': data.get('created_at'),
                'result_count': data.get('result_count', 0)
            })
        
        return result_list
    except Exception as e:
        print(f"Error retrieving results: {e}")
        return []

def get_result(user_id, result_id):
    """
    Get a specific result by ID.
    
    Args:
        user_id (str): The user's ID
        result_id (str): The result document ID
        
    Returns:
        dict: The result data with metadata
    """
    try:
        db = get_firestore_db()
        if not db:
            return None
        
        result_ref = db.collection('users').document(user_id).collection('results').document(result_id)
        result = result_ref.get()
        
        if not result.exists:
            return None
            
        return result.to_dict()
    except Exception as e:
        print(f"Error retrieving result: {e}")
        return None

def delete_result(user_id, result_id):
    """
    Delete a result.
    
    Args:
        user_id (str): The user's ID
        result_id (str): The result document ID
        
    Returns:
        dict: Success status
    """
    try:
        db = get_firestore_db()
        if not db:
            return {'success': False, 'error': 'Database connection failed'}
        
        result_ref = db.collection('users').document(user_id).collection('results').document(result_id)
        result_ref.delete()
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}