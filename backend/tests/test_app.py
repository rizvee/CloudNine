import pytest
from backend.app import app # Assuming app.py is in backend directory

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
