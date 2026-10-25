import csv
import hashlib
import html
import io
import json
import sqlite3
import threading
from datetime import datetime, timezone


class VocabularyStore:
    def __init__(self, data_dir):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir/'vocabulary.db'
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
            db.execute('INSERT OR IGNORE INTO vocabulary(id,game_id,game_title,word,dictionary_form,reading,meaning,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?)',
                       (key, item.game_id, item.game_title, item.word, item.dictionary_form, item.reading, item.meaning, now, now))
            inserted = db.execute('INSERT OR IGNORE INTO encounters(event_id,vocabulary_id,sentence,translation,encountered_at) VALUES(?,?,?,?,?)',
                                  (item.event_id, key, item.sentence, item.sentence_translation, now)).rowcount
            if inserted:
                db.execute('UPDATE vocabulary SET encounters=encounters+1,last_seen=? WHERE id=?', (now, key))
            return dict(db.execute('SELECT * FROM vocabulary WHERE id=?', (key,)).fetchone())

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
            return count
