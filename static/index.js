
// Current payload and results file path
// --- Global Variables ---
let currentPayload = null;
let resultsFilePath = null;
let exclusions = [];
let currentResultId = null;
let currentUserSettings = { search_tokens: 0, can_use_ai: false }; // Store current settings
let currentFetchTaskId = null; // To store the ID of the running fetch task
let taskCheckInterval = null; // To store the interval timer for checking task status

// Firebase configuration
const firebaseConfig = {
    apiKey: "AIzaSyC5XgDpWOkgXHHJs28DyQvC6JtTB1BpUWw",
    authDomain: "autoscraper-32bb0.firebaseapp.com",
    projectId: "autoscraper-32bb0",
    storageBucket: "autoscraper-32bb0.firebasestorage.app",
    messagingSenderId: "694443728322",
    appId: "1:694443728322:web:63770ddc18446c0a74ca5b",
    measurementId: "G-0NVZC6JPBN"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

// --- Helper Function to Clean Model Names (JavaScript version) ---
function cleanModelNameJS(modelName) {
    if (typeof modelName !== 'string') {
        return modelName; // Return as is if not a string
    }
    // Regex to find ' (number)' at the end of the string
    const match = modelName.match(/^(.*?)\s+\(\d+\)$/);
    if (match && match[1]) {
        return match[1].trim(); // Return the part before ' (number)'
    }
    return modelName; // Return original if pattern doesn't match
}
// --- End Helper Function ---

// Override Firebase's auth state observer to prevent unwanted redirects
const origOnAuthStateChanged = firebase.auth().onAuthStateChanged;
firebase.auth().onAuthStateChanged = function (callback) {
    const wrappedCallback = (user) => {
        console.log("Auth state changed but ignoring for server session");
        // Don't call the original callback to prevent redirects
    };
    return origOnAuthStateChanged.call(firebase.auth(), wrappedCallback);
};
function renamePayload() {
    const payloadSelect = document.getElementById('payloadSelect');
    const selectedOption = payloadSelect.options[payloadSelect.selectedIndex];
    const payloadId = selectedOption.getAttribute('data-id');

    if (!payloadId) {
        showNotification('Please select a payload to rename', 'warning');
        return;
    }

    // Set up the rename modal
    document.getElementById('renameItemType').value = 'payload';
    document.getElementById('renameItemId').value = payloadId;
    document.getElementById('newItemName').value = selectedOption.textContent;
    document.getElementById('renameModalLabel').textContent = 'Rename Payload';

    // Show the modal
    const renameModal = new bootstrap.Modal(document.getElementById('renameModal'));
    renameModal.show();
}

// Function to rename a result
function renameResult() {
    const resultSelect = document.getElementById('resultSelect');
    const resultId = resultSelect.value;

    if (!resultId) {
        showNotification('Please select a result to rename', 'warning');
        return;
    }

    // Set up the rename modal
    document.getElementById('renameItemType').value = 'result';
    document.getElementById('renameItemId').value = resultId;
    document.getElementById('newItemName').value = resultSelect.options[resultSelect.selectedIndex].textContent;
    document.getElementById('renameModalLabel').textContent = 'Rename Result';

    // Show the modal
    const renameModal = new bootstrap.Modal(document.getElementById('renameModal'));
    renameModal.show();
}

// Function to delete a payload
function deletePayload() {
    const payloadSelect = document.getElementById('payloadSelect');
    const selectedOption = payloadSelect.options[payloadSelect.selectedIndex];
    const payloadId = selectedOption.getAttribute('data-id');

    if (!payloadId) {
        showNotification('Please select a payload to delete', 'warning');
        return;
    }



    showLoading('Deleting payload...');

    fetchWithAuth('/api/delete_payload', {
        method: 'POST',
        body: JSON.stringify({ payload_id: payloadId }),
    })
        .then(data => {
            if (data.success) {
                showNotification('Payload deleted successfully', 'success');
                loadSavedPayloads();
            } else {
                showNotification('Failed to delete payload: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error deleting payload:', error);
            showNotification('Failed to delete payload. Please try again.', 'danger');
            hideLoading();
        });
}

// Function to handle the save rename button click
function handleSaveRename() {
    const itemType = document.getElementById('renameItemType').value;
    const itemId = document.getElementById('renameItemId').value;
    const newName = document.getElementById('newItemName').value.trim();

    if (!newName) {
        showNotification('Please enter a name', 'warning');
        return;
    }

    // Close the modal
    const renameModal = bootstrap.Modal.getInstance(document.getElementById('renameModal'));
    renameModal.hide();

    showLoading(`Renaming ${itemType}...`);

    if (itemType === 'payload') {
        fetchWithAuth('/api/rename_payload', {
            method: 'POST',
            body: JSON.stringify({ payload_id: itemId, new_name: newName }),
        })
            .then(data => {
                if (data.success) {
                    showNotification('Payload renamed successfully', 'success');
                    loadSavedPayloads();
                } else {
                    showNotification('Failed to rename payload: ' + data.error, 'danger');
                    hideLoading();
                }
            })
            .catch(error => {
                console.error('Error renaming payload:', error);
                showNotification('Failed to rename payload. Please try again.', 'danger');
                hideLoading();
            });
    } else if (itemType === 'result') {
        fetchWithAuth('/api/rename_result', {
            method: 'POST',
            body: JSON.stringify({ result_id: itemId, new_name: newName }),
        })
            .then(data => {
                if (data.success) {
                    showNotification('Result renamed successfully', 'success');
                    loadSavedResults();
                } else {
                    showNotification('Failed to rename result: ' + data.error, 'danger');
                    hideLoading();
                }
            })
            .catch(error => {
                console.error('Error renaming result:', error);
                showNotification('Failed to rename result. Please try again.', 'danger');
                hideLoading();
            });
    }
}

// Update the loadSavedPayloads function to use custom_name if available
function loadSavedPayloads() {
    showLoading('Loading saved payloads...');

    fetchWithAuth('/api/list_payloads')
        .then(data => {
            if (data.success) {
                const payloadSelect = document.getElementById('payloadSelect');
                payloadSelect.innerHTML = '<option value="">Select a saved payload</option>';

                data.payloads.forEach(payload => {
                    const option = document.createElement('option');

                    // Use an empty value - we'll use data-id attribute instead
                    option.value = "";

                    // Display the formatted name
                    option.textContent = payload.name || "Unnamed Payload";

                    // Store the actual ID in a data attribute
                    if (payload.id) {
                        option.setAttribute('data-id', payload.id);
                    }

                    payloadSelect.appendChild(option);
                });

                // Refresh the select element to show the updated options
                $(payloadSelect).change(); // If you're using jQuery

                hideLoading();
            } else {
                showNotification('Failed to load saved payloads: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error loading saved payloads:', error);
            showNotification('Failed to load saved payloads. Please try again.', 'danger');
            hideLoading();
        });
}

// Update the loadSavedResults function to use custom_name if available
function loadSavedResults() {
    showLoading('Loading saved results...');

    fetchWithAuth('/api/list_results')
        .then(data => {
            if (data.success) {
                const resultSelect = document.getElementById('resultSelect');
                resultSelect.innerHTML = '<option value="">Select a saved result</option>';

                data.results.forEach(result => {
                    const option = document.createElement('option');
                    option.value = result.id;

                    // Create a descriptive name from metadata
                    const metadata = result.metadata || {};
                    const make = metadata.make || 'Unknown';
                    const model = metadata.model || 'Unknown';
                    const yearMin = metadata.yearMin || '';
                    const yearMax = metadata.yearMax || '';
                    const priceMin = metadata.priceMin || '';
                    const priceMax = metadata.priceMax || '';
                    const count = result.result_count || 0;
                    const timestamp = metadata.timestamp || '';

                    const metadataText = `${make} ${model} (${yearMin}-${yearMax}, $${priceMin}-$${priceMax}) - ${count} results - ${timestamp}`;

                    // If custom name exists, show it alongside the metadata
                    if (metadata.custom_name) {
                        option.textContent = `${metadata.custom_name} - ${metadataText}`;
                    } else {
                        option.textContent = metadataText;
                    }

                    resultSelect.appendChild(option);
                });

                hideLoading();
            } else {
                showNotification('Failed to load saved results: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error loading saved results:', error);
            showNotification('Failed to load saved results. Please try again.', 'danger');
            hideLoading();
        });
}


// Function to refresh results list without showing loading indicator
function refreshResultsList() {
    console.log("Refreshing results list...");

    // Save the currently selected value to restore it after refresh
    const resultSelect = document.getElementById('resultSelect');
    const currentSelection = resultSelect.value;

    fetchWithAuth('/api/list_results')
        .then(data => {
            if (data.success) {
                const resultSelect = document.getElementById('resultSelect');

                // Store current options for comparison
                const currentOptions = Array.from(resultSelect.options).map(opt => opt.value);

                // Prepare new options
                let newOptionsHTML = '<option value="">Select a saved result</option>';
                let newOptions = [''];

                data.results.forEach(result => {
                    const metadata = result.metadata || {};
                    const make = metadata.make || 'Unknown';
                    const model = metadata.model || 'Unknown';
                    const yearMin = metadata.yearMin || '';
                    const yearMax = metadata.yearMax || '';
                    const priceMin = metadata.priceMin || '';
                    const priceMax = metadata.priceMax || '';
                    const count = result.result_count || 0;
                    const timestamp = metadata.timestamp || '';

                    const metadataText = `${make} ${model} (${yearMin}-${yearMax}, $${priceMin}-$${priceMax}) - ${count} results - ${timestamp}`;

                    // If custom name exists, show it alongside the metadata
                    let optionText;
                    if (metadata.custom_name) {
                        optionText = `${metadata.custom_name} - ${metadataText}`;
                    } else {
                        optionText = metadataText;
                    }

                    newOptionsHTML += `<option value="${result.id}">${optionText}</option>`;
                    newOptions.push(result.id);
                });

                // Check if there are any changes to the options
                const hasChanges = newOptions.length !== currentOptions.length ||
                    newOptions.some((opt, i) => opt !== currentOptions[i]);

                // Only update DOM if there are changes
                if (hasChanges) {
                    resultSelect.innerHTML = newOptionsHTML;

                    // Restore previously selected value if it still exists
                    if (currentSelection && newOptions.includes(currentSelection)) {
                        resultSelect.value = currentSelection;
                    }

                    // Show notification only if there's a meaningful change
                    if (newOptions.length > currentOptions.length) {
                        const newCount = newOptions.length - currentOptions.length;
                        showNotification(`${newCount} new result${newCount > 1 ? 's' : ''} added`, 'info');
                    }

                    console.log("Results list refreshed with changes");
                } else {
                    console.log("Results list refreshed (no changes)");
                }
            } else {
                console.error('Failed to refresh results list:', data.error);
            }
        })
        .catch(error => {
            console.error('Error refreshing results list:', error);
        });
}

// Wait for document to be fully loaded
document.addEventListener('DOMContentLoaded', function () {
    console.log("DOM loaded, initializing...");
    addSelectorPrototype();
    // Initialize all dropdowns
    const dropdownTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="dropdown"]'));
    dropdownTriggerList.map(function (dropdownTriggerEl) {
        return new bootstrap.Dropdown(dropdownTriggerEl);
    });

    // Add a slight delay to ensure all elements are rendered
    setTimeout(() => {
        // Load makes on page load
        loadMakes(true);

        // Load saved payloads
        loadSavedPayloads();

        // Load saved results (only once on page load)
        loadSavedResults();

        // Set up manual refresh button
        document.getElementById('refreshResultsBtn').addEventListener('click', function () {
            showNotification('Refreshing results list...', 'info');
            refreshResultsList();
        });
    }, 100);

    // Add exclusion keyword
    document.getElementById('addExclusionBtn').addEventListener('click', function () {
        const keyword = document.getElementById('exclusionKeyword').value.trim();
        if (keyword && !exclusions.includes(keyword)) {
            exclusions.push(keyword);
            updateExclusionsList();
            document.getElementById('exclusionKeyword').value = '';
        }
    });

    // Allow pressing Enter to add exclusion
    document.getElementById('exclusionKeyword').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            document.getElementById('addExclusionBtn').click();
        }
    });

    // Create payload button
    document.getElementById('createPayloadBtn').addEventListener('click', function () {
        const form = document.getElementById('searchForm');

        // Basic validation
        if (!document.getElementById('makeSelect').value) {
            showNotification('Please select a Make', 'warning');
            return;
        }

        // Create payload from form
        const payload = {
            Make: document.getElementById('makeSelect').value,
            Model: document.getElementById('modelSelect').value,
            Address: document.getElementById('address').value,
            Proximity: parseInt(document.getElementById('proximity').value),
            YearMin: document.getElementById('yearMin').value ? parseInt(document.getElementById('yearMin').value) : null,
            YearMax: document.getElementById('yearMax').value ? parseInt(document.getElementById('yearMax').value) : null,
            PriceMin: document.getElementById('priceMin').value ? parseInt(document.getElementById('priceMin').value) : null,
            PriceMax: document.getElementById('priceMax').value ? parseInt(document.getElementById('priceMax').value) : null,
            OdometerMin: document.getElementById('odometerMin').value ? parseInt(document.getElementById('odometerMin').value) : null,
            OdometerMax: document.getElementById('odometerMax').value ? parseInt(document.getElementById('odometerMax').value) : null,
            IsNew: document.getElementById('isNew').checked,
            IsUsed: document.getElementById('isUsed').checked,
            WithPhotos: document.getElementById('withPhotos').checked,
                    Exclusions: exclusions,
                    Inclusion: document.getElementById('inclusion').value,
                    // Get selected trim from the dropdown
                    Trim: document.getElementById('trimSelect').value || null, // Correctly read from trimSelect dropdown
                    Color: document.getElementById('colorSelect').value || null, // Read from colorSelect dropdown
                    Drivetrain: document.getElementById('drivetrainSelect').value || null,
            Transmission: document.getElementById('transmissionSelect').value || null,
            // Add new fields
            BodyType: document.getElementById('bodyTypeInput').value || null,
            NumberOfDoors: document.getElementById('numDoorsInput').value ? parseInt(document.getElementById('numDoorsInput').value) : null,
            SeatingCapacity: document.getElementById('seatingCapacityInput').value ? parseInt(document.getElementById('seatingCapacityInput').value) : null,
            IsDamaged: document.getElementById('isDamaged').checked,
        };

        // Clean up empty strings to null for consistency with backend expectations
        if (payload.BodyType === "") payload.BodyType = null;

        // Validation
        if (payload.YearMin !== null && payload.YearMax !== null && payload.YearMin > payload.YearMax) {
            showNotification('Minimum Year cannot be greater than Maximum Year', 'warning');
            return;
        }

        if (payload.PriceMin !== null && payload.PriceMax !== null && payload.PriceMin > payload.PriceMax) {
            showNotification('Minimum Price cannot be greater than Maximum Price', 'warning');
            return;
        }

        if (payload.OdometerMin !== null && payload.OdometerMax !== null && payload.OdometerMin > payload.OdometerMax) {
            showNotification('Minimum KMs cannot be greater than Maximum KMs', 'warning');
            return;
        }

        showLoading('Creating payload...');
        console.log("Creating payload:", payload); // Log payload

        fetchWithAuth('/api/create_payload', {
            method: 'POST',
            body: JSON.stringify(payload),
        })
            .then(data => {
                if (data.success) {
                    currentPayload = data.payload;
                    updatePayloadDisplay();
                    showNotification('Payload created successfully', 'success');
                } else {
                    showNotification('Failed to create payload: ' + data.error, 'danger');
                }
                hideLoading();
            })
            .catch(error => {
                console.error('Error creating payload:', error);
                showNotification('Failed to create payload. Please try again.', 'danger');
                hideLoading();
            });
    });


    const renamePayloadBtn = document.getElementById('renamePayloadBtn');
    if (renamePayloadBtn) {
        renamePayloadBtn.addEventListener('click', renamePayload);
    }

    // Add event listener for the delete payload button
    const deletePayloadBtn = document.getElementById('deletePayloadBtn');
    if (deletePayloadBtn) {
        deletePayloadBtn.addEventListener('click', deletePayload);
    }

    // Add event listener for the rename result button
    const renameResultBtn = document.getElementById('renameResultBtn');
    if (renameResultBtn) {
        renameResultBtn.addEventListener('click', renameResult);
    }

    // Add event listener for the save rename button in the modal
    const saveRenameBtn = document.getElementById('saveRenameBtn');
    if (saveRenameBtn) {
        saveRenameBtn.addEventListener('click', handleSaveRename);
    }

    // --- Fetch Data Button Handler (Modified for Async Task) ---
    const fetchDataBtn = document.getElementById('fetchDataBtn');
    if (fetchDataBtn) {
        fetchDataBtn.addEventListener('click', function () {
            console.log("Fetch data button clicked");

            // Prevent multiple clicks if a task is already running
            if (currentFetchTaskId) {
                showNotification('A fetch operation is already in progress.', 'warning');
                return;
            }

            if (!currentPayload) {
                showNotification('No payload to use. Please create a payload first.', 'warning');
                return;
            }

            console.log("Current payload for fetching data:", JSON.stringify(currentPayload, null, 2));

            if (!currentPayload.Make) {
                showNotification('Payload must include a Make. Please create a valid payload.', 'warning');
                return;
            }

            // Show initial message, hide previous results/errors
            document.getElementById('resultsInfo').innerHTML = '<p>Initiating search...</p>';
            showNotification('Initiating search, checking tokens...', 'info');
            fetchDataBtn.disabled = true; // Disable button during initiation

            // Sanitize payload (same as before)
            const sanitizedPayload = {
                Make: currentPayload.Make || "",
                Model: currentPayload.Model || "",
                Address: currentPayload.Address || "Kanata, ON",
                Proximity: currentPayload.Proximity !== undefined ? currentPayload.Proximity : -1,
                YearMin: currentPayload.YearMin || null,
                YearMax: currentPayload.YearMax || null,
                PriceMin: currentPayload.PriceMin || null,
                PriceMax: currentPayload.PriceMax || null,
                OdometerMin: currentPayload.OdometerMin || null,
                OdometerMax: currentPayload.OdometerMax || null,
                IsNew: currentPayload.IsNew !== undefined ? currentPayload.IsNew : true,
                IsUsed: currentPayload.IsUsed !== undefined ? currentPayload.IsUsed : true,
                WithPhotos: currentPayload.WithPhotos !== undefined ? currentPayload.WithPhotos : true,
                Exclusions: Array.isArray(currentPayload.Exclusions) ? currentPayload.Exclusions : [],
                Inclusion: currentPayload.Inclusion || "",
                Trim: currentPayload.Trim || null,
                Color: currentPayload.Color || null,
                Drivetrain: currentPayload.Drivetrain || null,
                Transmission: currentPayload.Transmission || null,
                BodyType: currentPayload.BodyType || null,
                NumberOfDoors: currentPayload.NumberOfDoors !== undefined ? currentPayload.NumberOfDoors : null,
                SeatingCapacity: currentPayload.SeatingCapacity !== undefined ? currentPayload.SeatingCapacity : null,
                IsDamaged: currentPayload.IsDamaged !== undefined ? currentPayload.IsDamaged : false,
            };
            console.log("Sending payload for fetch_data:", sanitizedPayload); // Log sanitized payload

            // Call the modified API endpoint
            fetch('/api/fetch_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ payload: sanitizedPayload }),
            })
            .then(async response => {
                const data = await response.json();
                console.log("Fetch data initiation response:", response.status, data);

                if (response.ok && data.success && data.task_id) {
                    // Task started successfully
                    currentFetchTaskId = data.task_id;
                    showNotification('Search started. Monitoring progress...', 'info');

                    // Reset and show progress bar
                    const progressContainer = document.getElementById('fetchProgressContainer');
                    const progressBar = document.getElementById('fetchProgressBar');
                    const progressStatus = document.getElementById('fetchProgressStatus');

                    progressStatus.textContent = 'Task started... Waiting for progress...';
                    progressBar.style.width = '0%';
                    progressBar.textContent = '0%';
                    progressBar.setAttribute('aria-valuenow', '0');
                    progressContainer.style.display = 'block';

                    // Clear any previous interval and start polling
                    if (taskCheckInterval) clearInterval(taskCheckInterval);
                    taskCheckInterval = setInterval(checkTaskStatus, 2000); // Check every 2 seconds

                    // Keep button disabled while task runs
                    fetchDataBtn.disabled = true;

                } else {
                    // Handle errors like insufficient tokens (402) or other issues
                    let errorMessage = data.error || `HTTP error! Status: ${response.status}`;
                    if (response.status === 402) {
                        errorMessage = `Insufficient Tokens: ${data.error || 'Not enough tokens for this search.'}`;
                    }
                    document.getElementById('resultsInfo').innerHTML = `
                        <div class="alert alert-danger">
                            <p><i class="bi bi-exclamation-triangle"></i> Error: ${errorMessage}</p>
                        </div>`;
                    showNotification('Failed to start search: ' + errorMessage, 'danger');
                    fetchDataBtn.disabled = false; // Re-enable button on failure to start
                }
            })
            .catch(error => {
                console.error('Error initiating fetch data task:', error);
                document.getElementById('resultsInfo').innerHTML = `
                    <div class="alert alert-danger">
                        <p><i class="bi bi-exclamation-triangle"></i> Network or server error during initiation.</p>
                    </div>`;
                showNotification('Failed to start search. Network or server error.', 'danger');
                fetchDataBtn.disabled = false; // Re-enable button on network error
            });
        });
    } else {
        console.error("Fetch data button not found");
    }

    // Save payload button
    document.getElementById('savePayloadBtn').addEventListener('click', function () {
        if (!currentPayload) {
            showNotification('No payload to save. Please create a payload first.', 'warning');
            return;
        }

        // Generate a default name based on the payload
        const make = currentPayload.Make || 'Unknown';
        const model = currentPayload.Model || 'Unknown';
        const yearMin = currentPayload.YearMin || '';
        const yearMax = currentPayload.YearMax || '';
        const priceMin = currentPayload.PriceMin || '';
        const priceMax = currentPayload.PriceMax || '';

        const defaultName = `${make} ${model} (${yearMin}-${yearMax}, $${priceMin}-$${priceMax})`;

        // Set the default name in the input field
        document.getElementById('payloadName').value = defaultName;

        // Show the modal
        const namePayloadModal = new bootstrap.Modal(document.getElementById('namePayloadModal'));
        namePayloadModal.show();
    });

    document.getElementById('saveNamedPayloadBtn').addEventListener('click', function () {
        const payloadName = document.getElementById('payloadName').value.trim();

        if (!payloadName) {
            showNotification('Please enter a name for your payload', 'warning');
            return;
        }

        // Add the name to the payload
        currentPayload.custom_name = payloadName;

        // Close the modal
        const namePayloadModal = bootstrap.Modal.getInstance(document.getElementById('namePayloadModal'));
        namePayloadModal.hide();

        // Now save the payload
        showLoading('Saving payload...');
        console.log("Saving payload:", currentPayload); // Log payload

        fetchWithAuth('/api/save_payload', {
            method: 'POST',
            body: JSON.stringify({ payload: currentPayload }),
        })
            .then(data => {
                if (data.success) {
                    showNotification(`Payload saved as "${payloadName}"`, 'success');
                    loadSavedPayloads();
                } else {
                    showNotification('Failed to save payload: ' + data.error, 'danger');
                }
                hideLoading();
            })
            .catch(error => {
                console.error('Error saving payload:', error);
                showNotification('Failed to save payload. Please try again.', 'danger');
                hideLoading();
            });
    });

    // Download current CSV button
    document.getElementById('downloadCsvBtn').addEventListener('click', function () {
        if (!resultsFilePath) {
            showNotification('No results file available. Please fetch data first.', 'warning');
            return;
        }

        downloadCsvFile(resultsFilePath);
    });

    // Download selected result button in modal
    document.getElementById('downloadSelectedResultBtn').addEventListener('click', function () {
        const resultId = currentResultId || document.getElementById('resultSelect').value;

        if (!resultId) {
            showNotification('No result selected to download', 'warning');
            return;
        }

        downloadResultAsCsv(resultId);
    });

    // View result button
    document.getElementById('viewResultBtn').addEventListener('click', function () {
        viewSelectedResult();
    });

    // Delete result button
    document.getElementById('deleteResultBtn').addEventListener('click', function () {
        deleteSelectedResult();
    });

    // Open links button
    document.getElementById('openLinksBtn').addEventListener('click', function () {
        if (!resultsFilePath) {
            showNotification('No results file available. Please fetch data first.', 'warning');
            return;
        }

        openLinksFromCsv(resultsFilePath);
    });

    // Open selected links button in modal
    document.getElementById('openSelectedLinksBtn').addEventListener('click', openSelectedVehicleLinks);

    // Load payload from dropdown
    setupLoadPayloadButton();

    // Setup Settings Button
    document.getElementById('settingsBtn').addEventListener('click', openUserSettingsModal);
    document.getElementById('saveUserSettingsBtn').addEventListener('click', saveUserSettings);
    document.getElementById('increaseTokensBtn').addEventListener('click', () => adjustTokens(1));
    document.getElementById('decreaseTokensBtn').addEventListener('click', () => adjustTokens(-1));

    // Initial fetch of user settings to display token count
    fetchUserSettings(true); // Pass true to update display initially

    // Clear Filters button
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', function () {
            const form = document.getElementById('searchForm');
            const inputs = form.querySelectorAll('input[type="text"], input[type="number"], input[type="email"], input[type="password"], textarea');
            const checkboxes = form.querySelectorAll('input[type="checkbox"]');
            const selects = form.querySelectorAll('select');

            inputs.forEach(input => {
                // Preserve default address and proximity
                if (input.id === 'address') {
                    input.value = 'Kanata, ON';
                } else if (input.id === 'proximity') {
                    input.value = '-1';
                } else {
                    input.value = '';
                }
            });

            checkboxes.forEach(checkbox => {
                // Default checked states
                if (checkbox.id === 'isNew' || checkbox.id === 'isUsed' || checkbox.id === 'withPhotos') {
                    checkbox.checked = true;
                } else {
                    checkbox.checked = false;
                }
            });

            selects.forEach(select => {
                if (select.id === 'makeSelect') {
                    select.value = ''; // Reset make to "Select Make"
                    // Trigger change to reset dependent dropdowns
                    select.dispatchEvent(new Event('change'));
                } else if (select.id === 'modelSelect') {
                    select.innerHTML = '<option value="">Select Model (Choose Make First)</option>';
                    select.value = '';
                } else if (select.id === 'trimSelect') {
                    select.innerHTML = '<option value="">Any Trim (Select Model First)</option>';
                    select.value = '';
                } else if (select.id === 'colorSelect') {
                    select.innerHTML = '<option value="">Any Color (Select Trim/Model First)</option>';
                    select.value = '';
                } else if (select.id === 'drivetrainSelect' || select.id === 'transmissionSelect') {
                    select.value = ''; // Reset to "Any"
                } else {
                    select.selectedIndex = 0; // For other selects, reset to the first option
                }
            });

            // Clear exclusions
            exclusions = [];
            updateExclusionsList();

            // Reset currentPayload if it exists
            currentPayload = null;
            if (document.getElementById('currentPayload')) {
                updatePayloadDisplay(); // Clear the display
            }


            showNotification('All filters cleared', 'info');
        });
    }

});

// Function to make authenticated API requests (modified to handle non-JSON responses better)
async function fetchWithAuth(url, options = {}) {
    try {
        console.log(`Making request to: ${url}`);
        const defaultHeaders = {
            'Content-Type': 'application/json',
        };

        // Get current Firebase user if available
        const user = firebase.auth().currentUser;
        if (user) {
            try {
                const token = await user.getIdToken();
                defaultHeaders['Authorization'] = `Bearer ${token}`;
            } catch (error) {
                console.warn("Could not get Firebase token:", error);
            }
        }

        // Merge default headers with provided options
        const mergedOptions = {
            ...options,
            headers: {
                ...defaultHeaders,
                ...(options.headers || {})
            }
        };

        // Make the request
        const response = await fetch(url, mergedOptions);

        if (!response.ok) {
            console.error(`HTTP error! Status: ${response.status}`);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        // Try parsing as JSON, but handle errors
        try {
            const data = await response.json();
            // Attach status to the data object for easier handling later
            data.status = response.status;
            return data;
        } catch (jsonError) {
            // If JSON parsing fails, return a generic error object with status
            console.error('Failed to parse JSON response:', jsonError);
            return { success: false, error: `Server returned non-JSON response (Status: ${response.status})`, status: response.status };
        }
    } catch (error) {
        console.error('API request failed:', error);
        // Return a consistent error format
        return { success: false, error: `Network or request error: ${error.message}`, status: 0 }; // Status 0 for network errors
    }
}

// Function to show notification
function showNotification(message, type = 'primary') {
    const notification = document.getElementById('notification');
    notification.classList.remove('bg-primary', 'bg-success', 'bg-danger', 'bg-warning');
    notification.classList.add(`bg-${type}`);
    document.getElementById('notification-content').textContent = message;

    const toast = new bootstrap.Toast(notification);
    toast.show();
}

// Function to show loading
function showLoading(message = 'Processing your request...') {
    const loadingMessage = document.getElementById('loadingMessage');
    const loadingCard = document.getElementById('loadingCard');

    if (loadingMessage) {
        loadingMessage.textContent = message;
    }

    if (loadingCard) {
        loadingCard.style.display = 'block';
    } else {
        console.log('Loading started: ' + message);
    }
}

// Function to hide loading
function hideLoading() {
    const loadingCard = document.getElementById('loadingCard');

    if (loadingCard) {
        loadingCard.style.display = 'none';
    } else {
        console.log('Loading complete');
    }
}

// Function to update payload display
function updatePayloadDisplay() {
    const payloadElement = document.getElementById('currentPayload');

    // If the element doesn't exist, just log a message and return
    if (!payloadElement) {
        console.log('Note: currentPayload element not found in the DOM');
        return;
    }

    if (currentPayload) {
        payloadElement.textContent = JSON.stringify(currentPayload, null, 2);
    } else {
        payloadElement.textContent = 'No payload created yet.';
    }
}

// Function to update exclusions list
function updateExclusionsList() {
    const exclusionsListEl = document.getElementById('exclusionsList');
    exclusionsListEl.innerHTML = '';

    exclusions.forEach((exclusion, index) => {
        const badge = document.createElement('span');
        badge.classList.add('badge', 'bg-secondary', 'keyword-badge');
        badge.innerHTML = `${exclusion} <i class="bi bi-x-circle" data-index="${index}" style="cursor: pointer;"></i>`;
        exclusionsListEl.appendChild(badge);
    });

    // Add click event to remove badges
    document.querySelectorAll('#exclusionsList .bi-x-circle').forEach(icon => {
        icon.addEventListener('click', function () {
            const index = parseInt(this.getAttribute('data-index'));
            exclusions.splice(index, 1);
            updateExclusionsList();
        });
    });
}

// Function to load makes
function loadMakes(popular = true) {
    showLoading('Loading makes...');
    console.log("Loading makes...");

    fetchWithAuth(`/api/makes?popular=${popular}`)
        .then(data => {
            console.log("Makes loaded:", data);
            const makeSelect = document.getElementById('makeSelect');
            makeSelect.innerHTML = '<option value="">Select Make</option>';

            data.forEach(make => {
                const option = document.createElement('option');
                option.value = make;
                option.textContent = make;
                makeSelect.appendChild(option);
            });

            hideLoading();
        })
        .catch(error => {
            console.error('Error loading makes:', error);
            showNotification('Failed to load makes. Please try again.', 'danger');
            hideLoading();
        });
}

// Load models when make changes
document.getElementById('makeSelect').addEventListener('change', function () {
    const make = this.value;
    const modelSelect = document.getElementById('modelSelect');

    modelSelect.innerHTML = '<option value="">Select Model</option>';
    // Also reset trim when make changes
    document.getElementById('trimSelect').innerHTML = '<option value="">Any Trim (Select Model First)</option>';

    if (!make) return;

    showLoading('Loading models...');
    console.log(`Loading models for make: ${make}`);

            fetchWithAuth(`/api/models/${make}`)
                .then(data => {
                    console.log("Models loaded:", data);
                    const models = Object.keys(data); // e.g., ["IS (387)", "RX (123)"]

                    models.forEach(modelWithCount => { // modelWithCount is like "IS (387)"
                        // Check if modelWithCount contains "status", case-insensitive
                        if (modelWithCount.toLowerCase().includes('status')) {
                            return; // Skip this iteration if "status" is found
                        }
                        const option = document.createElement('option');
                        option.value = cleanModelNameJS(modelWithCount); // Set value to cleaned name, e.g., "IS"
                        option.textContent = `${modelWithCount} (${data[modelWithCount]})`; // Display text: "IS (387) (10)"
                        modelSelect.appendChild(option);
                    });

                    hideLoading();
                })
        .catch(error => {
            console.error('Error loading models:', error);
            showNotification('Failed to load models. Please try again.', 'danger');
            hideLoading();
        });
});

// Load trims when model changes
document.getElementById('modelSelect').addEventListener('change', function () {
    const make = document.getElementById('makeSelect').value;
    const model = this.value;
    const trimSelect = document.getElementById('trimSelect');

    trimSelect.innerHTML = '<option value="">Any Trim</option>'; // Reset trims
    // Also reset color when model changes
    document.getElementById('colorSelect').innerHTML = '<option value="">Any Color (Select Trim/Model First)</option>';

    if (!make || !model) return;

    // Load trims AND colors (if no trim is selected initially)
    loadTrims(make, model);
    loadColors(make, model); // Load colors based on make/model initially
});

// Load colors when trim changes
document.getElementById('trimSelect').addEventListener('change', function () {
    const make = document.getElementById('makeSelect').value;
    const model = document.getElementById('modelSelect').value;
    const trim = this.value; // Can be "" for "Any Trim"

    if (!make || !model) return;

    loadColors(make, model, trim || null); // Pass null if trim is ""
});


// Function to load trims
function loadTrims(make, model, selectedTrim = null) {
    const trimSelect = document.getElementById('trimSelect');
    trimSelect.innerHTML = '<option value="">Loading Trims...</option>'; // Show loading state

    console.log(`Loading trims for make: ${make}, model: ${model}`);

    // Encode make and model for the URL
    const encodedMake = encodeURIComponent(make);
    const encodedModel = encodeURIComponent(model);

    fetchWithAuth(`/api/trims/${encodedMake}/${encodedModel}`)
        .then(data => {
            // Check for explicit failure from backend, even if fetch itself succeeded (e.g., 200 OK but {success: false})
            if (data && data.success === false) {
                console.error('Error loading trims (API Error):', data.error);
                showNotification(`Failed to load trims: ${data.error}`, 'danger');
                trimSelect.innerHTML = '<option value="">Error loading trims</option>';
                hideLoading();
                return; // Stop further processing
            }

            console.log("Trims loaded:", data); // Assuming data is the dictionary {trim: count} or {}
            trimSelect.innerHTML = '<option value="">Any Trim</option>'; // Reset with default
            const trims = Object.keys(data);

            trims.forEach(trim => {
                // Explicitly skip if the key is 'Status' (case-insensitive)
                if (trim.trim().toLowerCase() === 'status') {
                    return; // Skip this iteration
                }
                const option = document.createElement('option');
                option.value = trim;
                // Display count if available, otherwise just the trim name
                option.textContent = data[trim] ? `${trim} (${data[trim]})` : trim;
                trimSelect.appendChild(option);
            });

            // Re-select the trim if it was passed (e.g., when loading a payload)
            if (selectedTrim && trims.includes(selectedTrim)) {
                trimSelect.value = selectedTrim;
            }

            hideLoading(); // Assuming hideLoading exists
        })
        .catch(error => {
            console.error('Error loading trims:', error);
            showNotification('Failed to load trims. Please try again.', 'danger');
            trimSelect.innerHTML = '<option value="">Error loading trims</option>'; // Show error state
            hideLoading(); // Assuming hideLoading exists
        });
}

// Function to load colors
function loadColors(make, model, trim = null, selectedColor = null) {
    const colorSelect = document.getElementById('colorSelect');
    colorSelect.innerHTML = '<option value="">Loading Colors...</option>'; // Show loading state

    console.log(`Loading colors for make: ${make}, model: ${model}, trim: ${trim}`);

    // Encode make, model, and trim for the URL
    const encodedMake = encodeURIComponent(make);
    const encodedModel = encodeURIComponent(model);
    let url = `/api/colors/${encodedMake}/${encodedModel}`;
    if (trim) {
        url += `/${encodeURIComponent(trim)}`;
    }


    fetchWithAuth(url)
        .then(data => {
            // Check for explicit failure from backend
            if (data && data.success === false) {
                console.error('Error loading colors (API Error):', data.error);
                showNotification(`Failed to load colors: ${data.error}`, 'danger');
                colorSelect.innerHTML = '<option value="">Error loading colors</option>';
                hideLoading();
                return; // Stop further processing
            }

            console.log("Colors loaded:", data); // Assuming data is the list of color strings
            colorSelect.innerHTML = '<option value="">Any Color</option>'; // Reset with default

            // Handle dictionary response {color: count}
            if (typeof data === 'object' && data !== null && !Array.isArray(data)) {
                const colors = Object.keys(data); // Get color names from keys

                colors.forEach(color => {
                    // Explicitly skip if the key is 'Status' (case-insensitive) - safety check
                    if (color.trim().toLowerCase() === 'status') {
                        return; // Skip this iteration
                    }
                    const option = document.createElement('option');
                    option.value = color;
                    // Display count if available (data[color]), otherwise just the color name
                    option.textContent = data[color] ? `${color} (${data[color]})` : color;
                    colorSelect.appendChild(option);
                });

                // Re-select the color if it was passed and exists in the keys
                if (selectedColor && colors.includes(selectedColor)) {
                    colorSelect.value = selectedColor;
                }
            } else {
                console.warn("Received unexpected data format for colors:", data);
                // Keep "Any Color" as the only option if data is not a dictionary
            }

            hideLoading();
        })
        .catch(error => {
            console.error('Error loading colors:', error);
            showNotification('Failed to load colors. Please try again.', 'danger');
            colorSelect.innerHTML = '<option value="">Error loading colors</option>'; // Show error state
            hideLoading();
        });
}

// Show all makes button
document.getElementById('showAllMakes').addEventListener('click', function () {
    loadMakes(false);
});

// Function to load saved payloads
function loadSavedPayloads() {
    showLoading('Loading saved payloads...');

    fetchWithAuth('/api/list_payloads')
        .then(data => {
            if (data.success) {
                const payloadSelect = document.getElementById('payloadSelect');
                payloadSelect.innerHTML = '<option value="">Select a saved payload</option>';

                data.payloads.forEach(payload => {
                    const option = document.createElement('option');
                    option.value = payload.name || payload;
                    option.textContent = payload.name || payload;
                    if (payload.id) {
                        option.setAttribute('data-id', payload.id);
                    }
                    payloadSelect.appendChild(option);
                });
            } else {
                showNotification('Failed to load saved payloads: ' + data.error, 'danger');
            }
            hideLoading();
        })
        .catch(error => {
            console.error('Error loading saved payloads:', error);
            showNotification('Failed to load saved payloads. Please try again.', 'danger');
            hideLoading();
        });
}

// Function to populate form with payload data
function populateFormWithPayload(payload) {
    console.log("Populating form with payload:", payload);

    if (!payload) {
        console.error("No payload data provided to populateFormWithPayload");
        return;
    }

    // Make sure we have the expected properties
    const make = payload.Make || "";
    const model = payload.Model || "";

    // Select the make
    const makeSelect = document.getElementById('makeSelect');
    if (makeSelect) {
        console.log(`Setting make to: ${make}`);
        makeSelect.value = make;

        // If we have a valid make, load the associated models
        if (make) {
            console.log("Loading models for make:", make);

            // Show loading notification
            showNotification('Loading models for ' + make + '...', 'info');

            // Fetch models for this make
            fetchWithAuth(`/api/models/${make}`)
                .then(data => {
                    console.log("Models loaded:", data);
                    const modelSelect = document.getElementById('modelSelect');

                    // Clear existing options
                    modelSelect.innerHTML = '<option value="">Select Model</option>';

                    // Add new options
                    const models = Object.keys(data);
                    models.forEach(modelNameWithCount => { // modelNameWithCount is like "IS (387)"
                        const option = document.createElement('option');
                        option.value = cleanModelNameJS(modelNameWithCount); // Set value to cleaned name, e.g., "IS"
                        option.textContent = `${modelNameWithCount} (${data[modelNameWithCount]})`; // Display text: "IS (387) (10)"
                        modelSelect.appendChild(option);
                    });

                    // Now select the model from payload
                    if (model) {
                        console.log(`Setting model to: ${model}`);
                        modelSelect.value = model;
                        // Trigger trim and color loading after model is set
                        if (payload.Make && payload.Model) {
                            loadTrims(payload.Make, payload.Model, payload.Trim);
                            // Load colors based on make/model/trim from payload
                            loadColors(payload.Make, payload.Model, payload.Trim, payload.Color);
                        }
                    } else {
                        // If no model in payload, still load colors based on make if available
                        if (payload.Make) {
                            loadColors(payload.Make, null, null, payload.Color);
                        }
                    }
                })
                .catch(error => {
                    console.error('Error loading models:', error);
                    showNotification('Failed to load models for ' + make, 'danger');
                });
        }
    }

    // Fill other form fields
    const fieldsToPopulate = [
        { id: 'address', value: payload.Address || '' },
        { id: 'proximity', value: payload.Proximity !== undefined ? payload.Proximity : -1 },
        { id: 'yearMin', value: payload.YearMin || '' },
        { id: 'yearMax', value: payload.YearMax || '' },
        { id: 'priceMin', value: payload.PriceMin || '' },
        { id: 'priceMax', value: payload.PriceMax || '' },
        { id: 'odometerMin', value: payload.OdometerMin || '' },
        { id: 'odometerMax', value: payload.OdometerMax || '' }
    ];

    // Set values for text fields
    fieldsToPopulate.forEach(field => {
        const element = document.getElementById(field.id);
        if (element) {
            console.log(`Setting ${field.id} to:`, field.value);
            element.value = field.value;
        } else {
            console.warn(`Element with id ${field.id} not found`);
        }
    });

    // Set checkbox values
    const checkboxes = [
        { id: 'isNew', value: payload.IsNew !== undefined ? payload.IsNew : true },
        { id: 'isUsed', value: payload.IsUsed !== undefined ? payload.IsUsed : true },
        { id: 'withPhotos', value: payload.WithPhotos !== undefined ? payload.WithPhotos : true }
    ];

    checkboxes.forEach(checkbox => {
        const element = document.getElementById(checkbox.id);
        if (element) {
            console.log(`Setting ${checkbox.id} to:`, checkbox.value);
            element.checked = checkbox.value;
        } else {
            console.warn(`Element with id ${checkbox.id} not found`);
        }
    });

    // Set inclusion value
    const inclusionElement = document.getElementById('inclusion');
    if (inclusionElement) {
        inclusionElement.value = payload.Inclusion || '';
    }

    // Handle exclusions
    exclusions = Array.isArray(payload.Exclusions) ? [...payload.Exclusions] : [];
    console.log("Setting exclusions:", exclusions);
    updateExclusionsList();

    // Populate new fields - Special handling for Trim dropdown
    const trimSelect = document.getElementById('trimSelect');
    if (trimSelect) {
        // Reset trim select initially
        trimSelect.innerHTML = '<option value="">Any Trim</option>';
        // If make and model are present, attempt to load trims and select the saved one
        if (!payload.Make || !payload.Model) {
            // If no make/model, just set to 'Any'
            trimSelect.value = "";
        } else if (!payload.Trim) {
            // If make/model but no trim, load trims and keep 'Any' selected
            loadTrims(payload.Make, payload.Model);
        } else {
            // If make/model and trim, load trims and try to select the saved one
            // Color loading is handled separately after models load
        }
    }
    // Color is handled by loadColors called after models load
    const drivetrainSelect = document.getElementById('drivetrainSelect');
    if (drivetrainSelect) drivetrainSelect.value = payload.Drivetrain || '';
    const transmissionSelect = document.getElementById('transmissionSelect');
    if (transmissionSelect) transmissionSelect.value = payload.Transmission || '';

    // Populate new form fields
    const bodyTypeInput = document.getElementById('bodyTypeInput');
    if (bodyTypeInput) bodyTypeInput.value = payload.BodyType || '';
    const numDoorsInput = document.getElementById('numDoorsInput');
    if (numDoorsInput) numDoorsInput.value = payload.NumberOfDoors || '';
    const seatingCapacityInput = document.getElementById('seatingCapacityInput');
    if (seatingCapacityInput) seatingCapacityInput.value = payload.SeatingCapacity || '';
    const isDamagedCheckbox = document.getElementById('isDamaged');
    if (isDamagedCheckbox) isDamagedCheckbox.checked = payload.IsDamaged || false; // Default to false if missing
}

// Load saved results
function loadSavedResults() {
    showLoading('Loading saved results...');

    fetchWithAuth('/api/list_results')
        .then(data => {
            if (data.success) {
                const resultSelect = document.getElementById('resultSelect');
                resultSelect.innerHTML = '<option value="">Select a saved result</option>';

                data.results.forEach(result => {
                    const option = document.createElement('option');
                    option.value = result.id;

                    // Create a descriptive name from metadata
                    const metadata = result.metadata || {};
                    const make = metadata.make || 'Unknown';
                    const model = metadata.model || 'Unknown';
                    const yearMin = metadata.yearMin || '';
                    const yearMax = metadata.yearMax || '';
                    const priceMin = metadata.priceMin || '';
                    const priceMax = metadata.priceMax || '';
                    const count = result.result_count || 0;
                    const timestamp = metadata.timestamp || '';

                    option.textContent = `${make} ${model} (${yearMin}-${yearMax}, $${priceMin}-$${priceMax}) - ${count} results - ${timestamp}`;
                    resultSelect.appendChild(option);
                });

                hideLoading();
            } else {
                showNotification('Failed to load saved results: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error loading saved results:', error);
            showNotification('Failed to load saved results. Please try again.', 'danger');
            hideLoading();
        });
}

// Function to view selected result
function viewSelectedResult() {
    const resultId = document.getElementById('resultSelect').value;

    if (!resultId) {
        showNotification('Please select a result to view', 'warning');
        return;
    }

    currentResultId = resultId;
    showLoading('Loading result data...');

    fetchWithAuth('/api/get_result', {
        method: 'POST',
        body: JSON.stringify({ result_id: resultId }),
    })
        .then(data => {
            if (data.success) {
                displayResults(data.result);
                hideLoading();
            } else {
                showNotification('Failed to load result: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error loading result:', error);
            showNotification('Failed to load result. Please try again.', 'danger');
            hideLoading();
        });
}

function addSelectorPrototype() {
    // Add a contains selector implementation since we're not using jQuery
    // This will allow us to find elements by text content
    if (!Element.prototype.matches) {
        Element.prototype.matches = Element.prototype.msMatchesSelector ||
            Element.prototype.webkitMatchesSelector;
    }

    if (!document.querySelectorAll) return;

    document.querySelectorAll = (function (querySelectorAll) {
        return function (selector) {
            if (selector.includes(':contains(')) {
                // Extract the search text
                const matches = selector.match(/:contains\((['"])(.*?)\1\)/);
                if (matches) {
                    const searchText = matches[2];
                    const newSelector = selector.replace(/:contains\((['"])(.*?)\1\)/, '');

                    // Get elements that match the remaining selector
                    const elements = querySelectorAll.call(this, newSelector);

                    // Filter to find elements containing the text
                    return Array.prototype.filter.call(elements, function (element) {
                        return element.textContent.includes(searchText);
                    });
                }
            }

            return querySelectorAll.call(this, selector);
        };
    })(document.querySelectorAll);
}

// Variables to track sorting and filtering state
let currentSortField = '';
let currentSortDirection = 'asc';
let originalVehicles = []; // Holds the full list loaded into the modal
let currentVehicles = []; // Holds the currently displayed list (filtered/sorted)


// --- Filter Functions ---

function populateFilterDropdowns(vehicles) {
    const makeFilter = document.getElementById('filterMake');
    const modelFilter = document.getElementById('filterModel');
    const drivetrainFilter = document.getElementById('filterDrivetrain'); // Get drivetrain select

    const makes = [...new Set(vehicles.map(v => v.Make || ''))].filter(Boolean).sort();
    const models = [...new Set(vehicles.map(v => v.Model || ''))].filter(Boolean).sort();
    const drivetrains = [...new Set(vehicles.map(v => v.Drivetrain || ''))].filter(Boolean).sort(); // Get unique drivetrains

    makeFilter.innerHTML = '<option value="">All</option>'; // Shortened default text
    makes.forEach(make => {
        makeFilter.innerHTML += `<option value="${make}">${make}</option>`;
    });

    modelFilter.innerHTML = '<option value="">All</option>'; // Shortened default text
    models.forEach(model => {
        modelFilter.innerHTML += `<option value="${model}">${model}</option>`;
    });

    drivetrainFilter.innerHTML = '<option value="">All</option>'; // Add default for drivetrain
    drivetrains.forEach(drive => {
        drivetrainFilter.innerHTML += `<option value="${drive}">${drive}</option>`;
    });
}

function applyFiltersAndDisplay() {
    const filterMakeValue = document.getElementById('filterMake').value;
    const filterModelValue = document.getElementById('filterModel').value;
    const filterTrimValue = document.getElementById('filterTrim').value.toLowerCase(); // Get trim filter
    const filterYearValue = document.getElementById('filterYear').value;
    const filterPriceMaxValue = document.getElementById('filterPriceMax').value;
    const filterKmsMaxValue = document.getElementById('filterKmsMax').value; // Get KMs filter
    const filterDrivetrainValue = document.getElementById('filterDrivetrain').value; // Get drivetrain filter

    currentVehicles = originalVehicles.filter(vehicle => {
        const makeMatch = !filterMakeValue || (vehicle.Make && vehicle.Make === filterMakeValue);
        const modelMatch = !filterModelValue || (vehicle.Model && vehicle.Model === filterModelValue);
        const trimMatch = !filterTrimValue || (vehicle.Trim && vehicle.Trim.toLowerCase().includes(filterTrimValue)); // Trim contains check
        const yearMatch = !filterYearValue || (vehicle.Year && vehicle.Year.toString() === filterYearValue);

        // Price comparison
        let price = Infinity; // Default to Infinity if no price
        if (vehicle.Price) {
            price = parseFloat(String(vehicle.Price).replace(/[^0-9.]/g, '')) || Infinity;
        }
        const priceMatch = !filterPriceMaxValue || price <= parseFloat(filterPriceMaxValue);

        // KMs comparison
        let kms = Infinity; // Default to Infinity if no KMs
        if (vehicle.Kilometres) {
            kms = parseFloat(String(vehicle.Kilometres).replace(/[^0-9.]/g, '')) || Infinity;
        }
        const kmsMatch = !filterKmsMaxValue || kms <= parseFloat(filterKmsMaxValue);

        // Drivetrain comparison
        const drivetrainMatch = !filterDrivetrainValue || (vehicle.Drivetrain && vehicle.Drivetrain === filterDrivetrainValue);


        return makeMatch && modelMatch && trimMatch && yearMatch && priceMatch && kmsMatch && drivetrainMatch;
    });

    // Reset sort before displaying filtered results
    currentSortField = '';
    currentSortDirection = 'asc';
    document.querySelectorAll('.sort-icon').forEach(i => i.classList.add('d-none'));


    updateTableWithSortedData(currentVehicles);
    showNotification(`Filtered results: ${currentVehicles.length} listings shown.`, 'info');
}

// --- End Filter Functions ---

// --- Delete Listing Function ---
function deleteListing(indexToDelete) {
    // Find the actual vehicle object corresponding to the index in the *currently displayed* list
    const vehicleToDelete = currentVehicles[indexToDelete];

    if (!vehicleToDelete) {
        console.error("Could not find vehicle to delete at index:", indexToDelete);
        return;
    }

    // Find the index of this vehicle in the *original* list to remove it permanently
    const originalIndex = originalVehicles.findIndex(v =>
        v.Link === vehicleToDelete.Link && // Assuming Link is a unique identifier
        v.Year === vehicleToDelete.Year &&
        v.Make === vehicleToDelete.Make &&
        v.Model === vehicleToDelete.Model &&
        v.Price === vehicleToDelete.Price // Add more fields if Link isn't guaranteed unique
    );

    if (originalIndex > -1) {
        originalVehicles.splice(originalIndex, 1); // Remove from original list
        console.log("Removed from originalVehicles at index:", originalIndex);
    } else {
        console.warn("Could not find the exact vehicle in originalVehicles to remove.");
        // Fallback: Try removing based on index if original list wasn't modified elsewhere
        if (originalVehicles.length > indexToDelete) {
            // This might be risky if originalVehicles was modified independently
            // originalVehicles.splice(indexToDelete, 1);
        }
    }

    // Remove from the currently displayed list
    currentVehicles.splice(indexToDelete, 1);
    console.log("Removed from currentVehicles at index:", indexToDelete);


    // Re-render the table with the updated currentVehicles list
    updateTableWithSortedData(currentVehicles);
    showNotification('Listing removed from view. Saving change...', 'info');

    // Persist deletion to backend
    if (!currentResultId) {
        console.error("Cannot permanently delete listing: currentResultId is not set.");
        showNotification('Error: Could not determine which saved result to modify.', 'danger');
        // Consider reverting the local deletion here if desired
        return;
    }

    // Send enough details to uniquely identify the listing on the backend
    // Using the 'Link' is often a good unique identifier from scraping
    const listingIdentifier = { Link: vehicleToDelete.Link, /* Add other potentially unique fields if needed */ };

    fetchWithAuth('/api/delete_listing_from_result', {
        method: 'POST',
        body: JSON.stringify({
            result_id: currentResultId,
            listing_identifier: listingIdentifier // Send identifier instead of the whole object
        }),
    })
        .then(data => {
            if (data.success) {
                showNotification('Listing permanently deleted from saved result.', 'success');
                // Optionally refresh the main results list if the count changed significantly
                // refreshResultsList();
            } else {
                showNotification('Failed to permanently delete listing: ' + data.error, 'danger');
                // Revert local deletion if backend fails?
                // This is complex as it requires adding the item back to originalVehicles/currentVehicles
                // and re-rendering. For now, we'll leave it removed from view but notify the user.
                console.error("Backend deletion failed:", data.error);
            }
        })
        .catch(error => {
            showNotification('Error contacting server to delete listing.', 'danger');
            console.error("Network/server error during listing deletion:", error);
            // Also consider reverting local deletion here
        });
}
// --- End Delete Listing Function ---

// Combined handler for table actions (Analyze and Delete)
function handleTableActions(event) {
    const analyzeButton = event.target.closest('.analyze-btn');
    const deleteButton = event.target.closest('.delete-listing-btn');

    if (analyzeButton) {
        handleAnalyzeClick(event); // Call the existing analyze handler
    } else if (deleteButton) {
        const index = parseInt(deleteButton.getAttribute('data-index'));
        if (!isNaN(index)) {
            // Confirm before deleting
            if (confirm('Are you sure you want to remove this listing from the results?')) {
                deleteListing(index);
            }
        }
    }
}

// Function to sort vehicles by a specific field
function sortVehicles(vehicles, field, direction) {
    return [...vehicles].sort((a, b) => {
        let valueA = a[field] || '';
        let valueB = b[field] || '';

        // Handle numeric fields
        if (field === 'Year' || field === 'Price' || field === 'Kilometres') {
            // Extract numeric values (remove currency symbols, commas, etc.)
            valueA = parseFloat(String(valueA).replace(/[^0-9.]/g, '')) || 0;
            valueB = parseFloat(String(valueB).replace(/[^0-9.]/g, '')) || 0;
        } else {
            // For string values, convert to lowercase for case-insensitive comparison
            valueA = String(valueA).toLowerCase();
            valueB = String(valueB).toLowerCase();
        }

        // Compare based on direction
        if (direction === 'asc') {
            return valueA > valueB ? 1 : valueA < valueB ? -1 : 0;
        } else {
            return valueA < valueB ? 1 : valueA > valueB ? -1 : 0;
        }
    });
}

// Function to display results in a table
function displayResults(result) {
    const resultsTable = document.getElementById('resultsTableContainer');
    const resultsModal = new bootstrap.Modal(document.getElementById('resultsModal'));

    const metadata = result.metadata || {};
    const make = metadata.make || 'Unknown';
    const model = metadata.model || 'Unknown';
    const yearMin = metadata.yearMin || '';
    const yearMax = metadata.yearMax || '';

    // Update modal title with custom name if available
    if (metadata.custom_name) {
        document.getElementById('resultsModalLabel').textContent = metadata.custom_name;
    } else {
        document.getElementById('resultsModalLabel').textContent =
            `Results: ${make} ${model} (${yearMin}-${yearMax})`;
    }

    // Get results array and store it as the original list
    originalVehicles = result.results || [];
    currentVehicles = [...originalVehicles]; // Initially display all vehicles

    // Populate filter dropdowns
    populateFilterDropdowns(originalVehicles);

    // Create table
    let tableHTML = `
                <table class="table table-striped table-hover" id="vehicleResultsTable">
                    <thead>
                        <tr>
                            <th><input type="checkbox" id="selectAllVehicles"></th>
                            <th class="sortable" data-field="Year">Year <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th class="sortable" data-field="Make">Make <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th class="sortable" data-field="Model">Model <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th class="sortable" data-field="Trim">Trim <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th class="sortable" data-field="Price">Price <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th class="sortable" data-field="Kilometres">Kilometers <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th class="sortable" data-field="Drivetrain">Drivetrain <i class="bi bi-sort-down d-none sort-icon"></i></th>
                            <th>Actions</th>
                            <th>Delete</th> <!-- Added Delete Header -->
                        </tr>
                    </thead>
                    <tbody id="vehicleResultsTableBody"> <!-- Added ID for easier targeting -->
            `;

    // Use the current vehicles array (sorted if applicable)
    const vehiclesToDisplay = currentVehicles;

    vehiclesToDisplay.forEach((vehicle, index) => {
        tableHTML += `
                    <tr>
                        <td><input type="checkbox" class="vehicle-checkbox" data-link="${vehicle.Link || ''}"></td>
                        <td>${vehicle.Year || ''}</td>
                        <td>${vehicle.Make || ''}</td>
                        <td>${vehicle.Model || ''}</td>
                        <td>${vehicle.Trim || ''}</td>
                        <td>${vehicle.Price || ''}</td>
                        <td>${vehicle.Kilometres || ''}</td>
                        <td>${vehicle.Drivetrain || ''}</td>
                        <td>
                            <a href="${vehicle.Link || '#'}" target="_blank" class="btn btn-sm btn-primary me-1" title="View on AutoTrader">
                                <i class="bi bi-box-arrow-up-right"></i>
                            </a>
                            <button class="btn btn-sm btn-info analyze-btn"
                                    data-make="${vehicle.Make || ''}"
                                    data-model="${vehicle.Model || ''}"
                                    data-year="${vehicle.Year || ''}"
                                    data-trim="${vehicle.Trim || ''}"
                                    data-price="${vehicle.Price || ''}"
                                    data-km="${vehicle.Kilometres || ''}"
                                    title="Analyze Reliability with AI">
                                <i class="bi bi-robot"></i> Analyze
                            </button>
                        </td>
                        <td> <!-- Added Delete Cell -->
                            <button class="btn btn-sm btn-danger delete-listing-btn" data-index="${index}" title="Delete Listing">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
    });

    tableHTML += `
                    </tbody>
                </table>
            `;

    resultsTable.innerHTML = tableHTML;

    // Set up select all checkbox
    document.getElementById('selectAllVehicles').addEventListener('change', function () {
        const checkboxes = document.querySelectorAll('.vehicle-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.checked = this.checked;
        });
    });

    // Add event listeners for sortable columns
    document.querySelectorAll('.sortable').forEach(header => {
        header.addEventListener('click', function () {
            const field = this.getAttribute('data-field');
            const icon = this.querySelector('.sort-icon');

            // Reset all other sort icons
            document.querySelectorAll('.sort-icon').forEach(i => {
                if (i !== icon) {
                    i.classList.add('d-none');
                    i.classList.remove('bi-sort-down', 'bi-sort-up');
                }
            });

            // Toggle sort direction if clicking the same column
            if (field === currentSortField) {
                currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                currentSortField = field;
                currentSortDirection = 'asc';
            }

            // Update sort icon
            icon.classList.remove('d-none');
            if (currentSortDirection === 'asc') {
                icon.classList.remove('bi-sort-down');
                icon.classList.add('bi-sort-up');
            } else {
                icon.classList.remove('bi-sort-up');
                icon.classList.add('bi-sort-down');
            }

            // Sort the vehicles
            currentVehicles = sortVehicles(currentVehicles, field, currentSortDirection);

            // Update just the table body with sorted data instead of redisplaying the entire table
            updateTableWithSortedData(currentVehicles);
        });
    });

    // Show the modal
    resultsModal.show();

    // Add event listener for analyze and delete buttons (using delegation)
    const tableBody = document.getElementById('vehicleResultsTableBody');
    if (tableBody) {
        // Remove previous listeners if they exist to avoid duplicates
        tableBody.removeEventListener('click', handleTableActions); // Use a single handler
        tableBody.addEventListener('click', handleTableActions); // Attach the new handler
    }

    // Attach listener for the filter button
    const applyFiltersBtn = document.getElementById('applyFiltersBtn');
    if (applyFiltersBtn) {
        // Remove potential existing listener
        applyFiltersBtn.removeEventListener('click', applyFiltersAndDisplay);
        applyFiltersBtn.addEventListener('click', applyFiltersAndDisplay);
    }

    // Initial display of all data
    updateTableWithSortedData(currentVehicles);
}

// Function to update just the table body with sorted/filtered data
function updateTableWithSortedData(vehicles) {
    const tableBody = document.getElementById('vehicleResultsTableBody'); // Use ID
    if (!tableBody) return;

    // Create new table body content
    let tableBodyHTML = '';

    vehicles.forEach((vehicle, index) => {
        tableBodyHTML += `
                    <tr>
                        <td><input type="checkbox" class="vehicle-checkbox" data-link="${vehicle.Link || ''}"></td>
                        <td>${vehicle.Year || ''}</td>
                        <td>${vehicle.Make || ''}</td>
                        <td>${vehicle.Model || ''}</td>
                        <td>${vehicle.Trim || ''}</td>
                        <td>${vehicle.Price || ''}</td>
                        <td>${vehicle.Kilometres || ''}</td>
                        <td>${vehicle.Drivetrain || ''}</td>
                        <td>
                            <a href="${vehicle.Link || '#'}" target="_blank" class="btn btn-sm btn-primary me-1" title="View on AutoTrader">
                                <i class="bi bi-box-arrow-up-right"></i>
                            </a>
                             <button class="btn btn-sm btn-info analyze-btn"
                                    data-make="${vehicle.Make || ''}"
                                    data-model="${vehicle.Model || ''}"
                                    data-year="${vehicle.Year || ''}"
                                    data-trim="${vehicle.Trim || ''}"
                                    data-price="${vehicle.Price || ''}"
                                    data-km="${vehicle.Kilometres || ''}"
                                    title="Analyze Reliability with AI">
                                <i class="bi bi-robot"></i> Analyze
                            </button>
                        </td>
                        <td> <!-- Added Delete Cell -->
                            <button class="btn btn-sm btn-danger delete-listing-btn" data-index="${index}" title="Delete Listing">
                                <i class="bi bi-trash"></i>
                            </button>
                        </td>
                    </tr>
                `;
    });

    // Update the table body
    tableBody.innerHTML = tableBodyHTML;

    // Reattach event listeners to checkboxes
    document.querySelectorAll('.vehicle-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', function () {
            // Update "select all" checkbox state based on individual checkboxes
            const allCheckboxes = document.querySelectorAll('.vehicle-checkbox');
            const selectAllCheckbox = document.getElementById('selectAllVehicles');
            selectAllCheckbox.checked = allCheckboxes.length > 0 &&
                Array.from(allCheckboxes).every(cb => cb.checked);
        });
    });
}

// Function to delete selected result
function deleteSelectedResult() {
    const resultId = document.getElementById('resultSelect').value;

    if (!resultId) {
        showNotification('Please select a result to delete', 'warning');
        return;
    }



    showLoading('Deleting result...');

    fetchWithAuth('/api/delete_result', {
        method: 'POST',
        body: JSON.stringify({ result_id: resultId }),
    })
        .then(data => {
            if (data.success) {
                showNotification('Result deleted successfully', 'success');
                loadSavedResults();
            } else {
                showNotification('Failed to delete result: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error deleting result:', error);
            showNotification('Failed to delete result. Please try again.', 'danger');
            hideLoading();
        });
}

// Function to open selected vehicle links
function openSelectedVehicleLinks() {
    const checkboxes = document.querySelectorAll('.vehicle-checkbox:checked');

    if (checkboxes.length === 0) {
        showNotification('Please select at least one vehicle', 'warning');
        return;
    }

    // Limit the number of links to open to prevent browser overload
    const maxLinksToOpen = 15;
    const selectedLinks = [];

    checkboxes.forEach(checkbox => {
        const link = checkbox.getAttribute('data-link');
        if (link) {
            selectedLinks.push(link);
        }
    });

    const linksToOpen = selectedLinks.slice(0, maxLinksToOpen);

    if (linksToOpen.length < selectedLinks.length) {
        showNotification(`Opening first ${maxLinksToOpen} of ${selectedLinks.length} selected links to prevent browser overload`, 'warning');
    }

    // Open links in new tabs
    linksToOpen.forEach(link => {
        window.open(link, '_blank');
    });
}

// Function to open links from CSV file
function openLinksFromCsv(filePath) {
    showLoading('Opening links...');

    fetchWithAuth('/api/open_links', {
        method: 'POST',
        body: JSON.stringify({ file_path: filePath }),
    })
        .then(data => {
            if (data.success) {
                showNotification('Links opened in browser', 'success');
            } else {
                showNotification('Failed to open links: ' + data.error, 'danger');
            }
            hideLoading();
        })
        .catch(error => {
            console.error('Error opening links:', error);
            showNotification('Failed to open links. Please try again.', 'danger');
            hideLoading();
        });
}

// Function to download a CSV file
function downloadCsvFile(filePath) {
    showLoading('Preparing CSV download...');

    // Create a hidden anchor element to trigger the download
    const downloadLink = document.createElement('a');
    downloadLink.href = `/api/download_csv?file_path=${encodeURIComponent(filePath)}`;
    downloadLink.download = filePath.split('/').pop() || 'results.csv';

    // Add auth token to the request
    firebase.auth().currentUser.getIdToken()
        .then(token => {
            // Create a fetch request with the token
            return fetch(downloadLink.href, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.blob();
        })
        .then(blob => {
            // Create a URL for the blob
            const url = URL.createObjectURL(blob);

            // Update the link href to the blob URL
            downloadLink.href = url;

            // Trigger the download
            document.body.appendChild(downloadLink);
            downloadLink.click();

            // Clean up
            document.body.removeChild(downloadLink);
            URL.revokeObjectURL(url);

            showNotification('CSV file downloaded successfully', 'success');
            hideLoading();
        })
        .catch(error => {
            console.error('Error downloading CSV:', error);
            showNotification('Failed to download CSV. Please try again.', 'danger');
            hideLoading();
        });
}

// Function to download a result as CSV
function downloadResultAsCsv(resultId) {
    showLoading('Preparing CSV download...');

    fetchWithAuth('/api/get_result', {
        method: 'POST',
        body: JSON.stringify({ result_id: resultId }),
    })
        .then(data => {
            if (data.success) {
                const result = data.result;
                const vehicles = result.results || [];
                const metadata = result.metadata || {};

                if (vehicles.length === 0) {
                    showNotification('No vehicles found in this result', 'warning');
                    hideLoading();
                    return;
                }

                // Get all possible headers from the vehicles
                const headers = Object.keys(vehicles.reduce((acc, vehicle) => {
                    Object.keys(vehicle).forEach(key => {
                        acc[key] = true;
                    });
                    return acc;
                }, {}));

                // Create CSV content
                let csvContent = headers.join(',') + '\n';

                // Add vehicle data
                vehicles.forEach(vehicle => {
                    const row = headers.map(header => {
                        const value = vehicle[header] || '';
                        // Escape commas and quotes in values
                        return `"${String(value).replace(/"/g, '""')}"`;
                    });
                    csvContent += row.join(',') + '\n';
                });

                // Create a Blob with the CSV content
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });

                // Create a filename based on metadata
                const make = metadata.make || 'unknown';
                const model = metadata.model || 'unknown';
                const timestamp = metadata.timestamp || new Date().toISOString().replace(/[:.]/g, '-');
                const filename = `${make}_${model}_${timestamp}.csv`;

                // Create a download link
                const url = URL.createObjectURL(blob);
                const downloadLink = document.createElement('a');
                downloadLink.href = url;
                downloadLink.download = filename;

                // Trigger the download
                document.body.appendChild(downloadLink);
                downloadLink.click();

                // Clean up
                document.body.removeChild(downloadLink);
                URL.revokeObjectURL(url);

                showNotification('CSV file downloaded successfully', 'success');
                hideLoading();
            } else {
                showNotification('Failed to get result data: ' + data.error, 'danger');
                hideLoading();
            }
        })
        .catch(error => {
            console.error('Error downloading result as CSV:', error);
            showNotification('Failed to download CSV. Please try again.', 'danger');
            hideLoading();
        });
}

// Fix for the Load Payload functionality
// Replace the setupLoadPayloadButton function with this improved version

function setupLoadPayloadButton() {
    console.log("Setting up load payload button...");

    // Get the button element
    const loadPayloadBtn = document.getElementById('loadPayloadBtn');

    if (!loadPayloadBtn) {
        console.error("Load payload button not found!");
        return;
    }

    // Remove existing listeners by cloning and replacing the element
    const newLoadBtn = loadPayloadBtn.cloneNode(true);
    loadPayloadBtn.parentNode.replaceChild(newLoadBtn, loadPayloadBtn);

    // Add new event listener
    newLoadBtn.addEventListener('click', function (e) {
        e.preventDefault();
        console.log("Load payload button clicked (new handler)");

        const payloadSelect = document.getElementById('payloadSelect');

        if (!payloadSelect.value) {
            showNotification('Please select a payload to load', 'warning');
            return;
        }

        // Get the selected option element
        const selectedOption = payloadSelect.options[payloadSelect.selectedIndex];

        // Get the document ID from the data-id attribute
        const docId = selectedOption.getAttribute('data-id');

        if (!docId) {
            showNotification('Could not find document ID for selected payload', 'warning');
            return;
        }

        console.log(`Loading payload with docId: ${docId}`);

        showLoading('Loading payload...');

        fetchWithAuth('/api/load_payload', {
            method: 'POST',
            body: JSON.stringify({
                file_path: "Firebase/" + docId, // Ensure path is properly prefixed
                doc_id: docId
            }),
        })
            .then(data => {
                console.log("Load payload response:", data);

                if (data.success) {
                    currentPayload = data.payload;
                    console.log("Loaded payload:", currentPayload); // Log loaded payload

                    // Call the display function only if element exists
                    if (document.getElementById('currentPayload')) {
                        updatePayloadDisplay();
                    }

                    // Update form with loaded payload data
                    populateFormWithPayload(data.payload);

                    showNotification('Payload loaded successfully', 'success');
                } else {
                    showNotification('Failed to load payload: ' + data.error, 'danger');
                }
                hideLoading();
            })
            .catch(error => {
                console.error('Error loading payload:', error);
                showNotification('Failed to load payload. Please try again.', 'danger');
                hideLoading();
            });
    });

    console.log("Load payload button event listener attached");
}

// --- User Settings Functions ---

function fetchUserSettings(updateDisplay = false) {
    console.log("Fetching user settings...");
    // Optionally show a subtle loading indicator for settings
    document.getElementById('tokenValue').textContent = '...';

    fetchWithAuth('/api/get_user_settings')
        .then(data => {
            if (data.success && data.settings) {
                currentUserSettings = data.settings;
                console.log("User settings fetched:", currentUserSettings);
                if (updateDisplay) {
                    updateTokenDisplay(currentUserSettings.search_tokens);
                }
            } else {
                console.error("Failed to fetch user settings:", data.error);
                showNotification("Could not load user settings.", "warning");
                // Keep default settings or previous settings
                if (updateDisplay) {
                    updateTokenDisplay(currentUserSettings.search_tokens); // Show last known value or 0
                }
            }
        })
        .catch(error => {
            console.error("Error fetching user settings:", error);
            if (updateDisplay) {
                updateTokenDisplay(currentUserSettings.search_tokens); // Show last known value or 0
            }
        });
}

function updateTokenDisplay(tokens) {
    console.log("Initial updateTokenDisplay call - tokens:", tokens, "| type:", typeof tokens); // <-- ADD THIS LINE FOR DEBUGGING
    const tokenValueEl = document.getElementById('tokenValue');
    if (tokenValueEl) {
        tokenValueEl.textContent = tokens;
    }
    // Store the numeric part of tokens, defaulting to 0 if not a number
    const numericTokens = parseFloat(tokens);
    currentUserSettings.search_tokens = isNaN(numericTokens) ? 0 : numericTokens;
}

function openUserSettingsModal() {
    const modal = new bootstrap.Modal(document.getElementById('userSettingsModal'));
    const loadingDiv = document.getElementById('userSettingsLoading');
    const formDiv = document.getElementById('userSettingsForm');
    const errorDiv = document.getElementById('userSettingsError');

    loadingDiv.style.display = 'block';
    formDiv.style.display = 'none';
    errorDiv.style.display = 'none';
    modal.show();

    // Fetch latest settings when opening
    fetchWithAuth('/api/get_user_settings')
        .then(data => {
            loadingDiv.style.display = 'none';
            if (data.success && data.settings) {
                currentUserSettings = data.settings;
                document.getElementById('userTokensInput').value = currentUserSettings.search_tokens;
                document.getElementById('canUseAiCheckbox').checked = currentUserSettings.can_use_ai;
                formDiv.style.display = 'block';
            } else {
                errorDiv.textContent = "Failed to load settings: " + (data.error || 'Unknown error');
                errorDiv.style.display = 'block';
            }
        })
        .catch(error => {
            loadingDiv.style.display = 'none';
            errorDiv.textContent = "Failed to load settings: " + error.message;
            errorDiv.style.display = 'block';
        });
}

function adjustTokens(amount) {
    const input = document.getElementById('userTokensInput');
    let currentValue = parseInt(input.value) || 0;
    currentValue += amount;
    if (currentValue < 0) currentValue = 0; // Prevent negative tokens
    input.value = currentValue;
}

function saveUserSettings() {
    const tokens = parseInt(document.getElementById('userTokensInput').value);
    const canUseAi = document.getElementById('canUseAiCheckbox').checked;
    const errorDiv = document.getElementById('userSettingsError');
    errorDiv.style.display = 'none'; // Hide previous errors

    if (isNaN(tokens) || tokens < 0) {
        errorDiv.textContent = "Invalid token value. Must be a non-negative number.";
        errorDiv.style.display = 'block';
        return;
    }

    showLoading("Saving settings...");

    fetchWithAuth('/api/update_user_settings', {
        method: 'POST',
        body: JSON.stringify({
            search_tokens: tokens,
            can_use_ai: canUseAi
        }),
    })
        .then(data => {
            hideLoading();
            if (data.success && data.settings) {
                currentUserSettings = data.settings;
                updateTokenDisplay(currentUserSettings.search_tokens); // Update navbar display
                showNotification("Settings saved successfully!", "success");
                const modal = bootstrap.Modal.getInstance(document.getElementById('userSettingsModal'));
                modal.hide();
            } else {
                errorDiv.textContent = "Failed to save settings: " + (data.error || 'Unknown error');
                errorDiv.style.display = 'block';
                showNotification("Failed to save settings.", "danger");
            }
        })
        .catch(error => {
            hideLoading();
            errorDiv.textContent = "Failed to save settings: " + error.message;
            errorDiv.style.display = 'block';
            showNotification("Failed to save settings.", "danger");
        });
}

// --- End User Settings Functions ---


// --- AI Analysis Functions ---

// Handle clicks on Analyze buttons
function handleAnalyzeClick(event) {
    if (event.target.closest('.analyze-btn')) {
        const button = event.target.closest('.analyze-btn');
        const carDetails = {
            Make: button.dataset.make || '',
            Model: button.dataset.model || '',
            Year: button.dataset.year || '',
            Trim: button.dataset.trim || '',
            Price: button.dataset.price || '', // Add Price
            Kilometres: button.dataset.km || '' // Add Kilometres
        };

        // Basic validation
        if (!carDetails.Make || !carDetails.Model || !carDetails.Year) {
            showNotification('Missing Make, Model, or Year for analysis.', 'warning');
            return;
        }

        // Show the AI modal and loading state
        const aiModal = new bootstrap.Modal(document.getElementById('aiAnalysisModal'));
        const loadingDiv = document.getElementById('aiAnalysisLoading');
        const contentDiv = document.getElementById('aiAnalysisContent');
        const errorDiv = document.getElementById('aiAnalysisError');

        loadingDiv.style.display = 'block';
        contentDiv.textContent = '';
        contentDiv.style.display = 'none';
        errorDiv.style.display = 'none';
        document.getElementById('aiAnalysisModalLabel').textContent = `AI Analysis: ${carDetails.Year} ${carDetails.Make} ${carDetails.Model}`;
        aiModal.show();

        // Call the backend API
        // Initialize showdown converter
        const converter = new showdown.Converter();

        // Use fetch directly to handle non-200 responses
        fetch('/api/analyze_car', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Add Authorization header if needed
            },
            body: JSON.stringify(carDetails),
        })
            .then(async response => {
                const data = await response.json(); // Attempt to parse JSON
                console.log("Analyze car response:", response.status, data);
                loadingDiv.style.display = 'none';

                if (response.ok && data.success) {
                    // Convert Markdown summary to HTML
                    const htmlSummary = converter.makeHtml(data.summary || '');
                    contentDiv.innerHTML = htmlSummary; // Use innerHTML to render formatted content
                    contentDiv.innerHTML = htmlSummary; // Use innerHTML to render formatted content
                    contentDiv.style.display = 'block';
                } else {
                    // General error handling for non-OK responses
                    let errorMessage = data.error || `Analysis failed with status: ${response.status}`;
                    errorDiv.textContent = 'Analysis failed: ' + errorMessage;
                    errorDiv.style.display = 'block';
                }
            })
            .catch(error => {
                loadingDiv.style.display = 'none';
                errorDiv.textContent = 'Analysis request failed: ' + error.message;
                errorDiv.style.display = 'block';
                console.error('Error calling analyze API:', error);
            });
    }
}
// --- End AI Analysis Functions ---


// --- Task Status Checking Function ---
function checkTaskStatus() {
    if (!currentFetchTaskId) {
        console.log("No active task ID to check.");
        if (taskCheckInterval) clearInterval(taskCheckInterval);
        taskCheckInterval = null;
        return;
    }

    console.log(`Checking status for task: ${currentFetchTaskId}`);
    fetch(`/api/tasks/status/${currentFetchTaskId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Task status response:", data);
            const progressContainer = document.getElementById('fetchProgressContainer');
            const progressBar = document.getElementById('fetchProgressBar');
            const progressStatus = document.getElementById('fetchProgressStatus');
            const fetchDataBtn = document.getElementById('fetchDataBtn'); // Get button to re-enable

            switch (data.state) {
                case 'PENDING':
                    progressStatus.textContent = 'Task is pending...';
                    break;
                case 'STARTED':
                    progressStatus.textContent = 'Task started... Waiting for progress...';
                    break;
                case 'PROGRESS':
                    const progress = data.progress || 0;
                    const total = data.total || 100;
                    const step = data.step || 'Processing...';
                    const percentage = total > 0 ? Math.round((progress / total) * 100) : 0;

                    progressStatus.textContent = `${step} (${percentage}%)`;
                    progressBar.style.width = `${percentage}%`;
                    progressBar.textContent = `${percentage}%`;
                    progressBar.setAttribute('aria-valuenow', percentage);
                    break;
                case 'SUCCESS':
                    clearInterval(taskCheckInterval);
                    taskCheckInterval = null;
                    currentFetchTaskId = null;
                    progressContainer.style.display = 'none'; // Hide progress bar
                    fetchDataBtn.disabled = false; // Re-enable button

                    const result = data.result; // The dictionary returned by the Celery task
                    if (result && result.status === 'Complete') {
                        resultsFilePath = result.file_path;
                        currentResultId = result.doc_id || null;

                        // Update results info
                        document.getElementById('resultsInfo').innerHTML = `
                            <div class="alert alert-success">
                                <p><strong><i class="bi bi-check-circle"></i> Found:</strong> ${result.result_count} listings</p>
                                <p><strong><i class="bi bi-file-earmark-text"></i> Saved to:</strong> ${result.file_path || 'Firebase Only'}</p>
                                <p><strong><i class="bi bi-coin"></i> Tokens Charged:</strong> ${result.tokens_charged}</p>
                                <p><strong><i class="bi bi-wallet2"></i> Tokens Remaining:</strong> ${result.tokens_remaining}</p>
                            </div>`;
                        updateTokenDisplay(result.tokens_remaining); // Update navbar display

                        // Enable/disable buttons
                        document.getElementById('openLinksBtn').disabled = !result.file_path;
                        document.getElementById('downloadCsvBtn').disabled = !result.file_path;

                        showNotification(`Search complete! Found ${result.result_count} listings. Cost: ${result.tokens_charged} tokens.`, 'success');

                        // Refresh the results list
                        setTimeout(() => {
                            refreshResultsList();
                        }, 1000); // Short delay after success
                    } else {
                        // Handle cases where task succeeded but returned unexpected data
                        document.getElementById('resultsInfo').innerHTML = `
                            <div class="alert alert-warning">
                                <p><i class="bi bi-question-circle"></i> Task completed but returned unexpected data.</p>
                            </div>`;
                        showNotification('Task finished with unexpected result.', 'warning');
                    }
                    break;
                case 'FAILURE':
                    clearInterval(taskCheckInterval);
                    taskCheckInterval = null;
                    currentFetchTaskId = null;
                    progressContainer.style.display = 'none'; // Hide progress bar
                    fetchDataBtn.disabled = false; // Re-enable button

                    const errorMsg = data.error || 'Unknown error occurred during task execution.';
                    document.getElementById('resultsInfo').innerHTML = `
                        <div class="alert alert-danger">
                            <p><i class="bi bi-exclamation-triangle"></i> Search Failed: ${errorMsg}</p>
                        </div>`;
                    showNotification(`Search failed: ${errorMsg}`, 'danger');
                    break;
                case 'RETRY':
                    progressStatus.textContent = 'Task is retrying...';
                    break;
                default:
                    progressStatus.textContent = `Task state: ${data.state}`;
            }
        })
        .catch(error => {
            console.error('Error checking task status:', error);
            showNotification('Error checking search status. Stopping monitor.', 'danger');
            clearInterval(taskCheckInterval);
            taskCheckInterval = null;
            currentFetchTaskId = null;
            document.getElementById('fetchProgressContainer').style.display = 'none'; // Hide progress bar
            document.getElementById('fetchDataBtn').disabled = false; // Re-enable button
            // Optionally show error in results area
             document.getElementById('resultsInfo').innerHTML = `
                <div class="alert alert-danger">
                    <p><i class="bi bi-exclamation-triangle"></i> Error checking task status: ${error.message}</p>
                </div>`;
        });
}
// --- End Task Status Checking ---
