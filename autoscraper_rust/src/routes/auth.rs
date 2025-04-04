use axum::{
    extract::Form,
    response::{IntoResponse, Redirect},
    // Removed: http::StatusCode,
    extract::State,
};
// Removed unused imports: config::Settings, reqwest::Client, std::sync::Arc
use crate::{models::LoginForm, error::AppError, auth_middleware};

// Import AppState struct
use crate::AppState;

// Handler for POST /login
// Accepts the form data and the shared application state
pub async fn handle_login(
    State(app_state): State<AppState>, // Use AppState struct
    Form(form): Form<LoginForm>,
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("Received login token (first few chars): {}", &form.id_token[..std::cmp::min(form.id_token.len(), 10)]);

    // 1. Call verify_token from auth_middleware, passing the settings and http_client from app_state
    match auth_middleware::verify_token(&form.id_token, &app_state.settings, &app_state.http_client).await {
        Ok(claims) => { // verify_token now returns Claims struct
            tracing::info!("Token verified successfully for user_id: {}", claims.sub);

            // TODO:
            // 2. Create a session (e.g., set a signed cookie)

            // 3. Redirect to the main application page
            Ok(Redirect::to("/app")) // Redirect on success
        }
        Err(e) => {
            // Use Debug formatting for AppError in tracing
            tracing::error!("Token verification failed: {:?}", e);
            // Return the AppError directly as verify_token already returns a suitable error
            Err(e)
        }
    }
}

// We can add other auth handlers here later (e.g., logout)
