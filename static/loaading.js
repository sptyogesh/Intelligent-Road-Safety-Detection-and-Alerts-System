// Function to show loading spinner
function showLoading() {
    document.getElementById('loading-overlay').style.visibility = 'visible';
}

// Function to hide loading spinner
function hideLoading() {
    document.getElementById('loading-overlay').style.visibility = 'hidden';
}

// Show the loading spinner on page load, hide on page fully loaded
document.addEventListener('DOMContentLoaded', function() {
    hideLoading();  // Hide initially if no delay
});

// Attach to link clicks
document.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', function() {
        showLoading();
    });
});