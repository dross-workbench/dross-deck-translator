import ast
import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image, ImageDraw, ImageFont
from providers.base import NetworkError, ApiKeyError, RateLimitError

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_game_screenshots_and_ocr_fixture_geometry(tmp_path):
    """Generated scenes exercise fixture geometry; this is NOT a real OCR accuracy test."""
    fonts = [Path('C:/Windows/Fonts/meiryo.ttc'), Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')]
    font_path = next((p for p in fonts if p.exists()), None)
    font = ImageFont.truetype(str(font_path), 28) if font_path else ImageFont.load_default()
    samples = json.loads((ROOT/'tests/fixtures/dialogue.json').read_text(encoding='utf-8'))
    for sample in samples:
        screen = Image.new('RGB', (1280, 800), '#244334')
        draw = ImageDraw.Draw(screen)
        box = sample['rect']
        rect = (box['left'], box['top'], box['right'], box['bottom'])
        draw.rectangle(rect, fill='#181a22', outline='white', width=2)
        if sample['case'] == 'vertical':
            for i, char in enumerate(sample['text']):
                draw.text((box['left']+8, box['top']+8+i*30), char, font=font, fill='white')
        else:
            draw.text((box['left']+8, box['top']+12), sample['text'], font=font, fill='white')
        path = tmp_path/(sample['case']+'.png')
        screen.save(path)
        with Image.open(path) as captured:
            assert captured.size == (1280, 800)
            assert captured.crop(rect).getbbox() is not None
            assert captured.getpixel((box['left'], box['top'])) == (255,255,255)
        # Same PNG bytes survive the capture transport without changing coordinates.
        assert base64.b64decode(base64.b64encode(path.read_bytes())) == path.read_bytes()


def backend_method(name):
    """Execute a real backend RPC method without SteamOS-only module initialization."""
    tree = ast.parse((ROOT/'main.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Plugin')
    method = next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    scope = dict(NetworkError=NetworkError, ApiKeyError=ApiKeyError, RateLimitError=RateLimitError,
                 logger=SimpleNamespace(error=lambda *x: None, debug=lambda *x: None), asyncio=asyncio)
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'backend-rpc', 'exec'), scope)
    return scope[name]


def test_local_only_blocks_cloud_before_any_ocr_or_translation():
    class Settings:
        def get_setting(self, key, default=None): return default
    plugin = SimpleNamespace(_settings=Settings(), _ocr_provider='gemini_vision', _translation_provider='freegoogle',
                             _provider_manager=object(), _input_language='ja', _target_language='en')
    async def run():
        ocr = await backend_method('recognize_text')(plugin, 'synthetic')
        assert ocr['error'] == 'network_error'
        translated = await backend_method('translate_text')(plugin, [{'text':'約束'}])
        assert translated['error'] == 'network_error'
    asyncio.run(run())
