// Route definitions

use axum::{
    routing::{get, post},
    Router,
};
// Removed unused imports:
// use crate::config::Settings;
// use reqwest::Client;
// use std::sync::Arc;

// Import the AppState struct defined in main.rs (or move definition here)
// Assuming it's accessible via crate root for now
use crate::AppState;

// Declare submodules for different route groups
mod static_pages;
mod auth;
mod api;
// mod scrape;

// create_router now accepts the AppState and returns a Router without state specified here
// The state is provided when the router is consumed in main.rs
pub fn create_router(app_state: AppState) -> Router {
    // Define API routes separately.
    // These handlers will expect AppState via the State extractor.
    let api_router = Router::new()
        .route("/makes", get(api::get_makes))
        .route("/models/:make", get(api::get_models))
        .route("/trims", get(api::get_trims))
        .route("/colors", get(api::get_colors))
        .route("/search", post(api::search_listings))
        // Routes requiring authentication
        .route("/payloads", get(api::get_saved_payloads))
        .route("/payloads", post(api::save_new_payload))
        .route("/settings", get(api::get_settings))
        .route("/settings", post(api::save_settings))
        // Provide the state to the API router
        .with_state(app_state.clone()); // Clone AppState for the nested router

    // Combine static, auth, and API routes.
    Router::new()
        // Static page routes (these don't need the AppState)
        .route("/", get(static_pages::landing_page))
        .route("/login", get(static_pages::login_page))
        .route("/app", get(static_pages::app_page))
        // Auth routes (handle_login needs AppState)
        .route("/login", post(auth::handle_login))
        // Nest the API router which already has state
        .nest("/api", api_router)
        // Provide the state to the top-level router for routes that need it (like /login post)
        .with_state(app_state)
    // .merge(scrape::create_router()) // Example for later
    // Add routes for other static pages here later (e.g., /about, /pricing)
}

// Remove the old basic index handler
// async fn index() -> &'static str {
//     "Hello from Axum!"
// }
