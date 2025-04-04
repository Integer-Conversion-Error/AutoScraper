use anyhow::{Context, Result}; // Add Context
use axum::{extract::FromRef, Router}; // Add FromRef
use reqwest::Client;
use serde::Deserialize; // Add Deserialize
use std::{env, fs, net::SocketAddr, path::Path, sync::Arc}; // Add env, fs, Path
use tokio::net::TcpListener;
use crate::config::Settings;
use tower_http::services::ServeDir;
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
mod auth_middleware;

// Define structure for proxy configuration
#[derive(Deserialize, Debug)]
struct ProxyConfig {
    http_proxy: Option<String>,
    https_proxy: Option<String>,
}

// Function to load proxy config and set environment variables
fn load_and_set_proxy_env_vars() -> Result<()> {
    let config_path = Path::new("proxyconfig.json");
    if config_path.exists() {
        tracing::info!("Found proxyconfig.json, attempting to load proxy settings...");
        let config_content = fs::read_to_string(config_path)
            .context("Failed to read proxyconfig.json")?;
        let proxy_config: ProxyConfig = serde_json::from_str(&config_content)
            .context("Failed to parse proxyconfig.json")?;

        if let Some(http_proxy) = proxy_config.http_proxy {
            if !http_proxy.is_empty() {
                // SAFETY: Setting env vars at the start of main before heavy threading
                // is generally considered acceptable.
                unsafe { env::set_var("HTTP_PROXY", http_proxy.clone()); }
                tracing::info!("Set HTTP_PROXY environment variable from config.");
                // Optionally log the value, but be careful with credentials
                // tracing::debug!("HTTP_PROXY set to: {}", http_proxy);
            }
        }
        if let Some(https_proxy) = proxy_config.https_proxy {
             if !https_proxy.is_empty() {
                // SAFETY: Setting env vars at the start of main before heavy threading
                // is generally considered acceptable.
                unsafe { env::set_var("HTTPS_PROXY", https_proxy.clone()); }
                tracing::info!("Set HTTPS_PROXY environment variable from config.");
                // Optionally log the value, but be careful with credentials
                // tracing::debug!("HTTPS_PROXY set to: {}", https_proxy);
            }
        }
    } else {
        tracing::info!("proxyconfig.json not found, skipping proxy environment variable setup.");
    }
    Ok(())
}


// Define the application state struct
#[derive(Clone, FromRef)]
struct AppState {
    settings: Arc<Settings>,
    http_client: Arc<Client>,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Load .env file first. Ignore errors (e.g., file not found)
    dotenv::dotenv().ok();
    tracing::debug!("Loaded .env file if present."); // Add a trace log

    // Attempt to load proxy settings first (will override .env if keys conflict)
    if let Err(e) = load_and_set_proxy_env_vars() {
        // Log the error but continue execution, as proxy might not be essential
        tracing::warn!("Failed to load or apply proxy configuration: {}", e);
    }

    // Initialize logging
    tracing_subscriber::registry()
        .with(EnvFilter::try_from_default_env().unwrap_or_else(|_| "autoscraper_rust=info,tower_http=info".into())) // Default to info if RUST_LOG not set
        //.with(EnvFilter::new("autoscraper_rust=debug,tower_http=info")) // Keep this commented for easy debugging toggle if needed
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

    // Create the shared reqwest client *after* env vars are set
    // It will automatically pick up HTTP_PROXY/HTTPS_PROXY
    let http_client = Arc::new(
        Client::builder()
            .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36") // Consistent user agent
            .build()
            .context("Failed to build shared reqwest client")?
    );
    tracing::info!("Shared HTTP client created.");

    // Create the application state instance
    let app_state = AppState {
        settings: shared_settings.clone(),
        http_client: http_client.clone(),
    };

    // create_router needs to be updated to expect the AppState struct
    let router: Router = routes::create_router(app_state.clone()); // Pass state to router creation

    // Combine the router with static file serving
    // .with_state is no longer needed here as state is passed into create_router
    let app = router.nest_service("/static", ServeDir::new("static"));


    // Parse the server address from settings
    let addr: SocketAddr = match app_state.settings.server_address.parse() { // Use app_state here
        Ok(a) => a,
        Err(e) => {
            tracing::error!("Invalid server address format in configuration ('{}'): {}", app_state.settings.server_address, e);
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
