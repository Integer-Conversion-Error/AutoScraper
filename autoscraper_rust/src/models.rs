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
    pub results_per_page: Option<u32>, // Added to match Python 'Top' param usage
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


// Represents detailed vehicle information extracted from a VDP
#[derive(Debug, Serialize, Deserialize, Clone, Default)] // Added Default
#[serde(rename_all = "camelCase")]
pub struct VehicleDetails {
    // Fields corresponding to Python's extract_vehicle_info_from_json
    pub make: Option<String>,
    pub model: Option<String>,
    pub year: Option<String>, // Keep as String for now, parsing can be added if needed
    pub trim: Option<String>,
    pub price: Option<String>, // Keep as String
    pub drivetrain: Option<String>,
    pub kilometres: Option<String>, // Keep as String, parsing done in Python helper
    pub status: Option<String>,
    #[serde(rename = "bodyType")] // Match JSON key
    pub body_type: Option<String>,
    pub engine: Option<String>,
    pub cylinder: Option<String>, // Keep as String
    pub transmission: Option<String>,
    #[serde(rename = "exteriorColour")] // Match JSON key
    pub exterior_colour: Option<String>,
    pub doors: Option<String>, // Keep as String
    #[serde(rename = "fuelType")] // Match JSON key
    pub fuel_type: Option<String>,
    #[serde(rename = "cityFuelEconomy")] // Match JSON key
    pub city_fuel_economy: Option<String>, // Keep as String
    #[serde(rename = "hwyFuelEconomy")] // Match JSON key
    pub hwy_fuel_economy: Option<String>, // Keep as String
    // Add link for reference?
    pub link: Option<String>,
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
