from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = Flask(__name__)

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

    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "api_keys_status": api_keys_status,
        "openweathermap": openweathermap_data
    })

if __name__ == '__main__':
    app.run(debug=True)
