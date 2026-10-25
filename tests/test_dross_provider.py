import asyncio
import json
from pathlib import Path
import pytest
from providers.base import NetworkError, ApiKeyError
from providers.dross_local import DrossLocalProvider
from providers.translation_cache import TranslationCache


def test_cache_scopes_and_upstream_compatibility(tmp_path):
    cache = TranslationCache(str(tmp_path/'cache.db'))
    cache.put_many([('約束', 'promise')], 'ja', 'en', 2, 'freegoogle')
    assert cache.get_many(['約束'], 'ja', 'en', 1) == {'約束': 'promise'}
    assert cache.get_many(['約束'], 'ja', 'en', 3) == {}
    cache.put_many([('約束', 'our promise')], 'ja', 'en', 0, 'dross', namespace='context+modelA')
    assert cache.get_many(['約束'], 'ja', 'en', 0, namespace='context+modelB') == {}
    assert cache.get_many(['約束'], 'ja', 'en', 0, namespace='context+modelA') == {'約束': 'our promise'}
    cache.delete_entry('ja', 'en', '約束')
    assert cache.stats()['entries'] == 0
    cache.close()


@pytest.mark.parametrize('url', ['https://example.com', 'http://8.8.8.8', 'http://0.0.0.0', 'http://192.168.1.10', 'https://user:pass@127.0.0.1', 'https://127.0.0.1/?token=secret'])
def test_reject_unsafe_gateway(url):
    p = DrossLocalProvider()
    p.settings.update(dross_server_url=url, dross_token='fixture')
    with pytest.raises(NetworkError):
        p._request('GET', '/health')
    p.cache.close()


def test_fixture_coordinates_context_cache_and_no_screenshot():
    samples = json.loads((Path(__file__).parent/'fixtures/dialogue.json').read_text(encoding='utf-8'))
    async def run():
        p = DrossLocalProvider()
        calls = []
        async def request(method, path, payload=None):
            if path == '/health':
                return {'translation_available': True, 'model_identity': 'fixture-model'}
            if path == '/v1/vocabulary/encounters':
                return {'recorded': 0}
            assert 'image' not in payload and 'rect' not in json.dumps(payload)
            calls.append(payload)
            return {'segments': [{'id': s['id'], 'translation': 'Translation: '+s['text']} for s in payload['segments']]}
        p.request = request
        for sample in samples:
            region = {'text': sample['text'], 'rect': sample['rect'], 'confidence': 0.7}
            result = await p.translate_regions([region], 'ja', 'en', 'game-one')
            assert result[0]['rect'] == region['rect']
            assert result[0]['text'] == region['text']
            count = len(calls)
            await p.translate_regions([region], 'ja', 'en', 'game-one')
            assert len(calls) == count
        await p.translate_regions([region], 'ja', 'en', 'game-two')
        assert calls[-1]['context'] == []
        assert p.cache.stats()['entries'] > 0
        p.cache.close()
    asyncio.run(run())


def test_only_explicit_offline_fallback_and_no_auth_fallback():
    async def run():
        p = DrossLocalProvider()
        class Fallback:
            def is_available(self, *args): return True
            async def translate_batch(self, *args): return ['local offline']
        async def unavailable(*args, **kwargs): raise NetworkError('offline')
        p.health = unavailable
        with pytest.raises(NetworkError):
            await p.translate_regions([{'text':'約束'}], 'ja', 'en', 'g', fallback=Fallback())
        p.settings['dross_offline_fallback'] = True
        result = await p.translate_regions([{'text':'約束'}], 'ja', 'en', 'g', fallback=Fallback())
        assert result[0]['drossFallback'] is True
        async def wrong_token(): raise ApiKeyError('wrong token')
        p.health = wrong_token
        with pytest.raises(ApiKeyError):
            await p.translate_regions([{'text':'約束'}], 'ja', 'en', 'g', fallback=Fallback())
        p.cache.close()
    asyncio.run(run())
