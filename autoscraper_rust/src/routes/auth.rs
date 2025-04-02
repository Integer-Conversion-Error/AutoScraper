use axum::{
    extract::Form,
    response::{IntoResponse, Redirect},
    http::StatusCode,
    extract::State, // Add State extractor
};
use crate::{models::LoginForm, error::AppError, auth, config::Settings}; // Import Settings
use std::sync::Arc; // Import Arc

// Handler for POST /login
// Accepts the form data and the shared application state
pub async fn handle_login(
    State(settings): State<Arc<Settings>>, // Extract shared settings from state
    Form(form): Form<LoginForm>,
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("Received login token (first few chars): {}", &form.id_token[..std::cmp::min(form.id_token.len(), 10)]);

    // 1. Call verify_token, passing the settings
    match auth::verify_token(&form.id_token, &settings).await {
        Ok(user_id) => {
            tracing::info!("Token verified successfully for user_id: {}", user_id);

            // TODO:
            // 2. Create a session (e.g., set a signed cookie)

            // 3. Redirect to the main application page
            Ok(Redirect::to("/app")) // Redirect on success
        }
        Err(e) => {
            tracing::error!("Token verification failed: {}", e);
            // Return an error response (e.g., Unauthorized or Internal Server Error)
            // For now, just return InternalServerError, can refine later
            Err(AppError::InternalServerError(e.context("Token verification failed")))
        }
    }
}

// We can add other auth handlers here later (e.g., logout)
