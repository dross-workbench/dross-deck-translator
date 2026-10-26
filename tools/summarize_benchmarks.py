"""Publish only synthetic fixture benchmarks, excluding local configuration/paths."""
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root/'benchmarks'
target.mkdir(exist_ok=True)
names = ['qwen06-v3', 'qwen17-v3', 'qwen4-v3', 'translategemma4']
summary = []
for name in names:
    data = json.loads((root/'.local'/f'benchmark-{name}.json').read_text(encoding='utf-8'))
    sanitized = []
    for sample in data['samples']:
        result = sample['result']
        sanitized.append({
            'case': sample['case'], 'japanese': sample['text'], 'reference': sample['reference'],
            'output': result.get('segments', []), 'error': result.get('error'),
            'wall_ms': sample['wall_ms'], 'timings': result.get('timings', []),
            'peak_process_tree_rss_bytes': sample['ollama_peak_rss_bytes'],
            'available_ram_bytes': sample['available_ram_bytes'],
            'model_identity': result.get('model_identity'),
            'gpu_offload_bytes': max([x.get('size_vram', 0) for x in sample.get('loaded_models', [])] or [0]),
        })
    (target/f'{name}.json').write_text(json.dumps({'model': data['model'], 'samples': sanitized}, ensure_ascii=False, indent=2), encoding='utf-8')
    warm = [x['wall_ms'] for x in sanitized[1:] if x['timings']]
    summary.append({'model': data['model'], 'cold_ms': sanitized[0]['wall_ms'], 'warm_median_ms': statistics.median(warm),
                    'warm_range_ms': [min(warm), max(warm)], 'peak_rss_gib': round(max(x['peak_process_tree_rss_bytes'] for x in sanitized)/2**30, 2)})
(target/'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
