// Placeholder for custom error types and conversions
// This helps in providing consistent error responses in Axum

use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
};

// Define a custom application error type (can be expanded later)
#[derive(Debug)]
pub enum AppError {
    InternalServerError(anyhow::Error),
    Unauthorized(String), // Add Unauthorized variant with a message
    // Add other error variants like NotFound, etc.
}

// Implement conversion from anyhow::Error for easier error propagation
impl From<anyhow::Error> for AppError {
    fn from(error: anyhow::Error) -> Self {
        AppError::InternalServerError(error)
    }
}

// Implement IntoResponse for AppError to convert errors into HTTP responses
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, error_message) = match self {
            AppError::InternalServerError(e) => {
                // Log the detailed error here
                tracing::error!("Internal server error: {:?}", e);
                // Don't expose internal details to the client
                (StatusCode::INTERNAL_SERVER_ERROR, "Internal Server Error".to_string())
            }
            AppError::Unauthorized(message) => {
                tracing::warn!("Unauthorized access attempt: {}", message);
                (StatusCode::UNAUTHORIZED, message) // Return the specific message
            }
            // Handle other error variants here
        };

        // Consider returning JSON for API errors:
        // let body = Json(json!({ "error": error_message }));
        // (status, body).into_response()
        // For now, just return plain text:
        (status, error_message).into_response()
    }
}

// Define a custom Result type using our AppError
pub type AppResult<T> = Result<T, AppError>;
