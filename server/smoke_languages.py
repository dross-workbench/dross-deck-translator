"""Check the real pinned-HTTPS Deck provider against the locally configured gateway."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'py_modules'))
from providers.dross_local import DrossLocalProvider


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='.local/multilingual-https.json')
    args = parser.parse_args()
    config = json.loads((ROOT / 'server/.local/config.json').read_text(encoding='utf-8'))
    provider = DrossLocalProvider()
    provider.configure({'dross_server_url': f"https://{config['bind']}:{config['port']}",
        'dross_token': config['token'], 'dross_certificate_sha256': config['fingerprint'], 'dross_track_encounters': False})
    report = {'transport': 'authenticated HTTPS with certificate pinning', 'cases': []}
    try:
        health = await provider.health()
        assert health['version'] == '0.2.0' and health['automatic_detection']
        report['model'] = health['translation_model']
        for source, target, text, expected_source in [
            ('auto', 'en', '約束を忘れないで。', 'ja'),
            ('auto', 'en', 'Não abra a porta até eu voltar.', 'pt'),
            ('id', 'en', 'Jangan buka pintu sampai aku kembali.', 'id'),
            ('auto', 'en', 'Jangan buka pintu sampai aku kembali.', 'und'),
            ('ja', 'pt', '約束を忘れないで。', 'ja'),
            ('ja', 'id', '約束を忘れないで。', 'ja'),
        ]:
            regions = [{'text': text, 'rect': {'x': 100, 'y': 500, 'width': 600, 'height': 50}}]
            start = time.perf_counter()
            output = await provider.translate_regions(regions, source, target, 'synthetic-language-smoke')
            wall_ms = round((time.perf_counter() - start) * 1000)
            assert output[0]['rect'] == regions[0]['rect']
            assert output[0]['drossSourceLanguage'] == expected_source
            assert output[0]['drossTargetLanguage'] == target and output[0]['drossTranslation']
            if expected_source == 'und':
                assert output[0]['drossWarning'] and output[0]['drossTranslation'] == text
            start = time.perf_counter()
            repeated = await provider.translate_regions(regions, source, target, 'synthetic-language-smoke')
            assert repeated == output
            record = {'source': source, 'target': target, 'text': text, 'detected': expected_source,
                      'translation': output[0]['drossTranslation'], 'warning': output[0]['drossWarning'],
                      'wall_ms': wall_ms, 'repeat_ms': round((time.perf_counter() - start) * 1000), 'rectangle_preserved': True}
            report['cases'].append(record)
            print(json.dumps(record, ensure_ascii=True), flush=True)
        dest = ROOT / args.output
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        provider.cache.close()


if __name__ == '__main__':
    asyncio.run(main())
