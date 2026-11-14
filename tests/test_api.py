import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from backend.app import create_app

def get_client():
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()

def test_health():
    c = get_client()
    r = c.get('/api/health')
    assert r.status_code == 200
    assert r.json['status'] == 'ok'

def test_parse_api():
    c = get_client()
    r = c.post('/api/parse', json={'text':'3BHK 1500 sqft east facing'})
    assert r.status_code == 200
    assert 'parsed' in r.json
    assert r.json['parsed']['bedrooms'] == 3

def test_generate_api():
    c = get_client()
    r = c.post('/api/generate', json={'text':'I want a modern 3BHK 1500 sqft 3 bedrooms 2 bathrooms open kitchen balcony east facing'})
    assert r.status_code == 200
    j = r.json
    assert 'layout' in j and 'compliance' in j and 'cost' in j and 'gcn' in j
    assert len(j['layout']['rooms']) >= 7
    assert j['layout']['width'] > 0
    # ensure furniture/lighting/plumbing present
    assert len(j['layout']['furniture']) > 0
    assert len(j['layout']['lighting']) > 0
    assert len(j['layout']['plumbing_fixtures']) > 0
    # 2D/3D same data
    assert j['layout']['width'] == j['layout']['orientation']['width']

def test_validate_api():
    c = get_client()
    gen = c.post('/api/generate', json={'text':'2BHK 1100 sqft north facing'}).json
    r = c.post('/api/validate', json={'layout': gen['layout'], 'parsed': gen['parsed']})
    assert r.status_code == 200
    assert 'compliance' in r.json

def test_cost_api():
    c = get_client()
    gen = c.post('/api/generate', json={'text':'3BHK 1500 sqft'}).json
    r = c.post('/api/cost', json={'layout': gen['layout'], 'profile':'india_tier2_2025'})
    assert r.status_code == 200
    assert 'grand_total' in r.json

def test_invalid_parse():
    c = get_client()
    r = c.post('/api/parse', json={'text':''})
    assert r.status_code == 400

def test_model_status():
    c = get_client()
    r = c.get('/api/model/status')
    assert r.status_code == 200
    assert 'inference_mode' in r.json
