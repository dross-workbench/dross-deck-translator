import asyncio
import base64
import io
import json
import httpx
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from dross_server.app import create_app
from dross_server.anki import Anki
from dross_server.inference import ServiceError
from dross_server.config import Config
from dross_server.schemas import EncounterRequest
from dross_server.study import JapaneseStudy, grammar_notes
from dross_server.vocabulary import VocabularyStore
from test_study import item


def screenshot():
    output = io.BytesIO()
    Image.new('RGB', (1280, 800), '#222244').save(output, format='PNG')
    return base64.b64encode(output.getvalue()).decode()


def test_optional_screenshots_and_delete(tmp_path):
    config = Config(token='synthetic-private-test-token-32chars', data_dir=tmp_path)
    with TestClient(create_app(config)) as client:
        client.headers['Authorization'] = 'Bearer '+config.token
        body = item(screenshot_base64=screenshot()).model_dump()
        assert client.post('/v1/vocabulary', json=body).status_code == 403
        config.allow_images = True
        assert client.post('/v1/vocabulary', json={**body, 'screenshot_base64': 'not-base64'}).status_code == 422
        assert client.post('/v1/vocabulary', json=body).status_code == 200
        assert len(list((tmp_path/'screenshots').glob('*.png'))) == 1
        assert client.delete('/v1/vocabulary').json()['deleted'] == 1
        assert not list((tmp_path/'screenshots').glob('*.png'))


def test_saved_words_only_and_frame_idempotency(tmp_path):
    store = VocabularyStore(tmp_path)
    study = JapaneseStudy(tmp_path)
    request = EncounterRequest(event_id='frame-one', game_id='game-a', segments=[{'id':'0','text':'パンを食べる。'}])
    assert store.record_encounters(request, study) == 0
    store.save(item())
    assert store.record_encounters(request, study) == 1
    assert store.record_encounters(request, study) == 0
    assert store.list()[0]['encounters'] == 2
    assert grammar_notes('忘れないで。') and not grammar_notes('こんにちは。')


def test_anki_disabled_still_saves(tmp_path):
    config = Config(token='synthetic-private-test-token-32chars', data_dir=tmp_path)
    with TestClient(create_app(config)) as client:
        client.headers['Authorization'] = 'Bearer '+config.token
        r = client.post('/v1/vocabulary', json=item(sync_anki=True).model_dump())
        assert r.status_code == 200 and 'anki_error' in r.json()
        assert len(client.get('/v1/vocabulary').json()['items']) == 1


def test_anki_loopback_escaped_fields_and_duplicate_update(tmp_path):
    actions, notes = [], []
    def mock(r):
        assert r.url.host == '127.0.0.1' and r.url.port == 8765
        data = json.loads(r.content)
        actions.append(data)
        action = data['action']
        result = [] if action == 'modelNames' else notes.copy() if action == 'findNotes' else None
        if action == 'version':
            result = 6
        if action == 'addNote':
            notes.append(100)
            result = 100
            assert data['params']['note']['deckName'] == 'Japanese::Game Immersion::game-a'
            assert '&lt;script&gt;' in data['params']['note']['fields']['Meaning']
        return httpx.Response(200, json={'result': result, 'error': None})
    async def run():
        config = Config(token='synthetic-private-test-token-32chars', data_dir=tmp_path, anki_enabled=True)
        store = VocabularyStore(tmp_path)
        store.save(item(meaning='<script>example</script>', screenshot_base64=screenshot()))
        anki = Anki(config, httpx.MockTransport(mock))
        saved = store.list()[0]
        assert await anki.sync(saved) == 100
        assert await anki.sync(saved) == 100
    asyncio.run(run())
    assert sum(x['action'] == 'addNote' for x in actions) == 1
    assert sum(x['action'] == 'updateNoteFields' for x in actions) == 1
    assert any(x['action'] == 'storeMediaFile' for x in actions)


@pytest.mark.parametrize('response', [[], {'result': 5, 'error': None}, {'unrelated': 'service'}])
def test_anki_refuses_unrelated_or_incompatible_service(tmp_path, response):
    actions = []
    def mock(request):
        actions.append(json.loads(request.content)['action'])
        return httpx.Response(200, json=response)
    async def run():
        config = Config(token='synthetic-private-test-token-32chars', data_dir=tmp_path, anki_enabled=True)
        with pytest.raises(ServiceError) as error:
            await Anki(config, httpx.MockTransport(mock)).sync({})
        assert error.value.code == 'anki_unavailable'
    asyncio.run(run())
    assert actions == ['version']


def test_targeted_delete_preserves_other_words_and_media(tmp_path):
    store = VocabularyStore(tmp_path)
    first = store.save(item(screenshot_base64=screenshot()))
    second = store.save(item(event_id='different-event', dictionary_form='別', screenshot_base64=screenshot()))
    assert store.delete_one(first['id']) == 1
    assert store.delete_one(first['id']) == 0
    assert [word['id'] for word in store.list()] == [second['id']]
    assert len(list((tmp_path/'screenshots').glob('*.png'))) == 1
