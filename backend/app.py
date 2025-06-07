from flask import Flask, jsonify, request
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({'status': 'ok'})

@app.route('/api/weather')
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    openweathermap_api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
    weatherapi_com_api_key = os.environ.get('WEATHERAPI_COM_API_KEY')
    tomorrow_io_api_key = os.environ.get('TOMORROW_IO_API_KEY')

    api_keys_status = {
        "OPENWEATHERMAP_API_KEY": "Loaded" if openweathermap_api_key else "Not found",
        "WEATHERAPI_COM_API_KEY": "Loaded" if weatherapi_com_api_key else "Not found",
        "TOMORROW_IO_API_KEY": "Loaded" if tomorrow_io_api_key else "Not found"
    }

    if not lat or not lon:
        return jsonify({"error": "Latitude and longitude query parameters are required."}), 400

    return jsonify({
        "latitude": lat,
        "longitude": lon,
        "api_keys_status": api_keys_status
    })

if __name__ == '__main__':
    app.run(debug=True)
