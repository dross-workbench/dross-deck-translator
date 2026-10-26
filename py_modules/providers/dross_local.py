"""Authenticated text-only Workbench provider. GPLv3; upstream attribution retained."""
import asyncio
import hashlib
import http.client
import ipaddress
import json
import ssl
import time
import uuid
from urllib.parse import urlsplit
from .base import TranslationProvider, ProviderType, NetworkError, ApiKeyError
from .translation_cache import TranslationCache

DROSS_LANGUAGES = ('en', 'ja', 'ko', 'zh', 'zh-CN', 'zh-TW', 'es', 'fr', 'de', 'pt', 'id')

DROSS_DEFAULTS = {
    "dross_server_url": "", "dross_token": "", "dross_certificate_sha256": "",
    "dross_timeout": 120, "dross_offline_fallback": False,
    "dross_allow_http": False, "dross_local_only": True,
    "dross_save_text": False, "dross_allow_screenshots": False,
    "dross_context_lines": 3, "dross_display_mode": "english",
    "dross_mode": "translate",
    "dross_track_encounters": True,
    "dross_poll_seconds": 15,
}


class DrossLocalProvider(TranslationProvider):
    name = "Dross Local AI"
    provider_type = ProviderType.DROSS

    def __init__(self):
        self.settings = dict(DROSS_DEFAULTS)
        self.context = []
        self.game_id = ""
        self.last_seen = 0
        self.last_texts = []
        self.last_context = []
        self.last_regions = []
        self.language_pair = None
        self.last_detections = {}
        self.last_identity = None
        self.cache = TranslationCache(":memory:")
        self.lock = asyncio.Lock()

    def configure(self, settings):
        if any(self.settings.get(k) != settings.get(k) for k in ("dross_server_url", "dross_token", "dross_context_lines")):
            self.clear_session()
        self.settings = {**DROSS_DEFAULTS, **settings}

    def clear_session(self):
        self.context, self.last_texts, self.last_context, self.last_regions = [], [], [], []
        self.last_detections, self.last_identity = {}, None
        self.cache.clear()

    def _request(self, method, path, payload=None, timeout=None):
        url = urlsplit(self.settings["dross_server_url"])
        if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise NetworkError("Use only the Workbench gateway address and port.")
        host = url.hostname or ""
        try:
            address = ipaddress.ip_address("127.0.0.1" if host == "localhost" else host)
            if not (address.is_private or address.is_loopback) or address.is_unspecified:
                raise ValueError()
        except ValueError:
            raise NetworkError("Enter Workbench's private LAN IP address. Public servers and DNS names are not allowed.")
        if not self.settings["dross_token"]:
            raise ApiKeyError("Enter the Workbench pairing token in Dross settings.")
        timeout = max(0.5, min(300, float(timeout))) if timeout is not None else max(5, min(300, float(self.settings["dross_timeout"])))
        connection = None
        try:
            if url.scheme == "https":
                fingerprint = self.settings["dross_certificate_sha256"].replace(":", "").lower()
                if fingerprint:
                    if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                        raise NetworkError("Certificate fingerprint must be 64 hexadecimal characters.")
                    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                else:
                    ctx = ssl.create_default_context()
                connection = http.client.HTTPSConnection(str(address), url.port or 443, timeout=timeout, context=ctx)
                connection.connect()
                if fingerprint and hashlib.sha256(connection.sock.getpeercert(binary_form=True)).hexdigest() != fingerprint:
                    raise NetworkError("Workbench certificate fingerprint mismatch. No token or text was sent.")
            elif url.scheme == "http" and (address.is_loopback or self.settings["dross_allow_http"]):
                connection = http.client.HTTPConnection(str(address), url.port or 80, timeout=timeout)
            else:
                raise NetworkError("Use HTTPS, or explicitly enable unencrypted HTTP for a trusted LAN.")
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
            connection.request(method, path, body, {"Authorization": "Bearer " + self.settings["dross_token"], "Content-Type": "application/json"})
            response = connection.getresponse()
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise NetworkError("Workbench response exceeded the size limit.")
            if response.status == 401:
                raise ApiKeyError("Workbench rejected the pairing token.")
            if 300 <= response.status < 400:
                raise NetworkError("Workbench redirects are refused.")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise NetworkError("Workbench returned an invalid response.")
            if response.status >= 400:
                # Only protocol errors, never arbitrary response bodies, reach logs/UI.
                code = data.get("error", "server_error")
                messages = {"model_missing": "Configured model is not installed on Workbench.",
                            "screenshots_disabled": "Enable optional screenshots on Workbench as well as the Deck.",
                            "tokenizer_missing": "Run Install-Study.ps1 on Workbench and restart the gateway.",
                            "inference_timeout": "Workbench inference timed out. Try a smaller model.",
                            "model_changed": "Workbench model changed. Retry translation.",
                            "ollama_unavailable": "Start Ollama on Workbench.",
                            "inference_error": "Workbench cannot run the model. Check available RAM.",
                            "invalid_model_output": "The model returned an incomplete result. Try shorter dialogue."}
                messages['detector_missing'] = 'Update Workbench server requirements and restart it to enable local language detection.'
                raise NetworkError(messages.get(code, "Workbench request failed. Check server setup."))
            return data
        except (OSError, ValueError, http.client.HTTPException):
            raise NetworkError("Cannot reach Workbench securely. Check its address, certificate, firewall and server.")
        finally:
            if connection:
                connection.close()

    async def request(self, method, path, payload=None, *, timeout=None):
        return await asyncio.to_thread(self._request, method, path, payload, timeout)

    async def health(self):
        return await self.request("GET", "/health")

    def is_available(self, source_lang="ja", target_lang="en"):
        return bool(self.settings['dross_server_url'] and self.settings['dross_token']) and source_lang in (*DROSS_LANGUAGES, 'auto') and target_lang in DROSS_LANGUAGES

    def get_supported_languages(self):
        return list(DROSS_LANGUAGES)

    async def translate(self, text, source_lang, target_lang):
        return (await self.translate_batch([text], source_lang, target_lang))[0]

    async def translate_batch(self, texts, source_lang, target_lang):
        regions = await self.translate_regions([{"text": t} for t in texts], source_lang, target_lang, "unknown")
        return [r['drossTranslation'] for r in regions]

    async def translate_regions(self, regions, source_lang, target_lang, game_id, persistent_cache=None, fallback=None):
        if source_lang not in (*DROSS_LANGUAGES, 'auto') or target_lang not in DROSS_LANGUAGES:
            raise NetworkError('Choose a supported Dross input/output language in Translation settings.')
        async with self.lock:
            now = time.monotonic()
            if game_id != self.game_id or (source_lang, target_lang) != self.language_pair or now - self.last_seen > 900:
                self.clear_session()
                self.game_id = game_id
                self.language_pair = (source_lang, target_lang)
            self.last_seen = now
            texts = [r["text"] for r in regions]
            changed = texts != self.last_texts
            newly_seen = [t for t in texts if t not in self.last_texts]
            # An unchanged screen uses its original context, so repeated captures hit cache.
            context = self.last_context if texts == self.last_texts else self.context[:]
            count = max(0, min(6, int(self.settings["dross_context_lines"])))
            context = context[-count:] if count else []
            cache = persistent_cache if self.settings["dross_save_text"] and persistent_cache else self.cache
            fallback_used = False
            try:
                health = await self.health()
                identity = health.get("model_identity")
                if not health.get("translation_available") or not identity:
                    raise NetworkError("Workbench translation model is not ready.")
                if source_lang not in health.get('source_languages', ['ja']) or target_lang not in health.get('target_languages', ['en']):
                    raise NetworkError('Update Workbench to the multilingual server build for this language selection.')
                scope = json.dumps([identity, game_id, source_lang, target_lang, context], ensure_ascii=False)
                unique = list(dict.fromkeys(t for t in texts if t.strip()))
                if not unique:
                    detections = {}
                elif source_lang == 'auto':
                    if not health.get('automatic_detection'):
                        raise NetworkError('Update Workbench to enable automatic language detection.')
                    if not changed and self.last_identity == identity and self.last_detections:
                        detections = self.last_detections
                    else:
                        data = await self.request('POST', '/v1/detect', {'segments': [{'id': str(i), 'text': t} for i, t in enumerate(unique)]})
                        items = data.get('segments', [])
                        try:
                            mapped = {item['id']: item for item in items}
                            if len(items) != len(unique) or set(mapped) != {str(i) for i in range(len(unique))}:
                                raise ValueError()
                            detections = {t: mapped[str(i)] for i, t in enumerate(unique)}
                            for item in detections.values():
                                if item['status'] not in ('detected', 'uncertain', 'unsupported', 'non_linguistic') or (item['status'] == 'detected' and item['language'] not in DROSS_LANGUAGES):
                                    raise ValueError()
                        except (KeyError, TypeError, ValueError):
                            raise NetworkError('Workbench returned invalid language detections.')
                else:
                    detections = {t: {'language': source_lang, 'status': 'detected', 'confidence': None} for t in unique}
                translated = {t: t for t in texts}
                for language in dict.fromkeys(d['language'] for d in detections.values() if d['status'] == 'detected'):
                    group = [t for t in unique if detections[t]['status'] == 'detected' and detections[t]['language'] == language]
                    if language == target_lang:
                        continue
                    cached = cache.get_many(group, language, target_lang, 0, namespace=scope)
                    missing = [t for t in group if t not in cached]
                    if missing:
                        data = await self.request('POST', '/v1/translate', {
                            'segments': [{'id': str(i), 'text': t} for i, t in enumerate(missing)],
                            'context': context, 'game_id': game_id, 'model_identity': identity,
                            'source_language': language, 'target_language': target_lang})
                        items = data.get('segments', [])
                        try:
                            mapped = {r['id']: r['translation'] for r in items}
                        except (KeyError, TypeError):
                            raise NetworkError('Workbench returned invalid sentence mappings.')
                        if len(items) != len(missing) or set(mapped) != {str(i) for i in range(len(missing))} or any(not isinstance(v, str) or not v.strip() for v in mapped.values()):
                            raise NetworkError('Workbench returned invalid sentence mappings.')
                        pairs = [(t, mapped[str(i)]) for i, t in enumerate(missing)]
                        cache.put_many(pairs, language, target_lang, 0, 'dross', namespace=scope)
                        cached.update(pairs)
                    translated.update(cached)
                translations = [translated[t] for t in texts]
                self.last_detections, self.last_identity = detections, identity
            except NetworkError:
                if not self.settings['dross_offline_fallback'] or fallback is None:
                    raise
                if source_lang == 'auto':
                    raise NetworkError('Workbench is unavailable. Select an explicit input language to use on-device NLLB fallback.')
                if not fallback.is_available(source_lang, target_lang):
                    raise
                translations = await fallback.translate_batch(texts, source_lang, target_lang)
                if len(translations) != len(texts) or any(t is None for t in translations):
                    raise NetworkError("On-device fallback failed. Download the NLLB model in Translation settings.")
                fallback_used = True
                detections = {t: {'language': source_lang, 'status': 'detected', 'confidence': None} for t in texts}
            self.last_context, self.last_texts = context[:], texts[:]
            for t in texts:
                if t.strip() and (not self.context or self.context[-1] != t):
                    self.context.append(t)
            self.context = self.context[-count:] if count else []
            mode = self.settings["dross_display_mode"]
            result = []
            for region, translation in zip(regions, translations):
                detected = detections.get(region['text'], {})
                result.append({**region, 'drossTranslation': translation,
                    **({'englishTranslation': translation} if target_lang == 'en' else {}),
                    'translatedText': region['text'] if mode in ('japanese', 'source') else f"{region['text']}\n{translation}" if mode == 'bilingual' else translation,
                    'drossSourceLanguage': detected.get('language', source_lang), 'drossTargetLanguage': target_lang,
                    'drossDetectionConfidence': detected.get('confidence'),
                    'drossWarning': detected.get('reason') if detected.get('status') in ('uncertain', 'unsupported') else None,
                    'drossFallback': fallback_used})
            self.last_regions = result
            japanese_new = [t for t in newly_seen if detections.get(t, {}).get('language') == 'ja']
            if changed and japanese_new and not fallback_used and self.settings["dross_track_encounters"]:
                try:
                    await self.request("POST", "/v1/vocabulary/encounters", {
                        "event_id": str(uuid.uuid4()), "game_id": game_id,
                        "segments": [{"id": str(i), "text": t} for i, t in enumerate(japanese_new) if t.strip()]}, timeout=2)
                except (NetworkError, ApiKeyError):
                    # Optional history must never prevent a translated overlay.
                    pass
            return result
