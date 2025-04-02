// Placeholder for data structures (structs)
// e.g., User, SearchParams, ListingDetails

use serde::{Deserialize, Serialize};

// Search parameters received from the frontend form
#[derive(Debug, Deserialize, Serialize, Clone)] // Added Clone
#[serde(rename_all = "camelCase")] // Match JavaScript frontend keys
pub struct SearchParams {
    // Basic vehicle info
    pub make: Option<String>,
    pub model: Option<String>,
    pub trim: Option<String>,
    pub color: Option<String>, // Renamed from Colours for consistency
    pub year_min: Option<u32>,
    pub year_max: Option<u32>,

    // Price & Mileage
    pub price_min: Option<u32>,
    pub price_max: Option<u32>,
    pub odometer_min: Option<u32>,
    pub odometer_max: Option<u32>,

    // Location
    pub address: Option<String>,
    pub proximity: Option<i32>, // Can be -1

    // Condition & Features
    pub is_new: Option<bool>,
    pub is_used: Option<bool>,
    pub is_damaged: Option<bool>,
    pub with_photos: Option<bool>,
    // pub with_price: Option<bool>, // Assuming always true based on Python defaults

    // Filters
    pub drivetrain: Option<String>,
    pub transmission: Option<String>,
    pub body_type: Option<String>,
    pub num_doors: Option<u32>,
    pub seating_capacity: Option<u32>,

    // Keywords
    pub exclusions: Option<Vec<String>>,
    pub inclusion: Option<String>,

    // --- Fields from Python defaults/payload not explicitly on form yet ---
    // pub is_cpo: Option<bool>,
    // pub is_dealer: Option<bool>,
    // pub is_private: Option<bool>,
    // pub top: Option<u32>, // Results per page, default 100 in Python
}

// Represents a single listing found in search results
#[derive(Debug, Serialize, Deserialize, Clone)] // Added Clone + Deserialize
#[serde(rename_all = "camelCase")]
pub struct ListingResult {
    pub link: String,
    pub title: Option<String>,
    pub price: Option<String>,
    pub mileage: Option<String>,
    pub location: Option<String>,
    // Add more detailed fields later if needed after fetching details
    // pub year: Option<u32>,
    // pub make: Option<String>,
    // pub model: Option<String>,
    // pub trim: Option<String>,
    // pub drivetrain: Option<String>,
    // ... etc
}

// Struct to capture the ID token submitted from the login form
#[derive(Debug, Deserialize)]
pub struct LoginForm {
    // Field name must match the 'name' attribute in the HTML form input
    #[serde(rename = "idToken")]
    pub id_token: String,
}

// Represents a saved search payload stored in Firestore
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct SavedPayload {
    pub id: String, // Firestore document ID
    pub name: String, // User-defined name
    #[serde(flatten)] // Embed SearchParams fields directly
    pub params: SearchParams,
    // Add timestamp if needed later
    // pub saved_at: Option<chrono::DateTime<chrono::Utc>>,
}

// Represents user settings stored in Firestore
#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct UserSettings {
    // Assuming Firestore stores tokens as integer (or string convertible to integer)
    pub search_tokens: Option<i64>, // Use i64 for potentially large numbers
    pub can_use_ai: Option<bool>,
    // Add other settings fields as needed
}
