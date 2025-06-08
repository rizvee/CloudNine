import pytest
from backend.app import app # Assuming app.py is in backend directory
from unittest.mock import patch, MagicMock
import os
import requests # For exception types

# Comprehensive mock function for all API calls
def mock_api_calls(url, headers=None, timeout=None):
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 404 # Default
    mock_resp.json.return_value = {"error": "Mocked URL not found or not handled by mock_api_calls"}
    # Default raise_for_status to do nothing unless specified
    mock_resp.raise_for_status = MagicMock()

    if "api.openweathermap.org" in url:
        api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
        if api_key == 'raise_request_exception':
            raise requests.exceptions.RequestException("OWM mock: network error")
        if api_key == 'raise_http_error':
            mock_resp.status_code = 500
            mock_resp.json.return_value = {"error": "OWM mock: Server Error"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("OWM mock: Server Error")
        elif api_key: # Assumes any other non-empty key is valid for mock success
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"weather": [{"description": "clear sky"}], "main": {"temp": 25}}
        else: # Key not found
            mock_resp.status_code = 401 # Or some other error that app handles or ignores
            mock_resp.json.return_value = {"error": "OWM mock: API key missing"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("OWM mock: API key missing")


    elif "api.weatherapi.com" in url:
        api_key = os.environ.get('WEATHERAPI_COM_API_KEY')
        if api_key == 'raise_request_exception':
            raise requests.exceptions.RequestException("WAC mock: network error")
        if api_key == 'raise_http_error':
            mock_resp.status_code = 500
            mock_resp.json.return_value = {"error": "WAC mock: Server Error"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("WAC mock: Server Error")
        elif api_key:
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"current": {"temp_c": 26, "condition": {"text": "Sunny"}}}
        else:
            mock_resp.status_code = 401
            mock_resp.json.return_value = {"error": "WAC mock: API key missing"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("WAC mock: API key missing")

    elif "api.tomorrow.io" in url:
        api_key_in_header = headers.get("apikey") if headers else None
        env_api_key = os.environ.get('TOMORROW_IO_API_KEY')

        if api_key_in_header and api_key_in_header == env_api_key:
            if env_api_key == 'raise_request_exception':
                raise requests.exceptions.RequestException("TIO mock: network error")
            if env_api_key == 'raise_http_error':
                mock_resp.status_code = 503
                mock_resp.json.return_value = {"error": "TIO mock: Service Unavailable"}
                mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("TIO mock: Service Unavailable")
            elif env_api_key : # Valid key
                mock_resp.status_code = 200
                # Adjusted to match the example structure used in earlier Tomorrow.io test prompt
                mock_resp.json.return_value = {"data": {"timelines": [{"intervals": [{"values": {"temperature": 27}}]}]}}
            # else case: env_api_key is None but somehow passed header check - should not happen if app logic is correct
        else: # API key mismatch or missing in header/env
            mock_resp.status_code = 401 # Unauthorized
            mock_resp.json.return_value = {"error": "TIO mock: API key issue in request or env"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("TIO mock: API key issue")

    return mock_resp

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

# Tests for OpenWeatherMap
@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_openweathermap_success(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key', # Ensure other keys are set for full test
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['openweathermap']['main']['temp'] == 25
        assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Loaded"

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_openweathermap_key_missing(mock_get, client):
    original_env = os.environ.copy()
    env_vars = { # OWM key is absent
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        try:
            response = client.get('/api/weather?lat=12.34&lon=56.78')
            json_data = response.get_json()
            assert "OpenWeatherMap API key not configured" in json_data['openweathermap'].get('error', '')
            assert json_data['api_keys_status']['OPENWEATHERMAP_API_KEY'] == "Not found"
        finally:
            os.environ.clear()
            os.environ.update(original_env)

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_openweathermap_request_exception(mock_get, client):
    env_vars = {'OPENWEATHERMAP_API_KEY': 'raise_request_exception', 'WEATHERAPI_COM_API_KEY': 'dummy_wac', 'TOMORROW_IO_API_KEY': 'dummy_tio'}
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert "OpenWeatherMap API request failed" in json_data['openweathermap'].get('error', '')
        assert "OWM mock: network error" in json_data['openweathermap'].get('error', '')

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_openweathermap_http_error(mock_get, client):
    env_vars = {'OPENWEATHERMAP_API_KEY': 'raise_http_error', 'WEATHERAPI_COM_API_KEY': 'dummy_wac', 'TOMORROW_IO_API_KEY': 'dummy_tio'}
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert "OpenWeatherMap API request failed" in json_data['openweathermap'].get('error', '')
        assert "OWM mock: Server Error" in json_data['openweathermap'].get('error', '')

# Tests for WeatherAPI.com
@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_weatherapi_com_success(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert json_data['weatherapi_com']['current']['temp_c'] == 26
        assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Loaded"

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_weatherapi_com_key_missing(mock_get, client):
    original_env = os.environ.copy()
    env_vars = { # WAC key is absent
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        try:
            response = client.get('/api/weather?lat=12.34&lon=56.78')
            json_data = response.get_json()
            assert "WeatherAPI.com API key not configured" in json_data['weatherapi_com'].get('error', '')
            assert json_data['api_keys_status']['WEATHERAPI_COM_API_KEY'] == "Not found"
        finally:
            os.environ.clear()
            os.environ.update(original_env)

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_weatherapi_com_request_exception(mock_get, client):
    env_vars = {'WEATHERAPI_COM_API_KEY': 'raise_request_exception', 'OPENWEATHERMAP_API_KEY': 'dummy_owm', 'TOMORROW_IO_API_KEY': 'dummy_tio'}
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert "WeatherAPI.com API request failed" in json_data['weatherapi_com'].get('error', '')
        assert "WAC mock: network error" in json_data['weatherapi_com'].get('error', '')

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_weatherapi_com_http_error(mock_get, client):
    env_vars = {'WEATHERAPI_COM_API_KEY': 'raise_http_error', 'OPENWEATHERMAP_API_KEY': 'dummy_owm', 'TOMORROW_IO_API_KEY': 'dummy_tio'}
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert "WeatherAPI.com API request failed" in json_data['weatherapi_com'].get('error', '')
        assert "WAC mock: Server Error" in json_data['weatherapi_com'].get('error', '')

# Tests for Tomorrow.io
@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_tomorrow_io_success(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert json_data['tomorrow_io']['data']['timelines'][0]['intervals'][0]['values']['temperature'] == 27
        assert json_data['api_keys_status']['TOMORROW_IO_API_KEY'] == "Loaded"

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_tomorrow_io_key_missing(mock_get, client):
    original_env = os.environ.copy()
    env_vars = { # TIO key is absent
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        try:
            response = client.get('/api/weather?lat=12.34&lon=56.78')
            json_data = response.get_json()
            assert "Tomorrow.io API key not configured" in json_data['tomorrow_io'].get('error', '')
            assert json_data['api_keys_status']['TOMORROW_IO_API_KEY'] == "Not found"
        finally:
            os.environ.clear()
            os.environ.update(original_env)

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_tomorrow_io_request_exception(mock_get, client):
    env_vars = {'TOMORROW_IO_API_KEY': 'raise_request_exception', 'OPENWEATHERMAP_API_KEY': 'dummy_owm', 'WEATHERAPI_COM_API_KEY': 'dummy_wac'}
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert "Tomorrow.io API request failed" in json_data['tomorrow_io'].get('error', '')
        assert "TIO mock: network error" in json_data['tomorrow_io'].get('error', '')

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_tomorrow_io_http_error(mock_get, client):
    env_vars = {'TOMORROW_IO_API_KEY': 'raise_http_error', 'OPENWEATHERMAP_API_KEY': 'dummy_owm', 'WEATHERAPI_COM_API_KEY': 'dummy_wac'}
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        assert "Tomorrow.io API request failed" in json_data['tomorrow_io'].get('error', '')
        assert "TIO mock: Service Unavailable" in json_data['tomorrow_io'].get('error', '')
