import pytest
from backend.app import app # Assuming app.py is in backend directory
from unittest.mock import patch
import os
import requests # For exception types

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home_endpoint(client):
    """Test the home endpoint ("/")."""
    response = client.get('/')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}

def test_weather_endpoint_success(client):
    """Test the /api/weather endpoint with lat and lon parameters."""
    response = client.get('/api/weather?lat=12.34&lon=56.78')
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data['latitude'] == '12.34'
    assert json_data['longitude'] == '56.78'
    assert 'api_keys_status' in json_data

def test_weather_endpoint_missing_params(client):
    """Test the /api/weather endpoint without lat and lon parameters."""
    response = client.get('/api/weather')
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == "Latitude and longitude query parameters are required."


@patch('backend.app.requests.get') # Patch where 'requests' is used in 'app.py'
def test_weather_endpoint_openweathermap_success(mock_get, client):
    """Test /api/weather with successful OpenWeatherMap API call."""
    with patch.dict(os.environ, {'OPENWEATHERMAP_API_KEY': 'fake_key', 'WEATHERAPI_COM_API_KEY': 'dummy', 'TOMORROW_IO_API_KEY': 'dummy'}):
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {"weather": [{"description": "clear sky"}], "main": {"temp": 25}}

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()

        assert json_data['latitude'] == '12.34'
        assert json_data['longitude'] == '56.78'
        assert 'openweathermap' in json_data
        assert json_data['openweathermap'].get('main', {}).get('temp') == 25
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Loaded"

@patch('backend.app.requests.get')
def test_weather_endpoint_openweathermap_api_key_missing(mock_get, client):
    """Test /api/weather when OpenWeatherMap API key is missing."""
    original_env = os.environ.copy()
    # Ensure OPENWEATHERMAP_API_KEY is not in os.environ for this specific test context
    # We want app.py's os.environ.get('OPENWEATHERMAP_API_KEY') to return None
    # Keep other keys if they exist to check their status reporting
    env_vars_for_test = {k: v for k, v in original_env.items() if k != 'OPENWEATHERMAP_API_KEY'}
    # Also ensure the other keys are present for consistent api_keys_status check, or mark them as "Not found" too
    if 'WEATHERAPI_COM_API_KEY' not in env_vars_for_test: env_vars_for_test['WEATHERAPI_COM_API_KEY'] = 'dummy_other_key'
    if 'TOMORROW_IO_API_KEY' not in env_vars_for_test: env_vars_for_test['TOMORROW_IO_API_KEY'] = 'dummy_other_key'


    with patch.dict(os.environ, env_vars_for_test, clear=True):
        # If .env is loaded by app, this patch.dict should override for the scope of the test
        # No need to reload dotenv here as app.py does it once at startup.
        # The test client will interact with this modified environment.

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()

        assert 'openweathermap' in json_data
        assert "OpenWeatherMap API key not configured or missing." in json_data['openweathermap'].get('error', '')
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Not found"
        # Check other keys are still reported based on env_vars_for_test
        assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Loaded"
        assert json_data['api_keys_status']['TOMORROW_IO_API_KEY'] == "Loaded"


@patch('backend.app.requests.get')
def test_weather_endpoint_openweathermap_request_exception(mock_get, client):
    """Test /api/weather with OpenWeatherMap API call failing (RequestException)."""
    with patch.dict(os.environ, {'OPENWEATHERMAP_API_KEY': 'fake_key', 'WEATHERAPI_COM_API_KEY': 'dummy', 'TOMORROW_IO_API_KEY': 'dummy'}):
        mock_get.side_effect = requests.exceptions.RequestException("Test network error")

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'openweathermap' in json_data
        assert "OpenWeatherMap API request failed" in json_data['openweathermap'].get('error', '')
        assert "Test network error" in json_data['openweathermap'].get('error', '')
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Loaded"


@patch('backend.app.requests.get')
def test_weather_endpoint_openweathermap_http_error(mock_get, client):
    """Test /api/weather with OpenWeatherMap API call failing (HTTPError)."""
    with patch.dict(os.environ, {'OPENWEATHERMAP_API_KEY': 'fake_key', 'WEATHERAPI_COM_API_KEY': 'dummy', 'TOMORROW_IO_API_KEY': 'dummy'}):
        mock_response = mock_get.return_value
        mock_response.status_code = 500 # Or any 4xx/5xx error
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error 500")

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()
        assert 'openweathermap' in json_data
        assert "OpenWeatherMap API request failed" in json_data['openweathermap'].get('error', '')
        # The exact content of str(e) for HTTPError might include the status code
        assert "Server Error 500" in json_data['openweathermap'].get('error', '')
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Loaded"
