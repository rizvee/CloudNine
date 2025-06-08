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
    # Also ensure the other keys are present for consistent api_keys_status check.
    if 'WEATHERAPI_COM_API_KEY' not in env_vars_for_test: env_vars_for_test['WEATHERAPI_COM_API_KEY'] = 'dummy_wac_key'
    if 'TOMORROW_IO_API_KEY' not in env_vars_for_test: env_vars_for_test['TOMORROW_IO_API_KEY'] = 'dummy_tio_key'

    with patch.dict(os.environ, env_vars_for_test, clear=True):
        def side_effect_func(url, timeout=None):
            mock_resp = type(mock_get.return_value)()
            if "api.weatherapi.com" in url:
                # This API should be called if its key (dummy_wac_key) is present
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"current": {"temp_c": 27}} # Mocked WAC data
            elif "api.tomorrow.io" in url:
                # This API should be called if its key (dummy_tio_key) is present
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"data": {"values": {"temperature": 28}}} # Mocked TIO data
            elif "api.openweathermap.org" in url:
                # This should NOT be called, as OPENWEATHERMAP_API_KEY is missing.
                # If it's called, it's an error in the application logic.
                raise AssertionError("OpenWeatherMap API was called when its key was missing.")
            else:
                mock_resp.status_code = 404
                mock_resp.json.return_value = {"error": f"Mocked URL not found: {url}"}
            return mock_resp
        mock_get.side_effect = side_effect_func

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()

        assert 'openweathermap' in json_data
        assert "OpenWeatherMap API key not configured or missing." in json_data['openweathermap'].get('error', '')
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Not found"

        # Check that other API data (if keys were present) are also there and correctly mocked
        assert 'weatherapi_com' in json_data
        if env_vars_for_test.get('WEATHERAPI_COM_API_KEY'):
            assert json_data['weatherapi_com'].get('current', {}).get('temp_c') == 27
            assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Loaded"
        else: # Should not happen based on env_vars_for_test setup, but good for robustness
            assert "WeatherAPI.com API key not configured or missing." in json_data['weatherapi_com'].get('error', '')
            assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Not found"

        # Assuming TOMORROW_IO_API_KEY is also handled by the endpoint and env_vars_for_test
        # For now, this test primarily focuses on OWM key missing and WAC being present.
        # If Tomorrow.io is implemented, similar checks for it would be needed.
        assert json_data['api_keys_status']['TOMORROW_IO_API_KEY'] == "Loaded" # Based on dummy_tio_key

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


@patch('backend.app.requests.get')
def test_weather_endpoint_weatherapi_com_success(mock_get, client):
    """Test /api/weather with successful WeatherAPI.com call."""
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars):
        def side_effect_func(url, timeout=None):
            mock_resp = type(mock_get.return_value)()
            if "api.openweathermap.org" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"weather": [{"description": "clear sky"}], "main": {"temp": 25}}
            elif "api.weatherapi.com" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"current": {"temp_c": 26, "condition": {"text": "Sunny"}}}
            else:
                mock_resp.status_code = 404
                mock_resp.json.return_value = {"error": "Mocked URL not found"}
            return mock_resp
        mock_get.side_effect = side_effect_func

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()

        assert 'weatherapi_com' in json_data
        assert json_data['weatherapi_com'].get('current', {}).get('temp_c') == 26
        assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Loaded"
        assert 'openweathermap' in json_data
        assert json_data['openweathermap'].get('main', {}).get('temp') == 25
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Loaded"
        assert json_data['api_keys_status']['TOMORROW_IO_API_KEY'] == "Loaded"


@patch('backend.app.requests.get')
def test_weather_endpoint_weatherapi_com_key_missing(mock_get, client):
    """Test /api/weather when WeatherAPI.com API key is missing."""
    original_env = os.environ.copy()

    # Set up environment for the test: OWM and TIO keys present, WAC key absent
    env_for_test = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    # Ensure WEATHERAPI_COM_API_KEY is definitely not in this test's environment
    if 'WEATHERAPI_COM_API_KEY' in env_for_test:
        del env_for_test['WEATHERAPI_COM_API_KEY']

    with patch.dict(os.environ, env_for_test, clear=True): # clear=True ensures only keys in env_for_test are set
        def side_effect_func(url, timeout=None):
            mock_resp = type(mock_get.return_value)()
            if "api.openweathermap.org" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"weather": [{"description": "clear sky"}], "main": {"temp": 25}}
            # No call to WeatherAPI.com should be made if key is missing
            elif "api.weatherapi.com" in url:
                mock_resp.status_code = 500 # Should not happen
                mock_resp.json.return_value = {"error": "WeatherAPI.com called unexpectedly"}
                raise AssertionError("WeatherAPI.com was called when its key was missing")
            return mock_resp
        mock_get.side_effect = side_effect_func

        try:
            response = client.get('/api/weather?lat=12.34&lon=56.78')
            assert response.status_code == 200
            json_data = response.get_json()

            assert 'weatherapi_com' in json_data
            assert "WeatherAPI.com API key not configured or missing." in json_data['weatherapi_com'].get('error', '')
            assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Not found"

            assert 'openweathermap' in json_data
            assert json_data['openweathermap'].get('main', {}).get('temp') == 25
            assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Loaded"
            assert json_data['api_keys_status']['TOMORROW_IO_API_KEY'] == "Loaded"
        finally:
            os.environ.clear()
            os.environ.update(original_env)


@patch('backend.app.requests.get')
def test_weather_endpoint_weatherapi_com_request_exception(mock_get, client):
    """Test /api/weather with WeatherAPI.com call failing (RequestException)."""
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars):
        def side_effect_func(url, timeout=None):
            mock_resp = type(mock_get.return_value)()
            if "api.openweathermap.org" in url:
                mock_resp.status_code = 200
                mock_resp.json.return_value = {"weather": [{"description": "clear sky"}], "main": {"temp": 25}}
            elif "api.weatherapi.com" in url:
                raise requests.exceptions.RequestException("WAC network error")
            return mock_resp
        mock_get.side_effect = side_effect_func

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()

        assert 'weatherapi_com' in json_data
        assert "WeatherAPI.com API request failed" in json_data['weatherapi_com'].get('error', '')
        assert "WAC network error" in json_data['weatherapi_com'].get('error', '')
        assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Loaded"


@patch('backend.app.requests.get')
def test_weather_endpoint_weatherapi_com_http_error(mock_get, client):
    """Test /api/weather with WeatherAPI.com call failing (HTTPError)."""
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars):
        def side_effect_func(url, timeout=None):
            # Create a new mock for each call to avoid state issues if using a single mock_get.return_value
            current_call_mock_response = type(mock_get.return_value)()
            if "api.openweathermap.org" in url:
                current_call_mock_response.status_code = 200
                current_call_mock_response.json.return_value = {"weather": [{"description": "clear sky"}], "main": {"temp": 25}}
            elif "api.weatherapi.com" in url:
                current_call_mock_response.status_code = 500
                current_call_mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("WAC Server Error")
            else:
                current_call_mock_response.status_code = 404 # Should not happen
            return current_call_mock_response
        mock_get.side_effect = side_effect_func

        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()

        assert 'weatherapi_com' in json_data
        assert "WeatherAPI.com API request failed" in json_data['weatherapi_com'].get('error', '')
        assert "WAC Server Error" in json_data['weatherapi_com'].get('error', '')
        assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Loaded"
