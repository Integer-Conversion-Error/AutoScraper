use anyhow::{Context, Result, anyhow};
use jsonwebtoken::{decode, decode_header, Algorithm, DecodingKey, Validation};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::config::Settings; // Assuming Firebase Project ID is in config

// Struct to represent the claims inside the Firebase ID token
#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    aud: String, // Audience (Firebase project ID)
    iss: String, // Issuer (https://securetoken.google.com/<projectId>)
    sub: String, // Subject (Firebase user ID)
    email: Option<String>, // User's email
    name: Option<String>, // User's display name
    exp: usize, // Expiration time (Unix timestamp)
    // Add other claims if needed (e.g., auth_time, iat)
}

// Fetches Google's public keys for verifying Firebase tokens
// Uses simple caching to avoid fetching on every request
// In a real app, use a more robust caching mechanism (e.g., with TTL)
async fn get_google_public_keys() -> Result<HashMap<String, String>> {
    // TODO: Implement proper caching with TTL
    let url = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com";
    let client = reqwest::Client::new();
    let response = client.get(url).send().await?.error_for_status()?;
    let keys: HashMap<String, String> = response.json().await?;
    Ok(keys)
}

// Verifies a Firebase ID token and returns the user ID (sub claim) if valid
pub async fn verify_token(token: &str, settings: &Settings) -> Result<String> {
    let header = decode_header(token).context("Failed to decode JWT header")?;
    let kid = header.kid.ok_or_else(|| anyhow!("Token header missing 'kid'"))?;

    let keys = get_google_public_keys().await.context("Failed to fetch Google public keys")?;
    let public_key_pem = keys.get(&kid).ok_or_else(|| anyhow!("Public key for kid '{}' not found", kid))?;

    // Create a DecodingKey from the PEM-encoded public key
    let decoding_key = DecodingKey::from_rsa_pem(public_key_pem.as_bytes())
        .context("Failed to create decoding key from PEM")?;

    // Set up validation rules
    let project_id = settings.firebase_project_id.as_deref()
        .ok_or_else(|| anyhow!("Firebase project ID not configured"))?;
    let mut validation = Validation::new(Algorithm::RS256);
    validation.set_audience(&[project_id]);
    validation.set_issuer(&[format!("https://securetoken.google.com/{}", project_id)]);
    // Add leeway for clock skew if necessary: validation.leeway = 60;

    // Decode and validate the token
    let decoded_token = decode::<Claims>(token, &decoding_key, &validation)
        .context("JWT validation failed")?;

    // Token is valid, return the user ID (sub claim)
    Ok(decoded_token.claims.sub)
}

// We might also define Axum middleware or extractors here later
