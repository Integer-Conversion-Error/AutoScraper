import { showLoading, hideLoading, showNotification } from './ui.js';
// Import other necessary functions or state variables if needed later

// --- API Call Functions ---

// Generic fetch function - Modified for onAuthStateChanged
// Needs access to firebaseUser and authStatePromise (consider moving auth logic to auth.js)
// For now, assume they are available globally or passed in if needed.
// Let's assume firebaseUser and authStatePromise are globally accessible for this step.
async function fetchApi(url, options = {}) {
    console.log(`[fetchApi] START - Requesting: ${url}`);
    const defaultHeaders = {
        'Content-Type': 'application/json',
    };

    // Wait for auth state to be ready before proceeding
    // Assuming authStatePromise is globally available or managed elsewhere
    await window.authStatePromise; // Use window scope temporarily
    console.log(`[fetchApi] Auth state ready. User: ${window.firebaseUser ? window.firebaseUser.uid : 'null'}`);

    // Add Authorization header if user is logged in
    if (window.firebaseUser) {
        try {
            const token = await window.firebaseUser.getIdToken(true); // Force refresh token if needed
            defaultHeaders['Authorization'] = `Bearer ${token}`;
            console.log("[fetchApi] Added Auth token.");
        } catch (error) {
            console.error("Could not get Firebase ID token:", error);
            showNotification("Authentication token error. Please try logging in again.", "danger");
            throw new Error("Authentication token error"); // Stop the fetch
        }
    } else {
         console.warn("[fetchApi] No Firebase user logged in. Proceeding without token.");
    }

    const mergedOptions = { ...options, headers: { ...defaultHeaders, ...(options.headers || {}) } };

    try {
        console.log(`[fetchApi] Options prepared:`, mergedOptions);
        console.log(`[fetchApi] Calling fetch(${url})...`);
        const response = await fetch(url, mergedOptions);
        console.log(`[fetchApi] Fetch returned for ${url}, status: ${response.status}`);

        let data = null;
        const contentType = response.headers.get("content-type");

        if (!response.ok) {
            if (response.status === 401) {
                 showNotification("Authentication required or session expired. Please log in.", "warning");
            }
            const errorText = await response.text();
            console.error(`[fetchApi] HTTP error ${response.status} for ${url}: ${errorText}`);
            throw new Error(`HTTP error ${response.status}: ${errorText || response.statusText}`);
        }

        if (contentType && contentType.indexOf("application/json") !== -1) {
             if (response.status === 204) { data = null; } else { data = await response.json(); }
        } else if (response.ok && (response.headers.get('content-length') === '0' || !contentType)) {
             return { success: true, data: null, status: response.status };
        } else {
             const textData = await response.text();
             return { success: true, data: textData, status: response.status };
        }

         console.log(`[fetchApi] Success response data for ${url}:`, data);
         // Handle explicitly defined NON-GET JSON responses missing a 'success' field by wrapping them
         // Check if options.method exists and is not 'GET'
         if (response.ok && options.method && options.method.toUpperCase() !== 'GET' && contentType && contentType.indexOf("application/json") !== -1 && typeof data?.success === 'undefined') {
             console.warn(`Response from non-GET ${url} missing 'success' field. Wrapping response.`);
             // Wrap non-array data in a success object.
             if (data !== null && typeof data === 'object' && !Array.isArray(data)) { // Check it's an object, not an array
                 return { success: true, ...data, status: response.status };
             } else { // Wrap arrays or primitives
                 return { success: true, data: data, status: response.status };
             }
         }

         // For GET requests (options.method is undefined or 'GET'), or if data already has a success field, or wasn't JSON, return data as is.
         // This ensures raw arrays/objects from GET requests (like /api/makes, /api/models) are returned unmodified.
         return data;

     } catch (error) {
         console.error(`[fetchApi] CATCH block error for ${url}:`, error);
        if (!error.message.includes("Authentication")) { showNotification(`API request failed: ${error.message}`, 'danger'); }
        throw error;
    }
}
// Export fetchApi if it needs to be used directly by other modules (e.g., testing)
// export { fetchApi }; // Or keep it internal to this module if only used by functions below

export function loadMakes() {
    showLoading('Loading makes...');
    console.log("[loadMakes] Starting...");
    fetchApi(`/api/makes`)
        .then(makesData => {
            console.log("[loadMakes] fetchApi successful, received:", makesData);
            const makeSelect = document.getElementById('makeSelect');
            if (!makeSelect) { console.error("[loadMakes] makeSelect element not found!"); hideLoading(); return; }
            makeSelect.innerHTML = '<option value="">Select Make</option>';

            if (Array.isArray(makesData)) {
                makesData.forEach(make => {
                    const option = document.createElement('option');
                    option.value = make; // 'make' is the string from the array
                    option.textContent = make; // Display the make name
                    makeSelect.appendChild(option);
                });
                console.log("[loadMakes] Populated makes dropdown from array.");
            } else {
                console.warn("[loadMakes] Received non-array data format for makes:", makesData);
                showNotification('Failed to load makes: Invalid data format received.', 'danger');
            }
            hideLoading();
        })
        .catch(error => { console.error("[loadMakes] Error caught in .catch:", error); hideLoading(); });
}

export function loadModels(make) {
    const modelSelect = document.getElementById('modelSelect');
    modelSelect.innerHTML = '<option value="">Loading Models...</option>';
    document.getElementById('trimSelect').innerHTML = '<option value="">Any Trim (Select Model First)</option>';
    document.getElementById('colorSelect').innerHTML = '<option value="">Any Color (Select Model First)</option>';
    if (!make) { modelSelect.innerHTML = '<option value="">Select Model (Choose Make First)</option>'; return; }
    showLoading('Loading models...');
    fetchApi(`/api/models/${encodeURIComponent(make)}`)
        .then(modelsData => {
            console.log("Models loaded:", modelsData);
            modelSelect.innerHTML = '<option value="">Select Model</option>';
            if (typeof modelsData === 'object' && modelsData !== null) {
                Object.entries(modelsData).forEach(([modelName, count]) => {
                    const option = document.createElement('option'); option.value = modelName; option.textContent = `${modelName} (${count})`; modelSelect.appendChild(option);
                });
                 console.log("[loadModels] Populated models dropdown from object.");
            } else if (Array.isArray(modelsData)) {
                 modelsData.forEach(modelName => { const option = document.createElement('option'); option.value = modelName; option.textContent = modelName; modelSelect.appendChild(option); });
                console.log("[loadModels] Populated models dropdown from array.");
            } else {
                console.warn("Received unexpected data format for models:", modelsData);
                showNotification('Failed to load models: Invalid data format.', 'danger');
            }
            hideLoading();
        })
        .catch(error => { modelSelect.innerHTML = '<option value="">Error loading models</option>'; hideLoading(); });
}

export function loadTrims(make, model, selectedTrim = null) {
    const cleanedModel = model.replace(/\s*\([^)]*\)\s*$/, '').trim();
    console.log(`[loadTrims] Original model: "${model}", Cleaned model for API call: "${cleanedModel}"`);
    const trimSelect = document.getElementById('trimSelect');
    trimSelect.innerHTML = '<option value="">Loading Trims...</option>';
    document.getElementById('colorSelect').innerHTML = '<option value="">Any Color (Select Trim/Model First)</option>';
    if (!make || !cleanedModel) { trimSelect.innerHTML = '<option value="">Any Trim (Select Model First)</option>'; return; }
    showLoading('Loading trims...');
    fetchApi(`/api/trims?make=${encodeURIComponent(make)}&model=${encodeURIComponent(cleanedModel)}`)
        .then(trimsData => {
            console.log("Trims loaded:", trimsData);
            trimSelect.innerHTML = '<option value="">Any Trim</option>';
            if (Array.isArray(trimsData)) {
                trimsData.forEach(trim => { const option = document.createElement('option'); option.value = trim; option.textContent = trim; trimSelect.appendChild(option); });
                console.log("[loadTrims] Populated trims dropdown from array.");
            } else if (typeof trimsData === 'object' && trimsData !== null) {
                Object.entries(trimsData).forEach(([trimName, count]) => { if (trimName.toLowerCase() === 'status') return; const option = document.createElement('option'); option.value = trimName; option.textContent = `${trimName} (${count})`; trimSelect.appendChild(option); });
                console.log("[loadTrims] Populated trims dropdown from object.");
            } else { console.warn("[loadTrims] Received unexpected data format for trims:", trimsData); showNotification('Failed to load trims: Invalid data format.', 'danger'); }
            const availableTrims = Array.from(trimSelect.options).map(opt => opt.value);
            if (selectedTrim && availableTrims.includes(selectedTrim)) { trimSelect.value = selectedTrim; }
            hideLoading();
        })
        .catch(error => { trimSelect.innerHTML = '<option value="">Error loading trims</option>'; hideLoading(); });
}

export function loadColors(make, model, trim = null, selectedColor = null) {
    const cleanedModel = model.replace(/\s*\([^)]*\)\s*$/, '').trim();
    const cleanedTrim = trim ? trim.replace(/\s*\([^)]*\)\s*$/, '').trim() : null;
    console.log(`[loadColors] Cleaned model: "${cleanedModel}", Cleaned trim: "${cleanedTrim}"`);
    const colorSelect = document.getElementById('colorSelect');
    colorSelect.innerHTML = '<option value="">Loading Colors...</option>';
    if (!make || !cleanedModel) { colorSelect.innerHTML = '<option value="">Any Color (Select Model First)</option>'; return; }
    showLoading('Loading colors...');
    let url = `/api/colors?make=${encodeURIComponent(make)}&model=${encodeURIComponent(cleanedModel)}`;
    if (cleanedTrim) { url += `&trim=${encodeURIComponent(cleanedTrim)}`; }
    fetchApi(url)
        .then(colorsData => {
            console.log("Colors loaded:", colorsData);
            colorSelect.innerHTML = '<option value="">Any Color</option>';
            if (Array.isArray(colorsData)) {
                colorsData.forEach(color => { const option = document.createElement('option'); option.value = color; option.textContent = color; colorSelect.appendChild(option); });
                console.log("[loadColors] Populated colors dropdown from array.");
            } else if (typeof colorsData === 'object' && colorsData !== null) {
                Object.entries(colorsData).forEach(([colorName, count]) => { if (colorName.toLowerCase() === 'status') return; const option = document.createElement('option'); option.value = colorName; option.textContent = `${colorName} (${count})`; colorSelect.appendChild(option); });
                console.log("[loadColors] Populated colors dropdown from object.");
            } else { console.warn("[loadColors] Received unexpected data format for colors:", colorsData); showNotification('Failed to load colors: Invalid data format.', 'danger'); }
            const availableColors = Array.from(colorSelect.options).map(opt => opt.value);
             if (selectedColor && availableColors.includes(selectedColor)) { colorSelect.value = selectedColor; }
            hideLoading();
        })
        .catch(error => { colorSelect.innerHTML = '<option value="">Error loading colors</option>'; hideLoading(); });
}

// --- Functions requiring authentication ---
// These need access to firebaseUser, showLoading, hideLoading, showNotification
// Assume firebaseUser is global for now.
export function loadSavedPayloads() {
    console.log("loadSavedPayloads called (triggered by auth state)");
    if (!window.firebaseUser) { const ps = document.getElementById('payloadSelect'); if (ps) ps.innerHTML = '<option value="">Login to load payloads</option>'; return; }
    showLoading('Loading saved payloads...');
    fetchApi('/api/payloads')
        .then(payloads => {
            const payloadSelect = document.getElementById('payloadSelect');
            payloadSelect.innerHTML = '<option value="">Select a saved payload</option>';
            if (Array.isArray(payloads)) {
                payloads.forEach(payload => { const option = document.createElement('option'); option.value = ""; option.textContent = payload.name || "Unnamed Payload"; option.setAttribute('data-id', payload.id); payloadSelect.appendChild(option); });
            } else { showNotification('Failed to load saved payloads: Invalid data format.', 'danger'); }
            hideLoading();
        })
        .catch(error => hideLoading());
}

export function fetchUserSettings(updateDisplay = false) {
    console.log("fetchUserSettings called (triggered by auth state)");
    if (!window.firebaseUser) { if (updateDisplay) window.updateTokenDisplay?.(0); return; } // Use window scope for updateTokenDisplay if it becomes global
    if (updateDisplay) { const tv = document.getElementById('tokenValue'); if (tv) tv.textContent = '...'; }
    fetchApi('/api/settings')
        .then(data => {
            if (data && data.success && data.settings) {
                // Assuming currentUserSettings is global or managed elsewhere
                window.currentUserSettings = { searchTokens: data.settings.searchTokens ?? 0, canUseAi: data.settings.canUseAi ?? false };
                console.log("User settings processed:", window.currentUserSettings);
                if (updateDisplay) { window.updateTokenDisplay?.(window.currentUserSettings.searchTokens); }
            } else {
                showNotification(`Could not load user settings: ${data?.error || 'Unknown error'}`, "warning");
                if (updateDisplay) { window.updateTokenDisplay?.(window.currentUserSettings?.searchTokens ?? 0); }
            }
        })
        .catch(error => { if (updateDisplay) { window.updateTokenDisplay?.(window.currentUserSettings?.searchTokens ?? 0); } });
}

// --- Other API-related handlers ---

// Needs access to getCurrentFormParams, showLoading, fetchApi, showNotification, displayResults, hideLoading
// Assume these are imported or global
export function handleFetchData() {
    console.log("Fetch data button clicked");
    const params = window.getCurrentFormParams?.(); // Use window scope temporarily
    if (!params) return;
    showLoading('Fetching data from AutoTrader...');
    fetchApi('/api/search', { method: 'POST', body: JSON.stringify(params) })
    .then(resultsData => {
        console.log("Fetch data response:", resultsData);
        const resultCount = Array.isArray(resultsData) ? resultsData.length : 0;
        document.getElementById('resultsInfo').innerHTML = `<div class="alert alert-success"><p><strong><i class="bi bi-check-circle"></i> Found:</strong> ${resultCount} listings</p><p><i>Note: Saving results and token charging not yet implemented.</i></p></div>`;
        document.getElementById('openLinksBtn').disabled = resultCount === 0;
        document.getElementById('downloadCsvBtn').disabled = resultCount === 0;
        showNotification(`Found ${resultCount} listings.`, 'success');
        window.currentSearchResults = resultsData || []; // Assuming global state
        window.displayResults?.({ results: window.currentSearchResults, metadata: params }); // Assuming global
        hideLoading();
    })
    .catch(error => { document.getElementById('resultsInfo').innerHTML = `<div class="alert alert-danger"><p><i class="bi bi-exclamation-triangle"></i> Error fetching data: ${error.message}</p></div>`; hideLoading(); });
}

// Needs access to getCurrentFormParams, showNotification, showLoading, fetchApi, hideLoading, loadSavedPayloads
export function handleSaveNamedPayload() {
    const payloadName = document.getElementById('payloadName').value.trim();
    const params = window.getCurrentFormParams?.(); // Assuming global
    if (!payloadName) { showNotification('Please enter a name', 'warning'); return; }
    if (!params) return;
    const namePayloadModal = bootstrap.Modal.getInstance(document.getElementById('namePayloadModal'));
    namePayloadModal.hide();
    showLoading('Saving payload...');
    fetchApi('/api/payloads', { method: 'POST', body: JSON.stringify({ name: payloadName, params: params }) })
    .then(data => {
        hideLoading();
        if (data && data.success) { showNotification(`Payload saved successfully (ID: ${data.id})`, 'success'); loadSavedPayloads(); }
        else { showNotification(`Failed to save payload: ${data?.error || 'Unknown error'}`, 'danger'); }
    })
    .catch(error => hideLoading());
}

// Add other API-related functions like saveUserSettings, handleLoadPayload etc. here later
// Remember to export them if needed by other modules.
