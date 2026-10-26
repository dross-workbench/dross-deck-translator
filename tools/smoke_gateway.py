"""Exercise the real Deck-side HTTPS client against the local gateway."""
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'py_modules'))
from providers.dross_local import DrossLocalProvider


async def main():
    config = json.loads((root/'server/.local/config.json').read_text())
    provider = DrossLocalProvider()
    provider.settings.update(dross_server_url=f"https://{config['bind']}:{config['port']}", dross_token=config['token'], dross_certificate_sha256=config['fingerprint'])
    health = await provider.health()
    print(json.dumps({k:v for k,v in health.items() if k != 'model_identity'}))
    regions = [{'text': '約束を忘れないで。', 'rect': {'left': 80, 'top': 540, 'right': 1100, 'bottom': 680}}]
    for label in ('first', 'cached'):
        start = time.perf_counter()
        result = await provider.translate_regions(regions, 'ja', 'en', 'synthetic-test')
        assert result[0]['rect'] == regions[0]['rect']
        assert result[0]['englishTranslation'] != regions[0]['text']
        print(json.dumps({'run': label, 'latency_ms': round((time.perf_counter()-start)*1000), 'result': result}, ensure_ascii=True))
    analysis = await provider.request('POST', '/v1/analyze', {'text': regions[0]['text'], 'translation': result[0]['englishTranslation'], 'explain': True})
    token = analysis['tokens'][0]
    assert token['reading'] == 'やくそく' and analysis['dictionary_available']
    assert analysis['grammar']['source'] == 'Deterministic grammar notes'
    saved = await provider.request('POST', '/v1/vocabulary', {
        'event_id': str(uuid.uuid4()), 'word': token['surface'], 'dictionary_form': token['dictionary_form'],
        'reading': token['reading'], 'meaning': 'promise', 'sentence': regions[0]['text'],
        'sentence_translation': result[0]['englishTranslation'], 'game_id': 'synthetic-smoke-'+str(uuid.uuid4()),
    })
    assert saved['encounters'] == 1
    deleted = await provider.request('DELETE', '/v1/vocabulary/'+saved['id'])
    assert deleted['deleted'] == 1
    print('Live study, deterministic grammar, vocabulary save and targeted cleanup passed.')
    provider.cache.close()

asyncio.run(main())
