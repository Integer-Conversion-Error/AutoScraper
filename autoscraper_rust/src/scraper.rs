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

    for attempt in 0..MAX_RETRIES {
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

        match client.post(url).json(&payload).send().await {
            Ok(response) => {
                if let Err(e) = response.error_for_status_ref() {
                    // Handle HTTP errors
                    tracing::warn!("HTTP error on page {}: {}. Retrying...", page, e);
                    sleep(retry_delay).await;
                    retry_delay *= 2;
                    continue;
                }

                match response.json::<serde_json::Value>().await {
                    Ok(json_response) => {
                        let ads_html = json_response.get("AdsHtml").and_then(|v| v.as_str()).unwrap_or("");
                        let search_results_json_str = json_response.get("SearchResultsDataJson").and_then(|v| v.as_str()).unwrap_or("");

                        let exclusions_set: HashSet<String> = params.exclusions.clone().unwrap_or_default().into_iter().collect();
                        let page_results = parse_listing_html(ads_html, &exclusions_set);

                        let mut max_page = None;
                        if !search_results_json_str.is_empty() {
                             match serde_json::from_str::<serde_json::Value>(search_results_json_str) {
                                Ok(search_data) => {
                                    max_page = search_data.get("maxPage").and_then(|v| v.as_u64()).map(|p| p as u32);
                                }
                                Err(e) => tracing::warn!("Failed to parse SearchResultsDataJson on page {}: {}", page, e),
                            }
                        } else if page_results.is_empty() {
                            // No results at all, maybe retry?
                             tracing::warn!("No results (HTML or JSON) on page {}. Retrying...", page);
                             sleep(retry_delay).await;
                             retry_delay *= 2;
                             continue;
                        }

                        // Successfully got results for this page
                        return Ok((page_results, max_page));
                    }
                    Err(e) => {
                        // Handle JSON parsing errors
                        tracing::warn!("JSON parse error on page {}: {}. Retrying...", page, e);
                        sleep(retry_delay).await;
                        retry_delay *= 2;
                    }
                }
            }
            Err(e) => {
                // Handle network errors
                tracing::warn!("Network error on page {}: {}. Retrying...", page, e);
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
