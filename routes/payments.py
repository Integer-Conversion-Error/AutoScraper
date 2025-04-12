import stripe
import os
import logging
from flask import Blueprint, request, jsonify, redirect, url_for, session, current_app, render_template
from firebase_config import get_firestore_db # Assuming user data is in Firestore
from auth_decorator import login_required # To protect checkout creation

payments_bp = Blueprint('payments', __name__, url_prefix='/payment')

# Configure logging for this blueprint
logger = logging.getLogger(__name__)
# Example: Configure a specific handler if needed, or rely on app's config
# handler = logging.StreamHandler()
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)
# logger.setLevel(logging.INFO)

# --- Actual Product/Price IDs from Stripe Dashboard ---
# Subscriptions
PRICE_BASIC_MONTHLY = 'basic_tier_monthly' # User provided
PRICE_BASIC_YEARLY = 'basic_tier_yearly'   # User provided
PRICE_PRO_MONTHLY = 'pro_tier_monthly'     # User provided
PRICE_PRO_YEARLY = 'pro_sub_yearly'        # User provided (Note: User provided 'pro_sub_yearly', assuming this is correct)
# Tokens (One-time purchases)
PRICE_TOKENS_100 = '100_token'             # User provided
PRICE_TOKENS_500 = '500_token'             # User provided
PRICE_TOKENS_1500 = '1500_token'           # User provided
PRICE_TOKENS_4000 = '4000_token'           # User provided
PRICE_TOKENS_10000 = '10000_token'         # User provided

# TODO: Add Stripe Webhook Signing Secret (User will provide later)
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET') # Example if using env var
# Or load from config if stored there:
# try:
#     with open('config.json', 'r') as f:
#         config = json.load(f)
#     STRIPE_WEBHOOK_SECRET = config.get('STRIPE_WEBHOOK_SECRET')
# except Exception as e:
#     logger.error(f"Could not load STRIPE_WEBHOOK_SECRET: {e}")
#     STRIPE_WEBHOOK_SECRET = None


@payments_bp.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """
    Creates a Stripe Checkout session for a given Price ID.
    Expects JSON body: {'price_id': 'price_...'}
    """
    data = request.get_json()
    price_id = data.get('price_id')
    user_id = session.get('user_id') # Get user ID from session

    if not price_id:
        logger.warning(f"Missing price_id in request from user {user_id}")
        return jsonify({'error': 'Missing price_id'}), 400
    if not user_id:
         # Should be caught by @login_required, but double-check
        logger.error("User ID not found in session during checkout creation.")
        return jsonify({'error': 'User not logged in'}), 401

    logger.info(f"User {user_id} creating checkout session for price {price_id}")

    # Determine if it's a subscription or one-time payment based on Price ID
    # This is a simplified check; you might need a more robust way
    # (e.g., fetching the price object from Stripe or having a predefined map)
    mode = 'subscription' if 'monthly' in price_id or 'yearly' in price_id else 'payment'

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode=mode,
            success_url=url_for('payments.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payments.cancel', _external=True),
            # Associate the checkout session with the logged-in user
            client_reference_id=user_id,
            # If it's a subscription and you want to manage customer details:
            # customer_email=session.get('user_email'), # Pass user email if available
            # metadata={'user_id': user_id} # Alternative way to pass user ID
        )
        logger.info(f"Checkout session {checkout_session.id} created for user {user_id}, price {price_id}")
        # Return the session ID to the frontend
        return jsonify({'id': checkout_session.id})

    except Exception as e:
        logger.error(f"Error creating Stripe checkout session for user {user_id}, price {price_id}: {e}", exc_info=True)
        # Consider returning a more specific error based on Stripe's exception types
        return jsonify({'error': str(e)}), 500


@payments_bp.route('/success')
def success():
    """Page displayed after a successful payment."""
    session_id = request.args.get('session_id')
    # Optionally, retrieve the session to display more details or confirm status
    # try:
    #     checkout_session = stripe.checkout.Session.retrieve(session_id)
    #     # Check checkout_session.payment_status or other details
    # except stripe.error.InvalidRequestError:
    #     logger.warning(f"Invalid session_id '{session_id}' provided on success page.")
    #     # Handle error appropriately
    # except Exception as e:
    #     logger.error(f"Error retrieving session {session_id} on success page: {e}")
    #     # Handle error appropriately

    logger.info(f"User redirected to success page (session: {session_id})")
    # You might want to redirect to the main app dashboard or a specific page
    # return redirect(url_for('views.dashboard')) # Example redirect
    return render_template('payment_success.html') # Requires creating this template


@payments_bp.route('/cancel')
def cancel():
    """Page displayed if the user cancels the payment."""
    logger.info("User cancelled payment and redirected to cancel page.")
    # You might want to redirect to the pricing page or dashboard
    # return redirect(url_for('views.pricing')) # Example redirect
    return render_template('payment_cancel.html') # Requires creating this template


@payments_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Listens for webhook events from Stripe.
    Handles events like checkout completion to update user data.
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    event = None

    if not STRIPE_WEBHOOK_SECRET:
        logger.error("Stripe webhook secret is not configured. Cannot process webhook.")
        return jsonify({'error': 'Webhook secret not configured'}), 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        logger.info(f"Received Stripe webhook event: {event['type']} (ID: {event['id']})")
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid webhook payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid webhook signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        logger.error(f"Error constructing webhook event: {e}", exc_info=True)
        return jsonify({'error': 'Webhook processing error'}), 500

    # --- Handle specific events ---

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        user_id = session_data.get('client_reference_id')
        payment_status = session_data.get('payment_status')
        mode = session_data.get('mode') # 'payment' or 'subscription'

        logger.info(f"Processing checkout.session.completed for user {user_id}, session {session_data.id}, status {payment_status}, mode {mode}")

        if user_id and payment_status == 'paid':
            # Payment was successful, fulfill the order
            try:
                # Retrieve line items to know exactly what was purchased
                line_items = stripe.checkout.Session.list_line_items(session_data.id, limit=5)
                db = get_firestore_db()
                user_ref = db.collection('users').document(user_id)

                for item in line_items.data:
                    price_id = item.price.id
                    quantity = item.quantity # Usually 1 for these items

                    # --- TODO: Implement Firestore Update Logic ---
                    logger.info(f"Fulfilling order for user {user_id}, price {price_id}, quantity {quantity}")

                    # Example: Update token count for one-time purchases
                    if mode == 'payment':
                        tokens_to_add = 0
                        # Match against the actual Price IDs provided by the user
                        if price_id == PRICE_TOKENS_100: tokens_to_add = 100
                        elif price_id == PRICE_TOKENS_500: tokens_to_add = 500
                        elif price_id == PRICE_TOKENS_1500: tokens_to_add = 1500
                        elif price_id == PRICE_TOKENS_4000: tokens_to_add = 4000
                        elif price_id == PRICE_TOKENS_10000: tokens_to_add = 10000
                        else: logger.warning(f"Unknown one-time price ID {price_id} in checkout for user {user_id}")

                        if tokens_to_add > 0:
                            # Need a function in firebase_config or here to safely increment tokens
                            # update_user_tokens(user_id, tokens_to_add)
                            logger.info(f"TODO: Add {tokens_to_add} tokens to user {user_id}")
                            pass # Replace with actual Firestore update call

                    # Example: Update subscription status for subscriptions
                    elif mode == 'subscription':
                        subscription_id = session_data.get('subscription')
                        plan_name = "Unknown Plan" # Determine from price_id
                        # Match against the actual Price IDs provided by the user
                        if price_id in [PRICE_BASIC_MONTHLY, PRICE_BASIC_YEARLY]: plan_name = "Basic AI"
                        elif price_id in [PRICE_PRO_MONTHLY, PRICE_PRO_YEARLY]: plan_name = "Pro AI"
                        else: logger.warning(f"Unknown subscription price ID {price_id} in checkout for user {user_id}")

                        # Need a function to update user's subscription status
                        # update_user_subscription(user_id, subscription_id, plan_name, 'active')
                        logger.info(f"TODO: Set subscription {subscription_id} ({plan_name}) active for user {user_id}")
                        pass # Replace with actual Firestore update call

                logger.info(f"Successfully processed checkout.session.completed for user {user_id}")

            except Exception as e:
                logger.error(f"Error fulfilling order for user {user_id} after checkout {session_data.id}: {e}", exc_info=True)
                # Potentially retry or flag for manual intervention
                return jsonify({'error': 'Fulfillment error'}), 500

        elif payment_status != 'paid':
             logger.warning(f"Checkout session {session_data.id} for user {user_id} completed but payment status is {payment_status}. No fulfillment.")
        elif not user_id:
             logger.error(f"Checkout session {session_data.id} completed successfully but client_reference_id (user_id) is missing.")


    # Handle successful subscription payments (recurring)
    elif event['type'] == 'invoice.paid':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer') # Stripe Customer ID
        # You might need to map Stripe Customer ID back to your user_id if not using client_reference_id consistently
        # Or retrieve subscription to get metadata if you stored user_id there

        logger.info(f"Processing invoice.paid for subscription {subscription_id}, customer {customer_id}")

        # TODO: If subscriptions grant monthly tokens, add logic here to:
        # 1. Identify the user associated with the subscription/customer ID.
        # 2. Determine the plan based on the subscription.
        # 3. Add the corresponding monthly tokens to the user's account in Firestore.
        # Example:
        # user_id = get_user_id_from_stripe_customer(customer_id) # Need this mapping function
        # plan_details = get_plan_from_subscription(subscription_id) # Need this function
        # if user_id and plan_details:
        #    tokens_to_add = plan_details['monthly_tokens']
        #    update_user_tokens(user_id, tokens_to_add)
        #    logger.info(f"Added {tokens_to_add} monthly tokens to user {user_id} for subscription {subscription_id}")
        pass


    # Handle failed subscription payments
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        logger.warning(f"Invoice payment failed for subscription {subscription_id}, customer {customer_id}")
        # TODO: Add logic to handle failed payments:
        # 1. Notify the user.
        # 2. Potentially update subscription status in Firestore (e.g., 'past_due').
        pass

    # Handle subscription cancellations or ends
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        subscription_id = subscription.id
        customer_id = subscription.customer
        logger.info(f"Subscription {subscription_id} for customer {customer_id} was deleted (cancelled or ended).")
        # TODO: Add logic to update subscription status in Firestore:
        # 1. Find the user associated with the customer/subscription ID.
        # 2. Update their status to 'cancelled' or 'inactive'.
        pass

    else:
        logger.info(f"Unhandled Stripe event type: {event['type']}")

    # Acknowledge receipt of the event
    return jsonify({'received': True}), 200

# --- Helper Functions (Placeholder - Implement in firebase_config.py or here) ---

# def update_user_tokens(user_id, tokens_to_add):
#     """Safely increments the token count for a user in Firestore."""
#     # TODO: Implement this using Firestore transactions for safety
#     logger.info(f"[Placeholder] Adding {tokens_to_add} tokens to user {user_id}")
#     pass

# def update_user_subscription(user_id, subscription_id, plan_name, status):
#     """Updates the user's subscription details in Firestore."""
#     # TODO: Implement this
#     logger.info(f"[Placeholder] Updating subscription for user {user_id}: ID={subscription_id}, Plan={plan_name}, Status={status}")
#     pass

# def get_user_id_from_stripe_customer(customer_id):
#      """ Retrieves user_id based on Stripe customer_id (requires storing this mapping)."""
#      # TODO: Implement this lookup if needed
#      logger.warning(f"[Placeholder] Need to implement lookup for user_id from customer_id {customer_id}")
#      return None
