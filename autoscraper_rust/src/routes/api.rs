// Handlers for backend API endpoints

use axum::{
    response::{IntoResponse, Json},
    http::StatusCode,
    extract::{Query, Path, Json as JsonExtract, State},
};
use serde::{Deserialize, Serialize}; // Added Serialize
use crate::{
    error::AppError,
    autotrader_api,
    models::{SearchParams, UserSettings, SavedPayload}, // Added SavedPayload
    scraper,
    config::Settings,
    firestore,
};
use std::sync::Arc;

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
    id: Option<String>, // For returning created document ID
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

// Request body for saving a payload
#[derive(Deserialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct SavePayloadRequest { // Make struct public
    name: String, // User-provided name for the payload
    // Use flatten to directly embed SearchParams fields from JS object
    #[serde(flatten)]
    params: SearchParams,
}


// --- API Handlers ---

pub async fn get_makes() -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: get_makes");
    let makes = autotrader_api::fetch_all_makes(true).await?;
    Ok(Json(makes))
}

pub async fn get_models(Query(query): Query<ModelsQuery>) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: get_models for make: {}", query.make);
    let models = autotrader_api::fetch_models_for_make(&query.make).await?;
    Ok(Json(models))
}

pub async fn get_trims(Query(query): Query<TrimsQuery>) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: get_trims for make: {}, model: {}", query.make, query.model);
    let trims = autotrader_api::fetch_trims_for_model(&query.make, &query.model).await?;
    Ok(Json(trims))
}

pub async fn get_colors(Query(query): Query<ColorsQuery>) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: get_colors for make: {}, model: {}, trim: {:?}", query.make, query.model, query.trim);
    let colors = autotrader_api::fetch_colors(&query.make, &query.model, query.trim.as_deref()).await?;
    Ok(Json(colors))
}

pub async fn search_listings(
    JsonExtract(params): JsonExtract<SearchParams>
) -> Result<impl IntoResponse, AppError> {
    tracing::info!("API call: search_listings");
    let results = scraper::fetch_listings(&params).await?;
    Ok(Json(results))
}

pub async fn get_saved_payloads(
    State(settings): State<Arc<Settings>>,
) -> Result<impl IntoResponse, AppError> {
    // TODO: Extract user_id from authenticated session/token
    let user_id = "placeholder_user_id";
    tracing::info!("API call: get_saved_payloads for user: {}", user_id);
    let payloads = firestore::get_payloads(user_id, &settings).await?;
    Ok(Json(payloads))
}

// Handler for POST /api/payloads (Save Payload)
// This will require authentication later
pub async fn save_new_payload(
    State(settings): State<Arc<Settings>>,
    JsonExtract(payload_req): JsonExtract<SavePayloadRequest>,
) -> Result<impl IntoResponse, AppError> {
    // TODO: Extract user_id from authenticated session/token
    let user_id = "placeholder_user_id";
    tracing::info!("API call: save_new_payload for user: {}", user_id);

    match firestore::save_payload(user_id, &payload_req.name, &payload_req.params, &settings).await {
        Ok(doc_id) => Ok(Json(GenericResponse {
            success: true,
            message: Some("Payload saved successfully.".to_string()),
            id: Some(doc_id),
            error: None,
        })),
        Err(e) => {
            tracing::error!("Failed to save payload: {}", e);
            Err(AppError::InternalServerError(e.context("Failed to save payload")))
            // Or return a JSON error response:
            // Ok(Json(GenericResponse {
            //     success: false,
            //     message: None,
            //     id: None,
            //     error: Some(format!("Failed to save payload: {}", e)),
            // }))
        }
    }
}


pub async fn get_settings(
    State(settings): State<Arc<Settings>>,
) -> Result<impl IntoResponse, AppError> {
    // TODO: Extract user_id from authenticated session/token
    let user_id = "placeholder_user_id";
    tracing::info!("API call: get_settings for user: {}", user_id);

    let result = firestore::get_user_settings(user_id, &settings).await;

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
            // Err(AppError::InternalServerError(e.context("Failed to get user settings")))
        }
    }
}

// Add other API handlers here later (save settings, results management, etc.)
