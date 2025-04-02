// Functions for interacting with Google Cloud Firestore

use anyhow::{anyhow, Context, Result};
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use reqwest::Client;
use serde::{Deserialize, Serialize}; // Added Serialize
use serde_json::{json, Value}; // Added json macro and Value
use yup_oauth2::{ServiceAccountAuthenticator, ServiceAccountKey};
use std::{collections::HashMap, env};
use crate::models::{SavedPayload, SearchParams, UserSettings}; // Import UserSettings
use crate::config::Settings;

const FIRESTORE_SCOPES: [&str; 2] = [
    "https://www.googleapis.com/auth/datastore", // Firestore scope
    "https://www.googleapis.com/auth/cloud-platform", // General cloud scope
];

// Gets an authenticated reqwest client using service account credentials
// Reads credentials path from GOOGLE_APPLICATION_CREDENTIALS env var
pub async fn get_authenticated_client() -> Result<Client> {
    let creds_path = env::var("GOOGLE_APPLICATION_CREDENTIALS")
        .context("GOOGLE_APPLICATION_CREDENTIALS environment variable not set")?;

    let sa_key: ServiceAccountKey = yup_oauth2::read_service_account_key(&creds_path)
        .await
        .context("Failed to read service account key file")?;

    let auth = ServiceAccountAuthenticator::builder(sa_key)
        .build()
        .await
        .context("Failed to create service account authenticator")?;

    let token = auth.token(&FIRESTORE_SCOPES)
        .await
        .context("Failed to get OAuth2 token")?;

    let mut headers = HeaderMap::new();
    let auth_value = format!("Bearer {}", token.token().ok_or_else(|| anyhow!("Token string is empty"))?);
    headers.insert(
        AUTHORIZATION,
        HeaderValue::from_str(&auth_value).context("Failed to create Authorization header")?,
    );

    let client = Client::builder()
        .default_headers(headers)
        .build()
        .context("Failed to build authenticated reqwest client")?;

    Ok(client)
}

// --- Firestore Response/Request Structures ---

#[derive(Deserialize, Debug)]
#[serde(rename_all = "camelCase")]
struct FirestoreValue {
    string_value: Option<String>,
    integer_value: Option<String>, // Firestore integers are often strings
    boolean_value: Option<bool>,
    // array_value: Option<FirestoreArrayValue>, // Define if needed
    map_value: Option<FirestoreMapValue>,
    // null_value: Option<Value>, // For representing null
}

#[derive(Deserialize, Debug)]
struct FirestoreMapValue {
    fields: HashMap<String, FirestoreValue>,
}

#[derive(Deserialize, Debug)]
struct FirestoreDocument {
    name: String,
    fields: HashMap<String, FirestoreValue>,
}

#[derive(Deserialize, Debug)]
struct ListDocumentsResponse {
    documents: Option<Vec<FirestoreDocument>>,
}

// --- Firestore Serialization Helpers ---

fn to_string_value(val: &str) -> Value {
    json!({ "stringValue": val })
}

fn to_optional_string_value(val: &Option<String>) -> Value {
    match val {
        Some(s) => json!({ "stringValue": s }),
        None => json!({ "nullValue": null }),
    }
}

fn to_optional_int_value(val: &Option<u32>) -> Value {
    match val {
        Some(i) => json!({ "integerValue": i.to_string() }), // Store as string
        None => json!({ "nullValue": null }),
    }
}
fn to_optional_i32_value(val: &Option<i32>) -> Value {
     match val {
        Some(i) => json!({ "integerValue": i.to_string() }), // Store as string
        None => json!({ "nullValue": null }),
    }
}


fn to_optional_bool_value(val: &Option<bool>) -> Value {
    match val {
        Some(b) => json!({ "booleanValue": b }),
        None => json!({ "nullValue": null }),
    }
}

fn to_optional_string_array_value(val: &Option<Vec<String>>) -> Value {
    match val {
        Some(arr) => {
            let values: Vec<Value> = arr.iter().map(|s| json!({ "stringValue": s })).collect();
            json!({ "arrayValue": { "values": values } })
        }
        None => json!({ "nullValue": null }),
    }
}

// Converts SearchParams into a Firestore fields map (Value)
fn search_params_to_firestore_fields(name: &str, params: &SearchParams) -> Value {
    let mut fields = HashMap::new();
    fields.insert("name".to_string(), to_string_value(name));
    fields.insert("make".to_string(), to_optional_string_value(&params.make));
    fields.insert("model".to_string(), to_optional_string_value(&params.model));
    fields.insert("trim".to_string(), to_optional_string_value(&params.trim));
    fields.insert("color".to_string(), to_optional_string_value(&params.color));
    fields.insert("yearMin".to_string(), to_optional_int_value(&params.year_min));
    fields.insert("yearMax".to_string(), to_optional_int_value(&params.year_max));
    fields.insert("priceMin".to_string(), to_optional_int_value(&params.price_min));
    fields.insert("priceMax".to_string(), to_optional_int_value(&params.price_max));
    fields.insert("odometerMin".to_string(), to_optional_int_value(&params.odometer_min));
    fields.insert("odometerMax".to_string(), to_optional_int_value(&params.odometer_max));
    fields.insert("address".to_string(), to_optional_string_value(&params.address));
     fields.insert("proximity".to_string(), to_optional_i32_value(&params.proximity)); // Use i32 helper
    fields.insert("isNew".to_string(), to_optional_bool_value(&params.is_new));
    fields.insert("isUsed".to_string(), to_optional_bool_value(&params.is_used));
    fields.insert("isDamaged".to_string(), to_optional_bool_value(&params.is_damaged));
    fields.insert("withPhotos".to_string(), to_optional_bool_value(&params.with_photos));
    fields.insert("drivetrain".to_string(), to_optional_string_value(&params.drivetrain));
    fields.insert("transmission".to_string(), to_optional_string_value(&params.transmission));
    fields.insert("bodyType".to_string(), to_optional_string_value(&params.body_type));
    fields.insert("numDoors".to_string(), to_optional_int_value(&params.num_doors));
    fields.insert("seatingCapacity".to_string(), to_optional_int_value(&params.seating_capacity));
    fields.insert("exclusions".to_string(), to_optional_string_array_value(&params.exclusions));
    fields.insert("inclusion".to_string(), to_optional_string_value(&params.inclusion));

    json!({ "fields": fields })
}


// --- Firestore Interaction Functions ---

// Helper to extract document ID from the full name path
fn extract_doc_id(name: &str) -> Option<String> {
    name.split('/').last().map(|s| s.to_string())
}

// Helper to extract a string field from FirestoreValue map
fn get_string_field<'a>(fields: &'a HashMap<String, FirestoreValue>, key: &str) -> Option<&'a str> {
    fields.get(key)?.string_value.as_deref()
}

// Helper to extract an integer field (stored as string) from FirestoreValue map
fn get_integer_field(fields: &HashMap<String, FirestoreValue>, key: &str) -> Option<i64> {
    // Firestore integers might be strings or actual integer types in the JSON.
    // Let's try parsing string first, then check for integerValue if that fails.
    if let Some(s_val) = fields.get(key)?.string_value.as_ref() {
        if let Ok(parsed_int) = s_val.parse::<i64>() {
            return Some(parsed_int);
        }
    }
    // Add check for integerValue if needed, depends on how data is stored.
    // fields.get(key)?.integer_value.as_ref()?.parse::<i64>().ok()
    None // Return None if not found or not parsable as i64 string
}


// Helper to extract a boolean field from FirestoreValue map
fn get_boolean_field(fields: &HashMap<String, FirestoreValue>, key: &str) -> Option<bool> {
    // Firestore REST API typically uses "booleanValue" key
    fields.get(key)?.boolean_value
}


// Fetches saved payloads for a user
pub async fn get_payloads(user_id: &str, settings: &Settings) -> Result<Vec<SavedPayload>> {
    let client = get_authenticated_client().await?;
    let project_id = settings.firebase_project_id.as_deref()
        .ok_or_else(|| anyhow!("Firebase project ID not configured"))?;

    let url = format!(
        "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents/users/{}/payloads",
        project_id, user_id
    );

    let response = client.get(&url).send().await?.error_for_status()?;
    let list_response: ListDocumentsResponse = response.json().await
        .context("Failed to parse list documents response from Firestore")?;

    let mut payloads = Vec::new();
    if let Some(documents) = list_response.documents {
        for doc in documents {
            if let Some(doc_id) = extract_doc_id(&doc.name) {
                if let Some(name) = get_string_field(&doc.fields, "name") {
                    // TODO: Implement full parsing of SearchParams from doc.fields
                    let dummy_params = SearchParams {
                        make: None, model: None, trim: None, color: None, year_min: None,
                        year_max: None, price_min: None, price_max: None, odometer_min: None,
                        odometer_max: None, address: None, proximity: None, is_new: None,
                        is_used: None, is_damaged: None, with_photos: None, drivetrain: None,
                        transmission: None, body_type: None, num_doors: None, seating_capacity: None,
                        exclusions: None, inclusion: None
                    };
                    payloads.push(SavedPayload {
                        id: doc_id,
                        name: name.to_string(),
                        params: dummy_params,
                    });
                } else {
                    tracing::warn!("Payload document {} missing 'name' field", doc.name);
                }
            } else {
                tracing::warn!("Could not extract document ID from {}", doc.name);
            }
        }
    }
    Ok(payloads)
}

// Fetches user settings document
pub async fn get_user_settings(user_id: &str, settings: &Settings) -> Result<Option<UserSettings>> {
    let client = get_authenticated_client().await?;
    let project_id = settings.firebase_project_id.as_deref()
        .ok_or_else(|| anyhow!("Firebase project ID not configured"))?;

    let url = format!(
        "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents/users/{}",
        project_id, user_id
    );

    let response = client.get(&url).send().await?;
    if response.status() == reqwest::StatusCode::NOT_FOUND { return Ok(None); }
    let response = response.error_for_status()?;
    let doc: FirestoreDocument = response.json().await
        .context("Failed to parse user settings document response from Firestore")?;

    let user_settings = UserSettings {
        search_tokens: get_integer_field(&doc.fields, "searchTokens"),
        can_use_ai: get_boolean_field(&doc.fields, "canUseAi"),
    };
    Ok(Some(user_settings))
}

// Saves a new payload document for a user
pub async fn save_payload(user_id: &str, name: &str, params: &SearchParams, settings: &Settings) -> Result<String> {
    let client = get_authenticated_client().await?;
    let project_id = settings.firebase_project_id.as_deref()
        .ok_or_else(|| anyhow!("Firebase project ID not configured"))?;

    // URL for creating documents in the user's 'payloads' subcollection
    let url = format!(
        "https://firestore.googleapis.com/v1/projects/{}/databases/(default)/documents/users/{}/payloads",
        project_id, user_id
    );

    // Construct the Firestore document body
    let firestore_doc_body = search_params_to_firestore_fields(name, params);

    let response = client.post(&url)
        .json(&firestore_doc_body)
        .send()
        .await?
        .error_for_status()?;

    // Parse the response to get the name (which includes the generated ID) of the created document
    let created_doc: FirestoreDocument = response.json().await
        .context("Failed to parse response after creating payload document")?;

    let doc_id = extract_doc_id(&created_doc.name)
        .ok_or_else(|| anyhow!("Could not extract document ID from created payload response"))?;

    tracing::info!("Successfully saved payload with ID: {}", doc_id);
    Ok(doc_id)
}


// TODO: Implement Delete Payload (delete document)
// TODO: Implement Rename Payload (update document - might require get + delete + save)
// TODO: Implement Get Results (list documents)
// TODO: Implement Save Results (create document - maybe store results directly or link to storage)
// TODO: Implement Delete Results (delete document)
// TODO: Implement Rename Results (update document)
// TODO: Implement Save User Settings (update document)
