import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from dross_server.app import create_app
from dross_server.config import Config
from dross_server.inference import Ollama
from dross_server.languages import LanguageDetector, UI_LANGUAGES

SAMPLES = json.loads((Path(__file__).resolve().parents[2] / 'tests/fixtures/multilingual.json').read_text(encoding='utf-8'))
DETECTOR = LanguageDetector()


@pytest.mark.parametrize('sample', SAMPLES, ids=lambda s: s['name'])
def test_local_detection_fixtures(sample):
    result = DETECTOR.detect(sample['text'])
    assert result['language'] == sample['detected']
    assert 0 <= result['confidence'] <= 1
    if sample['detected'] == 'und':
        assert result['status'] != 'detected'


@pytest.mark.parametrize('text,status', [
    ('Не открывай дверь.', 'unsupported'), ('Non aprire la porta prima che io ritorni.', 'unsupported'),
    ('こんにちは 안녕하세요', 'uncertain'), ('你好', 'uncertain'), ('Olá', 'uncertain'), ('123 / 456', 'non_linguistic'),
])
def test_ambiguous_and_unsupported_text_is_not_forced(text, status):
    assert DETECTOR.detect(text)['status'] == status


def test_indonesian_is_detected_when_distinguishable_from_malay():
    result = DETECTOR.detect('Pemerintah Indonesia mengumumkan kebijakan baru untuk masyarakat.')
    assert result['language'] == 'id' and result['status'] == 'detected'


@pytest.fixture
def gateway(tmp_path):
    calls = []
    def mock(request):
        assert request.url.host == '127.0.0.1'
        calls.append(request)
        if request.url.path == '/api/tags':
            return httpx.Response(200, json={'models': [{'name': 'qwen3:4b', 'digest': 'fixture'}, {'name': 'translategemma:4b', 'digest': 'fixture-tg'}]})
        return httpx.Response(200, json={'message': {'content': json.dumps({'translation': 'local translation'})}})
    config = Config(token='synthetic-test-token-with-32-characters', data_dir=tmp_path, translation_model='qwen3:4b')
    with TestClient(create_app(config, Ollama(config, httpx.MockTransport(mock)))) as client:
        client.headers['Authorization'] = 'Bearer ' + config.token
        yield client, calls, config


def test_detect_never_calls_ollama_and_requires_auth(gateway):
    client, calls, _ = gateway
    body = {'segments': [{'id': 'pt', 'text': 'Não abra a porta até eu voltar.'}]}
    assert client.post('/v1/detect', json=body, headers={'Authorization': ''}).status_code == 401
    assert client.post('/v1/detect', json=body).json()['segments'][0]['language'] == 'pt'
    assert not calls
    assert client.post('/v1/detect', json={'segments': body['segments'] * 2}).status_code == 422
    assert client.post('/v1/detect', json={'segments': [{'id': str(i), 'text': 'a' * 1500} for i in range(5)]}).status_code == 422


def test_health_and_schema_advertise_only_supported_pairs(gateway):
    client, _, _ = gateway
    health = client.get('/health').json()
    assert {'auto', 'pt', 'id'} <= set(health['source_languages'])
    assert set(health['target_languages']) == set(UI_LANGUAGES)
    assert health['study_languages'] == ['ja']
    body = {'segments': [{'id': 'a', 'text': 'A dialogue line'}]}
    for source, target in [('xx', 'en'), ('en', 'auto'), ('it', 'en')]:
        assert client.post('/v1/translate', json={**body, 'source_language': source, 'target_language': target}).status_code == 422
    assert client.post('/v1/analyze', json={'source_language': 'id', 'text': 'Saya'}).status_code == 422


@pytest.mark.parametrize('source,target,source_name,target_name', [
    ('pt', 'en', 'Portuguese', 'English'), ('id', 'pt', 'Indonesian', 'Portuguese'),
    ('en', 'id', 'English', 'Indonesian'), ('ja', 'fr', 'Japanese', 'French'),
    ('zh-hant', 'zh-hans', 'Chinese (Traditional)', 'Chinese (Simplified)'),
])
def test_dynamic_language_prompts_and_output_metadata(gateway, source, target, source_name, target_name):
    client, calls, _ = gateway
    response = client.post('/v1/translate', json={'source_language': source, 'target_language': target,
        'segments': [{'id': 'a', 'text': 'game dialogue'}], 'context': ['previous dialogue']})
    assert response.status_code == 200
    item = response.json()['segments'][0]
    assert item['translation'] == 'local translation'
    assert item['target_language'] == ('zh-CN' if target == 'zh-hans' else target)
    prompt = json.loads(next(c.content for c in calls if c.url.path == '/api/chat'))
    assert source_name in prompt['messages'][0]['content'] and target_name in prompt['messages'][0]['content']
    assert 'previous dialogue' in prompt['messages'][1]['content']
    assert prompt['think'] is False


def test_auto_mixed_regions_pass_uncertainty_and_translate_known_text(gateway):
    client, calls, _ = gateway
    response = client.post('/v1/translate', json={'source_language': 'auto', 'segments': [
        {'id': 'ja', 'text': '約束を忘れないで。'}, {'id': 'pt', 'text': 'Não abra a porta até eu voltar.'},
        {'id': 'und', 'text': '東京'}, {'id': 'en', 'text': 'Do not open the door until I return.'},
        {'id': 'ocr', 'text': '約束を□ないで。'}]})
    assert response.status_code == 200
    items = {i['id']: i for i in response.json()['segments']}
    assert items['ja']['source_language'] == 'ja' and items['pt']['source_language'] == 'pt'
    assert items['und']['translation'] == '東京' and items['und']['warning']
    assert items['en']['status'] == 'unchanged'
    assert items['ocr']['status'] == 'unclear_ocr'
    assert sum(c.url.path == '/api/chat' for c in calls) == 2


def test_translategemma_uses_documented_dynamic_prompt(gateway):
    client, calls, config = gateway
    config.translation_model = 'translategemma:4b'
    response = client.post('/v1/translate', json={'source_language': 'pt', 'target_language': 'id',
        'segments': [{'id': 'a', 'text': 'Não abra a porta.'}], 'context': ['do not include this context']})
    assert response.status_code == 200
    prompt = json.loads(next(c.content for c in calls if c.url.path == '/api/chat'))
    assert len(prompt['messages']) == 1
    assert 'Portuguese (pt) to Indonesian (id)' in prompt['messages'][0]['content']
    assert 'do not include this context' not in prompt['messages'][0]['content']
    assert not response.json()['context_used']
