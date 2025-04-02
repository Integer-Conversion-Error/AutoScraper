// Route definitions

use axum::{
    routing::{get, post},
    Router,
};
use crate::config::Settings; // Add Settings import back
use std::sync::Arc; // Add Arc import back

// Declare submodules for different route groups
mod static_pages;
mod auth;
mod api;
// mod scrape;

// create_router returns a router expecting the Arc<Settings> state
pub fn create_router() -> Router<Arc<Settings>> {
    // Define API routes separately.
    // Nested routers must have the same state type as the parent.
    let api_router: Router<Arc<Settings>> = Router::new()
        .route("/makes", get(api::get_makes)) // These handlers don't use State yet, but the router type must match
        .route("/models", get(api::get_models))
        .route("/trims", get(api::get_trims))
        .route("/colors", get(api::get_colors))
        .route("/search", post(api::search_listings))
        .route("/payloads", get(api::get_saved_payloads)) // GET payloads
        .route("/payloads", post(api::save_new_payload)) // POST new payload
        .route("/settings", get(api::get_settings));
        // Add other API routes here later

    // Combine static, auth, and API routes. The final router type is Router<Arc<Settings>>.
    Router::new()
        // Static page routes (handlers don't require state)
        .route("/", get(static_pages::landing_page))
        .route("/login", get(static_pages::login_page))
        .route("/app", get(static_pages::app_page)) // app_page doesn't use State yet
        // Auth routes (handle_login requires State<Arc<Settings>>)
        .route("/login", post(auth::handle_login))
        // Nest API routes under /api prefix.
        // The nested router's state type must match the parent's state type.
        .nest("/api", api_router)
    // .merge(scrape::create_router()) // Example for later
    // Add routes for other static pages here later (e.g., /about, /pricing)
}

// Remove the old basic index handler
// async fn index() -> &'static str {
//     "Hello from Axum!"
// }
