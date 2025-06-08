import pytest
from backend.app import app # Assuming app.py is in backend directory
from unittest.mock import patch, MagicMock
import os
import requests # For exception types

# Updated mock_api_calls function
def mock_api_calls(url, headers=None, timeout=None):
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 404 # Default
    mock_resp.json.return_value = {"error": "Mocked URL not found or not handled by mock_api_calls"}
    mock_resp.raise_for_status = MagicMock() # Default to do nothing

    # OpenWeatherMap
    if "api.openweathermap.org" in url:
        api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
        if api_key == 'raise_request_exception':
            raise requests.exceptions.RequestException("OWM mock: network error")
        if api_key == 'raise_http_error':
            mock_resp.status_code = 500
            mock_resp.json.return_value = {"error": "OWM mock: Server Error"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("OWM mock: Server Error")
        elif api_key:
            mock_resp.status_code = 200
            mock_resp.json.return_value = { # Updated payload for normalization
                "main": {"temp": 283.15, "humidity": 60}, # 10 C
                "wind": {"speed": 5}, # 5 m/s = 18 kph
                "weather": [{"description": "OWM description"}]
            }
        else: # Key not found logic in app leads to "not configured", not an API call
            mock_resp.status_code = 401 # Should not be called by app if key missing
            mock_resp.json.return_value = {"error": "OWM mock: API key was missing in env"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("OWM mock: API key was missing in env")

    # WeatherAPI.com
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
            mock_resp.json.return_value = { # Updated payload
                "current": {"temp_c": 12.0, "humidity": 65, "wind_kph": 20.0, "condition": {"text": "WAC description"}}
            }
        else: # Key not found
            mock_resp.status_code = 401
            mock_resp.json.return_value = {"error": "WAC mock: API key was missing in env"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("WAC mock: API key was missing in env")

    # Tomorrow.io
    elif "api.tomorrow.io" in url:
        api_key_in_header = headers.get("apikey") if headers else None
        env_api_key = os.environ.get('TOMORROW_IO_API_KEY')

        if env_api_key == 'raise_request_exception': # This check should be based on env_api_key for consistency
            raise requests.exceptions.RequestException("TIO mock: network error")
        if env_api_key == 'raise_http_error':
            mock_resp.status_code = 503
            mock_resp.json.return_value = {"error": "TIO mock: Service Unavailable"}
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("TIO mock: Service Unavailable")
        elif api_key_in_header and api_key_in_header == env_api_key and env_api_key : # Valid key and header match
            mock_resp.status_code = 200
            mock_resp.json.return_value = { # Updated payload
                "data": {"timelines": [{"intervals": [{"values": {"temperature": 11.0, "humidity": 70, "windSpeed": 2.77778}}]}]} # 2.77778 m/s = 10 kph
            }
        else: # API key mismatch, missing in header, or missing in env
            mock_resp.status_code = 401
            mock_resp.json.return_value = {"error": "TIO mock: API key issue"}
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

def test_weather_endpoint_missing_params(client):
    """Test the /api/weather endpoint without lat and lon parameters."""
    response = client.get('/api/weather')
    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data['error'] == "Latitude and longitude query parameters are required."

# New tests for consolidated response
@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_all_apis_success(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        assert response.status_code == 200
        json_data = response.get_json()
        cc = json_data.get("current_conditions", {})
        # OWM: 10C (283.15K), 60%, 18kph (5m/s), "OWM description"
        # WAC: 12C, 65%, 20kph, "WAC description"
        # TIO: 11C, 70%, 10kph (2.77778m/s)
        assert cc.get("temperature_celsius") == pytest.approx(11.0)
        assert cc.get("humidity_percent") == pytest.approx(65.0)
        assert cc.get("wind_speed_kph") == pytest.approx(16.0) # (18+20+10)/3
        assert cc.get("condition") == "OWM description"
        assert sorted(json_data.get("data_sources", [])) == sorted(['openweathermap', 'tomorrow_io', 'weatherapi_com'])

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_one_api_fails(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'raise_http_error', # WAC fails
        'TOMORROW_IO_API_KEY': 'fake_tio_key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        cc = json_data.get("current_conditions", {})
        # OWM: 10C, 60%, 18kph
        # TIO: 11C, 70%, 10kph
        assert cc.get("temperature_celsius") == pytest.approx(10.5) # (10+11)/2
        assert cc.get("humidity_percent") == pytest.approx(65.0) # (60+70)/2
        assert cc.get("wind_speed_kph") == pytest.approx(14.0) # (18+10)/2
        assert cc.get("condition") == "OWM description"
        assert sorted(json_data.get("data_sources", [])) == sorted(['openweathermap', 'tomorrow_io'])

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_two_apis_fail(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'raise_request_exception', # OWM fails
        'WEATHERAPI_COM_API_KEY': 'raise_http_error',    # WAC fails
        'TOMORROW_IO_API_KEY': 'fake_tio_key'             # TIO succeeds
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        cc = json_data.get("current_conditions", {})
        # TIO: 11C, 70%, 10kph. No condition from TIO in this setup.
        assert cc.get("temperature_celsius") == pytest.approx(11.0)
        assert cc.get("humidity_percent") == pytest.approx(70.0)
        assert cc.get("wind_speed_kph") == pytest.approx(10.0)
        assert cc.get("condition") is None # OWM and WAC conditions fail
        assert json_data.get("data_sources", []) == ['tomorrow_io']

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_all_apis_fail(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'raise_request_exception',
        'WEATHERAPI_COM_API_KEY': 'raise_http_error',
        'TOMORROW_IO_API_KEY': 'raise_request_exception'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        cc = json_data.get("current_conditions", {})
        assert cc.get("temperature_celsius") is None
        assert cc.get("humidity_percent") is None
        assert cc.get("wind_speed_kph") is None
        assert cc.get("condition") is None
        assert json_data.get("data_sources", []) == []

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_condition_priority(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'raise_http_error',    # OWM fails
        'WEATHERAPI_COM_API_KEY': 'fake_wac_key',       # WAC provides condition
        'TOMORROW_IO_API_KEY': 'fake_tio_key'          # TIO also works but no condition text
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        cc = json_data.get("current_conditions", {})
        # WAC: 12C, 65%, 20kph, "WAC description"
        # TIO: 11C, 70%, 10kph
        assert cc.get("temperature_celsius") == pytest.approx(11.5) # (12+11)/2
        assert cc.get("humidity_percent") == pytest.approx(67.5) # (65+70)/2
        assert cc.get("wind_speed_kph") == pytest.approx(15.0) # (20+10)/2
        assert cc.get("condition") == "WAC description" # WAC is priority 2
        assert sorted(json_data.get("data_sources", [])) == sorted(['tomorrow_io', 'weatherapi_com'])

@patch('backend.app.requests.get', side_effect=mock_api_calls)
def test_weather_endpoint_only_openweathermap_success(mock_get, client):
    env_vars = {
        'OPENWEATHERMAP_API_KEY': 'fake_owm_key',
        'WEATHERAPI_COM_API_KEY': 'raise_http_error', # WAC fails
        'TOMORROW_IO_API_KEY': 'raise_request_exception'    # TIO fails
    }
    with patch.dict(os.environ, env_vars, clear=True):
        response = client.get('/api/weather?lat=12.34&lon=56.78')
        json_data = response.get_json()
        cc = json_data.get("current_conditions", {})
        # OWM: 10C, 60%, 18kph
        assert cc.get("temperature_celsius") == pytest.approx(10.0)
        assert cc.get("humidity_percent") == pytest.approx(60.0)
        assert cc.get("wind_speed_kph") == pytest.approx(18.0)
        assert cc.get("condition") == "OWM description"
        assert json_data.get("data_sources", []) == ['openweathermap']
