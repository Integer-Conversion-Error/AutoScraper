use crate::{
    models::{ListingResult, SearchParams},
    autotrader_api, // Assuming get_client might move here or be shared
    error::AppError, // Use our app error
};
use anyhow::{Context, Result};
use futures::future::join_all; // For running futures concurrently
use reqwest::Client;
use scraper::{Html, Selector};
use serde_json::json;
use std::collections::HashSet;
use tokio::time::{sleep, Duration}; // For retry delays

const RESULTS_PER_PAGE: u32 = 100; // Default from Python code
const MAX_RETRIES: u32 = 5;
const INITIAL_RETRY_DELAY_MS: u64 = 500;

// Helper to parse HTML snippet from search results
fn parse_listing_html(html_content: &str, exclusions: &HashSet<String>) -> Vec<ListingResult> {
    let document = Html::parse_fragment(html_content); // Use parse_fragment for snippets
    let item_selector = Selector::parse("div.result-item").unwrap();
    let link_selector = Selector::parse("a.inner-link").unwrap();
    let title_selector = Selector::parse("span.title-with-trim").unwrap();
    let price_selector = Selector::parse("span.price-amount").unwrap();
    let mileage_selector = Selector::parse("span.odometer-proximity").unwrap();
    let location_selector = Selector::parse("span.proximity-text").unwrap(); // Might need refinement

    let mut listings = Vec::new();

    for item in document.select(&item_selector) {
        let title_elem = item.select(&title_selector).next();
        let title = title_elem.map(|t| t.text().collect::<String>().trim().to_string());

        // Apply exclusions based on title
        if let Some(ref t) = title {
            if exclusions.iter().any(|ex| t.to_lowercase().contains(&ex.to_lowercase())) {
                continue; // Skip excluded listing
            }
        }

        let link_elem = item.select(&link_selector).next();
        let link = link_elem.and_then(|a| a.value().attr("href")).map(|l| {
            // Prepend domain if link is relative
            if l.starts_with('/') {
                format!("https://www.autotrader.ca{}", l)
            } else {
                l.to_string()
            }
        });

        // Only add if a link was found
        if let Some(link_url) = link {
            let price = item.select(&price_selector).next().map(|p| p.text().collect::<String>().trim().to_string());
            let mileage = item.select(&mileage_selector).next().map(|m| m.text().collect::<String>().trim().to_string());
            // Location parsing might need adjustment based on actual HTML structure
            let location = item.select(&location_selector).next().map(|loc| loc.text().collect::<String>().trim().to_string());

            listings.push(ListingResult {
                link: link_url,
                title,
                price,
                mileage,
                location,
            });
        }
    }
    listings
}


// Fetches a single page of results with retries
async fn fetch_page(
    page: u32,
    client: &Client,
    params: &SearchParams,
) -> Result<(Vec<ListingResult>, Option<u32>), String> { // Return error as String for simplicity here
    let mut retry_delay = Duration::from_millis(INITIAL_RETRY_DELAY_MS);
    let url = "https://www.autotrader.ca/Refinement/Search";
    tracing::debug!(page, url, "Attempting to fetch page");

    for attempt in 0..MAX_RETRIES {
        tracing::debug!(page, attempt, "Fetch attempt {}/{}", attempt + 1, MAX_RETRIES);
        // Construct payload for this page
        // Use defaults similar to Python code
        let payload = json!({
            "Address": params.address.as_deref().unwrap_or("Kanata, ON"),
            "Proximity": params.proximity.unwrap_or(-1),
            "Make": params.make,
            "Model": params.model,
            "Trim": params.trim,
            "PriceMin": params.price_min.unwrap_or(0),
            "PriceMax": params.price_max.unwrap_or(999999),
            "Skip": page * RESULTS_PER_PAGE,
            "Top": RESULTS_PER_PAGE,
            "IsNew": params.is_new.unwrap_or(true),
            "IsUsed": params.is_used.unwrap_or(true),
            "WithPhotos": params.with_photos.unwrap_or(true),
            "WithPrice": true, // Defaulted in Python
            "YearMin": params.year_min.unwrap_or(1950),
            "YearMax": params.year_max.unwrap_or(2050),
            "OdometerMin": params.odometer_min,
            "OdometerMax": params.odometer_max,
            "micrositeType": 1, // From Python payload
            // Optional fields from SearchParams
            "Colours": params.color, // Note key name difference
            "Drivetrain": params.drivetrain,
            "Transmissions": params.transmission, // Note key name difference
            "IsDamaged": params.is_damaged.unwrap_or(false),
            "BodyType": params.body_type,
            "NumberOfDoors": params.num_doors,
            "SeatingCapacity": params.seating_capacity,
        });
        tracing::debug!(page, attempt, payload = %payload, "Request payload"); // Log full payload at debug

        match client.post(url).json(&payload).send().await {
            Ok(response) => {
                let status = response.status();
                tracing::debug!(page, attempt, status = %status, "Received response status");

                if let Err(e) = response.error_for_status_ref() {
                    // Handle HTTP errors
                    let response_text = response.text().await.unwrap_or_else(|_| "[Failed to read response body]".to_string());
                    // Log full body at debug level for inspection, keep warning concise
                    tracing::debug!(page, attempt, status = %status, error = %e, response_body = response_text, "HTTP error details");
                    tracing::warn!(page, attempt, status = %status, error = %e, "HTTP error encountered. Retrying...");
                    sleep(retry_delay).await;
                    retry_delay *= 2;
                    continue;
                }

                // Need to buffer the response to read JSON and potentially text later on error
                let response_bytes = match response.bytes().await {
                     Ok(b) => b,
                     Err(e) => {
                         tracing::warn!(page, attempt, error = %e, "Failed to read response bytes. Retrying...");
                         sleep(retry_delay).await;
                         retry_delay *= 2;
                         continue;
                     }
                 };

                match serde_json::from_slice::<serde_json::Value>(&response_bytes) {
                    Ok(json_response) => {
                        tracing::debug!(page, attempt, "Successfully parsed JSON response"); // Changed to debug
                        let ads_html = json_response.get("AdsHtml").and_then(|v| v.as_str()).unwrap_or("");
                        let search_results_json_str = json_response.get("SearchResultsDataJson").and_then(|v| v.as_str()).unwrap_or("");
                        // Log full extracted strings at debug level
                        tracing::debug!(page, attempt, ads_html_len = ads_html.len(), search_json_len = search_results_json_str.len(), "Extracted content strings");
                        tracing::debug!(page, attempt, ads_html = ads_html, "Extracted AdsHtml");
                        tracing::debug!(page, attempt, search_results_json = search_results_json_str, "Extracted SearchResultsDataJson");


                        let exclusions_set: HashSet<String> = params.exclusions.clone().unwrap_or_default().into_iter().collect();
                        let page_results = parse_listing_html(ads_html, &exclusions_set);

                        let mut max_page = None;
                        if !search_results_json_str.is_empty() {
                             match serde_json::from_str::<serde_json::Value>(search_results_json_str) {
                                Ok(search_data) => {
                                    max_page = search_data.get("maxPage").and_then(|v| v.as_u64()).map(|p| p as u32);
                                    tracing::debug!(page, attempt, max_page, "Parsed maxPage from SearchResultsDataJson");
                                }
                                // Log the raw string at debug level if parsing fails
                                Err(e) => tracing::debug!(page, attempt, error = %e, json_str = search_results_json_str, "Failed to parse SearchResultsDataJson string"),
                            }
                        } else if page_results.is_empty() {
                            // No results HTML and no SearchResultsDataJson
                             tracing::warn!(page, attempt, "No AdsHtml or SearchResultsDataJson found. Retrying...");
                             sleep(retry_delay).await;
                             retry_delay *= 2;
                             continue;
                        }

                        // Successfully got results for this page
                        tracing::debug!(page, attempt, num_results = page_results.len(), max_page, "Successfully fetched and parsed page");
                        return Ok((page_results, max_page));
                    }
                    Err(e) => {
                        // Handle JSON parsing errors
                        let response_text = String::from_utf8_lossy(&response_bytes);
                        // Log full body at debug level for inspection, keep warning concise
                        tracing::debug!(page, attempt, error = %e, response_body = %response_text, "JSON parse error details");
                        tracing::warn!(page, attempt, error = %e, "JSON parse error encountered. Retrying...");
                        sleep(retry_delay).await;
                        retry_delay *= 2;
                    }
                }
            }
            Err(e) => {
                // Handle network errors (e.g., DNS resolution, connection refused)
                tracing::warn!(page, attempt, error = %e, "Network error during request. Retrying...");
                sleep(retry_delay).await;
                retry_delay *= 2;
            }
        }
    }

    // If all retries fail
    Err(format!("Failed to fetch page {} after {} attempts.", page, MAX_RETRIES))
}


// Main function to fetch all listings based on search parameters
pub async fn fetch_listings(params: &SearchParams) -> Result<Vec<ListingResult>> {
    // TODO: Use shared client with proxy/headers from config if needed
    let client = autotrader_api::get_client().await?; // Using client from autotrader_api for now

    tracing::info!("Starting fetch for params: {:?}", params);

    // Initial fetch (page 0) to get total pages
    let (initial_results, max_page_opt) = fetch_page(0, &client, params).await
        .map_err(|e| anyhow::anyhow!(e)) // Convert String error to anyhow::Error
        .context("Failed to fetch initial page (page 0)")?;

    let max_page = max_page_opt.unwrap_or(1); // Default to 1 page if not found
    tracing::info!("Initial fetch complete. Max pages: {}", max_page);

    let mut all_results = initial_results;

    // Fetch remaining pages concurrently
    if max_page > 1 {
        let page_futures: Vec<_> = (1..max_page) // Fetch pages 1 to max_page-1
            .map(|page| fetch_page(page, &client, params))
            .collect();

        let results = join_all(page_futures).await;

        for (page_num, result) in results.into_iter().enumerate() {
            match result {
                Ok((page_data, _)) => {
                    all_results.extend(page_data);
                    // Log progress if needed
                    tracing::debug!("Fetched page {}", page_num + 1);
                }
                Err(e) => {
                    // Log error but continue processing other pages
                    tracing::error!("Failed to fetch page {}: {}", page_num + 1, e);
                }
            }
        }
    }

    // --- Post-processing ---
    // Remove duplicates based on link (case-insensitive?)
    let mut seen_links = HashSet::new();
    all_results.retain(|item| {
        let link_lower = item.link.to_lowercase();
        seen_links.insert(link_lower) // insert returns true if the value was not already present
    });

    // Apply inclusion keyword filter if present
    if let Some(ref inclusion_keyword) = params.inclusion {
        if !inclusion_keyword.is_empty() {
            let keyword_lower = inclusion_keyword.to_lowercase();
            // This is a basic filter, Python version filtered CSV later.
            // Filtering here might be less efficient if details are needed anyway.
            // For now, we filter based on the basic info we have.
            all_results.retain(|item| {
                item.title.as_ref().map_or(false, |t| t.to_lowercase().contains(&keyword_lower)) ||
                item.location.as_ref().map_or(false, |l| l.to_lowercase().contains(&keyword_lower))
                // Add more fields to check if needed
            });
        }
    }

    tracing::info!("Fetch complete. Found {} unique listings after filtering.", all_results.len());
    Ok(all_results)
}

// TODO: Implement fetch_vehicle_details (equivalent to extract_vehicle_info)
