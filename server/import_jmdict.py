"""Build a local lookup index from licensed JMdict XML. No dictionary data is committed."""
import argparse
import gzip
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

ATTRIBUTION = 'JMdict © Electronic Dictionary Research and Development Group; CC BY-SA 4.0; https://www.edrdg.org/edrdg/licence.html'


def import_dictionary(source, target):
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Build separately so a failed import never damages the active dictionary.
    staging = target.with_suffix('.building')
    db = sqlite3.connect(staging)
    db.executescript('DROP TABLE IF EXISTS entries; DROP TABLE IF EXISTS metadata; CREATE TABLE entries (word TEXT, reading TEXT, entry_id TEXT, senses TEXT); CREATE INDEX lookup ON entries(word); CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT);')
    count = 0
    opener = gzip.open if source.suffix == '.gz' else open
    try:
        with opener(source, 'rb') as stream:
            for event, node in ET.iterparse(stream, events=('end',)):
                if node.tag != 'entry':
                    continue
                spellings = [n.text for n in node.findall('k_ele/keb')]
                for reading in node.findall('r_ele'):
                    kana = reading.findtext('reb')
                    restricted = [n.text for n in reading.findall('re_restr')]
                    words = restricted or spellings or [kana]
                    for word in set([*words, kana]):
                        senses, pos = [], []
                        for sense in node.findall('sense'):
                            pos = [n.text for n in sense.findall('pos')] or pos
                            stagk = [n.text for n in sense.findall('stagk')]
                            stagr = [n.text for n in sense.findall('stagr')]
                            if (stagk and word not in stagk) or (stagr and kana not in stagr):
                                continue
                            glosses = [n.text for n in sense.findall('gloss') if n.get('{http://www.w3.org/XML/1998/namespace}lang', 'eng') == 'eng']
                            if glosses:
                                senses.append({'definitions': glosses, 'part_of_speech': pos})
                        if senses:
                            db.execute('INSERT INTO entries VALUES(?,?,?,?)', (word, kana, node.findtext('ent_seq'), json.dumps(senses, ensure_ascii=False)))
                            count += 1
                node.clear()
        db.executemany('INSERT INTO metadata VALUES(?,?)', [('attribution', ATTRIBUTION), ('source_sha256', hashlib.file_digest(source.open('rb'), 'sha256').hexdigest())])
        db.commit()
    finally:
        db.close()
    staging.replace(target)
    return count


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source')
    p.add_argument('--output', default=str(Path(__file__).parent/'.local/data/jmdict.db'))
    args = p.parse_args()
    print(f'Indexed {import_dictionary(args.source, args.output)} dictionary forms. {ATTRIBUTION}')
