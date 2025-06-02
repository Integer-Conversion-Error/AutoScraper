# Selenium User Tests for AutoScraper Web Interface

This document outlines potential Selenium user tests for the AutoScraper web interface, categorized by functionality.

**I. Initial Page Load & Basic UI Verification**

1.  **Page Title:**
    *   Verify that the page title is "AutoScraper Web Interface".
2.  **Main Sections Presence:**
    *   Verify that the "Search Parameters" card is visible.
    *   Verify that the "Payload Management" card is visible.
    *   Verify that the "Saved Results Management" card is visible.
    *   Verify that the "Current Search Results" card is visible.
3.  **Navbar Elements:**
    *   Verify the "AutoScraper Web" brand/logo is present.
    *   Verify the user dropdown (displaying username) is present.
    *   Verify the "Tokens: ..." display is present in the navbar.
4.  **Flashed Messages:**
    *   If applicable, test scenarios where flashed messages (e.g., after login) are displayed and can be dismissed.

**II. Search Form Functionality (within "Search Parameters" Accordion)**

*   **Accordion Behavior:**
    1.  Test that each accordion section (Vehicle Selection, Location, Year Range, etc.) can be expanded and collapsed by clicking its header.
    2.  Verify that "Vehicle Selection" is expanded by default.

*   **A. Vehicle Selection Section:**
    1.  **Make Dropdown:**
        *   Verify the "Make" dropdown (`#makeSelect`) populates with options on page load.
        *   Test selecting a make.
    2.  **"Show All Makes" Button:**
        *   Click "Show All Makes" (`#showAllMakes`) and verify the "Make" dropdown updates with a potentially larger list.
    3.  **Model Dropdown:**
        *   After selecting a Make, verify the "Model" dropdown (`#modelSelect`) populates with relevant models.
        *   Test selecting a model.
    4.  **Trim Dropdown:**
        *   After selecting a Model, verify the "Trim" dropdown (`#trimSelect`) populates with relevant trims.
        *   Test selecting a trim.
    5.  **Color Dropdown:**
        *   After selecting a Model (and optionally Trim), verify the "Color" dropdown (`#colorSelect`) populates.
        *   Test selecting a color.
    6.  **Condition Checkboxes:**
        *   Test checking/unchecking "New" (`#isNew`), "Used" (`#isUsed`), "Photos" (`#withPhotos`), and "Damaged" (`#isDamaged`).
    7.  **Drivetrain & Transmission:**
        *   Test selecting options from "Drivetrain" (`#drivetrainSelect`) and "Transmission" (`#transmissionSelect`) dropdowns.
    8.  **Vehicle Spec Inputs:**
        *   Test entering values into "Body Type" (`#bodyTypeInput`), "Doors" (`#numDoorsInput`), and "Seats" (`#seatingCapacityInput`).

*   **B. Location Section:**
    1.  **Address Input:** Test entering text into the "Address" field (`#address`).
    2.  **Distance Input:** Test entering a number into the "Distance" field (`#proximity`).

*   **C. Year Range Section:**
    1.  **Min/Max Year Inputs:** Test entering numbers into "Minimum Year" (`#yearMin`) and "Maximum Year" (`#yearMax`).
    2.  **Validation:**
        *   Enter Min Year > Max Year and verify a notification/error appears when attempting to create a payload or fetch data.

*   **D. Price Range Section:**
    1.  **Min/Max Price Inputs:** Test entering numbers into "Minimum Price" (`#priceMin`) and "Maximum Price" (`#priceMax`).
    2.  **Validation:**
        *   Enter Min Price > Max Price and verify a notification/error appears.

*   **E. Mileage Section:**
    1.  **Min/Max KMs Inputs:** Test entering numbers into "Minimum KMs" (`#odometerMin`) and "Maximum KMs" (`#odometerMax`).
    2.  **Validation:**
        *   Enter Min KMs > Max KMs and verify a notification/error appears.

*   **F. Keyword Filtering Section:**
    1.  **Exclusion Keywords:**
        *   Enter a keyword in `#exclusionKeyword` and click "Add" (`#addExclusionBtn`). Verify the keyword appears in `#exclusionsList`.
        *   Test adding multiple exclusion keywords.
        *   Test removing an exclusion keyword by clicking the 'x' icon on its badge.
    2.  **Inclusion String:** Test entering text into "Required Inclusion String" (`#inclusion`).

**III. Search Action Buttons (below accordion)**

1.  **"Create Payload" Button (`#createPayloadBtn`):**
    *   Fill in mandatory search form fields (e.g., Make).
    *   Click "Create Payload".
    *   Verify a success notification appears.
    *   (Optional) Verify `currentPayload` variable in JS is updated (harder with Selenium, focus on UI feedback).
2.  **"Fetch Data" Button (`#fetchDataBtn`):**
    *   **Without Payload:** Click "Fetch Data" without creating a payload. Verify a warning notification appears.
    *   **With Payload:**
        *   Create a valid payload.
        *   Click "Fetch Data".
        *   Verify the button becomes disabled.
        *   Verify the progress bar container (`#fetchProgressContainer`) becomes visible.
        *   Verify the progress status text (`#fetchProgressStatus`) updates.
        *   (Mock backend for predictable results) Verify that after completion, the "Current Search Results" section (`#resultsInfo`) updates with success/failure message and result count.
        *   Verify "Open Links" and "Download CSV" buttons in "Current Search Results" enable/disable appropriately based on results.
        *   Verify token count in navbar updates if tokens are consumed.

**IV. Payload Management Section**

1.  **Load Saved Payload:**
    *   Ensure some payloads are pre-saved (or save one first).
    *   Select a payload from `#payloadSelect`.
    *   Click "Load Selected" (`#loadPayloadBtn`).
    *   Verify the search form populates with the selected payload's data.
    *   Verify Make, Model, Trim, and Color dropdowns load and select correctly.
    *   Verify a success notification.
2.  **Save Current Payload:**
    *   Create or load a payload into the form.
    *   Click "Save Current" (`#savePayloadBtn`).
    *   Verify the "Name Your Payload" modal (`#namePayloadModal`) appears.
    *   Enter a name in `#payloadName` and click "Save" (`#saveNamedPayloadBtn`).
    *   Verify a success notification.
    *   Verify the `#payloadSelect` dropdown updates to include the newly saved payload.
3.  **Rename Payload:**
    *   Select a payload from `#payloadSelect`.
    *   Click "Rename" (`#renamePayloadBtn`).
    *   Verify the "Rename Item" modal (`#renameModal`) appears with "Rename Payload" title.
    *   Enter a new name in `#newItemName` and click "Save" (`#saveRenameBtn`).
    *   Verify a success notification.
    *   Verify the `#payloadSelect` dropdown updates with the new name.
4.  **Delete Payload:**
    *   Select a payload from `#payloadSelect`.
    *   Click "Delete" (`#deletePayloadBtn`).
    *   (If there's a confirmation dialog, handle it).
    *   Verify a success notification.
    *   Verify the payload is removed from `#payloadSelect`.

**V. Saved Results Management Section**

1.  **Refresh Results List:**
    *   Click "Refresh" (`#refreshResultsBtn`).
    *   Verify a notification appears.
    *   Verify the `#resultSelect` dropdown updates if new results are available (mock backend to add a new result).
2.  **View Saved Result:**
    *   Ensure some results are pre-saved (or fetch data first).
    *   Select a result from `#resultSelect`.
    *   Click "View Selected" (`#viewResultBtn`).
    *   Verify the "Vehicle Results" modal (`#resultsModal`) appears and is populated with data.
3.  **Rename Saved Result:**
    *   Select a result from `#resultSelect`.
    *   Click "Rename" (`#renameResultBtn`).
    *   Verify the "Rename Item" modal (`#renameModal`) appears with "Rename Result" title.
    *   Enter a new name and click "Save".
    *   Verify a success notification and the `#resultSelect` updates.
4.  **Delete Saved Result:**
    *   Select a result from `#resultSelect`.
    *   Click "Delete Selected" (`#deleteResultBtn`).
    *   (If confirmation, handle it).
    *   Verify a success notification and the result is removed from `#resultSelect`.

**VI. "Current Search Results" Card (after fetching data)**

1.  **"Open Links in Browser" Button (`#openLinksBtn`):**
    *   After a successful data fetch that yields results with a file path.
    *   Verify the button is enabled.
    *   Click it and verify a success notification (actual link opening is hard to assert reliably in Selenium alone, focus on the call being made).
2.  **"Download CSV" Button (`#downloadCsvBtn`):**
    *   After a successful data fetch that yields results with a file path.
    *   Verify the button is enabled.
    *   Click it. Selenium can be configured to check if a download was initiated. Verify success notification.

**VII. "Vehicle Results" Modal Functionality (`#resultsModal`)**

1.  **Modal Opening:** Verified in "View Saved Result".
2.  **"Open Selected Links" Button (`#openSelectedLinksBtn`):**
    *   Check some vehicle checkboxes (`.vehicle-checkbox`).
    *   Click the button. Verify a notification. (Limit to a few links for testing).
3.  **"Download CSV" Button (`#downloadSelectedResultBtn`):**
    *   Click the button (no selection needed for this one as it downloads the currently viewed result).
    *   Verify download initiation and success notification.
4.  **Filtering Controls:**
    *   For each filter (Make, Model, Trim, Year, Max Price, Max KMs, Drivetrain):
        *   Select/enter a filter value.
        *   Click "Apply Filters" (`#applyFiltersBtn`).
        *   Verify the table updates to show only matching results.
        *   Verify the notification about filtered results count.
5.  **Sorting Table Columns:**
    *   For each sortable column (Year, Make, Model, Trim, Price, Kilometers, Drivetrain):
        *   Click the column header. Verify sort icon appears/changes (up/down). Verify table rows reorder.
        *   Click again. Verify sort direction reverses and icon changes.
6.  **Row Actions:**
    *   **View Link:** Click the link icon in a row. Verify it attempts to open a new tab (Selenium can check `window.handles`).
    *   **AI Analyze Button (`.analyze-btn`):**
        *   Click the "Analyze" button in a row.
        *   Verify the "AI Reliability Analysis" modal (`#aiAnalysisModal`) opens.
        *   Verify loading state, then content or error message.
    *   **Delete Listing Button (`.delete-listing-btn`):**
        *   Click the trash icon in a row.
        *   Confirm deletion if prompted.
        *   Verify the row is removed from the table.
        *   Verify a notification about deletion.
7.  **"Select All" Checkbox (`#selectAllVehicles`):**
    *   Click it. Verify all `.vehicle-checkbox` in the current view become checked.
    *   Uncheck it. Verify all become unchecked.
    *   Check/uncheck individual checkboxes and verify "Select All" state updates correctly.

**VIII. Other Modals**

1.  **AI Analysis Modal (`#aiAnalysisModal`):**
    *   Covered by row actions in Results Modal.
    *   Test closing the modal.
2.  **Rename Modal (`#renameModal`):**
    *   Covered by Payload and Result rename tests.
    *   Test "Cancel" button.
3.  **User Settings Modal (`#userSettingsModal`):**
    *   Click "Settings" in user dropdown. Verify modal opens.
    *   Verify current settings (tokens, AI permission) are loaded into the form.
    *   Test "Increase/Decrease Tokens" buttons (`#increaseTokensBtn`, `#decreaseTokensBtn`).
    *   Test checking/unchecking "Allow AI Analysis" (`#canUseAiCheckbox`).
    *   Click "Save Settings" (`#saveUserSettingsBtn`). Verify success notification, modal closes, and token count in navbar updates.
    *   Test "Cancel" button.
4.  **Name Payload Modal (`#namePayloadModal`):**
    *   Covered by "Save Current Payload".
    *   Test "Cancel" button.

**IX. Navigation and User Profile (Navbar)**

1.  **Settings Button:** Covered by User Settings Modal tests.
2.  **Logout Link (`#logoutLink`):**
    *   Click it. Verify the user is redirected to the logout URL (or login page).
3.  **Token Count Display (`#tokenValue`):**
    *   Verify it updates after actions that should change token count (e.g., fetching data, saving settings with new token amount).

**X. Notifications (`#notification`)**

*   Throughout all tests, observe that appropriate notifications (success, warning, danger, info) appear for different actions and can be dismissed or auto-hide.

**Notes:**

*   For tests involving backend interactions (fetching data, saving, loading), consider mocking backend responses in your Selenium test environment for consistent and predictable test runs.
*   Prioritize tests based on the most critical functionalities.
*   This list can be expanded as new features are added or existing ones are modified.
