"""Run real local inference on public synthetic dialogue; record measured data only."""
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
    p = argparse.ArgumentParser()
    p.add_argument('--model', default='qwen3:0.6b')
    p.add_argument('--output', default='.local/benchmark.json')
    p.add_argument('--limit', type=int, default=7)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    fixtures = json.loads((root/'tests/fixtures/dialogue.json').read_text(encoding='utf-8'))[:args.limit]
    client = Ollama(Config(token='benchmark-local-token-not-a-secret', translation_model=args.model, keep_alive='60s'))
    results = []
    for sample in fixtures:
        rss_peak = 0
        running = True
        async def sample_memory():
            nonlocal rss_peak
            while running:
                total = 0
                seen = set()
                for process in psutil.process_iter(['name']):
                    if 'ollama' in (process.info['name'] or '').lower():
                        try:
                            for child in [process, *process.children(recursive=True)]:
                                if child.pid not in seen:
                                    total += child.memory_info().rss
                                    seen.add(child.pid)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                rss_peak = max(rss_peak, total)
                await asyncio.sleep(0.25)
        task = asyncio.create_task(sample_memory())
        start = time.perf_counter()
        try:
            result = await client.translate(TranslateRequest(segments=[{'id': '0', 'text': sample['text']}]))
        except ServiceError as e:
            result = {'error': e.code, 'message': e.message}
        finally:
            running = False
            await task
        model_memory = await client.request('GET', '/api/ps')
        record = {**sample, 'result': result, 'wall_ms': round((time.perf_counter()-start)*1000), 'ollama_peak_rss_bytes': rss_peak, 'loaded_models': model_memory.get('models', []), 'available_ram_bytes': psutil.virtual_memory().available}
        results.append(record)
        print(json.dumps(record, ensure_ascii=True), flush=True)
        dest = root / args.output
        dest.parent.mkdir(exist_ok=True, parents=True)
        dest.write_text(json.dumps({'model': args.model, 'samples': results, 'median_wall_ms': statistics.median(r['wall_ms'] for r in results)}, ensure_ascii=False, indent=2), encoding='utf-8')
    await client.request('POST', '/api/generate', json={'model': args.model, 'keep_alive': 0})
    await client.client.aclose()

if __name__ == '__main__':
    asyncio.run(main())
