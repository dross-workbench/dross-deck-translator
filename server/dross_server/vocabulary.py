import csv
import hashlib
import html
import io
import json
import sqlite3
import threading
import base64
from pathlib import Path
from PIL import Image
from .inference import ServiceError
from datetime import datetime, timezone


class VocabularyStore:
    def __init__(self, data_dir):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir/'vocabulary.db'
        self.media = data_dir/'screenshots'
        self.lock = threading.Lock()
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id TEXT PRIMARY KEY, game_id TEXT, game_title TEXT, word TEXT,
                    dictionary_form TEXT, reading TEXT, meaning TEXT, first_seen TEXT,
                    last_seen TEXT, encounters INTEGER DEFAULT 0, anki_id INTEGER);
                CREATE TABLE IF NOT EXISTS encounters (
                    event_id TEXT PRIMARY KEY, vocabulary_id TEXT REFERENCES vocabulary(id) ON DELETE CASCADE,
                    sentence TEXT, translation TEXT, encountered_at TEXT, screenshot TEXT);
            ''')

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def save(self, item):
        key = hashlib.sha256(json.dumps([item.game_id, item.dictionary_form, item.reading], ensure_ascii=False).encode()).hexdigest()[:32]
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self.connect() as db:
            existing = db.execute('SELECT vocabulary_id FROM encounters WHERE event_id=?', (item.event_id,)).fetchone()
            if existing and existing[0] != key:
                raise ServiceError('event_conflict', 'This save event was already used for another word.', 409)
            screenshot = None
            if item.screenshot_base64:
                try:
                    raw = base64.b64decode(item.screenshot_base64, validate=True)
                    if len(raw) > 2_000_000:
                        raise ValueError()
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.format not in ('PNG', 'JPEG') or image.width*image.height > 4_000_000:
                            raise ValueError()
                        image.load()
                        clean = io.BytesIO()
                        image.convert('RGB').save(clean, format='PNG')
                    screenshot = hashlib.sha256(item.event_id.encode()).hexdigest()+'.png'
                    self.media.mkdir(exist_ok=True)
                    (self.media/screenshot).write_bytes(clean.getvalue())
                except (ValueError, OSError, Image.DecompressionBombError):
                    raise ServiceError('invalid_screenshot', 'Use a PNG or JPEG screenshot under 2 MB and 4 megapixels.', 422)
            db.execute('INSERT OR IGNORE INTO vocabulary(id,game_id,game_title,word,dictionary_form,reading,meaning,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?)',
                       (key, item.game_id, item.game_title, item.word, item.dictionary_form, item.reading, item.meaning, now, now))
            inserted = db.execute('INSERT OR IGNORE INTO encounters(event_id,vocabulary_id,sentence,translation,encountered_at,screenshot) VALUES(?,?,?,?,?,?)',
                                  (item.event_id, key, item.sentence, item.sentence_translation, now, screenshot)).rowcount
            if inserted:
                db.execute('UPDATE vocabulary SET encounters=encounters+1,last_seen=? WHERE id=?', (now, key))
            return dict(db.execute('SELECT * FROM vocabulary WHERE id=?', (key,)).fetchone())

    def record_encounters(self, request, study):
        with self.connect() as db:
            saved = [dict(r) for r in db.execute('SELECT * FROM vocabulary WHERE game_id=?', (request.game_id,))]
        if not saved:
            return 0
        now, count = datetime.now(timezone.utc).isoformat(), 0
        for segment in request.segments:
            analysis = study.analyze(segment.text)
            lemmas = {t['dictionary_form'] for t in analysis['tokens']}
            with self.lock, self.connect() as db:
                for word in saved:
                    if word['dictionary_form'] not in lemmas:
                        continue
                    event = hashlib.sha256((request.event_id+word['id']).encode()).hexdigest()
                    inserted = db.execute('INSERT OR IGNORE INTO encounters(event_id,vocabulary_id,sentence,translation,encountered_at) VALUES(?,?,?,?,?)',
                                          (event, word['id'], segment.text, '', now)).rowcount
                    if inserted:
                        db.execute('UPDATE vocabulary SET encounters=encounters+1,last_seen=? WHERE id=?', (now, word['id']))
                        count += 1
        return count

    def set_anki_id(self, key, note_id):
        with self.connect() as db:
            db.execute('UPDATE vocabulary SET anki_id=? WHERE id=?', (note_id, key))

    def list(self, game_id=None):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM vocabulary WHERE (? IS NULL OR game_id=?) ORDER BY last_seen DESC LIMIT 10000', (game_id, game_id)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item['examples'] = [dict(x) for x in db.execute('SELECT sentence,translation,encountered_at,screenshot FROM encounters WHERE vocabulary_id=? ORDER BY encountered_at', (row['id'],))]
                result.append(item)
            return result

    def export(self, game_id=None):
        stream = io.StringIO(newline='')
        stream.write('#separator:tab\n#html:true\n')
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        stream.write('#columns:DrossId\tWord\tDictionaryForm\tReading\tMeaning\tSentence\tSentenceTranslation\tGame\tFirstSeen\tEncounters\tAttribution\n')
        for item in self.list(game_id):
            examples = item['examples']
            values = [item['id'], item['word'], item['dictionary_form'], item['reading'], item['meaning'],
                      '\n'.join(dict.fromkeys(e['sentence'] for e in examples)), '\n'.join(dict.fromkeys(e['translation'] for e in examples)),
                      item['game_title'] or item['game_id'], item['first_seen'], str(item['encounters']),
                      'Dictionary definitions: JMdict © EDRDG, CC BY-SA 4.0; https://www.edrdg.org/edrdg/licence.html']
            # HTML escaping also prevents markup in Anki cards. Formula prefixes
            # are escaped for people opening this TSV in a spreadsheet first.
            writer.writerow([("'" if v.startswith(('=', '+', '-', '@')) else '') + html.escape(v).replace('\n', '<br>') for v in values])
        return stream.getvalue()

    def delete_all(self):
        with self.lock, self.connect() as db:
            count = db.execute('SELECT COUNT(*) FROM vocabulary').fetchone()[0]
            db.execute('DELETE FROM encounters')
            db.execute('DELETE FROM vocabulary')
            db.commit()
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            db.execute('VACUUM')
            if self.media.exists():
                for path in self.media.glob('*.png'):
                    # Generated hash names only; never accept a client file path.
                    if len(path.stem) == 64 and all(c in '0123456789abcdef' for c in path.stem):
                        path.unlink()
            return count
