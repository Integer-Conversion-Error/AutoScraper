// Handlers for backend API endpoints

use axum::{
    response::{IntoResponse, Json},
    http::StatusCode,
    extract::{Query, Path, Json as JsonExtract, State},
};
use serde::{Deserialize, Serialize};
use crate::{
    error::AppError,
    autotrader_api,
    models::{SearchParams, UserSettings, SavedPayload},
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

pub async fn get_makes() -> Result<impl IntoResponse, AppError> {
    // ADDED VERY FIRST LOG
    tracing::info!("***** ENTERING get_makes HANDLER *****");
    tracing::info!("[HANDLER] /api/makes - Request received.");

    // Restore original code:
    tracing::debug!("[HANDLER] /api/makes - Calling autotrader_api::fetch_all_makes(true)...");
    let makes_result = autotrader_api::fetch_all_makes(true).await;
    match makes_result {
        Ok(makes) => {
            tracing::info!("[HANDLER] /api/makes - Successfully fetched {} makes. Returning JSON.", makes.len());
            Ok(Json(makes))
        }
        Err(e) => {
            tracing::error!("[HANDLER] /api/makes - Error fetching makes: {:?}", e);
            Err(AppError::InternalServerError(e.context("Failed to fetch makes in handler")))
        }
    }
}

// Change to accept make as a path parameter
pub async fn get_models(Path(make): Path<String>) -> Result<impl IntoResponse, AppError> {
    tracing::info!("[HANDLER] /api/models/:make - Request received for make: {}", make);
    tracing::debug!("[HANDLER] /api/models/:make - Calling autotrader_api::fetch_models_for_make...");

    let models_result = autotrader_api::fetch_models_for_make(&make).await;

    match models_result {
        Ok(models_value) => {
            // Get the count from the returned JSON object
            let count = models_value.as_object().map_or(0, |map| map.len());
            tracing::info!("[HANDLER] /api/models/:make - Successfully fetched {} models for make '{}'. Returning JSON.", count, make);
            Ok(Json(models_value)) // Return the Value directly
        }
        Err(e) => {
            tracing::error!("[HANDLER] /api/models/:make - Error fetching models for make '{}': {:?}", make, e);
            Err(AppError::InternalServerError(e.context(format!("Failed to fetch models for make '{}' in handler", make))))
        }
    }
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
        }
    }
}

// Add other API handlers here later (save settings, results management, etc.)
