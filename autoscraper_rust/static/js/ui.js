// --- UI Helper Functions ---

export function showNotification(message, type = 'primary') {
    const notification = document.getElementById('notification');
    if (!notification) return;
    // Ensure correct removal of previous classes
    notification.className = 'toast align-items-center text-white border-0'; // Reset classes
    notification.classList.add(`bg-${type}`);
    document.getElementById('notification-content').textContent = message;
    // Make sure Bootstrap's Toast is initialized (might need to do this once elsewhere)
    const toast = bootstrap.Toast.getOrCreateInstance(notification, { delay: 3000 });
    toast.show();
}

export function showLoading(message = 'Processing...') {
    // Basic console log fallback
    console.log('Loading:', message);
    // TODO: Implement a proper visual loading indicator if desired
    // Example: document.getElementById('loadingIndicator').style.display = 'block';
}

export function hideLoading() {
    console.log('Loading complete.');
    // TODO: Hide visual loading indicator
    // Example: document.getElementById('loadingIndicator').style.display = 'none';
}

export function updateExclusionsList(exclusions) { // Pass exclusions as argument
    const exclusionsListEl = document.getElementById('exclusionsList');
    if (!exclusionsListEl) return;
    exclusionsListEl.innerHTML = '';
    exclusions.forEach((exclusion, index) => {
        const badge = document.createElement('span');
        badge.classList.add('badge', 'bg-secondary', 'keyword-badge');
        badge.innerHTML = `${exclusion} <i class="bi bi-x-circle" data-index="${index}" style="cursor: pointer;"></i>`;
        // Note: The click listener needs access to the exclusions array and the function itself.
        // This might require adjustments depending on how state is managed later.
        // For now, we assume it will be handled by the calling module.
        // badge.querySelector('.bi-x-circle').addEventListener('click', function () {
        //     exclusions.splice(index, 1);
        //     updateExclusionsList(exclusions); // Recursive call might be problematic, better handled by caller
        // });
        exclusionsListEl.appendChild(badge);
    });
}

// Add other UI-related functions here later (e.g., displayResults, renderTableBody, updateTokenDisplay)
