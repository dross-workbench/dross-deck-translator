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
        async def request(method, path, payload=None, **kwargs):
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


def test_auto_groups_languages_reuses_detections_and_preserves_coordinates():
    async def run():
        p = DrossLocalProvider()
        calls, identity = [], 'model-one'
        async def request(method, path, payload=None, **kwargs):
            calls.append((path, payload))
            if path == '/health':
                return {'translation_available': True, 'model_identity': identity, 'automatic_detection': True,
                        'source_languages': ['auto', 'pt', 'id'], 'target_languages': ['en', 'pt']}
            if path == '/v1/detect':
                return {'segments': [{'id': s['id'], 'language': ['pt', 'id', 'und'][int(s['id'])],
                    'status': 'uncertain' if s['text'] == '???' else 'detected', 'confidence': 0.9, 'reason': 'fixture'} for s in payload['segments']]}
            assert path == '/v1/translate'
            return {'segments': [{'id': s['id'], 'translation': payload['target_language'] + ':' + s['text']} for s in payload['segments']]}
        p.request = request
        regions = [{'text': t, 'rect': {'x': i * 30, 'y': 40, 'width': 20, 'height': 10}} for i, t in enumerate(['portuguese', 'indonesian', '???'])]
        first = await p.translate_regions(regions, 'auto', 'en', 'game')
        assert [r['rect'] for r in first] == [r['rect'] for r in regions]
        assert [r['drossSourceLanguage'] for r in first] == ['pt', 'id', 'und']
        assert first[2]['translatedText'] == '???' and first[2]['drossWarning']
        assert {payload['source_language'] for path, payload in calls if path == '/v1/translate'} == {'pt', 'id'}
        size = len(calls)
        assert await p.translate_regions(regions, 'auto', 'en', 'game') == first
        assert [path for path, _ in calls[size:]] == ['/health']
        identity = 'model-two'
        await p.translate_regions(regions, 'auto', 'en', 'game')
        assert sum(path == '/v1/detect' for path, _ in calls) == 2
        assert sum(path == '/v1/translate' for path, _ in calls) == 4
        changed = await p.translate_regions(regions, 'auto', 'pt', 'game')
        assert changed[0]['translatedText'] == 'portuguese'
        assert changed[1]['translatedText'] == 'pt:indonesian'
        assert 'englishTranslation' not in changed[1]
        assert calls[-1][1]['context'] == []
        p.cache.close()
    asyncio.run(run())


def test_multilingual_fallback_uses_selected_pair_and_auto_requires_choice():
    async def run():
        p = DrossLocalProvider()
        p.settings['dross_offline_fallback'] = True
        async def offline(): raise NetworkError('offline')
        p.health = offline
        class Fallback:
            def is_available(self, source, target): return (source, target) == ('pt', 'id')
            async def translate_batch(self, texts, source, target):
                assert (source, target) == ('pt', 'id')
                return ['local Indonesian']
        result = await p.translate_regions([{'text': 'Olá'}], 'pt', 'id', 'game', fallback=Fallback())
        assert result[0]['drossTranslation'] == 'local Indonesian' and result[0]['drossFallback']
        with pytest.raises(NetworkError, match='explicit input language'):
            await p.translate_regions([{'text': 'Olá'}], 'auto', 'en', 'game', fallback=Fallback())
        p.cache.close()
    asyncio.run(run())


def test_old_server_rejects_new_languages_instead_of_translating_as_japanese():
    async def run():
        p = DrossLocalProvider()
        async def health(): return {'translation_available': True, 'model_identity': 'legacy'}
        p.health = health
        with pytest.raises(NetworkError, match='Update Workbench'):
            await p.translate_regions([{'text': 'Olá'}], 'pt', 'en', 'game')
        p.cache.close()
    asyncio.run(run())
