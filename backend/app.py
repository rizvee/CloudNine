from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import requests
from flask_cors import CORS # New import

load_dotenv()

app = Flask(__name__)
CORS(app) # Initialize CORS

@app.route('/')
def home():
    return jsonify({'status': 'ok'})

@app.route('/api/weather')
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    # Initial check for lat/lon presence
    if not lat or not lon:
        return jsonify({"error": "Latitude and longitude query parameters are required."}), 400

    openweathermap_api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
    weatherapi_com_api_key = os.environ.get('WEATHERAPI_COM_API_KEY')
    tomorrow_io_api_key = os.environ.get('TOMORROW_IO_API_KEY')

    api_keys_status = {
        "OPENWEATHERMAP_API_KEY": "Loaded" if openweathermap_api_key else "Not found",
        "WEATHERAPI_COM_API_KEY": "Loaded" if weatherapi_com_api_key else "Not found",
        "TOMORROW_IO_API_KEY": "Loaded" if tomorrow_io_api_key else "Not found"
    }

    openweathermap_data = {}
    if openweathermap_api_key:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={openweathermap_api_key}&units=metric"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
            openweathermap_data = response.json()
        except requests.exceptions.RequestException as e:
            openweathermap_data = {"error": f"OpenWeatherMap API request failed: {str(e)}"}
        except Exception as e: # Catch any other unexpected errors during parsing etc.
            openweathermap_data = {"error": f"An unexpected error occurred with OpenWeatherMap data processing: {str(e)}"}
    else:
        openweathermap_data = {"error": "OpenWeatherMap API key not configured or missing."}

    weatherapi_com_data = {}
    if weatherapi_com_api_key: # This key is already retrieved and status set in api_keys_status
        url = f"http://api.weatherapi.com/v1/current.json?key={weatherapi_com_api_key}&q={lat},{lon}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            weatherapi_com_data = response.json()
        except requests.exceptions.RequestException as e:
            weatherapi_com_data = {"error": f"WeatherAPI.com API request failed: {str(e)}"}
        except Exception as e: # Catch any other unexpected errors
            weatherapi_com_data = {"error": f"An unexpected error occurred with WeatherAPI.com data processing: {str(e)}"}
    else:
        # This error is specific to this data block if lat/lon were present but key was not
        weatherapi_com_data = {"error": "WeatherAPI.com API key not configured or missing."}

    tomorrow_io_data = {}
    if tomorrow_io_api_key: # This key is already retrieved and status set in api_keys_status
        url = f"https://api.tomorrow.io/v4/weather/realtime?location={lat},{lon}"
        headers = {"apikey": tomorrow_io_api_key}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            tomorrow_io_data = response.json()
        except requests.exceptions.RequestException as e:
            tomorrow_io_data = {"error": f"Tomorrow.io API request failed: {str(e)}"}
        except Exception as e: # Catch any other unexpected errors
            tomorrow_io_data = {"error": f"An unexpected error occurred with Tomorrow.io data processing: {str(e)}"}
    else:
        tomorrow_io_data = {"error": "Tomorrow.io API key not configured or missing."}

    # Helper function for safe nested dictionary access
    def get_nested_value(data_dict, keys, default=None):
        current = data_dict
        for key_part in keys:
            if isinstance(current, dict) and key_part in current:
                current = current[key_part]
            elif isinstance(current, list) and isinstance(key_part, int) and key_part < len(current):
                current = current[key_part]
            else:
                return default
        return current

    temperatures_c = []
    humidities_percent = []
    wind_speeds_kph = []
    conditions_data = [] # List of (priority, text_description)
    successful_sources = []

    # Process OpenWeatherMap
    if isinstance(openweathermap_data, dict) and 'error' not in openweathermap_data:
        successful_sources.append('openweathermap')
        # OpenWeatherMap temperature is in Kelvin, convert to Celsius
        k_temp = get_nested_value(openweathermap_data, ['main', 'temp'])
        if isinstance(k_temp, (int, float)):
            temperatures_c.append(k_temp - 273.15)

        humidity_val = get_nested_value(openweathermap_data, ['main', 'humidity'])
        if isinstance(humidity_val, (int, float)):
            humidities_percent.append(humidity_val)

        # OpenWeatherMap wind speed is in m/s, convert to kph
        wind_ms_val = get_nested_value(openweathermap_data, ['wind', 'speed'])
        if isinstance(wind_ms_val, (int, float)):
            wind_speeds_kph.append(wind_ms_val * 3.6)

        condition_val = get_nested_value(openweathermap_data, ['weather', 0, 'description'])
        if condition_val is not None:
            conditions_data.append((1, str(condition_val)))

    # Process WeatherAPI.com
    if isinstance(weatherapi_com_data, dict) and 'error' not in weatherapi_com_data:
        successful_sources.append('weatherapi_com')
        c_temp_val = get_nested_value(weatherapi_com_data, ['current', 'temp_c'])
        if isinstance(c_temp_val, (int, float)):
            temperatures_c.append(c_temp_val)

        humidity_val = get_nested_value(weatherapi_com_data, ['current', 'humidity'])
        if isinstance(humidity_val, (int, float)):
            humidities_percent.append(humidity_val)

        wind_kph_val = get_nested_value(weatherapi_com_data, ['current', 'wind_kph'])
        if isinstance(wind_kph_val, (int, float)):
            wind_speeds_kph.append(wind_kph_val)

        condition_val = get_nested_value(weatherapi_com_data, ['current', 'condition', 'text'])
        if condition_val is not None:
            conditions_data.append((2, str(condition_val)))

    # Process Tomorrow.io
    if isinstance(tomorrow_io_data, dict) and 'error' not in tomorrow_io_data:
        successful_sources.append('tomorrow_io')
        c_temp_val = get_nested_value(tomorrow_io_data, ['data', 'timelines', 0, 'intervals', 0, 'values', 'temperature'])
        if isinstance(c_temp_val, (int, float)):
            temperatures_c.append(c_temp_val)

        humidity_val = get_nested_value(tomorrow_io_data, ['data', 'timelines', 0, 'intervals', 0, 'values', 'humidity'])
        if isinstance(humidity_val, (int, float)):
            humidities_percent.append(humidity_val)

        # Tomorrow.io wind speed is in m/s, convert to kph
        wind_ms_val = get_nested_value(tomorrow_io_data, ['data', 'timelines', 0, 'intervals', 0, 'values', 'windSpeed'])
        if isinstance(wind_ms_val, (int, float)):
            wind_speeds_kph.append(wind_ms_val * 3.6)

        # Tomorrow.io condition text is not used for final condition as per plan
        # condition_val = get_nested_value(tomorrow_io_data, ['data', 'timelines', 0, 'intervals', 0, 'values', 'weatherCode'])
        # if condition_val is not None:
        #    conditions_data.append((3, str(map_weather_code_to_text(condition_val))))


    avg_temp_c = round(sum(temperatures_c) / len(temperatures_c), 2) if temperatures_c else None
    avg_humidity_percent = round(sum(humidities_percent) / len(humidities_percent), 2) if humidities_percent else None
    avg_wind_speed_kph = round(sum(wind_speeds_kph) / len(wind_speeds_kph), 2) if wind_speeds_kph else None

    final_condition = None
    if conditions_data:
        conditions_data.sort(key=lambda item: item[0]) # Sort by priority
        final_condition = conditions_data[0][1]

    return jsonify({
        "current_conditions": {
            "temperature_celsius": avg_temp_c,
            "humidity_percent": avg_humidity_percent,
            "wind_speed_kph": avg_wind_speed_kph,
            "condition": final_condition
        },
        "data_sources": sorted(list(set(successful_sources)))
    })

if __name__ == '__main__':
    app.run(debug=True)
