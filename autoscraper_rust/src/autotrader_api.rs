// Functions to interact with AutoTrader.ca (fetching makes, models, etc.)

use anyhow::{anyhow, Context, Result};
use reqwest::Client;
use scraper::{Html, Selector};
use serde_json::{json, Value}; // Import json macro

// Reusable HTTP client (made public)
pub async fn get_client() -> Result<Client> {
    tracing::debug!("[AUTOTRADER_API] Creating reqwest client...");
    reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        .build()
        .context("Failed to build reqwest client")
}

// Fetches makes from AutoTrader homepage HTML, returning a JSON object { "MakeName": null, ... }
pub async fn fetch_all_makes(popular_only: bool) -> Result<Value> { // Changed return type
    tracing::info!("[AUTOTRADER_API] fetch_all_makes called (popular_only: {})", popular_only);
    let client = get_client().await.context("Failed to get client in fetch_all_makes")?;
    let url = "https://www.autotrader.ca/";
    tracing::debug!("[AUTOTRADER_API] Fetching URL: {}", url);

    let response_text = match client.get(url).send().await {
        Ok(resp) => {
            tracing::debug!("[AUTOTRADER_API] Received response status: {}", resp.status());
            match resp.error_for_status() {
                Ok(resp_ok) => resp_ok.text().await.context("Failed to get response text"),
                Err(e) => {
                    tracing::error!("[AUTOTRADER_API] HTTP error status: {}", e.status().unwrap_or_default());
                    Err(anyhow!(e).context("HTTP error fetching AutoTrader homepage"))
                }
            }
        }
        Err(e) => {
            tracing::error!("[AUTOTRADER_API] Network error fetching AutoTrader homepage: {:?}", e);
            Err(anyhow!(e).context("Network error fetching AutoTrader homepage"))
        }
    }?;

    tracing::debug!("[AUTOTRADER_API] Successfully fetched homepage HTML (length: {}).", response_text.len());
    // Log raw HTML for debugging (might be very long)
    tracing::debug!("[AUTOTRADER_API] Raw HTML Response:\n{}", response_text);
    tracing::debug!("[AUTOTRADER_API] Parsing HTML...");

    // Parse the HTML
    let document = Html::parse_document(&response_text);

    // Define the CSS selector based on popular_only flag
    let optgroup_label = if popular_only { "Popular Makes" } else { "All Makes" };
    let selector_str = format!("optgroup[label='{}'] > option", optgroup_label);
    tracing::debug!("[AUTOTRADER_API] Using selector: {}", selector_str);

    let option_selector = Selector::parse(&selector_str)
        .map_err(|e| anyhow!("Failed to parse make selector: {:?}", e))?;

    let makes: Vec<String> = document
        .select(&option_selector)
        .map(|element| element.text().collect::<String>().trim().to_string())
        .filter(|make| !make.is_empty())
        .collect();

    if makes.is_empty() {
        tracing::warn!("[AUTOTRADER_API] No makes found for optgroup label: {}", optgroup_label);
        // Consider returning an error or empty vec depending on desired behavior
        // return Err(anyhow!("No makes found for selector '{}'", selector_str));
    } else {
        tracing::info!("[AUTOTRADER_API] Found {} makes.", makes.len());
        tracing::debug!("[AUTOTRADER_API] Makes found: {:?}", makes);
    }

    // Convert Vec<String> to serde_json::Map<String, Value> with null values
    let makes_map: serde_json::Map<String, Value> = makes
        .into_iter()
        .map(|make| (make, Value::Null)) // Use null as placeholder value
        .collect();

    Ok(json!(makes_map)) // Return as serde_json::Value
}

// Fetches models for a given make, returning the JSON object { "ModelName": count, ... }
pub async fn fetch_models_for_make(make: &str) -> Result<Value> { // Changed return type
    tracing::info!("[AUTOTRADER_API] fetch_models_for_make called (make: {})", make);
    let client = get_client().await.context("Failed to get client in fetch_models_for_make")?;
    let url = "https://www.autotrader.ca/Home/Refine"; // This URL might be incorrect for fetching models via POST
    tracing::info!("[AUTOTRADER_API] Attempting to fetch models from URL: {}", url);

    let payload = json!({
        "IsDealer": true, "IsPrivate": true, "InMarketType": "basicSearch",
        "Address": "Rockland", "Proximity": -1, "Make": make, "Model": null,
        "IsNew": true, "IsUsed": true, "IsCpo": true, "IsDamaged": false,
        "WithPhotos": true, "WithPrice": true, "HasDigitalRetail": false
    });
    tracing::debug!("[AUTOTRADER_API] Models payload: {}", payload);

    let response_result = client.post(url)
        .json(&payload)
        .header("Accept", "application/json, text/javascript, */*; q=0.01")
        .send()
        .await;

    let response = match response_result {
        Ok(resp) => {
            tracing::info!("[AUTOTRADER_API] Models response status: {}", resp.status());
            resp.error_for_status()? // Check for HTTP errors (like 404)
        }
        Err(e) => {
            tracing::error!("[AUTOTRADER_API] Network error fetching models: {:?}", e);
            return Err(anyhow!(e).context("Network error fetching models"));
        }
    };

    let json_response: Value = response.json().await.context("Failed to parse JSON response for models")?;
    tracing::debug!("[AUTOTRADER_API] Models JSON response parsed: {:?}", json_response);

    // Extract the "Models" object, filter out "Status", and return it
    let models_value = json_response.get("Models")
        .cloned() // Clone the Value
        .context("Could not find 'Models' object in response")?;

    if let Some(models_map) = models_value.as_object() {
        let mut filtered_map = models_map.clone();
        filtered_map.remove("Status"); // Remove the status key if present
        tracing::info!("[AUTOTRADER_API] Found {} models (after filtering) for make '{}'.", filtered_map.len(), make);
        Ok(json!(filtered_map)) // Return the filtered map as a Value
    } else {
        Err(anyhow!("'Models' field is not a JSON object"))
    }
}

// Fetches trims for a given make and model
pub async fn fetch_trims_for_model(make: &str, model: &str) -> Result<Vec<String>> {
    tracing::info!("[AUTOTRADER_API] fetch_trims_for_model called (make: {}, model: {})", make, model);
    let client = get_client().await.context("Failed to get client in fetch_trims_for_model")?;
    let url = "https://www.autotrader.ca/Refinement/Refine";
    tracing::debug!("[AUTOTRADER_API] Fetching trims URL: {}", url);

    let payload = json!({
        "IsDealer": true, "IsPrivate": true, "InMarketType": "basicSearch",
        "Address": "Rockland", "Proximity": -1, "Make": make, "Model": model,
        "IsNew": true, "IsUsed": true, "IsCpo": true, "IsDamaged": false,
        "WithPhotos": true, "WithPrice": true, "HasDigitalRetail": false
    });
    tracing::debug!("[AUTOTRADER_API] Trims payload: {}", payload);

    let response = client.post(url)
        .json(&payload)
        .header("Accept", "application/json, text/javascript, */*; q=0.01")
        .send()
        .await?
        .error_for_status()?;

    tracing::debug!("[AUTOTRADER_API] Trims response status: {}", response.status());
    let json_response: Value = response.json().await.context("Failed to parse JSON response for trims")?;
    tracing::debug!("[AUTOTRADER_API] Trims JSON response parsed.");

    let trims_map = json_response.get("Trims")
        .and_then(|v| v.as_object())
        .context("Could not find 'Trims' object in response")?;

    let trims: Vec<String> = trims_map.keys()
        .filter(|&k| k.to_lowercase() != "status")
        .cloned()
        .collect();
    tracing::info!("[AUTOTRADER_API] Found {} trims for {} {}.", trims.len(), make, model);
    Ok(trims)
}

// Fetches colors for a given make, model, and optional trim
pub async fn fetch_colors(make: &str, model: &str, trim: Option<&str>) -> Result<Vec<String>> {
    tracing::info!("[AUTOTRADER_API] fetch_colors called (make: {}, model: {}, trim: {:?})", make, model, trim);
    let client = get_client().await.context("Failed to get client in fetch_colors")?;
    let url = "https://www.autotrader.ca/Refinement/Refine";
    tracing::debug!("[AUTOTRADER_API] Fetching colors URL: {}", url);

    let payload = json!({
        "IsDealer": true, "IsPrivate": true, "InMarketType": "basicSearch",
        "Address": "Rockland", "Proximity": -1, "Make": make, "Model": model, "Trim": trim,
        "IsNew": true, "IsUsed": true, "IsCpo": true, "IsDamaged": false,
        "WithPhotos": true, "WithPrice": true, "HasDigitalRetail": false
    });
    tracing::debug!("[AUTOTRADER_API] Colors payload: {}", payload);

    let response = client.post(url)
        .json(&payload)
        .header("Accept", "application/json, text/javascript, */*; q=0.01")
        .send()
        .await?
        .error_for_status()?;

    tracing::debug!("[AUTOTRADER_API] Colors response status: {}", response.status());
    let json_response: Value = response.json().await.context("Failed to parse JSON response for colors")?;
    tracing::debug!("[AUTOTRADER_API] Colors JSON response parsed.");

    let colors_map = json_response.get("ExteriorColour")
        .and_then(|v| v.as_object())
        .context("Could not find 'ExteriorColour' object in response")?;

    let colors: Vec<String> = colors_map.keys()
        .filter(|&k| k.to_lowercase() != "status")
        .cloned()
        .collect();
    tracing::info!("[AUTOTRADER_API] Found {} colors.", colors.len());
    Ok(colors)
}
