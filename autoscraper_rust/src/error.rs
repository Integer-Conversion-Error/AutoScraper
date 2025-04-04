use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json, // Added Json for potential future use
};
use serde_json::json; // Added json! macro for potential future use
use thiserror::Error;

// Define a custom application error type using thiserror
#[derive(Debug, Error)]
pub enum AppError {
    #[error("Internal Server Error: {0}")]
    InternalServerError(#[from] anyhow::Error), // Propagates underlying anyhow error message

    #[error("Unauthorized: {0}")]
    Unauthorized(String),

    #[error("Fetch Error: {0}")] // Added FetchError variant
    FetchError(String),

    #[error("Configuration Error: {0}")]
    ConfigError(#[from] config::ConfigError),

    #[error("IO Error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("HTTP Request Error: {0}")]
    ReqwestError(#[from] reqwest::Error),

    #[error("JSON Processing Error: {0}")]
    SerdeJsonError(#[from] serde_json::Error),

    #[error("JWT Error: {0}")]
    JwtError(#[from] jsonwebtoken::errors::Error),

    #[error("OAuth Error: {0}")]
    OAuthError(String), // Keep specific message handling if needed

    #[error("Firestore Error: {0}")]
    FirestoreError(String), // Keep specific message handling if needed

    #[error("Not Found: {0}")]
    NotFound(String),

    #[error("Bad Request: {0}")]
    BadRequest(String),
}

// Implement IntoResponse for AppError to convert errors into HTTP responses
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, error_message) = match &self {
            // Specific user-facing errors
            AppError::Unauthorized(msg) => (StatusCode::UNAUTHORIZED, msg.clone()),
            AppError::NotFound(msg) => (StatusCode::NOT_FOUND, msg.clone()),
            AppError::BadRequest(msg) => (StatusCode::BAD_REQUEST, msg.clone()),
            AppError::JwtError(_) => (StatusCode::UNAUTHORIZED, "Invalid or expired token".to_string()), // More generic JWT message
            AppError::SerdeJsonError(_) => (StatusCode::BAD_REQUEST, "Invalid JSON format".to_string()), // More generic JSON message

            // Internal errors - log details, return generic message
            AppError::InternalServerError(e) => {
                tracing::error!("Internal server error: {:?}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal Server Error".to_string())
            }
            AppError::FetchError(msg) => {
                 tracing::error!("Fetch error: {}", msg);
                 (StatusCode::INTERNAL_SERVER_ERROR, "Failed to fetch external data".to_string())
            }
            AppError::ReqwestError(e) => {
                 tracing::error!("Reqwest error: {:?}", e);
                 (StatusCode::INTERNAL_SERVER_ERROR, "Network request failed".to_string())
            }
             AppError::ConfigError(e) => {
                 tracing::error!("Config error: {:?}", e);
                 (StatusCode::INTERNAL_SERVER_ERROR, "Server configuration error".to_string())
            }
             AppError::IoError(e) => {
                 tracing::error!("IO error: {:?}", e);
                 (StatusCode::INTERNAL_SERVER_ERROR, "File system error".to_string())
            }
             AppError::OAuthError(msg) => {
                 tracing::error!("OAuth error: {}", msg);
                 (StatusCode::INTERNAL_SERVER_ERROR, "Authentication service error".to_string())
            }
             AppError::FirestoreError(msg) => {
                 tracing::error!("Firestore error: {}", msg);
                 (StatusCode::INTERNAL_SERVER_ERROR, "Database interaction error".to_string())
            }
        };

        // Using Json response for consistency
        let body = Json(json!({
            "error": error_message,
        }));

        (status, body).into_response()
    }
}

// Define a custom Result type using our AppError
pub type AppResult<T> = Result<T, AppError>;
