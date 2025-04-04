// Handlers for backend API endpoints

use axum::{
    response::{IntoResponse, Json},
    // Removed: http::StatusCode,
    extract::{Query, Path, Json as JsonExtract, State},
};
// Removed: use reqwest::Client;
use serde::{Deserialize, Serialize};
use crate::{
    auth_middleware::AuthenticatedUser, // Import the extractor
    error::AppError,
    autotrader_api,
    // Removed unused model: SavedPayload
    // Removed unused config: Settings
    models::{SearchParams, UserSettings},
    scraper,
    firestore,
};
use std::sync::Arc;

// Import AppState struct (assuming it's made public in main.rs or moved)
use crate::AppState;

// --- Response Wrappers ---

#[derive(Serialize)]
struct SettingsResponse {
    success: bool,
    settings: UserSettings,
    error: Option<String>,
}

#[derive(Serialize)]
struct GenericResponse {
    success: bool,
    message: Option<String>,
    id: Option<String>,
    error: Option<String>,
}

// --- Request Structs ---

#[derive(Deserialize)]
pub struct ModelsQuery {
    make: String,
}

#[derive(Deserialize)]
pub struct TrimsQuery {
    make: String,
    model: String,
}

#[derive(Deserialize)]
pub struct ColorsQuery {
    make: String,
    model: String,
    trim: Option<String>,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct SavePayloadRequest {
    name: String,
    #[serde(flatten)]
    params: SearchParams,
}


// --- API Handlers ---

pub async fn get_makes(
    State(app_state): State<AppState>, // Extract AppState
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("[HANDLER] /api/makes - Request received.");

    // Pass the shared client from app_state
    tracing::debug!("[HANDLER] /api/makes - Calling autotrader_api::fetch_all_makes(true)...");
    let makes_result = autotrader_api::fetch_all_makes(Arc::clone(&app_state.http_client), true).await;
    match makes_result {
        Ok(makes_value) => {
            // Transform the JSON object into a JSON array of make names (strings)
            let makes_list: Vec<String> = makes_value
                .as_object()
                .map(|map| {
                    // Extract the keys (make names) directly as strings
                    map.keys().cloned().collect()
                })
                .unwrap_or_else(|| {
                    tracing::warn!("[HANDLER] /api/makes - Received non-object response from fetch_all_makes, returning empty list.");
                    Vec::new() // Return empty list if not an object
                });

            tracing::info!("[HANDLER] /api/makes - Successfully fetched and transformed {} makes into a list.", makes_list.len());
            tracing::info!("[HANDLER] /api/makes - Data being returned as list: {:?}", makes_list);
            Ok(Json(makes_list)) // Return the Vec<String> which serializes to a JSON array
        }
        Err(e) => {
            tracing::error!("[HANDLER] /api/makes - Error fetching makes: {:?}", e);
            Err(AppError::InternalServerError(e.context("Failed to fetch makes in handler")))
        }
    }
}

// Change to accept make as a path parameter
pub async fn get_models(
    State(app_state): State<AppState>, // Extract AppState
    Path(make): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("[HANDLER] /api/models/:make - Request received for make: {}", make);
    tracing::debug!("[HANDLER] /api/models/:make - Calling autotrader_api::fetch_models_for_make...");

    // Pass the shared client
    let models_result = autotrader_api::fetch_models_for_make(Arc::clone(&app_state.http_client), &make).await;

    match models_result {
        Ok(models_value) => { // models_value is already filtered by fetch_models_for_make
            // Get the count from the returned JSON object
            let count = models_value.as_object().map_or(0, |map| map.len());
            tracing::info!("[HANDLER] /api/models/:make - Successfully fetched {} models for make '{}'. Returning JSON.", count, make);
            Ok(Json(models_value)) // Return the Value directly (already filtered in autotrader_api.rs)
        }
        Err(e) => {
            tracing::error!("[HANDLER] /api/models/:make - Error fetching models for make '{}': {:?}", make, e);
            Err(AppError::InternalServerError(e.context(format!("Failed to fetch models for make '{}' in handler", make))))
        }
    }
}

pub async fn get_trims(
    State(app_state): State<AppState>, // Extract AppState
    Query(query): Query<TrimsQuery>,
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: get_trims for make: {}, model: {}", query.make, query.model);
    // Pass the shared client
    let trims = autotrader_api::fetch_trims_for_model(Arc::clone(&app_state.http_client), &query.make, &query.model).await?;
    Ok(Json(trims))
}

pub async fn get_colors(
    State(app_state): State<AppState>, // Extract AppState
    Query(query): Query<ColorsQuery>,
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: get_colors for make: {}, model: {}, trim: {:?}", query.make, query.model, query.trim);
    // Pass the shared client
    let colors = autotrader_api::fetch_colors(Arc::clone(&app_state.http_client), &query.make, &query.model, query.trim.as_deref()).await?;
    Ok(Json(colors))
}

pub async fn search_listings(
    State(app_state): State<AppState>, // Extract AppState
    JsonExtract(params): JsonExtract<SearchParams>,
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: search_listings with params: {:?}", params);

    // --- Step 1: Fetch initial listing summaries ---
    let client_clone = Arc::clone(&app_state.http_client); // Clone Arc for fetch_listings
    let listings = match scraper::fetch_listings(client_clone, &params).await {
        Ok(l) => l,
        Err(e) => {
            tracing::error!("Failed during initial listing fetch: {}", e);
            // Convert anyhow::Error back to AppError for response
            return Err(AppError::InternalServerError(e.context("Failed to fetch listing summaries")));
        }
    };

    if listings.is_empty() {
        tracing::info!("No listings found matching criteria.");
        // Return a success response but indicate no results found
        return Ok(Json(GenericResponse {
            success: true,
            message: Some("Search complete. No listings found matching your criteria.".to_string()),
            id: None,
            error: None,
        }));
    }

    tracing::info!("Found {} initial listings. Proceeding to fetch details and save CSV.", listings.len());

    // --- Step 2: Construct output path ---
    let make_str = params.make.as_deref().unwrap_or("UnknownMake");
    let model_str = params.model.as_deref().unwrap_or("UnknownModel");
    let year_min_str = params.year_min.map_or("Any".to_string(), |y| y.to_string());
    let year_max_str = params.year_max.map_or("Any".to_string(), |y| y.to_string());
    let price_min_str = params.price_min.map_or("Any".to_string(), |p| p.to_string());
    let price_max_str = params.price_max.map_or("Any".to_string(), |p| p.to_string());
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S").to_string();

    let folder_name = format!("Results/{}_{}", make_str, model_str);
    // Ensure filename is valid (replace invalid chars if necessary, though Rust handles paths well)
    let file_name = format!(
        "{}-{}_{}-{}_{}.csv",
        year_min_str, year_max_str, price_min_str, price_max_str, timestamp
    );
    let output_dir = std::path::PathBuf::from(folder_name);
    let output_file_path = output_dir.join(file_name);


    // --- Step 3: Fetch details and save CSV ---
    let client_clone_2 = Arc::clone(&app_state.http_client); // Clone Arc for fetch_details_and_save_csv
    match scraper::fetch_details_and_save_csv(client_clone_2, listings, output_file_path.clone()).await {
        Ok(_) => {
            tracing::info!("Successfully fetched details and saved CSV to: {:?}", output_file_path);
            Ok(Json(GenericResponse {
                success: true,
                message: Some(format!("Search complete. Results saved to: {}", output_file_path.display())),
                id: None, // Or maybe return the filename/path as ID?
                error: None,
            }))
        }
        Err(e) => {
             tracing::error!("Failed during VDP fetch or CSV saving: {}", e);
             // Convert anyhow::Error back to AppError for response
             Err(AppError::InternalServerError(e.context("Failed to fetch vehicle details or save results")))
        }
    }
}

pub async fn get_saved_payloads(
    State(app_state): State<AppState>, // Use AppState struct
    authenticated_user: AuthenticatedUser,
) -> Result<impl IntoResponse, AppError> {
    let user_id = &authenticated_user.user_id;
    tracing::info!("API call: get_saved_payloads for user: {}", user_id);
    // Access settings via app_state.settings
    let payloads = firestore::get_payloads(user_id, &app_state.settings).await?;
    Ok(Json(payloads))
}

pub async fn save_new_payload(
    State(app_state): State<AppState>, // Use AppState struct
    authenticated_user: AuthenticatedUser,
    JsonExtract(payload_req): JsonExtract<SavePayloadRequest>,
) -> Result<impl IntoResponse, AppError> {
    let user_id = &authenticated_user.user_id;
    tracing::info!("API call: save_new_payload for user: {}", user_id);

    match firestore::save_payload(user_id, &payload_req.name, &payload_req.params, &app_state.settings).await {
        Ok(doc_id) => Ok(Json(GenericResponse {
            success: true,
            message: Some("Payload saved successfully.".to_string()),
            id: Some(doc_id),
            error: None,
        })),
        Err(e) => {
            tracing::error!("Failed to save payload: {}", e);
            Err(AppError::InternalServerError(e.context("Failed to save payload")))
        }
    }
}


pub async fn get_settings(
    State(app_state): State<AppState>, // Use AppState struct
    authenticated_user: AuthenticatedUser,
) -> Result<impl IntoResponse, AppError> {
    let user_id = &authenticated_user.user_id;
    tracing::info!("API call: get_settings for user: {}", user_id);

    let result = firestore::get_user_settings(user_id, &app_state.settings).await;

    match result {
        Ok(Some(user_settings)) => Ok(Json(SettingsResponse {
            success: true,
            settings: user_settings,
            error: None,
        })),
        Ok(None) => {
            Ok(Json(SettingsResponse {
                success: true,
                settings: UserSettings { search_tokens: Some(0), can_use_ai: Some(false) },
                error: None,
            }))
        }
        Err(e) => {
            tracing::error!("Failed to get user settings: {}", e);
             Ok(Json(SettingsResponse {
                 success: false,
                 settings: UserSettings { search_tokens: Some(0), can_use_ai: Some(false) },
                 error: Some(format!("Failed to retrieve settings: {}", e)),
             }))
        }
    }
}


pub async fn save_settings(
    State(app_state): State<AppState>, // Use AppState struct
    authenticated_user: AuthenticatedUser,
    JsonExtract(user_settings): JsonExtract<UserSettings>,
) -> Result<impl IntoResponse, AppError> {
    let user_id = &authenticated_user.user_id;
    tracing::info!("API call: save_settings for user: {}", user_id);

    match firestore::save_user_settings(user_id, &user_settings, &app_state.settings).await {
        Ok(_) => Ok(Json(GenericResponse {
            success: true,
            message: Some("Settings saved successfully.".to_string()),
            id: None, // No ID relevant here
            error: None,
        })),
        Err(e) => {
            tracing::error!("Failed to save user settings: {}", e);
            // Return AppError to let the central error handler manage the response
            Err(AppError::InternalServerError(e.context("Failed to save user settings")))
        }
    }
}

// Add other API handlers here later (results management, etc.)
