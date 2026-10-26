"""Measure local multilingual inference using authored fixtures, never private game data."""
import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
import psutil
from dross_server.config import Config
from dross_server.inference import Ollama, ServiceError
from dross_server.schemas import TranslateRequest


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='qwen3:4b')
    parser.add_argument('--output', default='.local/multilingual-benchmark.json')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixtures = json.loads((root / 'tests/fixtures/multilingual.json').read_text(encoding='utf-8'))
    client = Ollama(Config(token='synthetic-benchmark-token-not-a-secret', translation_model=args.model, keep_alive='60s'))
    results = []
    try:
        for model in (await client.request('GET', '/api/ps')).get('models', []):
            await client.request('POST', '/api/generate', json={'model': model['name'], 'keep_alive': 0})
        for sample in fixtures:
            start = time.perf_counter()
            detected = client.detector.detect(sample['text'])
            detection_ms = round((time.perf_counter() - start) * 1000, 2)
            peak_rss = 0
            running = True
            async def memory():
                nonlocal peak_rss
                while running:
                    seen, rss = set(), 0
                    for process in psutil.process_iter(['name']):
                        if 'ollama' not in (process.info['name'] or '').lower():
                            continue
                        try:
                            for child in [process, *process.children(recursive=True)]:
                                if child.pid not in seen:
                                    rss += child.memory_info().rss
                                    seen.add(child.pid)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    peak_rss = max(peak_rss, rss)
                    await asyncio.sleep(0.1)
            task = asyncio.create_task(memory())
            start = time.perf_counter()
            try:
                result = await client.translate(TranslateRequest(source_language=sample['source'], target_language=sample['target'],
                    segments=[{'id': '0', 'text': sample['text']}]))
            except ServiceError as exc:
                result = {'error': exc.code}
            finally:
                wall_ms = round((time.perf_counter() - start) * 1000)
                running = False
                await task
            record = {**sample, 'detection': detected, 'detection_ms': detection_ms, 'wall_ms': wall_ms,
                      'ollama_peak_rss_bytes': peak_rss, 'detector_process_rss_bytes': psutil.Process().memory_info().rss, 'result': result}
            results.append(record)
            print(json.dumps({'name': sample['name'], 'wall_ms': wall_ms, 'detection': detected['language'],
                              'result': result.get('segments', result)}, ensure_ascii=True), flush=True)
            timings = [r['wall_ms'] for r in results if r['result'].get('timings')]
            dest = root / args.output
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps({'model': args.model, 'note': 'Authored smoke cases; references allow valid paraphrases. No native-speaker accuracy score.',
                'warm_median_ms': statistics.median(timings[1:]) if len(timings) > 1 else None,
                'samples': results}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        await client.request('POST', '/api/generate', json={'model': args.model, 'keep_alive': 0})
        await client.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
