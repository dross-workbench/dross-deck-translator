"""Offline language identification and the deliberately bounded translation catalog."""
import re
import threading

LANGUAGES = {
    'en': 'English', 'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese',
    'zh-CN': 'Chinese (Simplified)', 'zh-TW': 'Chinese (Traditional)',
    'es': 'Spanish', 'fr': 'French', 'de': 'German', 'pt': 'Portuguese', 'id': 'Indonesian',
}
UI_LANGUAGES = [code for code in LANGUAGES if code != 'zh']
DETECTOR_ID = 'lingua-2.2.0-dross-v1'
KANA = re.compile(r'[\u3041-\u3096\u30a1-\u30fa\uff66-\uff9f]')
HANGUL = re.compile(r'[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]')
HAN = re.compile(r'[\u3400-\u9fff]')
HUD = re.compile(r'^(?:HP|MP|XP|SP|AP|LV|FPS|ATK|DEF)\s*[:\d/ .+%-]+$', re.I)


def normalize_language(code, allow_auto=False):
    if not isinstance(code, str):
        raise ValueError('Language must be a supported language code')
    aliases = {k.lower(): k for k in LANGUAGES}
    aliases.update({'zh-hans': 'zh-CN', 'zh-hant': 'zh-TW'})
    if allow_auto:
        aliases['auto'] = 'auto'
    result = aliases.get(code.strip().lower())
    if not result:
        raise ValueError('Choose English, Japanese, Chinese, Korean, Spanish, French, German, Portuguese or Indonesian')
    return result


def same_language(left, right):
    # A generic Chinese detection may still need Simplified/Traditional conversion.
    return left == right


class LanguageDetector:
    def __init__(self):
        self.engine = None
        self.lock = threading.Lock()

    def detect(self, text):
        def result(language='und', confidence=0.0, status='uncertain', reason='Language is uncertain; select the input language manually.'):
            return {'language': language, 'confidence': round(confidence, 4), 'status': status, 'reason': reason}

        if not any(c.isalpha() for c in text) or HUD.fullmatch(text.strip()):
            return result(status='non_linguistic', reason='Numbers, punctuation or a common HUD counter.')
        kana, hangul, han = bool(KANA.search(text)), bool(HANGUL.search(text)), HAN.findall(text)
        if kana and hangul:
            return result(reason='Mixed scripts in one OCR region; select an input language or reduce grouping.')
        if kana:
            return result('ja', 1.0, 'detected', 'Japanese kana script.')
        if hangul:
            return result('ko', 1.0, 'detected', 'Korean Hangul script.')
        if han and len(han) <= 4:
            return result(reason='A short Han-only label can be Japanese or Chinese; select the input language manually.')
        if not han and sum(c.isalpha() for c in text) < 4:
            return result(reason='Too little text to identify its language reliably.')
        # Prevent unsupported alphabets from being forced into a Latin language.
        if any(c.isalpha() and not (c <= '\u024f' or HAN.fullmatch(c)) for c in text):
            return result(status='unsupported', reason='This writing system is not supported by Dross translation yet.')
        with self.lock:
            if self.engine is None:
                from lingua import Language, LanguageDetectorBuilder
                # Unsupported alternatives reduce false matches with neighboring languages.
                self.engine = LanguageDetectorBuilder.from_languages(
                    Language.ENGLISH, Language.JAPANESE, Language.CHINESE, Language.KOREAN,
                    Language.SPANISH, Language.FRENCH, Language.GERMAN,
                    Language.PORTUGUESE, Language.INDONESIAN, Language.ITALIAN,
                    Language.DUTCH, Language.MALAY).build()
            values = self.engine.compute_language_confidence_values(text)
        top, second = values[0], values[1]
        code = top.language.iso_code_639_1.name.lower()
        if top.value < 0.75 or top.value - second.value < 0.20:
            return result(confidence=top.value)
        if code not in LANGUAGES:
            return result(code, top.value, 'unsupported', 'The detected language is outside the current Dross language set.')
        return result(code, top.value, 'detected', 'Local statistical language identification; confidence is not a guarantee.')

    def detect_segments(self, segments):
        return [{'id': segment.id, **self.detect(segment.text)} for segment in segments]
