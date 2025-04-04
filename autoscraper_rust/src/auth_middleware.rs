use axum::{
    async_trait,
    extract::{FromRequestParts, FromRef}, // Removed unused State
    http::request::Parts,
    // Removed: http::StatusCode, response::IntoResponse, response::Response
    RequestPartsExt,
};
use axum_extra::TypedHeader;
use headers::{authorization::Bearer, Authorization};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use once_cell::sync::Lazy;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::{collections::HashMap, sync::Arc, time::Duration};
use tracing::{error, info, warn};

use crate::{config::Settings, error::AppError}; // Assuming AppError exists

const GOOGLE_PUBLIC_KEYS_URL: &str =
    "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com";
const FIREBASE_ISSUER_PREFIX: &str = "https://securetoken.google.com/";

// --- Structs for Claims & Keys ---

#[derive(Debug, Serialize, Deserialize)]
pub struct Claims { // Make struct pub if needed elsewhere, or just fields
    pub aud: String, // Audience (Firebase Project ID)
    pub iss: String, // Issuer (e.g., https://securetoken.google.com/YOUR_PROJECT_ID)
    pub sub: String, // Subject (User ID)
    pub exp: usize,  // Expiration time (seconds since epoch)
    pub iat: usize,  // Issued at time (seconds since epoch)
    pub auth_time: usize,
    // Add other claims if needed (e.g., email, name)
    pub email: Option<String>,
    pub email_verified: Option<bool>,
}

// Structure to hold the fetched Google public keys
#[derive(Clone)]
struct GooglePublicKeys {
    keys: Arc<HashMap<String, DecodingKey>>,
    last_fetched: std::time::Instant,
    max_age: Duration,
}

// --- Key Fetching & Caching ---

// Use Lazy to fetch keys only once initially and cache them.
// TODO: Implement periodic refresh based on Cache-Control header from Google.
static PUBLIC_KEYS: Lazy<tokio::sync::RwLock<Option<GooglePublicKeys>>> =
    Lazy::new(|| tokio::sync::RwLock::new(None));

async fn get_google_keys(http_client: &Client) -> Result<Arc<HashMap<String, DecodingKey>>, AppError> {
    let read_guard = PUBLIC_KEYS.read().await;
    if let Some(cache) = &*read_guard {
        if cache.last_fetched.elapsed() < cache.max_age {
            info!("Using cached Google public keys.");
            return Ok(cache.keys.clone());
        }
    }
    drop(read_guard); // Release read lock before acquiring write lock

    info!("Fetching new Google public keys from {}", GOOGLE_PUBLIC_KEYS_URL);
    let response = http_client
        .get(GOOGLE_PUBLIC_KEYS_URL)
        .send()
        .await
        .map_err(|e| {
            error!("Failed to fetch Google public keys: {}", e);
            AppError::InternalServerError(anyhow::Error::new(e).context("Network error fetching Google keys"))
        })?;

    // Extract Cache-Control max-age
    let cache_control = response
        .headers()
        .get(reqwest::header::CACHE_CONTROL)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    let max_age = cache_control
        .split(',')
        .find_map(|part| {
            part.trim()
                .strip_prefix("max-age=")
                .and_then(|val| val.parse::<u64>().ok())
        })
        .map(Duration::from_secs)
        .unwrap_or_else(|| Duration::from_secs(3600)); // Default to 1 hour

    let response_text = response.text().await.map_err(|e| {
        error!("Failed to read Google public keys response body: {}", e);
        AppError::InternalServerError(anyhow::Error::new(e).context("Error reading Google keys response"))
    })?;

    let key_map: HashMap<String, String> = serde_json::from_str(&response_text).map_err(|e| {
        error!("Failed to parse Google public keys JSON: {}", e);
        AppError::InternalServerError(anyhow::Error::new(e).context("Error parsing Google keys JSON"))
    })?;

    let decoding_keys = key_map
        .into_iter()
        .filter_map(|(kid, key_pem)| {
            // Decode PEM format (assuming keys are PEM encoded)
            match DecodingKey::from_rsa_pem(key_pem.as_bytes()) {
                Ok(key) => Some((kid, key)),
                Err(e) => {
                    error!("Failed to decode public key PEM for kid {}: {}", kid, e);
                    None // Skip invalid keys
                }
            }
        })
        .collect::<HashMap<_, _>>();

    if decoding_keys.is_empty() {
        error!("No valid decoding keys could be parsed from Google's response.");
        return Err(AppError::InternalServerError(anyhow::anyhow!(
            "Failed to load any valid Google public keys"
        )));
    }

    let keys_arc = Arc::new(decoding_keys);
    let new_cache = GooglePublicKeys {
        keys: keys_arc.clone(),
        last_fetched: std::time::Instant::now(),
        max_age,
    };

    // Update the cache
    let mut write_guard = PUBLIC_KEYS.write().await;
    *write_guard = Some(new_cache);
    info!("Successfully fetched and cached {} Google public keys. Max-age: {:?}", keys_arc.len(), max_age);

    Ok(keys_arc)
}

// --- Token Verification ---

// Make pub so it can be called from login handler as well
pub async fn verify_token(token: &str, settings: &Settings, http_client: &Client) -> Result<Claims, AppError> {
    let header = decode_header(token).map_err(|e| {
        warn!("Invalid JWT header: {}", e);
        AppError::Unauthorized("Invalid token format".into())
    })?;

    let kid = header.kid.ok_or_else(|| {
        warn!("Token missing 'kid' (Key ID) in header");
        AppError::Unauthorized("Token missing key identifier".into())
    })?;

    let project_id = settings.firebase_project_id.as_deref().ok_or_else(|| {
        error!("Firebase Project ID not configured in settings.");
        AppError::InternalServerError(anyhow::anyhow!("Missing Firebase Project ID configuration"))
    })?;

    let keys = get_google_keys(http_client).await?;
    let decoding_key = keys.get(&kid).ok_or_else(|| {
        warn!("Unknown 'kid' {} found in token header", kid);
        // Optionally force refresh keys here if kid is unknown?
        AppError::Unauthorized("Unknown key identifier".into())
    })?;

    let mut validation = Validation::new(Algorithm::RS256);
    validation.set_audience(&[project_id]);
    let expected_issuer = format!("{}{}", FIREBASE_ISSUER_PREFIX, project_id);
    validation.set_issuer(&[expected_issuer]);
    // Add clock skew allowance if needed: validation.leeway = 60;

    let decoded = decode::<Claims>(token, decoding_key, &validation).map_err(|e| {
        warn!("Token validation failed: {}", e);
        match e.kind() {
            jsonwebtoken::errors::ErrorKind::ExpiredSignature => AppError::Unauthorized("Token expired".into()),
            jsonwebtoken::errors::ErrorKind::InvalidAudience => AppError::Unauthorized("Invalid token audience".into()),
            jsonwebtoken::errors::ErrorKind::InvalidIssuer => AppError::Unauthorized("Invalid token issuer".into()),
            _ => AppError::Unauthorized("Invalid token".into()),
        }
    })?;

    info!("Token successfully validated for user: {}", decoded.claims.sub);
    Ok(decoded.claims)
}

// --- Axum Middleware & Extractor ---

// This struct will be extracted from requests in protected handlers
#[derive(Clone)]
pub struct AuthenticatedUser {
    pub user_id: String,
    // Add other claims if needed (e.g., email)
    // pub email: Option<String>,
}

// Import AppState struct (assuming it's made public in main.rs or moved)
use crate::AppState;

#[async_trait]
impl<S> FromRequestParts<S> for AuthenticatedUser
where
    S: Send + Sync,
    AppState: FromRef<S>, // Require that AppState can be extracted from S
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        // Extract the token from the authorization header using axum_extra::TypedHeader
        let TypedHeader(Authorization(bearer)) = parts
            .extract::<TypedHeader<Authorization<Bearer>>>() // Use the imported TypedHeader from axum_extra
            .await
            .map_err(|e| {
                warn!("Failed to extract Authorization header: {}", e);
                AppError::Unauthorized("Missing or invalid Authorization header".into())
            })?;

        // Extract the AppState itself from the state S
        let app_state = AppState::from_ref(state);

        // Verify the token using fields from app_state
        let claims = verify_token(bearer.token(), &app_state.settings, &app_state.http_client).await?;

        // Return the authenticated user details
        Ok(AuthenticatedUser {
            user_id: claims.sub,
            // email: claims.email,
        })
    }
}

// You might not need a separate middleware layer if you just use the extractor
// in your handlers. However, a layer can be useful for applying auth to multiple routes.

// Example of a middleware function (if needed)
// pub async fn auth_middleware<B>(
//     State(settings): State<Arc<Settings>>,
//     State(http_client): State<Arc<Client>>, // Assuming Client is in state
//     mut req: axum::http::Request<B>,
//     next: axum::middleware::Next<B>,
// ) -> Result<Response, AppError> {
//     let auth_header = req.headers()
//         .get(axum::http::header::AUTHORIZATION)
//         .and_then(|header| header.to_str().ok());
//
//     let token = if let Some(header) = auth_header {
//         if let Some(token) = header.strip_prefix("Bearer ") {
//             token
//         } else {
//             warn!("Authorization header missing 'Bearer ' prefix");
//             return Err(AppError::Unauthorized("Invalid Authorization header format".into()));
//         }
//     } else {
//         warn!("Missing Authorization header");
//         return Err(AppError::Unauthorized("Authorization header required".into()));
//     };
//
//     match verify_token(token, &settings, &http_client).await {
//         Ok(claims) => {
//             // Store user info in request extensions
//             req.extensions_mut().insert(AuthenticatedUser { user_id: claims.sub });
//             Ok(next.run(req).await)
//         }
//         Err(e) => Err(e), // Propagate the AppError from verify_token
//     }
// }
