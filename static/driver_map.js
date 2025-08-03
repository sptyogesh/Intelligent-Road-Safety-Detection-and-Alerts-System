let map;
let userMarker; // Marker for user's location

// Function to get URL parameters (lat/lng)
function getUrlParameters() {
    const params = new URLSearchParams(window.location.search);
    return {
        lat: params.get('lat'),
        lng: params.get('lng')
    };
}

// Initialize Google Map
function initMap() {
    const params = getUrlParameters();
    const defaultLocation = {
        lat: params.lat ? parseFloat(params.lat) : 34.0522,
        lng: params.lng ? parseFloat(params.lng) : -118.2437
    };
    const radiusInMeters = 50;

    // Create the map centered on the default location
    map = new google.maps.Map(document.getElementById("map"), {
        zoom: 15,
        center: defaultLocation,
        mapTypeId: "roadmap"
    });

    drawCircle(defaultLocation, radiusInMeters, "#FF0000");

    // Draw alerts from the global alerts array (defined in script.js)
    drawAlertsOnMap(alerts);

    // Initialize user location tracking
    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(updateLocation, handleError, {
            enableHighAccuracy: true
        });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}

// Function to update user's location on the map
function updateLocation(position) {
    const userLocation = {
        lat: position.coords.latitude,
        lng: position.coords.longitude
    };

    if (!userMarker) {
        userMarker = new google.maps.Marker({
            position: userLocation,
            map: map,
            title: "Your Location"
        });
    } else {
        userMarker.setPosition(userLocation);
    }

    map.setCenter(userLocation);
}

// Function to handle geolocation errors
function handleError(error) {
    switch (error.code) {
        case error.PERMISSION_DENIED:
            alert("User denied the request for Geolocation. Please enable location access in your browser settings.");
            break;
        case error.POSITION_UNAVAILABLE:
            alert("Location information is unavailable. Ensure your device's location services are turned on.");
            break;
        case error.TIMEOUT:
            alert("The request to get user location timed out. Please try again.");
            break;
        case error.UNKNOWN_ERROR:
            alert("An unknown error occurred while trying to retrieve your location.");
            break;
    }
}

// Function to draw a circle on the map
function drawCircle(center, radius, color) {
    new google.maps.Circle({
        strokeColor: color,
        strokeOpacity: 0.8,
        strokeWeight: 2,
        fillColor: color,
        fillOpacity: 0.35,
        map: map,
        center: center,
        radius: radius
    });
}

// Function to draw alerts on the map
function drawAlertsOnMap(alerts) {
    alerts.forEach(alert => {
        const [lat, lng] = alert.location.split(',').map(Number);
        const alertLocation = { lat, lng };
        drawCircle(alertLocation, 50, "#FF0000");
    });
}

// Initialize the map when the page loads
window.onload = initMap;
