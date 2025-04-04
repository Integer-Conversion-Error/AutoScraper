use askama::Template;
use axum::response::{Html, IntoResponse};
// Removed: use axum::http::StatusCode;
use crate::error::AppError; // Use our custom error type

// Define the template struct pointing to our landing page file
#[derive(Template)]
#[template(path = "landing.html")]
struct LandingTemplate;

// Define the template struct for the login page
#[derive(Template)]
#[template(path = "login.html")]
struct LoginTemplate;

// Define the template struct for the main app page
#[derive(Template)]
#[template(path = "index.html")]
struct AppTemplate {
    username: String, // Field to hold the username
}

// Handler function to render the landing page
pub async fn landing_page() -> Result<impl IntoResponse, AppError> {
    let template = LandingTemplate {};
    match template.render() {
        Ok(html) => Ok(Html(html)),
        Err(e) => {
            tracing::error!("Failed to render landing template: {}", e);
            // Convert Askama error into our AppError
            Err(AppError::InternalServerError(anyhow::Error::new(e)))
        }
    }
}

// Handler function to render the login page
pub async fn login_page() -> Result<impl IntoResponse, AppError> {
    let template = LoginTemplate {};
    match template.render() {
        Ok(html) => Ok(Html(html)),
        Err(e) => {
            tracing::error!("Failed to render login template: {}", e);
            Err(AppError::InternalServerError(anyhow::Error::new(e)))
        }
    }
}

// Handler function to render the main application page
// This will eventually require authentication and fetching the actual username
pub async fn app_page() -> Result<impl IntoResponse, AppError> {
    // TODO: Get actual username from session/token after implementing auth properly
    let username = "Test User".to_string(); // Placeholder username

    let template = AppTemplate { username };
    match template.render() {
        Ok(html) => Ok(Html(html)),
        Err(e) => {
            tracing::error!("Failed to render app template: {}", e);
            Err(AppError::InternalServerError(anyhow::Error::new(e)))
        }
    }
}

// Add handlers for other static pages (about, pricing, terms, etc.) here later
