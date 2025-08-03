// Sample data for alerts
const alerts = [
    { type: "Pothole", location: "11.450936978534006,77.77001929243333", time: "12:34 PM", severity: "Critical", status: "Active" },
    { type: "Fallen Tree", location: "11.453881241352997,77.78529715430307", time: "1:00 PM", severity: "Moderate", status: "Active" }
];

// Function to display alerts
function displayAlerts() {
    const alertsContainer = document.getElementById('alerts');
    alertsContainer.innerHTML = ''; // Clear previous alerts
    alerts.forEach((alert, index) => {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert';
        alertDiv.innerHTML = `
            <p><strong>Hazard Type:</strong> ${alert.type}</p>
            <p><strong>Location:</strong> ${alert.location}</p>
            <p><strong>Time Detected:</strong> ${alert.time}</p>
            <p><strong>Severity:</strong> ${alert.severity}</p>
            <button aria-label="View ${alert.type} on Map" onclick="viewOnMap('${alert.location}')">View on Map</button>
            <button aria-label="Mark ${alert.type} as Seen" onclick="markAsSeen(${index})">Mark as Seen</button>
        `;
        alertsContainer.appendChild(alertDiv);
    });
}

// Function to redirect to the map page with coordinates
function viewOnMap(location) {
    const [lat, lng] = location.split(',');
    const locationAccessGranted = localStorage.getItem('locationAccessGranted');

    if (!locationAccessGranted) {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                () => {
                    localStorage.setItem('locationAccessGranted', 'true');
                    window.location.href = `index.html?lat=${lat}&lng=${lng}`;
                },
                (error) => {
                    let errorMessage = "Unable to access your location. Please allow location access.";
                    if (error.code === error.PERMISSION_DENIED) {
                        errorMessage = "Location access denied. Please enable it in your browser settings.";
                    } else if (error.code === error.POSITION_UNAVAILABLE) {
                        errorMessage = "Location information is unavailable.";
                    } else if (error.code === error.TIMEOUT) {
                        errorMessage = "The request to get your location timed out.";
                    }
                    alert(errorMessage);
                },
                { enableHighAccuracy: true }
            );
        } else {
            alert("Geolocation is not supported by this browser.");
        }
    } else {
        window.location.href = `index.html?lat=${lat}&lng=${lng}`;
    }
}

// Function to mark an alert as seen
function markAsSeen(index) {
    alerts[index].status = "Seen"; // Update the status
    alert('Alert marked as seen!');
    displayAlerts(); // Refresh alerts display
}

// Call the function to display alerts
displayAlerts();

document.addEventListener("DOMContentLoaded", function() {
    const menuToggle = document.querySelector('.menu-toggle');
    const navMenu = document.querySelector('nav ul');

    menuToggle.addEventListener('click', function() {
        navMenu.classList.toggle('show'); // Toggle the menu visibility
        const expanded = navMenu.classList.contains('show');
        menuToggle.setAttribute('aria-expanded', expanded); // Update aria-expanded attribute
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(event) {
        if (!navMenu.contains(event.target) && !menuToggle.contains(event.target)) {
            navMenu.classList.remove('show');
            menuToggle.setAttribute('aria-expanded', 'false');
        }
    });
});

function toggleDarkMode() {
    const body = document.body;
    if (body.dataset.theme === 'dark') {
        body.dataset.theme = 'light';
    } else {
        body.dataset.theme = 'dark';
    }
}
