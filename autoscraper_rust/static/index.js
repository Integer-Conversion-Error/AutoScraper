// Global state variables
let currentPayload = null; // Holds the parameters for the *next* search
let exclusions = [];
let currentResultId = null; // ID of the currently viewed/saved result in Firestore
let currentUserSettings = { searchTokens: 0, canUseAi: false }; // Local cache of user settings
let currentDisplayedResults = []; // Results currently shown in the modal
let originalVehicles = []; // Holds the full list loaded into the modal for filtering/sorting

// --- UI Helper Functions ---

function showNotification(message, type = 'primary') {
    const notification = document.getElementById('notification');
    if (!notification) return;
    notification.className = 'toast align-items-center text-white border-0'; // Reset classes
    notification.classList.add(`bg-${type}`);
    document.getElementById('notification-content').textContent = message;
    const toast = bootstrap.Toast.getOrCreateInstance(notification, { delay: 3000 });
    toast.show();
}

function showLoading(message = 'Processing...') {
    console.log('Loading:', message);
    // TODO: Implement a proper visual loading indicator
}

function hideLoading() {
    console.log('Loading complete.');
    // TODO: Hide visual loading indicator
}

function updateExclusionsList() {
    const exclusionsListEl = document.getElementById('exclusionsList');
    if (!exclusionsListEl) return;
    exclusionsListEl.innerHTML = '';
    exclusions.forEach((exclusion, index) => {
        const badge = document.createElement('span');
        badge.classList.add('badge', 'bg-secondary', 'keyword-badge');
        badge.innerHTML = `${exclusion} <i class="bi bi-x-circle" data-index="${index}" style="cursor: pointer;"></i>`;
        badge.querySelector('.bi-x-circle').addEventListener('click', function () {
            exclusions.splice(index, 1);
            updateExclusionsList();
        });
        exclusionsListEl.appendChild(badge);
    });
}

// --- API Call Functions (using fetchApi wrapper) ---

// Generic fetch function
async function fetchApi(url, options = {}) {
    console.log(`Making request to: ${url}`);
    const defaultHeaders = {
        'Content-Type': 'application/json',
    };

    // Add Authorization header if user is logged in (Firebase Auth)
    const user = firebase.auth().currentUser;
    if (user) {
        try {
            const token = await user.getIdToken();
            defaultHeaders['Authorization'] = `Bearer ${token}`;
        } catch (error) {
            console.warn("Could not get Firebase token:", error);
            // Decide if request should proceed without token
        }
    } else {
         console.warn("No Firebase user logged in for authenticated request.");
         // Potentially block requests requiring auth here
    }

    const mergedOptions = { ...options, headers: { ...defaultHeaders, ...(options.headers || {}) } };

    try {
        const response = await fetch(url, mergedOptions);
        let data = null;
        const contentType = response.headers.get("content-type");

        if (contentType && contentType.indexOf("application/json") !== -1) {
            data = await response.json();
        } else if (response.ok && response.headers.get('content-length') === '0') {
             console.warn(`Received empty but OK response for ${url}`);
             return { success: true, data: null, status: response.status }; // Treat as success
        } else if (!response.ok) {
             const errorText = await response.text();
             throw new Error(`HTTP error ${response.status}: ${errorText || response.statusText}`);
        } else {
             // Handle other content types if necessary, or treat as unexpected
             console.warn(`Received non-JSON response for ${url}: ${contentType}`);
             return { success: true, data: await response.text(), status: response.status }; // Return text if needed
        }

        if (!response.ok) { // Check again in case JSON parsing revealed an error structure
            const errorMessage = data?.error || data?.message || `HTTP ${response.status}`;
            throw new Error(errorMessage);
        }

        // For consistency, wrap successful data if it doesn't follow the {success: true, ...} pattern
        // Adjust this based on how your Rust endpoints *actually* return data
        if (typeof data.success === 'undefined') {
             // Assuming direct data return means success for GETs like /api/makes, /api/models etc.
             // For POST/PUT/DELETE that return GenericResponse, the success field should be present.
             if (options.method === 'POST' || options.method === 'PUT' || options.method === 'DELETE') {
                 // If success field is missing on mutation, it might be an issue
                 console.warn(`Response from ${url} missing 'success' field.`);
                 // You might want to treat this as an error or handle based on context
             }
             // Wrap direct data returns for simplicity downstream
             // return { success: true, data: data, status: response.status };
        }
        return data; // Return the parsed JSON data

    } catch (error) {
        console.error('API request failed:', url, error);
        showNotification(`API request failed: ${error.message}`, 'danger');
        throw error;
    }
}

function loadMakes() {
    showLoading('Loading makes...');
    fetchApi(`/api/makes`)
        .then(makes => {
            console.log("Makes loaded:", makes);
            const makeSelect = document.getElementById('makeSelect');
            makeSelect.innerHTML = '<option value="">Select Make</option>';
            if (Array.isArray(makes)) {
                makes.forEach(make => {
                    const option = document.createElement('option'); option.value = make; option.textContent = make; makeSelect.appendChild(option);
                });
            } else { showNotification('Failed to load makes: Invalid data format.', 'danger'); }
            hideLoading();
        })
        .catch(error => hideLoading());
}

function loadModels(make) {
    const modelSelect = document.getElementById('modelSelect');
    modelSelect.innerHTML = '<option value="">Loading Models...</option>';
    document.getElementById('trimSelect').innerHTML = '<option value="">Any Trim (Select Model First)</option>';
    document.getElementById('colorSelect').innerHTML = '<option value="">Any Color (Select Model First)</option>';
    if (!make) { modelSelect.innerHTML = '<option value="">Select Model (Choose Make First)</option>'; return; }
    showLoading('Loading models...');
    fetchApi(`/api/models?make=${encodeURIComponent(make)}`)
        .then(models => {
            console.log("Models loaded:", models);
            modelSelect.innerHTML = '<option value="">Select Model</option>';
            if (Array.isArray(models)) {
                models.forEach(model => {
                    const option = document.createElement('option'); option.value = model; option.textContent = model; modelSelect.appendChild(option);
                });
            } else { showNotification('Failed to load models: Invalid data format.', 'danger'); }
            hideLoading();
        })
        .catch(error => { modelSelect.innerHTML = '<option value="">Error loading models</option>'; hideLoading(); });
}

function loadTrims(make, model, selectedTrim = null) {
    const trimSelect = document.getElementById('trimSelect');
    trimSelect.innerHTML = '<option value="">Loading Trims...</option>';
    document.getElementById('colorSelect').innerHTML = '<option value="">Any Color (Select Trim/Model First)</option>';
    if (!make || !model) { trimSelect.innerHTML = '<option value="">Any Trim (Select Model First)</option>'; return; }
    showLoading('Loading trims...');
    fetchApi(`/api/trims?make=${encodeURIComponent(make)}&model=${encodeURIComponent(model)}`)
        .then(trims => {
            console.log("Trims loaded:", trims);
            trimSelect.innerHTML = '<option value="">Any Trim</option>';
            if (Array.isArray(trims)) {
                trims.forEach(trim => {
                    const option = document.createElement('option'); option.value = trim; option.textContent = trim; trimSelect.appendChild(option);
                });
                if (selectedTrim && trims.includes(selectedTrim)) { trimSelect.value = selectedTrim; }
            } else { showNotification('Failed to load trims: Invalid data format.', 'danger'); }
            hideLoading();
        })
        .catch(error => { trimSelect.innerHTML = '<option value="">Error loading trims</option>'; hideLoading(); });
}

function loadColors(make, model, trim = null, selectedColor = null) {
    const colorSelect = document.getElementById('colorSelect');
    colorSelect.innerHTML = '<option value="">Loading Colors...</option>';
    if (!make || !model) { colorSelect.innerHTML = '<option value="">Any Color (Select Model First)</option>'; return; }
    showLoading('Loading colors...');
    let url = `/api/colors?make=${encodeURIComponent(make)}&model=${encodeURIComponent(model)}`;
    if (trim) { url += `&trim=${encodeURIComponent(trim)}`; }
    fetchApi(url)
        .then(colors => {
            console.log("Colors loaded:", colors);
            colorSelect.innerHTML = '<option value="">Any Color</option>';
            if (Array.isArray(colors)) {
                colors.forEach(color => {
                    const option = document.createElement('option'); option.value = color; option.textContent = color; colorSelect.appendChild(option);
                });
                if (selectedColor && colors.includes(selectedColor)) { colorSelect.value = selectedColor; }
            } else { showNotification('Failed to load colors: Invalid data format.', 'danger'); }
            hideLoading();
        })
        .catch(error => { colorSelect.innerHTML = '<option value="">Error loading colors</option>'; hideLoading(); });
}

function loadSavedPayloads() {
    showLoading('Loading saved payloads...');
    fetchApi('/api/payloads') // GET /api/payloads
        .then(payloads => {
            const payloadSelect = document.getElementById('payloadSelect');
            payloadSelect.innerHTML = '<option value="">Select a saved payload</option>';
            if (Array.isArray(payloads)) {
                payloads.forEach(payload => {
                    const option = document.createElement('option');
                    option.value = ""; // Use data-id
                    option.textContent = payload.name || "Unnamed Payload";
                    option.setAttribute('data-id', payload.id);
                    payloadSelect.appendChild(option);
                });
            } else { showNotification('Failed to load saved payloads: Invalid data format.', 'danger'); }
            hideLoading();
        })
        .catch(error => hideLoading());
}

function fetchUserSettings(updateDisplay = false) {
    console.log("Fetching user settings...");
    if (updateDisplay) { document.getElementById('tokenValue').textContent = '...'; }
    fetchApi('/api/settings') // GET /api/settings
        .then(data => {
            if (data && data.success && data.settings) {
                currentUserSettings = {
                    searchTokens: data.settings.searchTokens ?? 0,
                    canUseAi: data.settings.canUseAi ?? false,
                };
                console.log("User settings processed:", currentUserSettings);
                if (updateDisplay) { updateTokenDisplay(currentUserSettings.searchTokens); }
            } else {
                showNotification(`Could not load user settings: ${data?.error || 'Unknown error'}`, "warning");
                if (updateDisplay) { updateTokenDisplay(currentUserSettings.searchTokens); }
            }
        })
        .catch(error => { if (updateDisplay) { updateTokenDisplay(currentUserSettings.searchTokens); } });
}

// --- Event Listeners and Initialization ---

document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM loaded, initializing...");

    // Load initial data
    loadMakes(true);
    loadSavedPayloads();
    // loadSavedResults(); // TODO: Implement Rust endpoint
    fetchUserSettings(true);

    // Event Listeners
    document.getElementById('makeSelect').addEventListener('change', function () { loadModels(this.value); });
    document.getElementById('modelSelect').addEventListener('change', function () {
        const make = document.getElementById('makeSelect').value;
        loadTrims(make, this.value);
        loadColors(make, this.value);
    });
    document.getElementById('trimSelect').addEventListener('change', function () {
        const make = document.getElementById('makeSelect').value;
        const model = document.getElementById('modelSelect').value;
        loadColors(make, model, this.value || null);
    });
    document.getElementById('showAllMakes').addEventListener('click', () => loadMakes(false));
    document.getElementById('addExclusionBtn').addEventListener('click', addExclusion);
    document.getElementById('exclusionKeyword').addEventListener('keypress', (e) => { if (e.key === 'Enter') { e.preventDefault(); addExclusion(); } });
    document.getElementById('fetchDataBtn').addEventListener('click', handleFetchData);
    document.getElementById('settingsBtn').addEventListener('click', openUserSettingsModal);
    document.getElementById('saveUserSettingsBtn').addEventListener('click', saveUserSettings);
    document.getElementById('increaseTokensBtn').addEventListener('click', () => adjustTokens(1));
    document.getElementById('decreaseTokensBtn').addEventListener('click', () => adjustTokens(-1));
    document.getElementById('loadPayloadBtn')?.addEventListener('click', handleLoadPayload);
    document.getElementById('savePayloadBtn')?.addEventListener('click', handleSavePayloadClick);
    document.getElementById('saveNamedPayloadBtn')?.addEventListener('click', handleSaveNamedPayload);
    document.getElementById('deletePayloadBtn')?.addEventListener('click', deletePayload);
    document.getElementById('renamePayloadBtn')?.addEventListener('click', renamePayload);
    document.getElementById('viewResultBtn')?.addEventListener('click', viewSelectedResult);
    document.getElementById('deleteResultBtn')?.addEventListener('click', deleteSelectedResult);
    document.getElementById('renameResultBtn')?.addEventListener('click', renameResult);
    document.getElementById('saveRenameBtn')?.addEventListener('click', handleSaveRename);
    document.getElementById('openLinksBtn')?.addEventListener('click', handleOpenLinks);
    document.getElementById('downloadCsvBtn')?.addEventListener('click', handleDownloadCsv);
    document.getElementById('openSelectedLinksBtn')?.addEventListener('click', openSelectedVehicleLinks);
    document.getElementById('downloadSelectedResultBtn')?.addEventListener('click', downloadSelectedResultCsv);
});

function addExclusion() {
    const keywordInput = document.getElementById('exclusionKeyword');
    const keyword = keywordInput.value.trim();
    if (keyword && !exclusions.includes(keyword)) {
        exclusions.push(keyword);
        updateExclusionsList();
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
        exclusions: exclusions.length > 0 ? exclusions : null,
        inclusion: document.getElementById('inclusion').value || null,
    };
    if (!params.make) { showNotification('Please select a Make', 'warning'); return null; }
    if (params.yearMin && params.yearMax && params.yearMin > params.yearMax) { showNotification('Minimum Year cannot be greater than Maximum Year', 'warning'); return null; }
    if (params.priceMin && params.priceMax && params.priceMin > params.priceMax) { showNotification('Minimum Price cannot be greater than Maximum Price', 'warning'); return null; }
    if (params.odometerMin && params.odometerMax && params.odometerMin > params.odometerMax) { showNotification('Minimum KMs cannot be greater than Maximum KMs', 'warning'); return null; }
    return params;
}

function handleFetchData() {
    console.log("Fetch data button clicked");
    const params = getCurrentFormParams();
    if (!params) return;

    showLoading('Fetching data from AutoTrader...');
    fetchApi('/api/search', { method: 'POST', body: JSON.stringify(params) })
    .then(resultsData => {
        console.log("Fetch data response:", resultsData);
        const resultCount = Array.isArray(resultsData) ? resultsData.length : 0;
        document.getElementById('resultsInfo').innerHTML = `
                <div class="alert alert-success">
                    <p><strong><i class="bi bi-check-circle"></i> Found:</strong> ${resultCount} listings</p>
                    <p><i>Note: Saving results and token charging not yet implemented.</i></p>
                </div>`;
        document.getElementById('openLinksBtn').disabled = resultCount === 0;
        document.getElementById('downloadCsvBtn').disabled = resultCount === 0;
        showNotification(`Found ${resultCount} listings.`, 'success');
        window.currentSearchResults = resultsData || [];
        displayResults({ results: window.currentSearchResults, metadata: params });
        hideLoading();
    })
    .catch(error => {
        document.getElementById('resultsInfo').innerHTML = `<div class="alert alert-danger"><p><i class="bi bi-exclamation-triangle"></i> Error fetching data: ${error.message}</p></div>`;
        hideLoading();
    });
}

// --- User Settings Functions ---

function updateTokenDisplay(tokens) {
    const tokenValueEl = document.getElementById('tokenValue');
    if (tokenValueEl) { tokenValueEl.textContent = tokens ?? '0'; }
    if (typeof tokens === 'number' || tokens === null) { currentUserSettings.searchTokens = tokens ?? 0; }
}

function openUserSettingsModal() {
    const modal = new bootstrap.Modal(document.getElementById('userSettingsModal'));
    const loadingDiv = document.getElementById('userSettingsLoading');
    const formDiv = document.getElementById('userSettingsForm');
    const errorDiv = document.getElementById('userSettingsError');
    loadingDiv.style.display = 'block'; formDiv.style.display = 'none'; errorDiv.style.display = 'none'; modal.show();
    fetchApi('/api/settings')
        .then(data => {
            loadingDiv.style.display = 'none';
            if (data && data.success && data.settings) {
                currentUserSettings = { searchTokens: data.settings.searchTokens ?? 0, canUseAi: data.settings.canUseAi ?? false };
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
    // TODO: Implement '/api/settings' (POST or PUT) endpoint in Rust backend
    // For now, just show notification and close modal
    showNotification("Saving settings... (Not implemented yet)", "info");
    const modal = bootstrap.Modal.getInstance(document.getElementById('userSettingsModal'));
    modal.hide();
    hideLoading();
    // fetchApi('/api/settings', { method: 'POST', body: JSON.stringify({ searchTokens: tokens, canUseAi: canUseAi }) })
    // .then(data => { /* ... handle success/error ... */ })
    // .catch(error => { /* ... handle error ... */ });
}

// --- Placeholder/Stubbed Functions ---

function handleSavePayloadClick() {
     const params = getCurrentFormParams();
     if (!params) return;
     const defaultName = `${params.make || 'Any'} ${params.model || 'Any'} (${params.yearMin || ''}-${params.yearMax || ''})`;
     document.getElementById('payloadName').value = defaultName;
     const namePayloadModal = new bootstrap.Modal(document.getElementById('namePayloadModal'));
     namePayloadModal.show();
}

function handleSaveNamedPayload() {
    const payloadName = document.getElementById('payloadName').value.trim();
    const params = getCurrentFormParams();
    if (!payloadName) { showNotification('Please enter a name', 'warning'); return; }
    if (!params) return;
    const namePayloadModal = bootstrap.Modal.getInstance(document.getElementById('namePayloadModal'));
    namePayloadModal.hide();
    showLoading('Saving payload...');
    fetchApi('/api/payloads', { method: 'POST', body: JSON.stringify({ name: payloadName, params: params }) })
    .then(data => {
        hideLoading();
        if (data && data.success) {
            showNotification(`Payload saved as "${payloadName}"`, 'success');
            loadSavedPayloads(); // Refresh list
        } else { showNotification(`Failed to save payload: ${data?.error || 'Unknown error'}`, 'danger'); }
    })
    .catch(error => hideLoading());
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
     checkboxes.forEach(checkbox => {
         if (count < maxLinksToOpen) { const link = checkbox.getAttribute('data-link'); if (link) { window.open(link, '_blank'); count++; } }
     });
     if (checkboxes.length > maxLinksToOpen) { showNotification(`Opening first ${maxLinksToOpen} links.`, 'warning'); }
}

// --- Table Display and Sorting (Basic Implementation) ---

let currentSortField = '';
let currentSortDirection = 'asc';

function displayResults(resultData) {
    console.log("Displaying results:", resultData);
    const resultsTableContainer = document.getElementById('resultsTableContainer');
    const resultsModal = new bootstrap.Modal(document.getElementById('resultsModal'));
    const metadata = resultData.metadata || {};
    const vehicles = resultData.results || [];

    document.getElementById('resultsModalLabel').textContent = `Results: ${metadata.make || 'Any'} ${metadata.model || 'Any'}`;
    originalVehicles = vehicles;
    currentDisplayedResults = [...originalVehicles];
    populateFilterDropdowns(originalVehicles); // Basic stub
    renderTableBody(currentDisplayedResults);
    setupTableListeners(); // Add listeners after table exists
    resultsModal.show();
}

function renderTableBody(vehicles) {
    let tableBody = document.getElementById('vehicleResultsTableBody');
    if (!tableBody) {
         const container = document.getElementById('resultsTableContainer');
         if (!container) return;
         container.innerHTML = `
             <table class="table table-striped table-hover" id="vehicleResultsTable">
                 <thead>
                     <tr>
                         <th><input type="checkbox" id="selectAllVehicles"></th>
                         <th class="sortable" data-field="title">Title <i class="bi bi-sort-down d-none sort-icon"></i></th>
                         <th class="sortable" data-field="price">Price <i class="bi bi-sort-down d-none sort-icon"></i></th>
                         <th class="sortable" data-field="mileage">Mileage <i class="bi bi-sort-down d-none sort-icon"></i></th>
                         <th class="sortable" data-field="location">Location <i class="bi bi-sort-down d-none sort-icon"></i></th>
                         <th>Link</th>
                         <th>Actions</th>
                     </tr>
                 </thead>
                 <tbody id="vehicleResultsTableBody"></tbody>
             </table>`;
         tableBody = document.getElementById('vehicleResultsTableBody'); // Re-get the body
    }

    tableBody.innerHTML = ''; // Clear existing rows
    vehicles.forEach((vehicle, index) => {
        const row = tableBody.insertRow();
        // Adapt to ListingResult structure
        row.innerHTML = `
            <td><input type="checkbox" class="vehicle-checkbox" data-link="${vehicle.link || ''}"></td>
            <td>${vehicle.title || ''}</td>
            <td>${vehicle.price || ''}</td>
            <td>${vehicle.mileage || ''}</td>
            <td>${vehicle.location || ''}</td>
            <td><a href="${vehicle.link || '#'}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="bi bi-box-arrow-up-right"></i></a></td>
            <td>
                <button class="btn btn-sm btn-info analyze-btn" title="Analyze (Not Implemented)"> <i class="bi bi-robot"></i> </button>
                <button class="btn btn-sm btn-danger delete-listing-btn" data-index="${index}" title="Delete (Not Implemented)"> <i class="bi bi-trash"></i> </button>
            </td>
        `;
    });
}

function setupTableListeners() {
    const oldTableBody = document.getElementById('vehicleResultsTableBody');
    if (oldTableBody) { oldTableBody.removeEventListener('click', handleTableActions); }
    document.querySelectorAll('.sortable').forEach(header => {
         const newHeader = header.cloneNode(true); header.parentNode.replaceChild(newHeader, header); newHeader.addEventListener('click', handleSortClick);
    });
    document.getElementById('selectAllVehicles')?.removeEventListener('change', handleSelectAll);
    document.getElementById('applyFiltersBtn')?.removeEventListener('click', applyFiltersAndDisplay);
    const tableBody = document.getElementById('vehicleResultsTableBody');
    if (tableBody) { tableBody.addEventListener('click', handleTableActions); }
    document.getElementById('selectAllVehicles')?.addEventListener('change', handleSelectAll);
    document.getElementById('applyFiltersBtn')?.addEventListener('click', applyFiltersAndDisplay);
}

function handleSortClick(event) {
    const header = event.currentTarget; const field = header.getAttribute('data-field'); const icon = header.querySelector('.sort-icon');
    document.querySelectorAll('.sort-icon').forEach(i => { if (i !== icon) { i.className = 'bi bi-sort-down d-none sort-icon'; } });
    if (field === currentSortField) { currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc'; } else { currentSortField = field; currentSortDirection = 'asc'; }
    icon.classList.remove('d-none', 'bi-sort-down', 'bi-sort-up'); icon.classList.add(currentSortDirection === 'asc' ? 'bi-sort-up' : 'bi-sort-down');
    currentDisplayedResults = sortVehicles(currentDisplayedResults, field, currentSortDirection);
    renderTableBody(currentDisplayedResults);
}

function handleSelectAll(event) { const isChecked = event.target.checked; document.querySelectorAll('.vehicle-checkbox').forEach(checkbox => { checkbox.checked = isChecked; }); }
function handleTableActions(event) {
    if (event.target.closest('.analyze-btn')) { showNotification("AI Analysis not implemented yet.", "info"); }
    else if (event.target.closest('.delete-listing-btn')) { showNotification("Deleting listings not implemented yet.", "info"); }
}

// --- Add Selector Prototype ---
function addSelectorPrototype() {
    if (!Element.prototype.matches) { Element.prototype.matches = Element.prototype.msMatchesSelector || Element.prototype.webkitMatchesSelector; }
    if (!document.querySelectorAll) return;
    document.querySelectorAll = (function (querySelectorAll) {
        return function (selector) {
            if (selector.includes(':contains(')) {
                const matches = selector.match(/:contains\((['"])(.*?)\1\)/);
                if (matches) {
                    const searchText = matches[2]; const newSelector = selector.replace(/:contains\((['"])(.*?)\1\)/, '');
                    const elements = querySelectorAll.call(this, newSelector);
                    return Array.prototype.filter.call(elements, function (element) { return element.textContent.includes(searchText); });
                }
            }
            return querySelectorAll.call(this, selector);
        };
    })(document.querySelectorAll);
}

// --- Filter/Sort Stubs ---
function populateFilterDropdowns(vehicles) { console.log("Populating filters (stub)"); }
function applyFiltersAndDisplay() {
    console.log("Applying filters (stub)");
    renderTableBody(currentDisplayedResults);
    showNotification(`Filtering not fully implemented. Showing ${currentDisplayedResults.length} listings.`, 'info');
}
function sortVehicles(vehicles, field, direction) {
    console.log(`Sorting by ${field} ${direction} (stub)`);
    return [...vehicles]; // Return unsorted for now
}

