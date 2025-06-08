document.addEventListener('DOMContentLoaded', () => {
    // DOM Element Selectors
    const locationDisplay = document.querySelector('.location-display');
    const weatherIcon = document.querySelector('.weather-icon');
    const temperatureDisplay = document.querySelector('.temperature');
    const weatherDescriptionDisplay = document.querySelector('.weather-description');
    const humidityValue = document.querySelector('.humidity-value');
    const windSpeedValue = document.querySelector('.wind-speed-value');
    const feelsLikeValue = document.querySelector('.feels-like-value');
    const loadingSpinner = document.querySelector('.loading-spinner');
    const errorMessageElement = document.querySelector('.error-message');
    const errorMessageText = errorMessageElement ? errorMessageElement.querySelector('p') : null;
    const mainWeatherContent = document.querySelector('.main-weather-display');
    const additionalDetailsContent = document.querySelector('.additional-details');

    // --- UI Helper Functions ---
    function showLoading(isLoading) {
        if (isLoading) {
            if (loadingSpinner) loadingSpinner.style.display = 'block';
            if (errorMessageElement) errorMessageElement.style.display = 'none';
            if (mainWeatherContent) mainWeatherContent.style.display = 'none';
            if (additionalDetailsContent) additionalDetailsContent.style.display = 'none';
            if (locationDisplay) locationDisplay.style.display = 'none';
        } else {
            if (loadingSpinner) loadingSpinner.style.display = 'none';
            if (mainWeatherContent) mainWeatherContent.style.display = 'flex';
            if (additionalDetailsContent) additionalDetailsContent.style.display = 'block';
            if (locationDisplay) locationDisplay.style.display = 'block';
        }
    }

    function displayError(message) {
        if (errorMessageElement && errorMessageText) {
            errorMessageText.textContent = message;
            errorMessageElement.style.display = 'block';
        }
        if (mainWeatherContent) mainWeatherContent.style.display = 'none';
        if (additionalDetailsContent) additionalDetailsContent.style.display = 'none';
        if (locationDisplay) locationDisplay.style.display = 'none';
        if (loadingSpinner) loadingSpinner.style.display = 'none';
    }

    function clearError() {
        if (errorMessageElement) {
            errorMessageElement.style.display = 'none';
        }
    }

    // --- Data Update Function ---
    function updateWeatherUI(weatherData, latitude, longitude) {
        // Destructure data for easier access, with fallbacks for safety
        const conditions = weatherData.current_conditions || {};
        const sources = weatherData.data_sources || [];

        // Location: Use lat/lon for now
        if (locationDisplay) {
            if (latitude !== undefined && longitude !== undefined) {
                locationDisplay.textContent = `Weather for Lat: ${latitude.toFixed(2)}, Lon: ${longitude.toFixed(2)}`;
            } else {
                locationDisplay.textContent = "Current Location Weather";
            }
        }

        // Temperature
        if (temperatureDisplay) {
            temperatureDisplay.textContent = conditions.temperature_celsius !== null && conditions.temperature_celsius !== undefined
                ? `${Math.round(conditions.temperature_celsius)}°C`
                : '--°C';
        }

        // Weather Description
        if (weatherDescriptionDisplay) {
            weatherDescriptionDisplay.textContent = conditions.condition || 'Not available';
        }

        // Humidity
        if (humidityValue) {
            humidityValue.textContent = conditions.humidity_percent !== null && conditions.humidity_percent !== undefined
                ? `${Math.round(conditions.humidity_percent)}%`
                : '--%';
        }

        // Wind Speed
        if (windSpeedValue) {
            windSpeedValue.textContent = conditions.wind_speed_kph !== null && conditions.wind_speed_kph !== undefined
                ? `${Math.round(conditions.wind_speed_kph)} kph`
                : '-- kph';
        }

        // Feels Like (placeholder, as it's not in current backend response)
        if (feelsLikeValue) {
            feelsLikeValue.textContent = '--°C';
        }

        // Weather Icon (placeholder, for future implementation)
        if (weatherIcon) {
            // weatherIcon.src = mapConditionToIcon(conditions.condition); // Example future call
            weatherIcon.alt = conditions.condition || "Weather icon";
        }

        console.log("Data sourced from:", sources.join(', '));

        showLoading(false); // Hide spinner and show content
    }

    // --- API Call Function ---
    async function fetchWeatherData(url, latitude, longitude) {
        console.log("Fetching weather data from:", url);

        try {
            const response = await fetch(url);
            if (!response.ok) {
                let errorMsg = `Failed to fetch weather data. Status: ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMsg += ` - ${errorData.error || response.statusText}`;
                } catch (e) {
                    errorMsg += ` - ${response.statusText}`;
                }
                throw new Error(errorMsg);
            }
            const data = await response.json();
            if (Object.keys(data).length === 0 && data.constructor === Object) {
                throw new Error("Received empty weather data from server.");
            }
            updateWeatherUI(data, latitude, longitude);
            clearError();
        } catch (error) {
            console.error("Error fetching weather data:", error);
            displayError(error.message || "Could not fetch weather data. Check console for details.");
        }
    }

    // --- Geolocation Logic ---
    function getGeoLocation() {
        showLoading(true);
        clearError();

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const latitude = position.coords.latitude;
                    const longitude = position.coords.longitude;
                    // Use config.apiBaseUrl to construct the full API URL
                    const apiUrl = `${config.apiBaseUrl}/api/weather?lat=${latitude}&lon=${longitude}`;
                    fetchWeatherData(apiUrl, latitude, longitude); // Pass full URL and coords
                },
                (error) => {
                    console.error('Geolocation error:', error);
                    displayError(`Geolocation Error: ${error.message}`);
                }
            );
        } else {
            console.error("Geolocation is not supported by this browser.");
            displayError("Geolocation is not supported by this browser.");
        }
    }

    // --- Initial Call ---
    getGeoLocation();
});
