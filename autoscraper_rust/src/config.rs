// Placeholder for loading configuration
// Will use the 'config' crate and potentially 'dotenv'

use anyhow::Result;
use config::{Config, File, Environment};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct Settings {
    pub proxy_url: Option<String>,
    // Add other configuration fields here, e.g., Firebase credentials
    pub firebase_project_id: Option<String>,
    pub server_address: String,
}

impl Settings {
    pub fn new() -> Result<Self> {
        dotenv::dotenv().ok(); // Load .env file if present

        let builder = Config::builder()
            // Add default values
            .set_default("server_address", "127.0.0.1:3000")?
            // Load from a configuration file (e.g., config.toml)
            .add_source(File::with_name("config").required(false))
            // Load from environment variables (e.g., APP_PROXY_URL)
            .add_source(Environment::with_prefix("APP").separator("_"));

        let settings = builder.build()?.try_deserialize()?;
        Ok(settings)
    }
}
