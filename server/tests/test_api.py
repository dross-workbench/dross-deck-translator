import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from dross_server.app import create_app
from dross_server.config import Config
from dross_server.inference import Ollama

TOKEN = 'synthetic-test-token-with-32-characters'


@pytest.fixture
def service(tmp_path):
    calls = []
    def mock(request):
        assert request.url.host == '127.0.0.1'
        calls.append(request)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'qwen3:0.6b', 'digest': 'fixture-digest'}]})
        return httpx.Response(200, json={'message': {'content': json.dumps({'translation': "Don't forget our promise."})}, 'done_reason': 'stop'})
    config = Config(token=TOKEN, data_dir=tmp_path, translation_model='qwen3:0.6b')
    app = create_app(config, Ollama(config, httpx.MockTransport(mock)))
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer ' + TOKEN
        yield client, calls


def test_health_and_auth(service):
    client, calls = service
    assert client.get('/health').json()['local_only'] is True
    assert client.get('/health', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    assert client.get('/docs').status_code == 404


def test_translation_contract_and_no_images(service):
    client, calls = service
    body = {'segments': [{'id': 'a', 'text': '約束を忘れないで。'}]}
    r = client.post('/v1/translate', json=body)
    assert r.status_code == 200
    assert r.json()['segments'][0] == {'id': 'a', 'translation': "Don't forget our promise.",
        'source_language': 'ja', 'target_language': 'en', 'detection_confidence': None, 'status': 'translated'}
    assert client.post('/v1/translate', json={**body, 'image': 'forbidden'}).status_code == 422
    assert all('images' not in json.loads(c.content) for c in calls if c.method == 'POST')


def test_identity_and_limits(service):
    client, _ = service
    body = {'segments': [{'id': 'a', 'text': '約束'}]}
    assert client.post('/v1/translate', json={**body, 'model_identity': 'old'}).status_code == 409
    assert client.post('/v1/translate', json={'segments': body['segments'] * 2}).status_code == 422
    assert client.post('/v1/translate', json={'segments': []}).status_code == 422
    assert client.post('/v1/translate', json={**body, 'context': ['x'*1501]}).status_code == 422
    assert client.post('/v1/translate', content=b'x'*4_000_001).status_code == 413


def test_english_ui_does_not_infer(service):
    client, calls = service
    assert client.post('/v1/translate', json={'segments': [{'id': 'ui', 'text': 'HP 120'}]}).json()['segments'][0]['translation'] == 'HP 120'
    assert not any(c.url.path == '/api/chat' for c in calls)


def test_reject_cloud_models():
    with pytest.raises(ValueError):
        Config(token=TOKEN, translation_model='qwen3-cloud')


def test_ollama_errors_are_sanitized():
    config = Config(token=TOKEN)
    inference = Ollama(config, httpx.MockTransport(lambda r: httpx.Response(500, text='private source or secret')))
    with TestClient(create_app(config, inference)) as client:
        response = client.get('/health', headers={'Authorization': 'Bearer '+TOKEN})
        assert response.status_code == 503
        assert 'private source' not in response.text


def test_model_switch_unloads_previous():
    calls = []
    def mock(r):
        calls.append((r.url.path, json.loads(r.content)))
        return httpx.Response(200, json={'message': {'content': 'ok'}})
    async def run():
        c = Ollama(Config(token=TOKEN), httpx.MockTransport(mock))
        await c.chat('qwen3:0.6b', [])
        await c.chat('qwen3:1.7b', [])
        await c.client.aclose()
    asyncio.run(run())
    assert calls[1] == ('/api/generate', {'model': 'qwen3:0.6b', 'keep_alive': 0})
