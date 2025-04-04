// Firebase configuration - IMPORTANT: Ensure this is present and correct
const firebaseConfig = {
    apiKey: "AIzaSyC5XgDpWOkgXHHJs28DyQvC6JtTB1BpUWw", // Replace with your actual API key if different
    authDomain: "autoscraper-32bb0.firebaseapp.com",
    projectId: "autoscraper-32bb0",
    storageBucket: "autoscraper-32bb0.firebasestorage.app",
    messagingSenderId: "694443728322",
    appId: "1:694443728322:web:63770ddc18446c0a74ca5b",
    measurementId: "G-0NVZC6JPBN"
};

// Initialize Firebase - IMPORTANT: Must be called before using Firebase services
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
} else {
    firebase.app(); // if already initialized, use that one
}


// --- Firebase Auth State Handling ---
export let firebaseUser = null; // Export for other modules
export let authReady = false;   // Export if needed elsewhere, maybe not
let authStatePromiseResolver = null;
export const authStatePromise = new Promise(resolve => { // Export the promise
    authStatePromiseResolver = resolve;
});

// Import necessary functions if they are moved to other modules
// Example: import { loadSavedPayloads, fetchUserSettings } from './api.js';
// Example: import { updateTokenDisplay } from './ui.js';
// For now, assume they might be globally available via window scope or defined later in main.js

firebase.auth().onAuthStateChanged(user => {
    console.log("Firebase auth state changed. User:", user ? user.uid : 'null');
    firebaseUser = user; // Update the exported user variable
    authReady = true;    // Mark auth as ready

    if (user) {
        // User is signed in, load data that requires authentication
        console.log("User is signed in, loading authenticated data...");
        // These functions need to be imported or available globally
        window.loadSavedPayloads?.();
        window.fetchUserSettings?.(true);
    } else {
        // User is signed out
        console.log("User is signed out.");
        window.updateTokenDisplay?.(0);
        const payloadSelect = document.getElementById('payloadSelect');
        if (payloadSelect) payloadSelect.innerHTML = '<option value="">Login to load payloads</option>';
    }

    if (authStatePromiseResolver) {
        authStatePromiseResolver();
        authStatePromiseResolver = null;
    }
});
// --- End Firebase Auth State Handling ---
