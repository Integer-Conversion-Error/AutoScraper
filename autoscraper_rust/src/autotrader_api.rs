// Functions to interact with AutoTrader.ca (fetching makes, models, etc.)

use anyhow::{Context, Result};
use reqwest::Client; // Use reqwest for HTTP requests
use scraper::{Html, Selector}; // Use scraper for HTML parsing
use serde_json::Value; // For parsing JSON responses later

// Reusable HTTP client (made public)
// Consider creating this once and passing it around or using a lazy_static/once_cell approach
pub async fn get_client() -> Result<Client> {
    // Basic client for now, add proxy/headers later if needed based on config
    reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        .build()
        .context("Failed to build reqwest client")
}

// Fetches makes from AutoTrader homepage HTML
pub async fn fetch_all_makes(popular_only: bool) -> Result<Vec<String>> {
    let client = get_client().await?;
    let url = "https://www.autotrader.ca/";

    let response_text = client.get(url)
        .send()
        .await?
        .error_for_status()? // Check for HTTP errors
        .text()
        .await
        .context("Failed to get response text from AutoTrader homepage")?;

    // Parse the HTML
    let document = Html::parse_document(&response_text);

    // Define the CSS selector based on popular_only flag
    let optgroup_label = if popular_only { "Popular Makes" } else { "All Makes" };
    let selector_str = format!("optgroup[label='{}'] > option", optgroup_label);
    let option_selector = Selector::parse(&selector_str)
        .map_err(|e| anyhow::anyhow!("Failed to parse make selector: {:?}", e))?;

    let makes: Vec<String> = document
        .select(&option_selector)
        .map(|element| element.text().collect::<String>().trim().to_string())
        .filter(|make| !make.is_empty()) // Filter out empty strings
        .collect();

    if makes.is_empty() {
        tracing::warn!("No makes found for optgroup label: {}", optgroup_label);
    }

    Ok(makes)
}

// Fetches models for a given make
pub async fn fetch_models_for_make(make: &str) -> Result<Vec<String>> {
    let client = get_client().await?;
    let url = "https://www.autotrader.ca/Home/Refine"; // Endpoint from Python code

    // Construct the payload based on Python code
    let payload = serde_json::json!({
        "IsDealer": true,
        "IsPrivate": true,
        "InMarketType": "basicSearch",
        "Address": "Rockland", // Default location from Python code
        "Proximity": -1,
        "Make": make,
        "Model": null, // Explicitly null for model refinement
        "IsNew": true,
        "IsUsed": true,
        "IsCpo": true,
        "IsDamaged": false,
        "WithPhotos": true,
        "WithPrice": true,
        "HasDigitalRetail": false
    });

    let response = client.post(url)
        .json(&payload)
        // Add headers similar to Python code if needed, client might handle some
        .header("Accept", "application/json, text/javascript, */*; q=0.01")
        .send()
        .await?
        .error_for_status()?;

    // Parse the JSON response
    let json_response: Value = response.json().await
        .context("Failed to parse JSON response for models")?;

    // Extract models from the "Models" field, which seems to be a map/object
    let models_map = json_response.get("Models")
        .and_then(|v| v.as_object())
        .context("Could not find 'Models' object in response")?;

    // Get the keys (model names) from the map
    let models: Vec<String> = models_map.keys().cloned().collect();

    Ok(models)
}

// Fetches trims for a given make and model
pub async fn fetch_trims_for_model(make: &str, model: &str) -> Result<Vec<String>> {
    let client = get_client().await?;
    let url = "https://www.autotrader.ca/Refinement/Refine"; // Endpoint from Python code

    // Construct the payload
    let payload = serde_json::json!({
        "IsDealer": true,
        "IsPrivate": true,
        "InMarketType": "basicSearch",
        "Address": "Rockland", // Default location
        "Proximity": -1,
        "Make": make,
        "Model": model,
        // No Trim field needed when fetching trims
        "IsNew": true,
        "IsUsed": true,
        "IsCpo": true,
        "IsDamaged": false,
        "WithPhotos": true,
        "WithPrice": true,
        "HasDigitalRetail": false
    });

    let response = client.post(url)
        .json(&payload)
        .header("Accept", "application/json, text/javascript, */*; q=0.01")
        .send()
        .await?
        .error_for_status()?;

    let json_response: Value = response.json().await
        .context("Failed to parse JSON response for trims")?;

    // Extract trims from the "Trims" field
    let trims_map = json_response.get("Trims")
        .and_then(|v| v.as_object())
        .context("Could not find 'Trims' object in response")?;

    // Get the keys (trim names), filter out "Status" if present
    let trims: Vec<String> = trims_map.keys()
        .filter(|&k| k.to_lowercase() != "status") // Filter out "Status" key
        .cloned()
        .collect();

    Ok(trims)
}

// Fetches colors for a given make, model, and optional trim
pub async fn fetch_colors(make: &str, model: &str, trim: Option<&str>) -> Result<Vec<String>> {
    let client = get_client().await?;
    let url = "https://www.autotrader.ca/Refinement/Refine";

    // Construct the payload, including trim if provided
    let payload = serde_json::json!({
        "IsDealer": true,
        "IsPrivate": true,
        "InMarketType": "basicSearch",
        "Address": "Rockland", // Default location
        "Proximity": -1,
        "Make": make,
        "Model": model,
        "Trim": trim, // Will be null if trim is None, handled by json! macro
        "IsNew": true,
        "IsUsed": true,
        "IsCpo": true,
        "IsDamaged": false,
        "WithPhotos": true,
        "WithPrice": true,
        "HasDigitalRetail": false
    });

    let response = client.post(url)
        .json(&payload)
        .header("Accept", "application/json, text/javascript, */*; q=0.01")
        .send()
        .await?
        .error_for_status()?;

    let json_response: Value = response.json().await
        .context("Failed to parse JSON response for colors")?;

    // Extract colors from the "ExteriorColour" field (note the 'u')
    let colors_map = json_response.get("ExteriorColour")
        .and_then(|v| v.as_object())
        .context("Could not find 'ExteriorColour' object in response")?;

    // Get the keys (color names), filter out "Status"
    let colors: Vec<String> = colors_map.keys()
        .filter(|&k| k.to_lowercase() != "status")
        .cloned()
        .collect();

    Ok(colors)
}
