"""Real host-side RapidOCR on authored synthetic scenes; no game captures or AI API.

Run in an isolated environment with rapidocr==3.8.3, onnxruntime==1.26.0 and Pillow.
--download fetches the Japanese model files from the existing upstream manifest.
This measures host CPU inference, not Steam Deck performance or game-font accuracy.
"""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import os
import time
import unicodedata
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]


def source_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'py_modules/providers'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--font', type=Path)
    parser.add_argument('--dll-dir', type=Path, help='Optional Windows directory containing a compatible Microsoft C++ runtime')
    args = parser.parse_args()
    dll_handle = os.add_dll_directory(str(args.dll_dir.resolve())) if os.name == 'nt' and args.dll_dir else None
    fonts = [Path('C:/Windows/Fonts/YuGothM.ttc'), Path('C:/Windows/Fonts/meiryo.ttc'), Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    font_path = args.font or next((p for p in fonts if p.exists()), None)
    if not font_path:
        parser.error('Pass --font pointing to a Japanese-capable TrueType/OpenType font')
    font = ImageFont.truetype(str(font_path), 28)
    folder = ROOT/'.local/ocr-benchmark'
    models = folder/'models'
    models.mkdir(parents=True, exist_ok=True)
    manifest = source_module('rapidocr_downloader').MANIFEST[:4]
    for url, name, _ in manifest:
        target = models/name
        if not target.exists():
            if not args.download:
                parser.error('Models are missing. Run once with --download')
            urllib.request.urlretrieve(url, target)
    ocr = source_module('rapidocr_subprocess')
    start = time.perf_counter()
    engine = ocr._build_engine(str(models), 0.5, 0.5, 1.6, 'ch', intra_threads=1)
    initialization_ms = round((time.perf_counter()-start)*1000)
    samples = json.loads((ROOT/'tests/fixtures/dialogue.json').read_text(encoding='utf-8'))
    results = []
    for sample in samples:
        screen = Image.new('RGB', (1280, 800), '#244334')
        draw = ImageDraw.Draw(screen)
        box = sample['rect']
        rect = tuple(box[k] for k in ('left', 'top', 'right', 'bottom'))
        draw.rectangle(rect, fill='#181a22', outline='white', width=2)
        if sample['case'] == 'vertical':
            for i, char in enumerate(sample['text']):
                draw.text((box['left']+8, box['top']+8+i*30), char, font=font, fill='white')
        else:
            draw.text((box['left']+8, box['top']+12), sample['text'], font=font,
                      fill='#ffdd66' if sample['case'] == 'stylized' else 'white',
                      stroke_width=1 if sample['case'] == 'stylized' else 0)
        if sample['case'] == 'poor_ocr':
            screen = screen.filter(ImageFilter.GaussianBlur(1.1))
        path = folder/(sample['case']+'.png')
        screen.save(path)
        image = ocr._load_image_rgb(str(path))
        start = time.perf_counter()
        regions = ocr._result_to_regions(engine(image), 0.5)
        elapsed = round((time.perf_counter()-start)*1000)
        for region in regions:
            r = region['rect']
            assert 0 <= r['left'] < r['right'] <= 1280 and 0 <= r['top'] < r['bottom'] <= 800
        detected = ''.join(r['text'] for r in regions)
        normalized = lambda s: ''.join(unicodedata.normalize('NFKC', s).split())
        results.append({'case': sample['case'], 'expected': sample['text'], 'detected': detected,
                        'normalized_exact': normalized(detected) == normalized(sample['text']),
                        'latency_ms': elapsed, 'regions': regions})
    assert results[0]['detected'], 'Normal Japanese dialogue produced no OCR regions'
    report = {'platform': 'Windows Workbench CPU; one ONNX thread', 'font': font_path.name,
              'versions': {name: importlib.metadata.version(name) for name in ('rapidocr', 'onnxruntime', 'Pillow')},
              'model_sha256': {name: hashlib.sha256((models/name).read_bytes()).hexdigest() for _, name, _ in manifest},
              'initialization_ms': initialization_ms, 'results': results}
    output = ROOT/'benchmarks/rapidocr-workbench.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'initialization_ms': initialization_ms, 'cases': len(results),
                      'normalized_exact': sum(r['normalized_exact'] for r in results),
                      'ocr_ms': [r['latency_ms'] for r in results]}))
    if dll_handle:
        dll_handle.close()


if __name__ == '__main__':
    main()
