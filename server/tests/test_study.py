import json
from pathlib import Path
from dross_server.study import JapaneseStudy
from dross_server.schemas import VocabularyRequest
from dross_server.vocabulary import VocabularyStore
from import_jmdict import import_dictionary


def item(**values):
    return VocabularyRequest(**({'event_id': 'event-one', 'word': '食べ', 'dictionary_form': '食べる', 'reading': 'たべる',
        'meaning': 'eat', 'sentence': 'りんごを食べた。', 'sentence_translation': 'I ate an apple.', 'game_id': 'game-a'} | values))


def test_tokenization_reading_particle_and_dictionary(tmp_path):
    xml = tmp_path/'synthetic.xml'
    xml.write_text('<JMdict><entry><ent_seq>1</ent_seq><k_ele><keb>食べる</keb></k_ele><r_ele><reb>たべる</reb></r_ele><sense><pos>verb</pos><gloss>eat</gloss></sense></entry></JMdict>', encoding='utf-8')
    assert import_dictionary(xml, tmp_path/'jmdict.db') == 2
    analysis = JapaneseStudy(tmp_path).analyze('りんごを食べた。')
    verb = next(t for t in analysis['tokens'] if t['dictionary_form'] == '食べる')
    assert verb['reading'] == 'たべ'
    assert verb['dictionary_entries'][0]['reading'] == 'たべる'
    assert verb['dictionary_entries'][0]['senses'][0]['definitions'] == ['eat']
    particle = next(t for t in analysis['tokens'] if t['surface'] == 'を')
    assert 'direct object' in particle['particle_note']
    assert ''.join(t['surface'] for t in analysis['tokens']) == 'りんごを食べた。'


def test_missing_dictionary_is_explicit(tmp_path):
    result = JapaneseStudy(tmp_path).analyze('約束')
    assert not result['dictionary_available']
    assert result['tokens'][0]['dictionary_entries'] == []


def test_vocabulary_dedup_examples_export_and_delete(tmp_path):
    store = VocabularyStore(tmp_path)
    first = store.save(item())
    assert store.save(item())['encounters'] == 1  # idempotent retry
    second = store.save(item(event_id='event-two', sentence='パンを食べた。'))
    assert second['id'] == first['id'] and second['encounters'] == 2
    assert len(store.list('game-a')[0]['examples']) == 2
    store.save(item(event_id='event-three', game_id='game-b', meaning='<script>bad</script>'))
    assert len(store.list()) == 2
    export = store.export()
    assert '\t' in export and '&lt;script&gt;' in export and '<script>' not in export
    assert 'JMdict' in export and '#html:true' in export
    assert store.delete_all() == 2
    assert not store.list()
