import { firebaseUser, authStatePromise } from './auth.js'; // Import auth state
import { showNotification, showLoading, hideLoading, updateExclusionsList } from './ui.js';
import { loadMakes, loadModels, loadTrims, loadColors, loadSavedPayloads, fetchUserSettings, handleFetchData, handleSaveNamedPayload } from './api.js';
// Import other necessary functions from api.js or ui.js as needed

// --- Global State (Consider a dedicated state module later) ---
// These might be needed by functions moved from the original index.js
// If functions in other modules need these, they might need to be passed as arguments
// or accessed via a shared state module. For now, keep them here.
let currentPayload = null;
let exclusions = [];
let currentResultId = null;
let currentUserSettings = { searchTokens: 0, canUseAi: false };
let currentDisplayedResults = [];
let originalVehicles = [];
window.currentSearchResults = []; // Make accessible for now if displayResults needs it globally

// Make functions globally accessible if they were previously global and are needed by inline handlers or other scripts
// Or, preferably, attach listeners programmatically in listeners.js
window.loadMakes = loadMakes;
window.loadModels = loadModels;
window.loadTrims = loadTrims;
window.loadColors = loadColors;
window.loadSavedPayloads = loadSavedPayloads; // Needed by auth.js
window.fetchUserSettings = fetchUserSettings; // Needed by auth.js
window.updateTokenDisplay = (tokens) => { // Define globally if needed by auth.js
    const tokenValueEl = document.getElementById('tokenValue');
    if (tokenValueEl) { tokenValueEl.textContent = tokens ?? '0'; }
    currentUserSettings.searchTokens = tokens ?? 0; // Update local cache
};
window.getCurrentFormParams = getCurrentFormParams; // Needed by api.js
window.displayResults = displayResults; // Needed by api.js

// --- Initialization ---
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM loaded, initializing main.js...");

    // Ensure Firebase auth state is ready before potentially needing user info
    authStatePromise.then(() => {
        console.log("Auth state ready, proceeding with DOM setup.");

        // Initial data loads (non-auth dependent ones can start earlier if needed)
        loadMakes(true); // Load makes initially

        // Auth-dependent loads are now triggered by onAuthStateChanged in auth.js

        // --- Attach Event Listeners ---
        // (These listeners might need access to global state like 'exclusions')
        document.getElementById('makeSelect')?.addEventListener('change', function () { loadModels(this.value); });
        document.getElementById('modelSelect')?.addEventListener('change', function () {
            const make = document.getElementById('makeSelect').value;
            const model = this.value;
            loadTrims(make, model);
            loadColors(make, model);
        });
        document.getElementById('trimSelect')?.addEventListener('change', function () {
            const make = document.getElementById('makeSelect').value;
            const model = document.getElementById('modelSelect').value;
            loadColors(make, model, this.value || null);
        });
        document.getElementById('showAllMakes')?.addEventListener('click', () => loadMakes(false));
        document.getElementById('addExclusionBtn')?.addEventListener('click', addExclusion);
        document.getElementById('exclusionKeyword')?.addEventListener('keypress', (e) => { if (e.key === 'Enter') { e.preventDefault(); addExclusion(); } });
        document.getElementById('fetchDataBtn')?.addEventListener('click', handleFetchData);
        document.getElementById('settingsBtn')?.addEventListener('click', openUserSettingsModal);
        document.getElementById('saveUserSettingsBtn')?.addEventListener('click', saveUserSettings);
        document.getElementById('increaseTokensBtn')?.addEventListener('click', () => adjustTokens(1));
        document.getElementById('decreaseTokensBtn')?.addEventListener('click', () => adjustTokens(-1));
        document.getElementById('loadPayloadBtn')?.addEventListener('click', handleLoadPayload); // Placeholder
        document.getElementById('savePayloadBtn')?.addEventListener('click', handleSavePayloadClick); // Placeholder
        document.getElementById('saveNamedPayloadBtn')?.addEventListener('click', handleSaveNamedPayload);
        document.getElementById('deletePayloadBtn')?.addEventListener('click', deletePayload); // Placeholder
        document.getElementById('renamePayloadBtn')?.addEventListener('click', renamePayload); // Placeholder
        document.getElementById('viewResultBtn')?.addEventListener('click', viewSelectedResult); // Placeholder
        document.getElementById('deleteResultBtn')?.addEventListener('click', deleteSelectedResult); // Placeholder
        document.getElementById('renameResultBtn')?.addEventListener('click', renameResult); // Placeholder
        document.getElementById('saveRenameBtn')?.addEventListener('click', handleSaveRename); // Placeholder
        document.getElementById('openLinksBtn')?.addEventListener('click', handleOpenLinks); // Placeholder
        document.getElementById('downloadCsvBtn')?.addEventListener('click', handleDownloadCsv); // Placeholder
        document.getElementById('openSelectedLinksBtn')?.addEventListener('click', openSelectedVehicleLinks); // Placeholder
        document.getElementById('downloadSelectedResultBtn')?.addEventListener('click', downloadSelectedResultCsv); // Placeholder

        console.log("Event listeners attached.");
    });
});

// --- Functions previously in index.js (need access to state/UI/API) ---
// These functions might need imports or access to global state

function addExclusion() {
    const keywordInput = document.getElementById('exclusionKeyword');
    const keyword = keywordInput.value.trim();
    if (keyword && !exclusions.includes(keyword)) { // Access global 'exclusions'
        exclusions.push(keyword);
        updateExclusionsList(exclusions); // Pass state to UI function
        keywordInput.value = '';
    }
}

function getCurrentFormParams() {
     const make = document.getElementById('makeSelect').value;
     const params = {
        make: make || null,
        model: document.getElementById('modelSelect').value || null,
        trim: document.getElementById('trimSelect').value || null,
        color: document.getElementById('colorSelect').value || null,
        yearMin: parseInt(document.getElementById('yearMin').value) || null,
        yearMax: parseInt(document.getElementById('yearMax').value) || null,
        priceMin: parseInt(document.getElementById('priceMin').value) || null,
        priceMax: parseInt(document.getElementById('priceMax').value) || null,
        odometerMin: parseInt(document.getElementById('odometerMin').value) || null,
        odometerMax: parseInt(document.getElementById('odometerMax').value) || null,
        address: document.getElementById('address').value || "Kanata, ON",
        proximity: parseInt(document.getElementById('proximity').value) ?? -1,
        isNew: document.getElementById('isNew').checked,
        isUsed: document.getElementById('isUsed').checked,
        isDamaged: document.getElementById('isDamaged').checked,
        withPhotos: document.getElementById('withPhotos').checked,
        drivetrain: document.getElementById('drivetrainSelect').value || null,
        transmission: document.getElementById('transmissionSelect').value || null,
        bodyType: document.getElementById('bodyTypeInput').value || null,
        numDoors: parseInt(document.getElementById('numDoorsInput').value) || null,
        seatingCapacity: parseInt(document.getElementById('seatingCapacityInput').value) || null,
        exclusions: exclusions.length > 0 ? exclusions : null, // Access global 'exclusions'
        inclusion: document.getElementById('inclusion').value || null,
    };
    // Validation... (keep as is)
    if (!params.make) { showNotification('Please select a Make', 'warning'); return null; }
    if (params.yearMin && params.yearMax && params.yearMin > params.yearMax) { showNotification('Minimum Year cannot be greater than Maximum Year', 'warning'); return null; }
    if (params.priceMin && params.priceMax && params.priceMin > params.priceMax) { showNotification('Minimum Price cannot be greater than Maximum Price', 'warning'); return null; }
    if (params.odometerMin && params.odometerMax && params.odometerMin > params.odometerMax) { showNotification('Minimum KMs cannot be greater than Maximum KMs', 'warning'); return null; }
    return params;
}


// --- User Settings Modal Functions ---
// Needs access to fetchApi, showLoading, hideLoading, showNotification, currentUserSettings, updateTokenDisplay
function openUserSettingsModal() {
    const modal = new bootstrap.Modal(document.getElementById('userSettingsModal'));
    const loadingDiv = document.getElementById('userSettingsLoading');
    const formDiv = document.getElementById('userSettingsForm');
    const errorDiv = document.getElementById('userSettingsError');
    loadingDiv.style.display = 'block'; formDiv.style.display = 'none'; errorDiv.style.display = 'none'; modal.show();
    fetchApi('/api/settings') // fetchApi is imported
        .then(data => {
            loadingDiv.style.display = 'none';
            if (data && data.success && data.settings) {
                currentUserSettings = { searchTokens: data.settings.searchTokens ?? 0, canUseAi: data.settings.canUseAi ?? false }; // Update global
                document.getElementById('userTokensInput').value = currentUserSettings.searchTokens;
                document.getElementById('canUseAiCheckbox').checked = currentUserSettings.canUseAi;
                formDiv.style.display = 'block';
            } else { errorDiv.textContent = "Failed to load settings: " + (data?.error || 'Unknown error'); errorDiv.style.display = 'block'; }
        })
        .catch(error => { loadingDiv.style.display = 'none'; errorDiv.textContent = "Failed to load settings: " + error.message; errorDiv.style.display = 'block'; });
}

function adjustTokens(amount) {
    const input = document.getElementById('userTokensInput');
    let currentValue = parseInt(input.value) || 0;
    currentValue += amount;
    if (currentValue < 0) currentValue = 0;
    input.value = currentValue;
}

function saveUserSettings() {
    const tokens = parseInt(document.getElementById('userTokensInput').value);
    const canUseAi = document.getElementById('canUseAiCheckbox').checked;
    const errorDiv = document.getElementById('userSettingsError');
    errorDiv.style.display = 'none';
    if (isNaN(tokens) || tokens < 0) { errorDiv.textContent = "Invalid token value."; errorDiv.style.display = 'block'; return; }
    showLoading("Saving settings...");
    showNotification("Saving settings... (Not implemented yet)", "info"); // Still needs backend implementation
    const modal = bootstrap.Modal.getInstance(document.getElementById('userSettingsModal'));
    modal.hide();
    hideLoading();
    // fetchApi('/api/settings', { method: 'POST', body: JSON.stringify({ searchTokens: tokens, canUseAi: canUseAi }) }) ...
}

// --- Placeholder/Stubbed Functions ---
// These were mostly just showing notifications, keep them here for now
function handleSavePayloadClick() {
     const params = getCurrentFormParams();
     if (!params) return;
     const defaultName = `${params.make || 'Any'} ${params.model || 'Any'} (${params.yearMin || ''}-${params.yearMax || ''})`;
     document.getElementById('payloadName').value = defaultName;
     const namePayloadModal = new bootstrap.Modal(document.getElementById('namePayloadModal'));
     namePayloadModal.show();
}
function handleLoadPayload() { showNotification("Loading selected payload not implemented yet.", "info"); }
function deletePayload() { showNotification("Deleting payloads not implemented yet.", "info"); }
function renamePayload() { showNotification("Renaming payloads not implemented yet.", "info"); }
function loadSavedResults() { console.log("loadSavedResults: Not implemented in Rust backend yet."); }
function viewSelectedResult() { showNotification("Viewing saved results not implemented yet.", "info"); }
function deleteSelectedResult() { showNotification("Deleting saved results not implemented yet.", "info"); }
function renameResult() { showNotification("Renaming results not implemented yet.", "info"); }
function handleSaveRename() { showNotification("Saving rename not implemented yet.", "info"); }
function handleOpenLinks() { showNotification("Opening links from current results not implemented yet.", "info"); }
function handleDownloadCsv() { showNotification("Downloading current results as CSV not implemented yet.", "info"); }
function downloadSelectedResultCsv() { showNotification("Downloading selected result as CSV not implemented yet.", "info"); }
function handleAnalyzeClick(event) { showNotification("AI Analysis not implemented yet.", "info"); }
function openSelectedVehicleLinks() {
     const checkboxes = document.querySelectorAll('.vehicle-checkbox:checked');
     if (checkboxes.length === 0) { showNotification('Please select at least one vehicle', 'warning'); return; }
     const maxLinksToOpen = 15; let count = 0;
     checkboxes.forEach(checkbox => { if (count < maxLinksToOpen) { const link = checkbox.getAttribute('data-link'); if (link) { window.open(link, '_blank'); count++; } } });
     if (checkboxes.length > maxLinksToOpen) { showNotification(`Opening first ${maxLinksToOpen} links.`, 'warning'); }
}

// --- Table Display/Sort Functions (Keep here or move to ui.js) ---
// Needs access to global state: originalVehicles, currentDisplayedResults, currentSortField, currentSortDirection
// Needs access to UI functions: populateFilterDropdowns, renderTableBody, setupTableListeners, showNotification
// Needs access to helper: sortVehicles
let currentSortField = '';
let currentSortDirection = 'asc';

function displayResults(resultData) { // Called by handleFetchData in api.js
    console.log("Displaying results:", resultData);
    const resultsTableContainer = document.getElementById('resultsTableContainer');
    const resultsModal = new bootstrap.Modal(document.getElementById('resultsModal'));
    const metadata = resultData.metadata || {};
    const vehicles = resultData.results || [];
    document.getElementById('resultsModalLabel').textContent = `Results: ${metadata.make || 'Any'} ${metadata.model || 'Any'}`;
    originalVehicles = vehicles; // Update global state
    currentDisplayedResults = [...originalVehicles]; // Update global state
    populateFilterDropdowns(originalVehicles);
    renderTableBody(currentDisplayedResults);
    setupTableListeners();
    resultsModal.show();
}

function renderTableBody(vehicles) {
    let tableBody = document.getElementById('vehicleResultsTableBody');
    if (!tableBody) { /* ... create table structure ... */ } // Simplified
    tableBody.innerHTML = '';
    vehicles.forEach((vehicle, index) => { /* ... create row HTML ... */ });
}

function setupTableListeners() { /* ... add listeners for sort, selectAll, actions ... */ }
function handleSortClick(event) { /* ... update sort state, call sortVehicles, call renderTableBody ... */ }
function handleSelectAll(event) { /* ... update checkboxes ... */ }
function handleTableActions(event) { /* ... handle analyze/delete clicks ... */ }
function populateFilterDropdowns(vehicles) { console.log("Populating filters (stub)"); }
function applyFiltersAndDisplay() { console.log("Applying filters (stub)"); renderTableBody(currentDisplayedResults); showNotification(`Filtering not fully implemented.`, 'info'); }
function sortVehicles(vehicles, field, direction) { console.log(`Sorting by ${field} ${direction} (stub)`); return [...vehicles]; }

// Add Selector Prototype (Keep here or move to a utils.js)
function addSelectorPrototype() { /* ... implementation ... */ }
addSelectorPrototype(); // Call it
