use anyhow::Result;
use axum::Router; // Add Router import back
use std::{net::SocketAddr, sync::Arc};
use tokio::net::TcpListener;
use crate::config::Settings; // Import Settings struct
use tower_http::services::ServeDir; // Import ServeDir
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter, fmt};

// Declare modules
mod auth;
mod config;
mod error;
mod models;
mod routes;
mod scraper;
mod autotrader_api;
mod firestore; // Declare the firestore module

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging (read level from RUST_LOG env var, default to info)
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "autoscraper_rust=info,tower_http=info".into()))
        .with(fmt::layer())
        .init();

    tracing::info!("Initializing AutoScraper Rust server...");

    // Load configuration
    let settings = match config::Settings::new() {
        Ok(s) => {
            tracing::info!("Configuration loaded successfully.");
            s
        }
        Err(e) => {
            tracing::error!("Failed to load configuration: {}", e);
            return Err(e); // Propagate the error
        }
    };
    // Wrap settings in Arc for shared ownership
    let shared_settings = Arc::new(settings);

    // create_router returns a router expecting the Arc<Settings> state
    let router_expecting_state = routes::create_router();

    // Combine the router with static file serving and provide the actual state
    let app = router_expecting_state
        .nest_service("/static", ServeDir::new("static"))
        .with_state(shared_settings.clone()); // Clone Arc for state


    // Parse the server address from settings (use the original settings struct here)
    let addr: SocketAddr = match shared_settings.server_address.parse() { // Use shared_settings here too
        Ok(a) => a,
        Err(e) => {
            tracing::error!("Invalid server address format in configuration ('{}'): {}", shared_settings.server_address, e);
            // Use anyhow's context for better error reporting if needed
            return Err(anyhow::anyhow!("Invalid server address format: {}", shared_settings.server_address));
        }
    };
    // Removed duplicated block

    // Create a TCP listener
    let listener = match TcpListener::bind(&addr).await {
        Ok(l) => {
            tracing::info!("Server listening on {}", addr);
            l
        }
        Err(e) => {
            tracing::error!("Failed to bind to address {}: {}", addr, e);
            return Err(e.into()); // Convert std::io::Error to anyhow::Error
        }
    };

    // Run the server
    axum::serve(listener, app.into_make_service()) // Use into_make_service
        .await?;

    Ok(())
}
